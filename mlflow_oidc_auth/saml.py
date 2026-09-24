"""SAML 2.0 service provider: SP-initiated SSO and single logout (issues #328, #329).

A thin, strict layer over python3-saml (the ``[saml]`` extra). This module builds messages and
validates what comes back; the routes that call it (``routers/saml.py``) decide what a validated
message is allowed to do.

Three properties this module is responsible for, and which the rest of the flow relies on:

* **Every message is tied to a request we sent.** An AuthnRequest's ``ID`` is derived from the
  ``auth_state`` row whose ``state`` travels as ``RelayState``, so a Response can be checked
  against the one request it answers — and an unsolicited Response (no ``InResponseTo``, the
  IdP-initiated SSO shape) is refused, because nothing started it.
* **Nothing about the SP's own URLs comes from the request when it can come from configuration.**
  The ACS URL is what a Response's ``Destination`` and ``Recipient`` are compared with. When
  ``OIDC_REDIRECT_URI`` is set its origin is used, so a forged ``Host`` cannot move them.
* **The library is the only XML parser.** python3-saml parses with ``resolve_entities=False`` and
  refuses DTDs outright, which is what keeps an external-entity or billion-laughs document from
  being expanded. Nothing here parses XML another way.

Importing this module never requires the extra: python3-saml is imported inside the functions
that need it, and ``saml_available()`` says whether they can run.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.provider_registry import ProviderConfig, _saml_extra_installed

logger = get_logger()

ACS_PATH = "/callback"
SLS_PATH = "/slo"
METADATA_PATH = "/saml/metadata"

BINDING_HTTP_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
BINDING_HTTP_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"


class SamlError(Exception):
    """A SAML message was refused.

    ``reason`` is for the server log only. It can name what the IdP sent, so it never reaches
    a response body: every refusal answers the browser with the same fixed string.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SamlIdentity:
    """What a validated assertion says about the user.

    Attributes:
        name_id: The subject's ``NameID`` — the identity bound to a local user.
        name_id_format: Its format, kept for the LogoutRequest.
        session_index: The IdP's ``SessionIndex``, kept for single logout.
        attributes: Assertion attributes, each a list of strings.
        assertion_id: The assertion's ``ID``, recorded to refuse a replay.
        replay_until: Unix seconds after which the assertion can no longer pass validation, so
            its replay record may be swept.
        session_not_on_or_after: The IdP's ``SessionNotOnOrAfter`` as Unix seconds, if it set one.
    """

    name_id: str
    name_id_format: Optional[str]
    session_index: Optional[str]
    attributes: Dict[str, List[str]] = field(repr=False)
    assertion_id: str
    replay_until: int
    session_not_on_or_after: Optional[int] = None


@dataclass(frozen=True)
class SamlLogoutRequest:
    """A validated IdP-initiated LogoutRequest.

    Attributes:
        name_id: Whose sessions to end.
        session_indexes: Which of their sessions; empty means every session from this IdP.
        response_url: The redirect carrying our LogoutResponse back to the IdP.
        request_id: The LogoutRequest's ``ID``, recorded to refuse a replay.
        replay_until: Unix seconds after which the request can no longer pass validation, so its
            replay record may be swept.
    """

    name_id: str
    session_indexes: Tuple[str, ...]
    response_url: str
    request_id: str = ""
    replay_until: int = 0


def saml_available() -> bool:
    """Whether the ``[saml]`` extra is installed and loads."""
    return _saml_extra_installed()


def request_id_for(state: str, purpose: str) -> str:
    """The SAML ``ID`` for the request whose ``RelayState`` is ``state``.

    Derived rather than stored, so the ``auth_state`` row needs no new column: the callback
    recomputes it from the ``RelayState`` it consumed. Hashed so the value is a valid ``xs:ID``
    (it must not start with a digit) and reveals nothing the IdP was not already sent.
    """
    return "_" + hashlib.sha256(f"mlflow-oidc-auth:saml:{purpose}:{state}".encode()).hexdigest()


