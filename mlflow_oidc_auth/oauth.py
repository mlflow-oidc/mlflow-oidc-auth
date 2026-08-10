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

oauth: OAuth = OAuth()

# Registration state per provider id. A one-shot global flag could not express "provider A is
# registered, provider B failed", which is the state that matters once there is more than one.
_registered: Dict[str, bool] = {}


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


def _has_required_config() -> bool:
    """Whether the flat ``OIDC_*`` variables describe a usable client."""
    return bool(config.OIDC_CLIENT_ID and config.OIDC_CLIENT_SECRET and config.OIDC_DISCOVERY_URL)


def _secret_env_key(provider_id: str) -> str:
    """Config key holding a provider's client secret.

    ``okta-eu`` becomes ``OIDC_CLIENT_SECRET_OKTA_EU``. Anything outside ``A-Z0-9`` collapses to
    an underscore so a provider id that is legal in JSON is still a legal environment variable
    name.
    """

    return "OIDC_CLIENT_SECRET_" + re.sub(r"[^A-Z0-9]+", "_", provider_id.upper())


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


def _client_settings(provider_id: str) -> Optional[Dict[str, Optional[str]]]:
    """Gather what authlib needs to register ``provider_id``, or None if it cannot be built.

    The default provider falls back to the flat ``OIDC_*`` variables when the registry has no
    entry for it, so a deployment that configures an explicit registry without a ``default``
    entry still behaves exactly as it does today.
    """

    provider = config.AUTH_PROVIDERS.by_id(provider_id)

    if provider is None:
        if provider_id != DEFAULT_PROVIDER_ID or not _has_required_config():
            return None
        return {
            "client_id": config.OIDC_CLIENT_ID,
            "client_secret": config.OIDC_CLIENT_SECRET,
            "server_metadata_url": config.OIDC_DISCOVERY_URL,
        }

    if provider.type != "oidc":
        # SAML has no authlib OAuth client, and a Kubernetes issuer is verified from its JWKS
        # rather than driven through an authorization flow.
        return None

    client_id = provider.client_id or (config.OIDC_CLIENT_ID if provider_id == DEFAULT_PROVIDER_ID else None)
    discovery_url = provider.discovery_url or (config.OIDC_DISCOVERY_URL if provider_id == DEFAULT_PROVIDER_ID else None)
    client_secret = _client_secret_for(provider_id)

    if not (client_id and client_secret and discovery_url):
        return None

    return {"client_id": client_id, "client_secret": client_secret, "server_metadata_url": discovery_url}


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
    if not results and _has_required_config():
        # No registry entries at all, but flat configuration is present: keep the legacy client.
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
