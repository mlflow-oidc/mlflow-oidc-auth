"""OAuth client registry for the FastAPI application.

Unit tests expect the module attribute `oauth` to be an instance of
`authlib.integrations.starlette_client.OAuth`.

Registration stays lazy so importing this module needs no OIDC configuration and performs no
network calls.

**One client per provider** (issue #315). Previously there was a single global client hardcoded
as ``"oidc"`` with a one-shot registration flag, which cannot express more than one identity
provider. Clients are now registered per provider id from the registry landed in #308.

The legacy name is preserved deliberately: the ``default`` provider registers under the authlib
name ``"oidc"``, so ``oauth.oidc`` keeps resolving for every existing call site and test. A
deployment that configures no registry gets a synthesised ``default`` provider from the flat
``OIDC_*`` variables, so nothing about its behaviour changes.

Client secrets are **not** read from the registry. ``ProviderConfig`` has no secret field, on
purpose: the registry is declarative configuration that may sit in a JSON file or an env var,
and secrets belong in the secrets manager. Each additional provider takes its secret from
``OIDC_CLIENT_SECRET_<PROVIDER_ID>`` resolved through the normal config chain, so the existing
providers (Vault, AWS, Azure) keep working.

A provider may instead be declared a **public client** (``OIDC_PUBLIC_CLIENT`` for the flat
configuration, ``"public_client": true`` on a registry entry): it is registered with no secret at
all and PKCE authenticates its token exchange. The declaration is explicit; a missing secret alone
never makes a client public — see ``_credentials_usable``.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from authlib.integrations.starlette_client import OAuth

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.config_providers import config_manager
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID

logger = get_logger()

# The authlib client name the single-provider deployment has always used. Every existing call
# site reaches the client as ``oauth.oidc``, so the default provider keeps this name rather than
# being renamed to "default" — a rename would be a breaking change for no benefit.
LEGACY_CLIENT_NAME = "oidc"


class PKCEUnsupportedError(Exception):
    """The provider advertises PKCE methods and the configured one is not among them (#312)."""


oauth: OAuth = OAuth()

# Registration state per provider id. A one-shot global flag could not express "provider A is
# registered, provider B failed", which is the state that matters once there is more than one.
_registered: Dict[str, bool] = {}

# Credential refusals already logged, by (provider id, rule). A refused provider is re-checked on
# every ``is_oidc_configured`` call — the readiness probe, each login attempt — and the error is
# worth one line per process, not one per probe.
_refusals_logged: set = set()


def get_oauth() -> OAuth:
    """Return the module-level OAuth instance."""

    return oauth


def client_name(provider_id: str) -> str:
    """The authlib client name for a provider id.

    ``default`` maps to ``"oidc"`` so ``oauth.oidc`` continues to resolve; every other provider
    registers under its own id.
    """

    return LEGACY_CLIENT_NAME if provider_id == DEFAULT_PROVIDER_ID else provider_id


def get_client(provider_id: str = DEFAULT_PROVIDER_ID):
    """Return the registered client for ``provider_id``, or None if it is not registered."""

    return getattr(oauth, client_name(provider_id), None)


async def assert_pkce_supported(client, provider_id: str = DEFAULT_PROVIDER_ID) -> None:
    """Fail the login *before* the redirect if the provider cannot do the configured PKCE method.

    PKCE is on by default since #312. A provider that does not support it usually ignores the
    extra parameters and then rejects the token exchange with a bare ``invalid_grant`` — an
    error that says nothing about PKCE and sends the operator looking at client secrets and
    redirect URIs instead. This turns that into one sentence naming the variable to change.

    Only an *explicit* contradiction fails: RFC 8414 makes ``code_challenge_methods_supported``
    optional, and plenty of providers support PKCE without advertising it, so an absent field is
    not evidence of anything and is allowed through.

    Parameters:
        client: The registered authlib client for this provider.
        provider_id: Registry id, used only in the message.

    Raises:
        PKCEUnsupportedError: If the provider advertises its supported methods and the
            configured one is not among them.
    """
    method = config.OIDC_CODE_CHALLENGE
    if not method or client is None:
        return

    loader = getattr(client, "load_server_metadata", None)
    if loader is None:
        return

    try:
        metadata = await loader()
    except Exception as exc:
        # Discovery being unreachable is a different failure, reported by the code that needs
        # the metadata for real. Never let this check be the thing that breaks a login.
        logger.debug("Could not load server metadata for PKCE check on '%s': %s", provider_id, exc)
        return

    supported = (metadata or {}).get("code_challenge_methods_supported")
    if not supported or not isinstance(supported, (list, tuple, set)):
        return

    if method not in supported:
        raise PKCEUnsupportedError(
            f"Provider '{provider_id}' does not support the configured PKCE method {method!r} "
            f"(it advertises: {', '.join(str(m) for m in supported) or 'none'}). "
            f"Set OIDC_CODE_CHALLENGE to a supported method, or to 'none' to disable PKCE for this deployment."
        )


def _has_required_config() -> bool:
    """Whether the flat ``OIDC_*`` variables name a client worth attempting to register.

    Credentials are deliberately *not* checked here. ``_credentials_usable`` checks them and
    reports why when they are unusable, so a deployment that set a client id and a discovery URL
    reaches that message instead of being counted as one that configured nothing at all.
    """
    return bool(config.OIDC_CLIENT_ID and config.OIDC_DISCOVERY_URL)


def _credential_hints(provider_id: str) -> tuple:
    """The settings an operator would change for ``provider_id``: ``(secret, public-client flag)``.

    Named literally rather than derived with ``_secret_env_key``: the derived key is tainted by the
    secret accessor for CodeQL, and logging it is reported as clear-text exposure of a secret.
    """
    if provider_id != DEFAULT_PROVIDER_ID:
        return "OIDC_CLIENT_SECRET_<PROVIDER_ID>", '"public_client": true on its registry entry'
    if config.AUTH_PROVIDERS.source == "legacy":
        return "OIDC_CLIENT_SECRET", "OIDC_PUBLIC_CLIENT=true"
    return "OIDC_CLIENT_SECRET", '"public_client": true on its registry entry'


def _log_refusal(rule: str, message: str, provider_id: str, *args: str) -> None:
    """Log a credential refusal once per provider and rule, at ERROR.

    Parameters:
        rule: Which rule refused the provider; part of the de-duplication key.
        message: The %-format message; its first placeholder is the provider id.
        provider_id: The refused provider.
        args: Further format arguments. Never a secret.
    """
    key = (provider_id, rule)
    if key in _refusals_logged:
        return
    _refusals_logged.add(key)
    logger.error(message, provider_id, *args)


def _credentials_usable(provider_id: str, client_secret: Optional[str], public_client: bool) -> bool:
    """Whether the provider's client credentials are a coherent configuration, reporting it when not.

    A client is either **confidential** — it has a secret — or **public**, declared explicitly with
    ``OIDC_PUBLIC_CLIENT`` / ``"public_client": true`` and authenticated by PKCE instead (#300).
    A missing secret is never read as "public": a secret that failed to load from a secrets
    manager must surface as a missing secret, not quietly change how the client authenticates.

    ====================  ==============  ============  ===========================================
    public_client         secret          PKCE          outcome
    ====================  ==============  ============  ===========================================
    False                 set             any           confidential client (registered)
    False                 missing         any           refused: set the secret or declare public
    True                  missing         on            public client (registered, no secret)
    True                  any             off           refused: a public client needs PKCE
    True                  set             on            refused: contradictory configuration
    ====================  ==============  ============  ===========================================

    Parameters:
        provider_id: Registry id of the provider, used only for the log line.
        client_secret: The resolved secret, or None. Never logged.
        public_client: Whether the provider is declared a public client.

    Returns:
        True when the provider may be registered.
    """
    secret_setting, public_setting = _credential_hints(provider_id)

    if not public_client:
        if client_secret:
            return True
        _log_refusal(
            "no_secret",
            "Provider '%s' has no client secret; refusing to register it. Set its client secret (%s), "
            "or declare it a public client (%s), which PKCE then authenticates instead.",
            provider_id,
            secret_setting,
            public_setting,
        )
        return False

    if not config.OIDC_CODE_CHALLENGE:
        _log_refusal(
            "no_pkce",
            "Provider '%s' is declared a public client but PKCE is disabled; refusing to register it. A public client has no "
            "secret, so PKCE is what authenticates its token exchange: leave OIDC_CODE_CHALLENGE at its S256 default.",
            provider_id,
        )
        return False

    if client_secret:
        _log_refusal(
            "contradictory",
            "Provider '%s' is declared a public client but a client secret (%s) is also configured; refusing to register it "
            "because the configuration is contradictory. Remove the secret, or stop declaring it a public client.",
            provider_id,
            secret_setting,
        )
        return False

    return True


def _secret_env_key(provider_id: str) -> str:
    """Config key holding a provider's client secret.

    ``okta-eu`` becomes ``OIDC_CLIENT_SECRET_OKTA_EU``. Anything outside ``A-Z0-9`` collapses to
    an underscore so a provider id that is legal in JSON is still a legal environment variable
    name.
    """

    return "OIDC_CLIENT_SECRET_" + re.sub(r"[^A-Z0-9]+", "_", provider_id.upper())


def _colliding_secret_keys() -> Dict[str, list]:
    """Provider ids that would share a client-secret key, grouped by that key.

    ``_secret_env_key`` collapses runs of non-alphanumeric characters, so ``okta-eu`` and
    ``okta_eu`` — both legal, distinct registry ids — resolve to the same variable. Registering
    either would give one provider the other's client secret, and the failure would surface as
    an opaque ``invalid_client`` from the IdP rather than as a configuration error.

    Detected rather than silently resolved: with no way to tell which provider the operator
    meant, refusing both is the only answer that cannot cross-wire a credential.
    """
    by_key: Dict[str, list] = {}
    for provider in config.AUTH_PROVIDERS.providers:
        by_key.setdefault(_secret_env_key(provider.id), []).append(provider.id)
    return {key: ids for key, ids in by_key.items() if len(ids) > 1}


def _client_secret_for(provider_id: str) -> Optional[str]:
    """Resolve a provider's client secret through the config chain."""

    if provider_id == DEFAULT_PROVIDER_ID:
        return config.OIDC_CLIENT_SECRET
    return config_manager.get(_secret_env_key(provider_id))


def _build_scope() -> str:
    """Build the space-delimited OIDC scope string for the authorize/token requests.

    OAuth 2.0 (RFC 6749 §3.3) requires the ``scope`` parameter to be space-delimited.
    We accept the configured value in comma- or space-separated form (or a mix) and
    always emit space-delimited scopes, so strict providers like Microsoft Entra ID do
    not reject the request (issue #238). ``offline_access`` is appended when the
    refresh-token flow is enabled. Duplicate scopes are collapsed, order preserved.
    """

    raw = config.OIDC_SCOPE or ""
    scopes = [s for s in raw.replace(",", " ").split() if s]
    if config.OIDC_USE_REFRESH_TOKEN and "offline_access" not in scopes:
        scopes.append("offline_access")

    seen: set[str] = set()
    unique = [s for s in scopes if not (s in seen or seen.add(s))]
    return " ".join(unique)


def _settings_dict(client_id: str, client_secret: Optional[str], discovery_url: str) -> Dict[str, Optional[str]]:
    """Authlib registration settings, omitting ``client_secret`` for a public client.

    A public client leaves the key out entirely rather than passing an empty value, so authlib
    authenticates its token, refresh and revocation requests with the ``none`` method
    (``client_id`` in the body) because there is no secret, not because of how it reads a falsy
    one. PKCE is what binds the code exchange.
    """

    settings: Dict[str, Optional[str]] = {"client_id": client_id, "server_metadata_url": discovery_url}
    if client_secret:
        settings["client_secret"] = client_secret
    return settings


def _client_settings(provider_id: str) -> Optional[Dict[str, Optional[str]]]:
    """Gather what authlib needs to register ``provider_id``, or None if it cannot be built.

    The default provider falls back to the flat ``OIDC_*`` variables only when no registry was
    configured at all, so a legacy deployment is unaffected while an explicit registry that
    omits an OIDC provider is honoured rather than overridden.
    """

    if any(provider_id in ids for ids in _colliding_secret_keys().values()):
        # Only ``provider_id`` — the plain argument — is logged. Neither the derived key nor the
        # id list from _colliding_secret_keys() appears here: both are dataflow-tainted from the
        # secret accessor, and CodeQL reports logging either as clear-text exposure of a secret.
        # Nothing is lost, because this runs once per provider, so every colliding provider
        # still names itself on its own line.
        logger.error(
            "Provider '%s' shares a client-secret configuration key with another provider; refusing to register it, "
            "because one of them would be given the other's credential. Rename them so their ids differ by more than punctuation.",
            provider_id,
        )
        return None

    provider = config.AUTH_PROVIDERS.by_id(provider_id)

    if provider is None:
        # Falling back to the flat OIDC_* variables is only correct when no registry was
        # configured at all. If the operator wrote a registry that omits an OIDC provider, that
        # omission *is* the configuration — leftover OIDC_* variables from before the migration
        # must not resurrect a browser login path they removed.
        if provider_id != DEFAULT_PROVIDER_ID or config.AUTH_PROVIDERS.source != "legacy" or not _has_required_config():
            return None
        if not _credentials_usable(DEFAULT_PROVIDER_ID, config.OIDC_CLIENT_SECRET, getattr(config, "OIDC_PUBLIC_CLIENT", False) is True):
            return None
        return _settings_dict(config.OIDC_CLIENT_ID, config.OIDC_CLIENT_SECRET, config.OIDC_DISCOVERY_URL)

    if provider.type != "oidc":
        # SAML has no authlib OAuth client, and a Kubernetes issuer is verified from its JWKS
        # rather than driven through an authorization flow.
        return None

    client_id = provider.client_id or (config.OIDC_CLIENT_ID if provider_id == DEFAULT_PROVIDER_ID else None)
    discovery_url = provider.discovery_url or (config.OIDC_DISCOVERY_URL if provider_id == DEFAULT_PROVIDER_ID else None)
    client_secret = _client_secret_for(provider_id)

    if not (client_id and discovery_url):
        return None

    if not _credentials_usable(provider_id, client_secret, getattr(provider, "public_client", False) is True):
        return None

    return _settings_dict(client_id, client_secret, discovery_url)


def ensure_client_registered(provider_id: str = DEFAULT_PROVIDER_ID) -> bool:
    """Ensure the authlib client for ``provider_id`` is registered.

    Args:
        provider_id: Registry id of the provider. Defaults to ``default``, which is the
            synthesised single provider a legacy deployment has.

    Returns:
        False when the provider is unknown, is not an OIDC provider, has incomplete
        configuration, or registration raised. Never propagates: one misconfigured provider must
        not stop the others from working, and must not take the application down at startup.
    """

    if _registered.get(provider_id):
        return True

    settings = _client_settings(provider_id)
    if settings is None:
        return False

    try:
        oauth.register(
            name=client_name(provider_id),
            client_kwargs={
                "scope": _build_scope(),
                "verify": config.OIDC_VERIFY_SSL,
                "code_challenge_method": config.OIDC_CODE_CHALLENGE,
            },
            **settings,
        )
        _registered[provider_id] = True
        return True
    except Exception as exc:
        logger.warning(f"Failed to register OIDC client for provider '{provider_id}': {exc}")
        return False


def ensure_all_clients_registered() -> Dict[str, bool]:
    """Register every OIDC provider in the registry, independently.

    Each provider is attempted on its own, so one that is misconfigured or whose discovery
    document is unreachable leaves the rest usable — with several providers the alternative
    would be one bad entry disabling login for everyone.

    Returns:
        ``{provider_id: registered}`` for every OIDC provider found. Empty when the registry
        holds none.
    """

    results: Dict[str, bool] = {}
    for provider in config.AUTH_PROVIDERS.providers:
        if provider.type != "oidc":
            continue
        results[provider.id] = ensure_client_registered(provider.id)
    if not results and config.AUTH_PROVIDERS.source == "legacy" and _has_required_config():
        # No registry configured at all, but flat configuration is present: keep the legacy
        # client. Gated on the registry being the legacy shim rather than merely holding no
        # OIDC entry, so an explicit registry that omits one is honoured (#347 review).
        results[DEFAULT_PROVIDER_ID] = ensure_client_registered(DEFAULT_PROVIDER_ID)
    return results


def ensure_oidc_client_registered() -> bool:
    """Ensure the legacy ``oidc`` client is registered.

    Kept as the name the application and its tests already use; it is now the ``default``
    provider's registration.
    """

    return ensure_client_registered(DEFAULT_PROVIDER_ID)


def is_oidc_configured(provider_id: str = DEFAULT_PROVIDER_ID) -> bool:
    """Return True if the provider's config is present and its client is registered."""

    return ensure_client_registered(provider_id)


def reset_oauth() -> None:
    """Reset the OAuth instance and all registration state (primarily for tests)."""

    global oauth
    oauth = OAuth()
    _registered.clear()
    _refusals_logged.clear()