def sp_base_url(request: Any) -> str:
    """The origin and mount prefix this SP's endpoints live under.

    Taken from ``OIDC_REDIRECT_URI`` when it is set: that is an operator-written absolute URL of
    this deployment's callback, so its origin and the prefix above ``/callback`` are the SP's.
    Otherwise from the request, with ``root_path`` discarded when it is not a plain path — the
    same reasoning as ``routers.auth._login_path``: a proxy listed in ``TRUSTED_PROXIES`` sets it
    from ``X-Forwarded-Prefix``, and a ``//host`` prefix would move the URL off-origin. Scheme,
    host and prefix come from the scope, which reflects forwarded headers only from a trusted
    proxy and is the direct connection's otherwise. The ``Host`` header is the one input left,
    which is why production deployments should set ``OIDC_REDIRECT_URI``.
    """
    from mlflow_oidc_auth.config import config

    configured = getattr(config, "OIDC_REDIRECT_URI", None)
    if isinstance(configured, str) and configured.strip():
        parsed = urlparse(configured.strip())
        if parsed.scheme in ("http", "https") and parsed.netloc:
            prefix = parsed.path.rstrip("/").rsplit("/", 1)[0] if "/" in parsed.path.rstrip("/") else ""
            return f"{parsed.scheme}://{parsed.netloc}{prefix}"

    root_path = request.scope.get("root_path", "") or ""
    if not root_path.startswith("/") or root_path.startswith("//"):
        root_path = ""
    return f"{request.url.scheme}://{request.url.netloc}{root_path.rstrip('/')}"


def acs_url(provider: ProviderConfig, base_url: str) -> str:
    """This SP's AssertionConsumerService for ``provider`` (HTTP-POST)."""
    return f"{base_url}{ACS_PATH}/{provider.id}"


def sls_url(provider: ProviderConfig, base_url: str) -> str:
    """This SP's SingleLogoutService for ``provider`` (HTTP-Redirect)."""
    return f"{base_url}{SLS_PATH}/{provider.id}"


def build_settings(provider: ProviderConfig, base_url: str, *, want_messages_signed: bool) -> Dict[str, Any]:
    """python3-saml settings for ``provider``, always strict.

    Parameters:
        provider: A validated ``type: saml`` registry entry.
        base_url: From :func:`sp_base_url`.
        want_messages_signed: Whether the *message* must carry a signature. Per operation rather
            than per provider, because python3-saml uses the one flag for two things: a signed
            Response on the ACS (``want_response_signed``), and a signed LogoutRequest on the SLS
            — which is required always, since an unsigned one would let any page log a user out.
    """
    certs = list(provider.idp_x509_certs)
    idp: Dict[str, Any] = {
        "entityId": provider.idp_entity_id,
        "singleSignOnService": {"url": provider.idp_sso_url, "binding": BINDING_HTTP_REDIRECT},
    }
    if len(certs) == 1:
        idp["x509cert"] = certs[0]
    else:
        idp["x509certMulti"] = {"signing": certs, "encryption": certs[:1]}
    if provider.idp_slo_url:
        idp["singleLogoutService"] = {"url": provider.idp_slo_url, "binding": BINDING_HTTP_REDIRECT}

    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": provider.entity_id,
            "assertionConsumerService": {"url": acs_url(provider, base_url), "binding": BINDING_HTTP_POST},
            "singleLogoutService": {"url": sls_url(provider, base_url), "binding": BINDING_HTTP_REDIRECT},
            "NameIDFormat": provider.name_id_format,
            "x509cert": provider.sp_x509_cert or "",
            "privateKey": provider.sp_private_key or "",
        },
        "idp": idp,
        "security": {
            "authnRequestsSigned": provider.sign_requests,
            "logoutRequestSigned": provider.sign_requests,
            "logoutResponseSigned": provider.sign_requests,
            "signMetadata": False,
            "wantAssertionsSigned": provider.want_assertions_signed,
            "wantMessagesSigned": want_messages_signed,
            "wantNameId": True,
            "wantAssertionsEncrypted": False,
            "wantNameIdEncrypted": False,
            # Attributes are optional: the username falls back to the NameID.
            "wantAttributeStatement": False,
            "rejectDeprecatedAlgorithm": True,
            "signatureAlgorithm": RSA_SHA256,
            "digestAlgorithm": SHA256,
            "allowRepeatAttributeName": False,
            # python3-saml's default asks for PasswordProtectedTransport exactly, which an IdP
            # that authenticated with MFA or Kerberos answers with an error. Authentication
            # strength is the IdP's policy; nothing here reads the context back.
            "requestedAuthnContext": False,
            # A deployment reached at a single-label host (``mlflow``, ``localhost``) must still
            # produce valid settings. This relaxes URL *format* checking only.
            "allowSingleLabelDomains": True,
        },
    }


