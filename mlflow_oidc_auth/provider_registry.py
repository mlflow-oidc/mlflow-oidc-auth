"""Identity provider registry (issue #308).

Configuration is a flat set of ``OIDC_*`` singletons and cannot express more than one identity
provider. This module adds a structured registry that can, while leaving the flat variables as
the sole source of truth for deployments that have not adopted it.

**Nothing consumes this yet.** It is the shape the rest of the enterprise-identity epic (#304)
is built against; login, callback and token validation are unchanged by this module.

Two ways to configure it, both read through the existing ``config_providers`` chain so secrets
managers keep working:

``AUTH_PROVIDERS``
    A JSON array of provider objects.
``AUTH_PROVIDERS_FILE``
    A path to a file containing the same JSON.

With neither set, a single provider ``default`` is synthesised from the flat ``OIDC_*``
variables with ``jit`` / ``every_login`` / ``authoritative`` — which is what the plugin does
today, so an existing deployment sees no change.

Invalid entries are **dropped, not repaired**, and the reasons are reported so startup can log
them. Dropping rather than raising follows the ``_warn_if_*`` precedent in ``config.py``:
``AppConfig`` is a module-level singleton imported by tooling with nothing to do with login —
Alembic's migration environment, for one — so raising here would take that tooling down over a
provider it never uses. Dropping is also the deny-by-default answer: an entry that cannot be
validated does not exist, so nobody can authenticate through it.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# The provider id synthesised from the flat OIDC_* variables.
DEFAULT_PROVIDER_ID = "default"

PROVIDER_TYPES = ("oidc", "saml", "k8s")

# Provider types that can carry a browser login flow. ``k8s`` cannot: a projected
# service-account token is presented directly as a bearer credential — there is no
# authorization endpoint to redirect a human to, no consent, and no callback. This is a
# different axis from ``type``, which describes how a credential is *verified*: a k8s provider
# verifies tokens the same way an OIDC one does (JWT against the cluster's JWKS), it just can
# never appear on a login page.
INTERACTIVE_BY_DEFAULT = {"oidc": True, "saml": True, "k8s": False}
PROVISIONING_MODES = ("jit", "scim", "none")
GROUP_SYNC_MODES = ("none", "first_login", "every_login")
GROUP_SYNC_STRATEGIES = ("additive", "authoritative")
# Provider types whose credentials are bearer tokens verified against a JWKS. They carry the
# extra requirements in _validate: an issuer to pin, and a key source of their own.
TOKEN_PROVIDER_TYPES = ("oidc", "k8s")

# "scim" is deliberately absent — see _validate_admin_source.
ADMIN_SOURCES = ("claims", "none")
IDENTITY_BINDINGS = ("subject", "email")

# Symmetric algorithms: the verifier holds the same secret the signer does. Combined with a
# JWKS source this is the classic algorithm-confusion setup, where a public verification key is
# replayed as an HMAC secret and any caller can mint a valid token.
HMAC_ALGORITHMS = ("HS256", "HS384", "HS512")

# Asymmetric algorithms this plugin can actually verify: signatures are checked against keys
# fetched from the provider's JWKS.
ASYMMETRIC_ALGORITHMS = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)

# Canonical spelling by uppercase name, so "rs256" and "eddsa" resolve to "RS256" and "EdDSA".
# Storing the canonical form matters: a consumer comparing against "RS256" would otherwise miss
# a provider configured as "rs256", and silently fall through to whatever its own default is.
_CANONICAL_ALGORITHMS = {algorithm.upper(): algorithm for algorithm in ASYMMETRIC_ALGORITHMS + HMAC_ALGORITHMS}

# ``alg: none`` means the token carries no signature at all. Rejected by name and with its own
# message because it is the single most dangerous value this field can take, and because it is
# easy to arrive at innocently by copying an example.
NONE_ALGORITHM = "NONE"

DEFAULT_ALGORITHMS = ("RS256",)


@dataclass(frozen=True)
class ProviderConfig:
    """One identity provider and the policy that applies to it.

    Frozen because the registry is read at startup and shared; a consumer mutating a provider
    in place would change authentication policy for every later request.

    Attributes:
        id: Stable identifier, unique across the registry. Used as ``provider_id`` on
            ``user_identities`` rows (#333).
        type: One of ``oidc``, ``saml``, ``k8s``.
        display_name: Human-readable label for the login picker.
        provisioning: ``jit`` creates users on first login, ``scim`` expects an external
            directory to create them, ``none`` requires them to exist already.
        group_sync: When group membership is refreshed from provider claims.
        group_sync_mode: ``authoritative`` replaces local membership with the claim,
            ``additive`` only adds.
        admin_source: Where administrator status may come from. Never ``scim``.
        interactive: Whether this provider can carry a browser login flow, and so whether it
            belongs on the login page (#317, #330). Independent of ``type``, which describes how
            a credential is *verified*: a ``k8s`` provider verifies tokens exactly as an
            ``oidc`` one does, but a projected service-account token is presented directly as a
            bearer credential — there is no authorization endpoint to redirect to. Defaults
            from the type and cannot be set True for a type that has no browser flow.
        identity_binding: Which token field identifies the user.
        allowed_email_domains: Required when binding on ``email``; an email-bound provider
            with no domain restriction lets anyone who can prove any address take an account.
        allowed_algorithms: Accepted JWT signing algorithms.
        audience: Expected ``aud``. Required — a token with no audience check is valid for
            any relying party the issuer serves.
        issuer: Expected ``iss``, when known.
        discovery_url: OIDC discovery document, for ``oidc`` providers.
        client_id: OAuth client id, for ``oidc`` providers.
    """

    id: str
    type: str = "oidc"
    display_name: str = ""
    provisioning: str = "jit"
    group_sync: str = "every_login"
    group_sync_mode: str = "authoritative"
    admin_source: str = "claims"
    identity_binding: str = "subject"
    interactive: bool = True
    allowed_email_domains: Tuple[str, ...] = ()
    allowed_algorithms: Tuple[str, ...] = DEFAULT_ALGORITHMS
    audience: Optional[str] = None
    issuer: Optional[str] = None
    discovery_url: Optional[str] = None
    client_id: Optional[str] = None

    def has_own_key_source(self) -> bool:
        """Whether this entry names its own JWKS source rather than inheriting the flat one.

        Reports only what the entry says. It is deliberately *not* used to decide whether an
        algorithm is safe: an entry naming no source still resolves keys somehow — from the
        deployment-wide ``OIDC_DISCOVERY_URL`` — so gating the algorithm checks on this was
        evadable by simply omitting two optional fields. Algorithms are validated on their own
        merits instead (see :func:`_validate_algorithms`).
        """
        return bool(self.discovery_url or self.issuer)


@dataclass
class RegistryLoadResult:
    """Providers that validated, plus why anything else did not.

    Attributes:
        providers: Entries that passed every check, in configuration order.
        errors: One human-readable line per rejected entry or per structural problem.
        source: Where the registry came from — ``legacy``, ``env`` or ``file``.
    """

    providers: List[ProviderConfig] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    source: str = "legacy"

    def interactive_providers(self) -> List[ProviderConfig]:
        """Providers that belong on the login page.

        What #317 renders one button per. Excludes machine-only providers such as a Kubernetes
        service-account issuer, which verifies tokens like any other OIDC provider but has no
        flow a browser can start.
        """
        return [provider for provider in self.providers if provider.interactive]

    def by_id(self, provider_id: str) -> Optional[ProviderConfig]:
        """Return the provider with ``provider_id``, or None."""
        for provider in self.providers:
            if provider.id == provider_id:
                return provider
        return None


def _as_tuple(value: Any) -> Tuple[str, ...]:
    """Coerce a JSON scalar or list into a tuple of non-blank strings.

    A single string is treated as a one-element list, which is what an operator writing
    ``"allowed_email_domains": "example.com"`` means.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _validate(entry: Dict[str, Any], index: int, seen_ids: set) -> Tuple[Optional[ProviderConfig], List[str]]:
    """Validate one registry entry.

    Returns:
        ``(provider, errors)``. ``provider`` is None whenever ``errors`` is non-empty — an
        entry is never partially accepted, because a provider missing half its policy is more
        dangerous than one that does not exist.
    """
    errors: List[str] = []
    label = f"provider[{index}]"

    provider_id = entry.get("id")
    if not isinstance(provider_id, str) or not provider_id.strip():
        return None, [f"{label}: 'id' is required and must be a non-empty string"]
    provider_id = provider_id.strip()
    label = f"provider '{provider_id}'"

    if provider_id in seen_ids:
        # Both copies are rejected by the caller: with two entries claiming one id there is no
        # way to tell which policy the operator meant, and guessing would silently apply the
        # wrong one.
        return None, [f"{label}: duplicate id"]

    # Before anything else touches these values. See _validate_field_types.
    type_errors = _validate_field_types(entry, label)
    if type_errors:
        return None, type_errors

    provider_type = entry.get("type", "oidc")
    if provider_type not in PROVIDER_TYPES:
        errors.append(f"{label}: unknown type {provider_type!r}; expected one of {', '.join(PROVIDER_TYPES)}")

    provisioning = entry.get("provisioning", "jit")
    if provisioning not in PROVISIONING_MODES:
        errors.append(f"{label}: unknown provisioning {provisioning!r}; expected one of {', '.join(PROVISIONING_MODES)}")

    group_sync = entry.get("group_sync", "every_login")
    if group_sync not in GROUP_SYNC_MODES:
        errors.append(f"{label}: unknown group_sync {group_sync!r}; expected one of {', '.join(GROUP_SYNC_MODES)}")

    group_sync_mode = entry.get("group_sync_mode", "authoritative")
    if group_sync_mode not in GROUP_SYNC_STRATEGIES:
        errors.append(f"{label}: unknown group_sync_mode {group_sync_mode!r}; expected one of {', '.join(GROUP_SYNC_STRATEGIES)}")

    errors.extend(_validate_admin_source(entry.get("admin_source", "claims"), label))

    identity_binding = entry.get("identity_binding", "subject")
    if identity_binding not in IDENTITY_BINDINGS:
        errors.append(f"{label}: unknown identity_binding {identity_binding!r}; expected one of {', '.join(IDENTITY_BINDINGS)}")

    interactive_default = INTERACTIVE_BY_DEFAULT.get(provider_type, True)
    interactive = entry.get("interactive", interactive_default)
    if not isinstance(interactive, bool):
        errors.append(f"{label}: 'interactive' must be true or false, got {interactive!r}")
    elif interactive and not interactive_default:
        # Rejected rather than silently corrected: an operator who asked for this expects a
        # login button, and #317 would render one that cannot complete a flow.
        errors.append(
            f"{label}: type {provider_type!r} has no browser login flow, so 'interactive' cannot be true; "
            "its credentials are presented directly as bearer tokens"
        )

    allowed_email_domains = _as_tuple(entry.get("allowed_email_domains"))
    if identity_binding == "email" and not allowed_email_domains:
        errors.append(
            f"{label}: identity_binding 'email' requires allowed_email_domains; without it any account at any domain "
            "the provider will assert can claim a local user"
        )

    allowed_algorithms, algorithm_errors = _validate_algorithms(entry.get("allowed_algorithms"), label)
    errors.extend(algorithm_errors)

    audience = entry.get("audience")
    issuer = entry.get("issuer")
    discovery_url = entry.get("discovery_url")
    client_id = entry.get("client_id")

    if not isinstance(audience, str) or not audience.strip():
        errors.append(f"{label}: 'audience' is required; a token validated with no audience check is valid for every relying party of that issuer")

    if provider_type in TOKEN_PROVIDER_TYPES:
        # Both required for the same reason ``audience`` is, and both became load-bearing when
        # validation went per-provider (#313).
        #
        # Without ``issuer`` nothing pins ``iss``, so every tenant of a shared key set is
        # accepted: an Entra ``common`` endpoint, a multi-tenant Keycloak realm and a cluster
        # issuer fronting several namespaces all publish one JWKS for many issuers, and a token
        # from any of them carries a valid signature. The attacker needs only their own tenant.
        #
        # Without ``discovery_url`` the provider inherits the deployment-wide key source and its
        # single-entry cache, so two such providers share one cache slot: a rotation refresh for
        # one evicts the other's keys, and an unauthenticated caller sending bad signatures can
        # hold that slot permanently cold. Naming a source keeps each provider's keys its own.
        if not isinstance(issuer, str) or not issuer.strip():
            errors.append(
                f"{label}: 'issuer' is required for a '{provider_type}' provider; without it no 'iss' check is performed and "
                "every issuer sharing that key set is accepted"
            )
        if not isinstance(discovery_url, str) or not discovery_url.strip():
            errors.append(
                f"{label}: 'discovery_url' is required for a '{provider_type}' provider; without it the provider shares the "
                "deployment-wide key cache with every other provider that omits one"
            )

    if provider_type == "saml" and not _saml_extra_installed():
        errors.append(f"{label}: type 'saml' requires the [saml] extra to be installed")

    if errors:
        return None, errors

    return (
        ProviderConfig(
            id=provider_id,
            type=provider_type,
            display_name=entry.get("display_name") or provider_id,
            provisioning=provisioning,
            group_sync=group_sync,
            group_sync_mode=group_sync_mode,
            admin_source=entry.get("admin_source", "claims"),
            identity_binding=identity_binding,
            interactive=bool(interactive),
            allowed_email_domains=allowed_email_domains,
            allowed_algorithms=allowed_algorithms,
            audience=audience.strip(),
            issuer=issuer.strip() if isinstance(issuer, str) else None,
            discovery_url=discovery_url.strip() if isinstance(discovery_url, str) else None,
            client_id=client_id.strip() if isinstance(client_id, str) else None,
        ),
        [],
    )


# Entry fields that must be strings when present. Checked up front, before any of them is used
# as a dict key or has a string method called on it: JSON can put a list or object in any of
# these, and this module must report that rather than raise. ``AppConfig`` is instantiated at
# import time, so an exception here does not degrade login — it stops the plugin and Alembic
# from importing at all, which is the opposite of what dropping invalid entries is for.
_STRING_FIELDS = (
    "type",
    "display_name",
    "provisioning",
    "group_sync",
    "group_sync_mode",
    "admin_source",
    "identity_binding",
    "audience",
    "issuer",
    "discovery_url",
    "client_id",
)

# Fields that may be a single string or a list of them.
_LIST_FIELDS = ("allowed_email_domains", "allowed_algorithms")


def _validate_field_types(entry: Dict[str, Any], label: str) -> List[str]:
    """Check that every field is the shape the rest of validation assumes.

    Runs before any other check and short-circuits it, so no later line can call ``.strip()`` on
    a list or use one as a dict key. Reporting the wrong type is also more useful to an operator
    than the downstream symptom: ``'type' must be a string, got list`` points at the mistake,
    whereas ``unhashable type: 'list'`` points at our dictionary.
    """
    errors = []
    for key in _STRING_FIELDS:
        value = entry.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"{label}: '{key}' must be a string, got {type(value).__name__}")
    for key in _LIST_FIELDS:
        value = entry.get(key)
        if value is not None and not isinstance(value, (str, list, tuple)):
            errors.append(f"{label}: '{key}' must be a string or a list of strings, got {type(value).__name__}")
    return errors


def _validate_algorithms(value: Any, label: str) -> Tuple[Tuple[str, ...], List[str]]:
    """Resolve ``allowed_algorithms`` to canonical names, rejecting anything unverifiable.

    Three rules, in descending order of how badly they end:

    * ``none`` is rejected outright. It means the token carries no signature, so accepting it
      lets anyone mint a token for that provider. It is worse than the algorithm-confusion case
      below, which at least requires a key to confuse.
    * Symmetric (HMAC) algorithms are rejected outright, not merely when a JWKS source appears
      on the same entry. This plugin has no symmetric-key verification path at all — signatures
      are checked against keys fetched from the provider's JWKS — so an HMAC entry cannot work,
      and the only question is whether it fails safely. Gating on whether the *entry* names a
      key source was evadable by omitting ``issuer``/``discovery_url`` while the deployment's
      flat ``OIDC_DISCOVERY_URL`` still supplied one, which is the confusion setup restored.
      This is stricter than issue #308 asked for, deliberately.
    * Anything not in the supported set is rejected rather than passed through, so a typo
      becomes a startup message instead of an algorithm a consumer silently does not honour.

    Returns:
        ``(algorithms, errors)``. Names are canonically spelled, so a consumer comparing against
        ``"RS256"`` matches an entry written as ``"rs256"``.
    """
    if value is None:
        return DEFAULT_ALGORITHMS, []

    # Present but unusable is reported rather than quietly defaulted. Falling back to RS256 is
    # the safe direction, but an operator who believes they narrowed or widened the accepted
    # set needs to find out that they did not — silently discarding a configured value leaves
    # nothing to debug from.
    items = [value] if isinstance(value, str) else list(value)
    non_strings = [item for item in items if not isinstance(item, str)]
    if non_strings:
        return DEFAULT_ALGORITHMS, [f"{label}: 'allowed_algorithms' must contain only strings; got {type(non_strings[0]).__name__}"]

    raw = _as_tuple(value)
    if not raw:
        return DEFAULT_ALGORITHMS, [f"{label}: 'allowed_algorithms' is set but lists no algorithm; omit it to accept the default {DEFAULT_ALGORITHMS[0]}"]

    algorithms: List[str] = []
    errors: List[str] = []
    for algorithm in raw:
        upper = algorithm.upper()
        if upper == NONE_ALGORITHM:
            errors.append(f"{label}: algorithm 'none' is never allowed; it means the token carries no signature, so anyone could mint one for this provider")
            continue
        if upper in HMAC_ALGORITHMS:
            errors.append(
                f"{label}: symmetric algorithm {algorithm!r} is not supported; this plugin verifies signatures against the provider's JWKS, "
                "and accepting an HMAC algorithm alongside a fetched public key is the algorithm-confusion setup where that key is replayed "
                "as a shared secret"
            )
            continue
        canonical = _CANONICAL_ALGORITHMS.get(upper)
        if canonical is None:
            errors.append(f"{label}: unknown algorithm {algorithm!r}; expected one of {', '.join(ASYMMETRIC_ALGORITHMS)}")
            continue
        algorithms.append(canonical)

    if errors:
        return DEFAULT_ALGORITHMS, errors
    return tuple(algorithms), []


def _validate_admin_source(admin_source: Any, label: str) -> List[str]:
    """Reject ``admin_source: scim``, and anything else outside the allowed set.

    SCIM is rejected on purpose rather than as an oversight. If administrator status can be
    derived from a SCIM-provisioned group, then whoever can create groups in the external
    directory — or influence their naming — can grant themselves admin here. Grafana shipped
    exactly that privilege-escalation flaw. Admin group names stay server-side configuration.
    """
    if admin_source == "scim":
        return [
            f"{label}: admin_source 'scim' is not allowed; it would let whoever controls group naming in the external "
            "directory grant themselves administrator. Keep admin group names in server-side configuration."
        ]
    if admin_source not in ADMIN_SOURCES:
        return [f"{label}: unknown admin_source {admin_source!r}; expected one of {', '.join(ADMIN_SOURCES)}"]
    return []


# Candidate imports for the optional SAML dependency. Which library ships as the ``[saml]``
# extra is decided by the packaging spike (#327) and is not settled here — this lists the
# realistic candidates so the check works whichever is chosen, and so whoever closes #327 has an
# obvious place to pin it down.
#
# Until that extra exists, no import succeeds and every ``type: saml`` provider is rejected.
# That is the correct answer rather than a gap: SAML cannot be configured before SAML is
# implemented, and silently accepting the entry would leave a provider in the registry that
# nothing can authenticate against.
_SAML_MODULE_CANDIDATES = ("onelogin.saml2", "saml2")


def _saml_extra_installed() -> bool:
    """Whether a SAML implementation is importable."""
    import importlib.util

    for module in _SAML_MODULE_CANDIDATES:
        try:
            if importlib.util.find_spec(module) is not None:
                return True
        except (ImportError, ValueError):
            continue
    return False


def _is_present(value: Any) -> bool:
    """Whether a configuration value was actually supplied.

    A blank or whitespace-only string counts as absent, matching how the rest of the config
    layer treats an unset variable; an empty list or dict does not, because writing one is a
    deliberate statement that there are no providers.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _parse_entries(raw: Any, origin: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parse the payload into a list of entry dicts.

    ``raw`` may already be a list or dict rather than a JSON string. Providers in the
    ``config_providers`` chain are typed ``-> Any``, and the AWS Secrets Manager provider in
    particular ``json.loads`` its whole secret, so a registry stored as nested JSON — the
    natural way to write one in a secrets manager — arrives already parsed. Treating that as
    "not a string, therefore not configured" silently ignored the operator's entire
    configuration.
    """
    if isinstance(raw, (list, dict)):
        parsed: Any = raw
    else:
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError) as exc:
            return [], [f"{origin}: could not be parsed as JSON ({exc})"]

    if isinstance(parsed, dict):
        # Tolerate {"providers": [...]}, which is what most people write first.
        parsed = parsed.get("providers", parsed)
    if not isinstance(parsed, list):
        return [], [f"{origin}: expected a JSON array of provider objects"]

    entries = []
    errors = []
    for index, entry in enumerate(parsed):
        if isinstance(entry, dict):
            entries.append(entry)
        else:
            errors.append(f"{origin}: provider[{index}] is not an object")
    return entries, errors


