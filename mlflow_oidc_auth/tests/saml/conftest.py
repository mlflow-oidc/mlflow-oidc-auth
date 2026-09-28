"""Fixtures for the SAML suite (issues #328, #329): an in-test IdP, a real store, the real middleware.

No real IdP and no committed keys. The IdP's RSA key and self-signed certificate are generated
once per session with ``cryptography``; Responses and LogoutRequests are built as XML here and
signed with python3-saml's own ``xmlsec``-backed helpers — the same primitives an IdP uses — so
the SP under test verifies real signatures, not mocks.

Every test here that needs python3-saml is skipped without the ``[saml]`` extra; the one suite
that proves the plugin works *without* it lives in ``test_saml_extra_missing.py``.
"""

import base64
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth import audit
from mlflow_oidc_auth.provider_registry import ProviderConfig, RegistryLoadResult, _saml_extra_installed

requires_saml = pytest.mark.skipif(not _saml_extra_installed(), reason="the [saml] extra is not installed")

PROVIDER_ID = "saml1"
OTHER_PROVIDER_ID = "saml2"
SP_ENTITY_ID = "https://mlflow.example.test/saml/sp"
IDP_ENTITY_ID = "https://idp.example.test/entity"
IDP_SSO_URL = "https://idp.example.test/sso"
IDP_SLO_URL = "https://idp.example.test/slo"
BASE_URL = "http://testserver"
ACS_URL = f"{BASE_URL}/callback/{PROVIDER_ID}"
SLS_URL = f"{BASE_URL}/slo/{PROVIDER_ID}"
PROTECTED = "/saml-suite/protected"
OIDC_LOGIN = "/login/saml-suite-oidc"  # under the unprotected /login prefix
USER_EMAIL = "alice@example.com"
NAME_ID = "alice@example.com"


def _saml_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class KeyPair:
    key_pem: str
    cert_pem: str

    @property
    def cert_body(self) -> str:
        return "".join(line for line in self.cert_pem.splitlines() if "-----" not in line)


def _generate_keypair(common_name: str) -> KeyPair:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return KeyPair(
        key_pem=key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        cert_pem=cert.public_bytes(serialization.Encoding.PEM).decode(),
    )


@pytest.fixture(scope="session")
def idp_keys() -> KeyPair:
    return _generate_keypair("test-idp")


@pytest.fixture(scope="session")
def sp_keys() -> KeyPair:
    return _generate_keypair("test-sp")


@pytest.fixture(scope="session")
def rogue_keys() -> KeyPair:
    """A key the SP does not trust — what an attacker without the IdP's key signs with."""
    return _generate_keypair("rogue-idp")