def _settings(provider: ProviderConfig, base_url: str, *, want_messages_signed: bool):
    from onelogin.saml2.settings import OneLogin_Saml2_Settings

    return OneLogin_Saml2_Settings(build_settings(provider, base_url, want_messages_signed=want_messages_signed))


def prepare_request(
    base_url: str,
    path: str,
    *,
    post_data: Optional[Dict[str, str]] = None,
    get_data: Optional[Dict[str, str]] = None,
    query_string: Optional[str] = None,
) -> Dict[str, Any]:
    """The request dict python3-saml validates ``Destination`` and signatures against.

    Built from ``base_url`` (see :func:`sp_base_url`) rather than the raw request, so the URL a
    message is checked against is the configured one.

    Parameters:
        base_url: The SP's origin and prefix.
        path: The endpoint path under it, e.g. ``/callback/corp``.
        post_data: Form fields, for the HTTP-POST binding.
        get_data: Query parameters, for the HTTP-Redirect binding.
        query_string: The raw query string. When given, a redirect-binding signature is checked
            over the bytes the IdP signed rather than over a re-encoding of them — IdPs differ
            in how they percent-encode, and a re-encoding that differs fails verification.
    """
    parsed = urlparse(base_url)
    return {
        "https": "on" if parsed.scheme == "https" else "off",
        "http_host": parsed.netloc,
        "script_name": parsed.path,
        "path_info": path,
        "get_data": dict(get_data or {}),
        "post_data": dict(post_data or {}),
        "query_string": query_string or "",
        "validate_signature_from_qs": bool(query_string),
    }


def _with_fixed_id(base_cls, request_id: str):
    """A python3-saml request class whose ``ID`` is ``request_id`` instead of a random one."""

    class _FixedId(base_cls):
        def _generate_request_id(self):  # noqa: D401 - python3-saml hook
            return request_id

    return _FixedId


