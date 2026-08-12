import base64
import json
import threading

import requests
from authlib.jose import JsonWebToken
from authlib.jose.errors import BadSignatureError
from cachetools import TTLCache

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.provider_registry import ASYMMETRIC_ALGORITHMS

# Provider types whose credentials are bearer tokens verified against a JWKS. SAML asserts
# identity through a browser POST instead, so it never resolves a token here.
TOKEN_PROVIDER_TYPES = ("oidc", "k8s")
from mlflow_oidc_auth.user import create_user, populate_groups, update_user

logger = get_logger()

# Signing algorithms accepted when validating a token.
#
# Passed explicitly so the algorithm is chosen by *us*, never by the token's own header. A JWT
# names its algorithm in an unauthenticated header, so a decoder that trusts that field lets the
# presenter decide how — or whether — their token is verified. RFC 8725 §3.1 is explicit that the
# set must be pinned by the verifier.
#
# The same asymmetric set the provider registry accepts (#308): signatures are checked against
# keys fetched from the provider's JWKS, so a symmetric algorithm has no legitimate use here and
# an unsigned token none at all.
_ACCEPTED_ALGORITHMS = list(ASYMMETRIC_ALGORITHMS)
_jwt = JsonWebToken(_ACCEPTED_ALGORITHMS)

# JWKS cache for the deployment-wide ``OIDC_DISCOVERY_URL``. TTL from
# OIDC_JWKS_CACHE_TTL_SECONDS (default 300s). Thread-safe via a lock, since multiple ASGI
# workers validate concurrently.
_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=config.OIDC_JWKS_CACHE_TTL_SECONDS)
_jwks_cache_lock = threading.Lock()

_JWKS_CACHE_KEY = "jwks"

# Per-provider JWKS, keyed by provider id (#313). Separate from the cache above so a rotation
# retry for one issuer cannot evict another's keys: sharing one entry across issuers would mean
# every failed signature refetched whichever provider happened to be there, and two issuers with
# different rotation schedules would thrash each other indefinitely.
_provider_jwks_cache: TTLCache = TTLCache(maxsize=32, ttl=config.OIDC_JWKS_CACHE_TTL_SECONDS)
_provider_jwks_lock = threading.Lock()


def _get_oidc_jwks(force_refresh: bool = False) -> dict:
    """Fetch JWKS from OIDC provider, with TTL-based caching.

    Results are cached for ``OIDC_JWKS_CACHE_TTL_SECONDS`` (default 300s) to
    avoid hitting the OIDC provider on every token validation.  When
    ``force_refresh`` is True the cache is cleared first — this is used on
    ``BadSignatureError`` to handle key rotation.

    Parameters:
        force_refresh: If True, bypass the cache and fetch fresh JWKS.

    Returns:
        The JWKS payload as a JSON-decoded dictionary.
    """
    if config.OIDC_DISCOVERY_URL is None:
        raise ValueError("OIDC_DISCOVERY_URL is not set in the configuration")

    with _jwks_cache_lock:
        if force_refresh:
            _jwks_cache.pop(_JWKS_CACHE_KEY, None)

        cached = _jwks_cache.get(_JWKS_CACHE_KEY)
        if cached is not None:
            return cached

    # Fetch outside the lock to avoid blocking other threads during HTTP I/O.
    # Timeouts are essential: without them, a hung IdP can block request threads
    # until the OS-level TCP timeout (~2 minutes), causing cascading auth failures.
    timeout = config.OIDC_HTTP_TIMEOUT_SECONDS
    try:
        logger.debug("Fetching OIDC discovery metadata")
        metadata = requests.get(config.OIDC_DISCOVERY_URL, timeout=timeout, verify=config.OIDC_VERIFY_SSL).json()
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise ValueError("No jwks_uri found in OIDC discovery metadata")

        logger.debug("Fetching JWKS from %s", jwks_uri)
        jwks = requests.get(jwks_uri, timeout=timeout, verify=config.OIDC_VERIFY_SSL).json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch OIDC JWKS: %s", e)
        raise

    with _jwks_cache_lock:
        _jwks_cache[_JWKS_CACHE_KEY] = jwks

    return jwks


def _get_provider_jwks(provider, force_refresh: bool = False) -> dict:
    """Fetch the JWKS for one provider, cached per provider id (#313).

    A provider that names no key source of its own inherits the deployment-wide
    ``OIDC_DISCOVERY_URL``, so it goes through :func:`_get_oidc_jwks` and shares that cache —
    which is what keeps a single-provider deployment behaving exactly as before.

    Parameters:
        provider: The resolved :class:`ProviderConfig`.
        force_refresh: Drop this provider's cached keys first. Used on ``BadSignatureError`` to
            pick up a rotated key — and only ever for the provider whose signature failed.

    Returns:
        The JWKS payload.
    """
    if not provider.discovery_url:
        # Only the synthesised legacy provider reaches this: the registry requires a token
        # provider to name its own key source, precisely so that two providers cannot share the
        # single-entry cache below and evict each other's keys on every refresh.
        return _get_oidc_jwks(force_refresh=force_refresh)

    # Keyed on the source as well as the id, so repointing a provider at a different IdP does
    # not keep serving the previous one's keys for the rest of the TTL.
    cache_key = (provider.id, provider.discovery_url)
    with _provider_jwks_lock:
        if force_refresh:
            _provider_jwks_cache.pop(cache_key, None)
        cached = _provider_jwks_cache.get(cache_key)
        if cached is not None:
            return cached

    timeout = config.OIDC_HTTP_TIMEOUT_SECONDS
    try:
        logger.debug("Fetching OIDC discovery metadata for provider %s", provider.id)
        metadata = requests.get(provider.discovery_url, timeout=timeout, verify=config.OIDC_VERIFY_SSL).json()
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise ValueError(f"No jwks_uri in discovery metadata for provider '{provider.id}'")

        logger.debug("Fetching JWKS for provider %s", provider.id)
        jwks = requests.get(jwks_uri, timeout=timeout, verify=config.OIDC_VERIFY_SSL).json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch JWKS for provider %s: %s", provider.id, e)
        raise

    with _provider_jwks_lock:
        _provider_jwks_cache[cache_key] = jwks

    return jwks