class TestIdP:
    """Builds what an IdP sends. Defaults describe a valid, assertion-signed Response."""

    __test__ = False  # not a test class, despite the name

    def __init__(self, keys: KeyPair):
        self.keys = keys

    def assertion_xml(
        self,
        *,
        in_response_to: Optional[str],
        name_id: str = NAME_ID,
        attributes: Optional[Dict[str, List[str]]] = None,
        issuer: str = IDP_ENTITY_ID,
        audience: Optional[str] = SP_ENTITY_ID,
        recipient: str = ACS_URL,
        session_index: str = "_session-index-1",
        not_before: Optional[datetime] = None,
        not_on_or_after: Optional[datetime] = None,
        subject_not_on_or_after: Optional[datetime] = None,
        session_not_on_or_after: Optional[datetime] = None,
        include_conditions_expiry: bool = True,
        include_subject_expiry: bool = True,
        assertion_id: Optional[str] = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        attributes = {"email": [USER_EMAIL], "displayName": ["Alice Example"], "groups": ["mlflow"]} if attributes is None else attributes
        not_before = not_before or now - timedelta(minutes=1)
        not_on_or_after = not_on_or_after or now + timedelta(minutes=5)
        subject_not_on_or_after = subject_not_on_or_after or now + timedelta(minutes=5)
        session_not_on_or_after = session_not_on_or_after or now + timedelta(hours=8)
        irt = f' InResponseTo="{in_response_to}"' if in_response_to else ""
        scd_expiry = f' NotOnOrAfter="{_saml_time(subject_not_on_or_after)}"' if include_subject_expiry else ""
        cond_expiry = f' NotOnOrAfter="{_saml_time(not_on_or_after)}"' if include_conditions_expiry else ""
        audience_xml = f"<saml:AudienceRestriction><saml:Audience>{audience}</saml:Audience></saml:AudienceRestriction>" if audience else ""
        attrs = "".join(
            f'<saml:Attribute Name="{name}" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:basic">'
            + "".join(f'<saml:AttributeValue xsi:type="xs:string">{value}</saml:AttributeValue>' for value in values)
            + "</saml:Attribute>"
            for name, values in attributes.items()
        )
        return (
            '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
            f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ID="{assertion_id or "_a" + uuid.uuid4().hex}" Version="2.0" '
            f'IssueInstant="{_saml_time(now)}">'
            f"<saml:Issuer>{issuer}</saml:Issuer>"
            "<saml:Subject>"
            f'<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID>'
            '<saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">'
            f'<saml:SubjectConfirmationData{scd_expiry} Recipient="{recipient}"{irt}/>'
            "</saml:SubjectConfirmation>"
            "</saml:Subject>"
            f'<saml:Conditions NotBefore="{_saml_time(not_before)}"{cond_expiry}>{audience_xml}</saml:Conditions>'
            f'<saml:AuthnStatement AuthnInstant="{_saml_time(now)}" SessionIndex="{session_index}" '
            f'SessionNotOnOrAfter="{_saml_time(session_not_on_or_after)}">'
            "<saml:AuthnContext><saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
            "</saml:AuthnContextClassRef></saml:AuthnContext>"
            "</saml:AuthnStatement>"
            f"<saml:AttributeStatement>{attrs}</saml:AttributeStatement>"
            "</saml:Assertion>"
        )

    def sign(self, xml: str, keys: Optional[KeyPair] = None) -> str:
        from onelogin.saml2.utils import OneLogin_Saml2_Utils

        keys = keys or self.keys
        signed = OneLogin_Saml2_Utils.add_sign(xml, keys.key_pem, keys.cert_pem)
        return signed.decode() if isinstance(signed, bytes) else signed

    def response_xml(
        self,
        assertion: str,
        *,
        in_response_to: Optional[str],
        issuer: str = IDP_ENTITY_ID,
        destination: str = ACS_URL,
    ) -> str:
        irt = f' InResponseTo="{in_response_to}"' if in_response_to else ""
        return (
            '<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
            f'ID="_r{uuid.uuid4().hex}" Version="2.0" IssueInstant="{_saml_time(datetime.now(timezone.utc))}" Destination="{destination}"{irt}>'
            f"<saml:Issuer>{issuer}</saml:Issuer>"
            '<samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>'
            f"{assertion}"
            "</samlp:Response>"
        )

    def response(
        self,
        in_response_to: Optional[str],
        *,
        sign_assertion: bool = True,
        sign_response: bool = False,
        signing_keys: Optional[KeyPair] = None,
        response_kwargs: Optional[dict] = None,
        **assertion_kwargs,
    ) -> str:
        """A base64 Response, as the IdP's auto-submitting form posts it."""
        assertion = self.assertion_xml(in_response_to=in_response_to, **assertion_kwargs)
        if sign_assertion:
            assertion = self.sign(assertion, signing_keys)
        document = self.response_xml(assertion, in_response_to=in_response_to, **(response_kwargs or {}))
        if sign_response:
            document = self.sign(document, signing_keys)
        return base64.b64encode(document.encode()).decode()

    def logout_request_query(
        self,
        *,
        name_id: str = NAME_ID,
        session_indexes: tuple = ("_session-index-1",),
        relay_state: Optional[str] = "idp-relay",
        issuer: str = IDP_ENTITY_ID,
        destination: str = SLS_URL,
        sign: bool = True,
        signing_keys: Optional[KeyPair] = None,
        issue_instant: Optional[datetime] = None,
        not_on_or_after: Optional[datetime] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """A redirect-binding LogoutRequest query string, signed over its raw bytes."""
        indexes = "".join(f"<samlp:SessionIndex>{index}</samlp:SessionIndex>" for index in session_indexes)
        xml = (
            '<samlp:LogoutRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
            f'ID="{request_id or "_l" + uuid.uuid4().hex}" Version="2.0" IssueInstant="{_saml_time(issue_instant or datetime.now(timezone.utc))}" '
            + (f'NotOnOrAfter="{_saml_time(not_on_or_after)}" ' if not_on_or_after else "")
            + f'Destination="{destination}">'
            f"<saml:Issuer>{issuer}</saml:Issuer>"
            f'<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID>'
            f"{indexes}"
            "</samlp:LogoutRequest>"
        )
        return self._redirect_query("SAMLRequest", xml, relay_state, sign, signing_keys)

    def logout_response_query(self, *, in_response_to: str, relay_state: str, destination: str = SLS_URL, sign: bool = True) -> str:
        xml = (
            '<samlp:LogoutResponse xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
            f'ID="_lr{uuid.uuid4().hex}" Version="2.0" IssueInstant="{_saml_time(datetime.now(timezone.utc))}" '
            f'Destination="{destination}" InResponseTo="{in_response_to}">'
            f"<saml:Issuer>{IDP_ENTITY_ID}</saml:Issuer>"
            '<samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>'
            "</samlp:LogoutResponse>"
        )
        return self._redirect_query("SAMLResponse", xml, relay_state, sign, None)

    def _redirect_query(self, kind: str, xml: str, relay_state: Optional[str], sign: bool, signing_keys: Optional[KeyPair]) -> str:
        import xmlsec
        from onelogin.saml2.utils import OneLogin_Saml2_Utils

        keys = signing_keys or self.keys
        parts = [f"{kind}={OneLogin_Saml2_Utils.escape_url(OneLogin_Saml2_Utils.deflate_and_base64_encode(xml))}"]
        if relay_state is not None:
            parts.append(f"RelayState={OneLogin_Saml2_Utils.escape_url(relay_state)}")
        if not sign:
            return "&".join(parts)
        parts.append(f"SigAlg={OneLogin_Saml2_Utils.escape_url('http://www.w3.org/2001/04/xmldsig-more#rsa-sha256')}")
        signed_query = "&".join(parts)
        signature = OneLogin_Saml2_Utils.sign_binary(signed_query, keys.key_pem, xmlsec.Transform.RSA_SHA256)
        return signed_query + f"&Signature={OneLogin_Saml2_Utils.escape_url(OneLogin_Saml2_Utils.b64encode(signature))}"


@pytest.fixture
def idp(idp_keys) -> TestIdP:
    return TestIdP(idp_keys)


def saml_provider(idp_keys: KeyPair, provider_id: str = PROVIDER_ID, **overrides) -> ProviderConfig:
    values = dict(
        id=provider_id,
        type="saml",
        display_name="Corp SAML",
        admin_source="none",
        entity_id=SP_ENTITY_ID,
        idp_entity_id=IDP_ENTITY_ID,
        idp_sso_url=IDP_SSO_URL,
        idp_slo_url=IDP_SLO_URL,
        idp_x509_certs=(idp_keys.cert_body,),
    )
    values.update(overrides)
    return ProviderConfig(**values)


def oidc_provider(provider_id: str = "corp-oidc") -> ProviderConfig:
    return ProviderConfig(id=provider_id, type="oidc", display_name="Corp OIDC", audience="mlflow", issuer="https://oidc.example.test/")


def _patch_live_configs(monkeypatch, **values):
    """Set ``values`` on every config object the code under test reads (see the sessions e2e suite)."""
    from mlflow_oidc_auth.config import config as current
    from mlflow_oidc_auth.middleware import auth_middleware as middleware_module
    from mlflow_oidc_auth.routers import auth as auth_module
    from mlflow_oidc_auth.routers import saml as saml_router_module

    targets = {id(c): c for c in (current, middleware_module.config, auth_module.config, saml_router_module.config)}
    for cfg in targets.values():
        for name, value in values.items():
            monkeypatch.setattr(cfg, name, value, raising=False)


def install_providers(monkeypatch, *providers: ProviderConfig) -> None:
    """Replace the registry for the rest of the test (restored by ``monkeypatch``)."""
    _patch_live_configs(monkeypatch, AUTH_PROVIDERS=RegistryLoadResult(providers=list(providers), errors=[]))


@pytest.fixture
def providers(idp_keys):
    """The registry the suite runs against. Tests may replace entries before building the client."""
    return [saml_provider(idp_keys), saml_provider(idp_keys, provider_id=OTHER_PROVIDER_ID), oidc_provider()]


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield s
    s.engine.dispose()


@pytest.fixture
def audit_events():
    """Every audit event emitted during the test, parsed."""
    records = []

    class _Collector(logging.Handler):
        def emit(self, record):
            records.append(json.loads(record.getMessage()))

    logger = audit._get_audit_logger()
    handler = _Collector(level=logging.DEBUG)
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)


@pytest.fixture
def client(store, providers, monkeypatch):
    """The real auth and SAML routers behind the real ``AuthMiddleware``, cookie ``SameSite=Lax``.

    Middleware order mirrors ``app.py``. The session middleware uses ``same_site="lax"`` — the
    default this feature must work under, not be weakened for.
    """
    from mlflow_oidc_auth.routers.auth import auth_router
    from mlflow_oidc_auth.routers.saml import saml_router

    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)
    _patch_live_configs(
        monkeypatch,
        AUTH_PROVIDERS=RegistryLoadResult(providers=list(providers), errors=[]),
        OIDC_REDIRECT_URI=None,
        OIDC_GROUP_NAME=["mlflow"],
        OIDC_ADMIN_GROUP_NAME=["mlflow-admin"],
        MLFLOW_ENABLE_WORKSPACES=False,
        DEFAULT_LANDING_PAGE_IS_PERMISSIONS=True,
    )

    app = FastAPI()

    @app.get(PROTECTED)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @app.get(OIDC_LOGIN)
    async def oidc_login(request: Request):
        # An OIDC session for the same user, as the OIDC callback would open it.
        from mlflow_oidc_auth.routers.auth import _open_server_session
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        request.session["session_id"] = _open_server_session(USER_EMAIL, provider_id="corp-oidc", tokens=SessionTokens(provider_id="corp-oidc"))
        return {"ok": True}

    app.include_router(auth_router)
    app.include_router(saml_router)
    app.add_middleware(__import__("mlflow_oidc_auth.middleware", fromlist=["AuthMiddleware"]).AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential", same_site="lax")

    try:
        with TestClient(app, follow_redirects=False) as c:
            yield c
    finally:
        object.__setattr__(store_module.store, "_instance", previous)


def relay_state_of(location: str) -> str:
    """The RelayState in a redirect to the IdP."""
    return parse_qs(urlparse(location).query)["RelayState"][0]


def decoded_request(location: str, kind: str = "SAMLRequest") -> str:
    """The XML of a redirect-binding message in ``location``."""
    from onelogin.saml2.utils import OneLogin_Saml2_Utils

    value = parse_qs(urlparse(location).query)[kind][0]
    inflated = OneLogin_Saml2_Utils.decode_base64_and_inflate(value)
    return inflated.decode() if isinstance(inflated, bytes) else inflated


def start_login(client, provider_id: str = PROVIDER_ID, next_path: Optional[str] = None) -> str:
    """Begin SP-initiated SSO; return the RelayState the IdP will echo back."""
    response = client.get(f"/login/{provider_id}", params={"next": next_path} if next_path else None)
    assert response.status_code == 302, response.text
    assert response.headers["location"].startswith(IDP_SSO_URL)
    return relay_state_of(response.headers["location"])


def post_to_acs(client, saml_response: str, relay_state: Optional[str], provider_id: str = PROVIDER_ID, cookies_cleared: bool = True):
    """POST the IdP's form to the ACS. By default with no cookie, as a cross-site POST under Lax arrives."""
    if cookies_cleared:
        client.cookies.clear()
    data = {"SAMLResponse": saml_response}
    if relay_state is not None:
        data["RelayState"] = relay_state
    return client.post(f"/callback/{provider_id}", data=data)