def build_authn_redirect(provider: ProviderConfig, base_url: str, relay_state: str) -> str:
    """The IdP URL, with a (signed, if configured) AuthnRequest, to send the browser to.

    Parameters:
        provider: The SAML provider.
        base_url: From :func:`sp_base_url`.
        relay_state: The ``auth_state`` row's ``state``; the request ``ID`` is derived from it.

    Returns:
        The redirect URL (HTTP-Redirect binding).
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.authn_request import OneLogin_Saml2_Authn_Request

    auth = OneLogin_Saml2_Auth(prepare_request(base_url, f"/login/{provider.id}"), _settings(provider, base_url, want_messages_signed=False))
    auth.authn_request_class = _with_fixed_id(OneLogin_Saml2_Authn_Request, request_id_for(relay_state, "authn"))
    return auth.login(return_to=relay_state)


def _unix(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def process_response(provider: ProviderConfig, base_url: str, post_data: Dict[str, str], relay_state: str) -> SamlIdentity:
    """Validate a Response posted to the ACS and return the identity it asserts.

    Beyond python3-saml's strict checks (signature, ``Issuer``, ``Destination``, ``Recipient``,
    ``InResponseTo`` when present, timestamps with its own fixed drift):

    * ``InResponseTo`` must be present and equal the ``ID`` derived from ``relay_state`` — on the
      Response and on the signed assertion's bearer ``SubjectConfirmationData``, whose
      ``Recipient`` must also equal this ACS exactly. The library accepts a Response with none,
      which is IdP-initiated SSO — an assertion nobody here asked for, and the shape an injected
      one takes.
    * The assertion must name this SP in an ``AudienceRestriction``; the library accepts none.
    * ``Conditions`` are re-checked with the provider's own ``clock_skew_seconds``.
    * The assertion must carry an ``ID`` and some ``NotOnOrAfter``, or it could not be kept out of
      the replay table for as long as it stays valid.

    Raises:
        SamlError: On any failure. Never returns a partially validated identity.
    """
    from onelogin.saml2.response import OneLogin_Saml2_Response
    from onelogin.saml2.utils import OneLogin_Saml2_Utils

    saml_response = post_data.get("SAMLResponse")
    if not isinstance(saml_response, str) or not saml_response:
        raise SamlError("no SAMLResponse in the POST")

    expected_id = request_id_for(relay_state, "authn")
    request_data = prepare_request(base_url, f"{ACS_PATH}/{provider.id}", post_data=post_data)
    try:
        response = OneLogin_Saml2_Response(_settings(provider, base_url, want_messages_signed=provider.want_response_signed), saml_response)
        response.is_valid(request_data, expected_id, raise_exceptions=True)
    except Exception as exc:
        raise SamlError(f"invalid Response: {exc}") from None

    try:
        if response.get_in_response_to() != expected_id:
            raise SamlError("the Response does not answer the AuthnRequest this RelayState started (unsolicited or mismatched InResponseTo)")
        # The Response-level InResponseTo is unsigned when only the assertion is signed, so it
        # proves nothing about which request the *assertion* answers. Require a bearer
        # SubjectConfirmationData — inside the signed assertion — that names our request and our
        # ACS exactly. python3-saml checks both only when present, and Recipient only by substring,
        # so an unsolicited assertion, or one addressed to another provider whose id extends this
        # one's, would otherwise pass.
        expected_recipient = acs_url(provider, base_url)
        confirmations = response._query_assertion("/saml:Subject/saml:SubjectConfirmation")
        if not any(
            confirmation.get("Method") == "urn:oasis:names:tc:SAML:2.0:cm:bearer"
            and data.get("InResponseTo") == expected_id
            and data.get("Recipient") == expected_recipient
            for confirmation in confirmations
            for data in confirmation.findall("{urn:oasis:names:tc:SAML:2.0:assertion}SubjectConfirmationData")
        ):
            raise SamlError("the signed assertion does not confirm this request (SubjectConfirmationData InResponseTo/Recipient)")
        if provider.entity_id not in (response.get_audiences() or []):
            raise SamlError("the assertion does not name this SP in an AudienceRestriction")

        skew = provider.clock_skew_seconds
        now = OneLogin_Saml2_Utils.now()
        conditions = response._query_assertion("/saml:Conditions")
        condition = conditions[0] if conditions else None
        not_before = condition.get("NotBefore") if condition is not None else None
        conditions_nooa = condition.get("NotOnOrAfter") if condition is not None else None
        if not_before and OneLogin_Saml2_Utils.parse_SAML_to_time(not_before) > now + skew:
            raise SamlError("the assertion is not yet valid (Conditions NotBefore beyond the allowed clock skew)")
        if conditions_nooa and OneLogin_Saml2_Utils.parse_SAML_to_time(conditions_nooa) + skew <= now:
            raise SamlError("the assertion has expired (Conditions NotOnOrAfter beyond the allowed clock skew)")

        windows = [
            _unix(OneLogin_Saml2_Utils.parse_SAML_to_time(conditions_nooa)) if conditions_nooa else None,
            _unix(response.get_assertion_not_on_or_after()),
        ]
        windows = [value for value in windows if value is not None]
        if not windows:
            raise SamlError("the assertion carries no NotOnOrAfter, so it would stay replayable forever")

        assertion_id = response.get_assertion_id()
        if not assertion_id:
            raise SamlError("the assertion has no ID")
        name_id = response.get_nameid()
        if not isinstance(name_id, str) or not name_id.strip():
            raise SamlError("the assertion carries no NameID")

        attributes = {name: [str(value) for value in values if value is not None] for name, values in (response.get_attributes() or {}).items()}
        return SamlIdentity(
            name_id=name_id.strip(),
            name_id_format=response.get_nameid_format(),
            session_index=response.get_session_index(),
            attributes=attributes,
            assertion_id=assertion_id,
            replay_until=max(windows) + max(skew, 0) + 1,
            session_not_on_or_after=_unix(response.get_session_not_on_or_after()),
        )
    except SamlError:
        raise
    except Exception as exc:
        raise SamlError(f"invalid Response: {exc}") from None


def build_logout_redirect(
    provider: ProviderConfig,
    base_url: str,
    *,
    name_id: str,
    name_id_format: Optional[str],
    session_index: Optional[str],
    relay_state: str,
) -> str:
    """The IdP URL, with a LogoutRequest for this session, to send the browser to (SP-initiated SLO).

    Raises:
        SamlError: When the provider has no SLO endpoint or the request cannot be built.
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.logout_request import OneLogin_Saml2_Logout_Request

    if not provider.idp_slo_url:
        raise SamlError("the provider has no idp_slo_url")
    try:
        auth = OneLogin_Saml2_Auth(prepare_request(base_url, "/logout"), _settings(provider, base_url, want_messages_signed=False))
        auth.logout_request_class = _with_fixed_id(OneLogin_Saml2_Logout_Request, request_id_for(relay_state, "logout"))
        return auth.logout(return_to=relay_state, name_id=name_id, session_index=session_index, name_id_format=name_id_format)
    except Exception as exc:
        raise SamlError(f"could not build a LogoutRequest: {exc}") from None