def _legacy_entry(app_config: Any) -> Dict[str, Any]:
    """Describe the flat ``OIDC_*`` configuration as a single registry entry.

    The policy values are the behaviour the plugin has today, stated explicitly: users are
    created on first login, groups are re-read from the claim on every login, and that claim
    replaces local membership.
    """
    return {
        "id": DEFAULT_PROVIDER_ID,
        "type": "oidc",
        "display_name": getattr(app_config, "OIDC_PROVIDER_DISPLAY_NAME", "") or DEFAULT_PROVIDER_ID,
        "provisioning": "jit",
        "group_sync": "every_login",
        "group_sync_mode": "authoritative",
        "admin_source": "claims",
        "identity_binding": "subject",
        # The set the synthesised provider is built with below — the whole asymmetric set, which
        # is what validation accepted before it became per-provider.
        "allowed_algorithms": list(ASYMMETRIC_ALGORITHMS),
        "audience": getattr(app_config, "OIDC_AUDIENCE", None),
        "issuer": getattr(app_config, "OIDC_ISSUER", None),
        "discovery_url": getattr(app_config, "OIDC_DISCOVERY_URL", None),
        "client_id": getattr(app_config, "OIDC_CLIENT_ID", None),
    }


def _reject_duplicate_issuers(providers: List[ProviderConfig]) -> Tuple[List[ProviderConfig], List[str]]:
    """Drop every provider after the first that claims a given issuer.

    Token validation selects a provider by exact ``iss`` match and takes the first hit, so two
    entries claiming one issuer means the second's policy — its audience, its binding, its group
    rules — is never applied, and no error says so. Rejecting the later entries makes the
    collision visible instead of resolving it by configuration order.
    """
    kept: List[ProviderConfig] = []
    errors: List[str] = []
    seen: Dict[str, str] = {}
    for provider in providers:
        if provider.issuer and provider.issuer in seen:
            errors.append(
                f"provider '{provider.id}': issuer {provider.issuer!r} is already claimed by provider '{seen[provider.issuer]}'; "
                "a token can only be validated under one policy, so the later entry is ignored"
            )
            continue
        if provider.issuer:
            seen[provider.issuer] = provider.id
        kept.append(provider)
    return kept, errors