def _unverified_issuer(token: str) -> str | None:
    """Read ``iss`` from a token **without verifying anything**.

    This is the one place unverified token content is read, and it is read for exactly one
    purpose: choosing which validator to apply. That is safe only because the choice can never
    grant anything — an unrecognised value selects no validator and the token is refused, and a
    recognised one selects a provider whose keys, algorithms, issuer and audience are then all
    enforced. Nothing here is trusted; it is a lookup key.
    """
    try:
        payload = token.split(".")[1]
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        issuer = json.loads(decoded).get("iss")
    except Exception:
        return None
    return issuer if isinstance(issuer, str) else None


def resolve_token_provider(token: str):
    """The provider whose policy applies to ``token``. See :func:`_resolve_provider`."""
    return _resolve_provider(token)


def _resolve_provider(token: str):
    """Pick the provider whose validator applies to ``token``.

    A deployment with one provider has nothing to choose between: the single validator applies,
    and no unverified token content is consulted at all. This is also what keeps every existing
    single-provider deployment byte-for-byte unchanged.

    With more than one, the token's unverified ``iss`` selects the provider by **exact match**,
    and an issuer that matches nothing is refused. There is deliberately no fallback validator:
    a default would be the one an attacker aims at, since reaching it requires only an ``iss``
    that matches nothing.

    Raises:
        ValueError: If no provider matches, or the registry has none at all.
    """
    providers = [provider for provider in config.AUTH_PROVIDERS.providers if provider.type in TOKEN_PROVIDER_TYPES]
    if not providers:
        raise ValueError("No token-validating provider is configured")

    if len(providers) == 1:
        return providers[0]

    issuer = _unverified_issuer(token)
    if not issuer:
        raise ValueError("Token carries no issuer, and this deployment has more than one provider to choose between")

    for provider in providers:
        if provider.issuer and provider.issuer == issuer:
            return provider

    # Deliberately not logged with the issuer at error level in a way that would let an
    # unauthenticated caller fill the log with arbitrary strings; debug carries the detail.
    logger.debug("No configured provider claims issuer %r", issuer)
    raise ValueError("Token issuer does not match any configured provider")


def _claims_options_for(provider) -> dict | None:
    """Build the claims constraints for one provider.

    Audience is required of every explicitly configured provider (the registry refuses an entry
    without one), so a multi-provider deployment always pins it. The synthesised ``default``
    provider may carry none, which is the pre-#313 behaviour for a deployment that never set
    ``OIDC_AUDIENCE``, preserved so upgrading changes nothing.
    """
    options = {}
    if provider.audience:
        options["aud"] = {"essential": True, "value": provider.audience}
    if provider.issuer:
        options["iss"] = {"essential": True, "value": provider.issuer}
    return options or None


def _jwt_for(provider) -> JsonWebToken:
    """A decoder pinned to this provider's accepted algorithms.

    Per-provider rather than global because a Kubernetes issuer and an Entra tenant need not
    agree on an algorithm set, and the registry already refuses a symmetric one — so whatever is
    here is asymmetric, and the token's own header still chooses nothing.
    """
    algorithms = [algorithm for algorithm in provider.allowed_algorithms if algorithm in ASYMMETRIC_ALGORITHMS]
    if not algorithms:
        raise ValueError(f"Provider '{provider.id}' has no usable signing algorithm")
    return JsonWebToken(algorithms)


def validate_token(token: str):
    """Validate a bearer token against the provider that issued it.

    The provider is chosen first (see :func:`_resolve_provider`), and everything after that —
    keys, accepted algorithms, expected issuer, expected audience — comes from that provider
    alone. No union of keys across providers is ever offered to the decoder, so a ``kid`` can
    only ever select a key belonging to the issuer the token claims.

    Returns:
        The validated claims.

    Raises:
        ValueError: If no provider matches the token's issuer.
        Exception: Whatever authlib raises for a token that does not validate.
    """
    provider = _resolve_provider(token)
    claims_options = _claims_options_for(provider)
    decoder = _jwt_for(provider)

    try:
        jwks = _get_provider_jwks(provider)
        payload = decoder.decode(token, jwks, claims_options=claims_options)
        payload.validate()
        return payload
    except BadSignatureError as e:
        logger.error("Token validation failed with bad signature for provider %s: %s", provider.id, str(e))
        # Refresh *this* provider's keys and retry once, for key rotation.
        jwks = _get_provider_jwks(provider, force_refresh=True)
        payload = decoder.decode(token, jwks, claims_options=claims_options)
        payload.validate()
        return payload
    except Exception as e:
        logger.error("Unexpected error during token validation: %s", str(e))
        raise