def process_logout_response(provider: ProviderConfig, base_url: str, get_data: Dict[str, str], query_string: Optional[str], relay_state: str) -> None:
    """Validate the IdP's LogoutResponse to an SP-initiated logout.

    Informational: the local session was revoked before the browser left for the IdP, so the
    outcome only decides which page the user lands on. A signature is verified when present and
    not required — requiring one would turn an IdP that does not sign these into an error page
    after a logout that already succeeded.

    Raises:
        SamlError: When the response is invalid, answers a different request, or is not a success.
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    expected_id = request_id_for(relay_state, "logout")
    try:
        auth = OneLogin_Saml2_Auth(
            prepare_request(base_url, f"{SLS_PATH}/{provider.id}", get_data=get_data, query_string=query_string),
            _settings(provider, base_url, want_messages_signed=False),
        )
        auth.process_slo(keep_local_session=True, request_id=expected_id)
    except Exception as exc:
        raise SamlError(f"invalid LogoutResponse: {exc}") from None
    if auth.get_errors():
        raise SamlError(f"invalid LogoutResponse: {auth.get_last_error_reason() or ', '.join(auth.get_errors())}")


def process_logout_request(provider: ProviderConfig, base_url: str, get_data: Dict[str, str], query_string: Optional[str]) -> SamlLogoutRequest:
    """Validate an IdP-initiated LogoutRequest and build the LogoutResponse redirect.

    The request must be signed (``wantMessagesSigned``), by the IdP's certificate, and name the
    IdP as its ``Issuer``. Without that, any page could send a browser here and end the user's
    sessions — a nuisance rather than a breach, but one that needs nothing but a link.

    Raises:
        SamlError: On any failure. The caller must not revoke anything in that case.
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.logout_request import OneLogin_Saml2_Logout_Request
    from onelogin.saml2.xml_utils import OneLogin_Saml2_XML

    if not provider.idp_slo_url:
        # With no SLO endpoint, python3-saml would send the LogoutResponse to the RelayState —
        # a URL the sender chose.
        raise SamlError("the provider has no idp_slo_url to answer at")
    try:
        auth = OneLogin_Saml2_Auth(
            prepare_request(base_url, f"{SLS_PATH}/{provider.id}", get_data=get_data, query_string=query_string),
            _settings(provider, base_url, want_messages_signed=True),
        )
        response_url = auth.process_slo(keep_local_session=True)
    except Exception as exc:
        raise SamlError(f"invalid LogoutRequest: {exc}") from None
    if auth.get_errors() or not response_url:
        raise SamlError(f"invalid LogoutRequest: {auth.get_last_error_reason() or ', '.join(auth.get_errors())}")

    try:
        request_xml = auth.get_last_request_xml()
        if OneLogin_Saml2_Logout_Request.get_issuer(request_xml) != provider.idp_entity_id:
            raise SamlError("the LogoutRequest does not name the IdP as its Issuer")
        root = OneLogin_Saml2_XML.to_etree(request_xml)
        # Exact, and required. python3-saml compares Destination by prefix and skips it when
        # absent, so a request an IdP addressed to /slo/<id>-eu — another provider sharing the
        # same IdP certificate — would otherwise validate here. Mirrors the ACS Recipient check.
        if root.get("Destination") != sls_url(provider, base_url):
            raise SamlError("the LogoutRequest's Destination is not this provider's SLO endpoint")
        name_id = OneLogin_Saml2_Logout_Request.get_nameid(request_xml)
        session_indexes = tuple(index for index in OneLogin_Saml2_Logout_Request.get_session_indexes(request_xml) if index)
        request_id = OneLogin_Saml2_Logout_Request.get_id(request_xml)
        replay_until = _logout_replay_window(provider, root)
    except SamlError:
        raise
    except Exception as exc:
        raise SamlError(f"invalid LogoutRequest: {exc}") from None
    if not isinstance(name_id, str) or not name_id.strip():
        raise SamlError("the LogoutRequest carries no NameID")
    if not isinstance(request_id, str) or not request_id:
        raise SamlError("the LogoutRequest has no ID")
    return SamlLogoutRequest(
        name_id=name_id.strip(), session_indexes=session_indexes, response_url=response_url, request_id=request_id, replay_until=replay_until
    )