def build_provider_registry(config_manager: Any, app_config: Any) -> RegistryLoadResult:
    """Build the provider registry from configuration.

    Resolution order: ``AUTH_PROVIDERS`` (inline JSON), then ``AUTH_PROVIDERS_FILE``, then the
    legacy flat variables. Both registry sources are read through ``config_manager`` so a
    secrets manager can supply them.

    Parameters:
        config_manager: The chain used to resolve configuration keys.
        app_config: The partially built :class:`~mlflow_oidc_auth.config.AppConfig`, read for
            the flat ``OIDC_*`` values when synthesising the legacy provider.

    Returns:
        RegistryLoadResult: Valid providers, plus a reason for every rejection.
    """
    raw = config_manager.get("AUTH_PROVIDERS")
    source = "env"
    origin = "AUTH_PROVIDERS"

    if _is_present(raw) and not isinstance(raw, (str, list, dict)):
        # Configured, but as something no reading of it can turn into providers. Say so rather
        # than falling through to legacy as though it had never been set.
        return RegistryLoadResult(
            providers=_legacy_providers(app_config),
            errors=[
                f"{origin}: expected a JSON array (or an already-parsed list) but got {type(raw).__name__}; " "falling back to the legacy OIDC_* configuration"
            ],
            source="legacy",
        )

    if not _is_present(raw):
        path = config_manager.get("AUTH_PROVIDERS_FILE")
        if isinstance(path, str) and path.strip():
            source = "file"
            origin = f"AUTH_PROVIDERS_FILE ({path})"
            try:
                with open(os.path.expanduser(path.strip()), "r", encoding="utf-8") as handle:
                    raw = handle.read()
            except OSError as exc:
                # Fall back to legacy rather than leaving the deployment with no providers at
                # all: an unreadable file is an operator error, not a reason to lock everyone
                # out of a working installation.
                return RegistryLoadResult(
                    providers=_legacy_providers(app_config),
                    errors=[f"{origin}: could not be read ({exc}); falling back to the legacy OIDC_* configuration"],
                    source="legacy",
                )
        else:
            return RegistryLoadResult(providers=_legacy_providers(app_config), errors=[], source="legacy")

    entries, errors = _parse_entries(raw, origin)
    if not entries and errors:
        # Malformed payload: keep the legacy provider working rather than silently ending up
        # with an empty registry, and report why.
        return RegistryLoadResult(
            providers=_legacy_providers(app_config),
            errors=errors + [f"{origin}: falling back to the legacy OIDC_* configuration"],
            source="legacy",
        )

    providers: List[ProviderConfig] = []
    seen_ids: set = set()
    duplicate_ids: set = set()

    # First pass records ids so a duplicate can reject *both* copies rather than keeping
    # whichever happened to be written first.
    id_counts: Dict[str, int] = {}
    for entry in entries:
        entry_id = entry.get("id")
        if isinstance(entry_id, str) and entry_id.strip():
            id_counts[entry_id.strip()] = id_counts.get(entry_id.strip(), 0) + 1
    duplicate_ids = {entry_id for entry_id, count in id_counts.items() if count > 1}

    for index, entry in enumerate(entries):
        entry_id = entry.get("id")
        if isinstance(entry_id, str) and entry_id.strip() in duplicate_ids:
            if entry_id.strip() not in seen_ids:
                errors.append(f"provider '{entry_id.strip()}': duplicate id; every entry using it is ignored")
                seen_ids.add(entry_id.strip())
            continue
        provider, entry_errors = _validate(entry, index, seen_ids)
        if provider is None:
            errors.extend(entry_errors)
            continue
        seen_ids.add(provider.id)
        providers.append(provider)

    providers, issuer_errors = _reject_duplicate_issuers(providers)
    errors.extend(issuer_errors)

    return RegistryLoadResult(providers=providers, errors=errors, source=source)


def _legacy_providers(app_config: Any) -> List[ProviderConfig]:
    """The single ``default`` provider synthesised from the flat ``OIDC_*`` variables.

    Built directly rather than run through :func:`_validate`, and the difference is deliberate:
    ``audience`` is **required of an explicitly configured entry but not of this one**.

    ``OIDC_AUDIENCE`` is optional today, and a deployment that leaves it unset performs no
    audience check — that is the current behaviour, whatever one thinks of it. Holding the
    synthesised provider to the stricter rule would produce an empty registry for most existing
    installations, which is precisely the back-compat break this synthesis exists to prevent.

    New configuration is held to the higher standard; existing configuration is described
    faithfully, including where it is weak. Tightening it is a behaviour change and belongs
    with whichever task first consumes the registry, not here.
    """
    entry = _legacy_entry(app_config)
    audience = entry.get("audience")
    if not (isinstance(audience, str) and audience.strip()):
        logger.debug(
            "OIDC_AUDIENCE is not set, so the synthesised 'default' provider carries no audience — matching today's behaviour, "
            "in which no audience check is performed."
        )
    return [
        ProviderConfig(
            id=DEFAULT_PROVIDER_ID,
            type="oidc",
            display_name=entry["display_name"],
            provisioning="jit",
            group_sync="every_login",
            group_sync_mode="authoritative",
            admin_source="claims",
            identity_binding="subject",
            # The full asymmetric set, not DEFAULT_ALGORITHMS. Before the registry existed, token
            # validation accepted every asymmetric algorithm, so a deployment whose IdP signs with
            # ES256 or RS512 — Auth0, several Okta and Keycloak configurations, Kubernetes — is
            # working today. Narrowing that here would lock them out on upgrade with no
            # configuration change of their own, which is the one thing the synthesised entry
            # exists to prevent. An *explicitly* configured entry still defaults to RS256: there
            # the operator is writing the policy, and can widen it deliberately.
            allowed_algorithms=ASYMMETRIC_ALGORITHMS,
            audience=audience.strip() if isinstance(audience, str) and audience.strip() else None,
            issuer=entry["issuer"],
            discovery_url=entry["discovery_url"],
            client_id=entry["client_id"],
        )
    ]