# How long a LogoutRequest without ``NotOnOrAfter`` is accepted after its ``IssueInstant``, on top
# of the provider's clock skew. The redirect is followed immediately; five minutes is generous.
LOGOUT_REQUEST_LIFETIME_SECONDS = 300


def _logout_replay_window(provider: ProviderConfig, root) -> int:
    """Unix seconds until which a validated LogoutRequest must stay in the replay table.

    With ``NotOnOrAfter``, python3-saml refuses the request after it, so the record is kept that
    long plus the skew. Without one the library would accept it forever, so it is bounded here
    instead: the ``IssueInstant`` must be recent, and the record is kept for as long as it is.

    Raises:
        SamlError: When the request is outside that window.
    """
    from onelogin.saml2.utils import OneLogin_Saml2_Utils

    skew = max(provider.clock_skew_seconds, 0)
    now = OneLogin_Saml2_Utils.now()
    not_on_or_after = root.get("NotOnOrAfter")
    if not_on_or_after:
        return int(OneLogin_Saml2_Utils.parse_SAML_to_time(not_on_or_after)) + skew + 1
    issue_instant = root.get("IssueInstant")
    if not issue_instant:
        raise SamlError("the LogoutRequest has neither NotOnOrAfter nor IssueInstant")
    issued = int(OneLogin_Saml2_Utils.parse_SAML_to_time(issue_instant))
    if issued > now + skew:
        raise SamlError("the LogoutRequest was issued in the future (IssueInstant beyond the allowed clock skew)")
    if issued + LOGOUT_REQUEST_LIFETIME_SECONDS + skew <= now:
        raise SamlError("the LogoutRequest is stale (IssueInstant too old and no NotOnOrAfter)")
    return issued + LOGOUT_REQUEST_LIFETIME_SECONDS + skew + 1


def sp_metadata(provider: ProviderConfig, base_url: str) -> str:
    """This SP's metadata document for ``provider``, validated before it is served.

    Raises:
        SamlError: When the generated document does not validate.
    """
    settings = _settings(provider, base_url, want_messages_signed=False)
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)
    if errors:
        raise SamlError(f"generated SP metadata is invalid: {', '.join(errors)}")
    return metadata.decode() if isinstance(metadata, bytes) else metadata


def unix_now() -> int:
    """Current time as Unix seconds."""
    return int(datetime.now(timezone.utc).timestamp())
