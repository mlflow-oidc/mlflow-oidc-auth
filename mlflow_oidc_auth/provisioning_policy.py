"""Per-provider provisioning and group-sync policy (issue #318).

Three decisions used to be made the same way for everyone, from deployment-wide configuration:
who may become a user, whose group membership wins, and who may be an administrator. With one
identity provider that is a reasonable simplification. With two it is a vulnerability — a second
provider asserting ``email: alice@corp.com`` would reach Alice's account, and a tenant emitting a
group named like the admin group would confer administrator rights across the deployment.

Each decision now comes from the registry entry of the provider that actually asserted the
identity:

``provisioning``
    ``jit`` creates a user on first login. ``scim`` and ``none`` never create: an unknown user is
    refused with a message saying so, which is the enterprise gate where app assignment in the
    directory is what controls access.

``group_sync`` / ``group_sync_mode``
    Whether claims refresh group membership, and whether they *replace* it. ``authoritative``
    genuinely removes memberships the claims no longer assert — Keycloak's ``FORCE`` mapper is
    add-only in practice ([keycloak#36578](https://github.com/keycloak/keycloak/issues/36578)),
    so a deployment that expects revocation to propagate has to get it from here.

``admin_source``
    ``claims`` reads the admin group from the token as before; ``none`` means this provider can
    never confer administrator rights, whatever it asserts. The admin group name itself stays
    server-side configuration and is never SCIM-writable.

The ``default`` provider's defaults are today's behaviour exactly — ``jit``, ``every_login``,
``authoritative``, ``claims`` — so a deployment that changes no configuration sees no change.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

from mlflow_oidc_auth.identity_resolution import IdentityDecision, Resolution, _domain_of
from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


@dataclass(frozen=True)
class ProvisioningOutcome:
    """What the caller may do with a resolved identity.

    Attributes:
        allowed: Whether the login may proceed at all.
        create: Whether a user record must be created first.
        username: The local username, when allowed.
        reason: Why, for logs and audit. Always set when refused.
    """

    allowed: bool
    create: bool = False
    username: Optional[str] = None
    reason: str = ""


def apply_provisioning_policy(
    provider,
    decision: IdentityDecision,
    *,
    derived_username: Optional[str],
    user_exists,
    providers_bound_to=None,
    providers_in_domain: Optional[Callable[[str], Iterable[str]]] = None,
) -> ProvisioningOutcome:
    """Turn an identity decision into a provisioning decision for ``provider``.

    Parameters:
        provider: The registry entry of the provider that asserted the identity.
        decision: What :func:`~mlflow_oidc_auth.identity_resolution.resolve_identity` decided.
        derived_username: The username the deployment's configured claim fields produce.
        user_exists: Callable ``(username) -> bool``.
        providers_bound_to: Callable ``(username) -> list[str]`` naming the providers already
            bound to that user. Used to tell "this account is mine, from before identities were
            recorded" from "this account belongs to somebody else".
        providers_in_domain: Callable ``(domain) -> iterable of provider ids`` naming the providers
            whose identities own accounts in an email domain (an unbound account counts as
            ``default``'s). Used to keep a provider other than ``default`` from creating an account
            in a domain whose accounts belong to another provider — see :func:`_squats_a_domain`.

    Returns:
        ProvisioningOutcome: Check ``allowed`` before anything else.
    """
    if not decision.is_allowed:
        return ProvisioningOutcome(allowed=False, reason=decision.reason or "identity refused")

    if decision.resolution in (Resolution.MATCHED, Resolution.LINK):
        return ProvisioningOutcome(allowed=True, create=False, username=decision.username, reason=decision.reason)

    # CREATE. Two things have to be true: the provider may create users at all, and the name it
    # would create is not already someone else's.
    if not derived_username:
        return ProvisioningOutcome(allowed=False, reason="no username could be derived from the provider's claims")

    if user_exists(derived_username):
        bound_to = list(providers_bound_to(derived_username)) if providers_bound_to else []
        foreign = [bound for bound in bound_to if bound != provider.id]

        if not foreign and provider.id == DEFAULT_PROVIDER_ID:
            # The account predates identity records, or its only binding is this provider's own.
            #
            # This is every user of every deployment that upgrades: the Phase 0 backfill wrote
            # ``subject = username`` because that was all it had, and a real ``sub`` is not a
            # username — so the first login after upgrading resolves to CREATE, finds the name
            # taken, and without this would refuse *every existing user, including every
            # administrator*, with no way back that does not involve the database.
            #
            # Adoption is safe precisely here and nowhere else: this is the deployment's own
            # provider, the one that named the account in the first place.
            return ProvisioningOutcome(allowed=True, create=False, username=derived_username, reason="adopting an account from before identities were recorded")

        # The name is taken by someone another provider owns. Under subject binding this is the
        # cross-provider takeover: a second provider asserting an existing user's email or
        # preferred_username would otherwise be handed their account.
        return ProvisioningOutcome(
            allowed=False,
            reason=f"username {derived_username!r} already belongs to another identity; provider '{provider.id}' cannot claim it",
        )

    squatted = _squats_a_domain(provider, derived_username, providers_in_domain)
    if squatted:
        return ProvisioningOutcome(allowed=False, reason=squatted)

    if provider.provisioning != "jit":
        # The enterprise gate: the directory decides who exists, and login does not.
        return ProvisioningOutcome(
            allowed=False,
            reason=f"provider '{provider.id}' has provisioning '{provider.provisioning}', so an unknown user is not created at login",
        )

    return ProvisioningOutcome(allowed=True, create=True, username=derived_username, reason="new principal")


def local_group_name(provider, claimed: str) -> str:
    """The local group a provider's claimed group name maps to.

    Namespaced for every provider but the deployment's own. Group *names* are the permission
    boundary — ``set_user_groups`` joins by name and ``populate_groups`` creates whatever is
    missing — so an unnamespaced second provider could assert ``finance-ds`` and have its users
    join the local group of that name, inheriting every permission granted to it without any
    takeover or admin flag. Prefixing makes that impossible to say.

    The ``default`` provider keeps raw names: they are the names every existing deployment
    already has, and there is nothing to collide with.
    """
    if provider.id == DEFAULT_PROVIDER_ID:
        return claimed
    return f"{provider.id}:{claimed}"


def groups_to_apply(provider, claimed_groups: Sequence[str], current_groups: Optional[Sequence[str]], *, is_new_user: bool) -> Optional[List[str]]:
    """The group membership to write, or None to leave it alone.

    Parameters:
        provider: The asserting provider's registry entry.
        claimed_groups: Groups the token asserts.
        current_groups: Groups the user has locally.
        is_new_user: Whether this login just created the account.

    Returns:
        The full membership to store, or None when this provider does not touch groups.
    """
    if provider.group_sync == "none":
        return None
    if provider.group_sync == "first_login" and not is_new_user:
        return None

    claimed = [local_group_name(provider, group) for group in claimed_groups if group]
    if provider.group_sync_mode == "authoritative":
        # Replaces, which is the point: a membership the claims no longer assert is removed.
        return list(dict.fromkeys(claimed))

    # additive: never removes. For a deployment where some groups are managed elsewhere — SCIM,
    # or by hand — and the token only knows about its own.
    if current_groups is None:
        # The current membership could not be read. Writing the claimed set alone would *delete*
        # everything else, turning an additive sync into the destructive one it exists to avoid.
        logger.warning("Skipping additive group sync for provider '%s': current membership is unknown", provider.id)
        return None
    return list(dict.fromkeys([*current_groups, *claimed]))


def admin_from_claims(provider, claimed_groups: Sequence[str], admin_group_names: Sequence[str]) -> bool:
    """Whether this provider may confer administrator rights, and does.

    ``admin_source: none`` means no claim from this provider makes anyone an administrator —
    the answer for a partner or contractor tenant whose group names you do not control.
    """
    if provider.admin_source != "claims":
        return False
    return any(group in claimed_groups for group in admin_group_names)


def _squats_a_domain(provider, username: str, providers_in_domain) -> Optional[str]:
    """Why ``provider`` may not create ``username``, or None when it may.

    A provider other than ``default`` creating an account named by an email address would otherwise
    claim it for good — the account is bound to that provider's identity, and the address's real
    owner signing in later through their own provider is refused as a foreign account. So such a
    provider may not create an account in a domain whose existing accounts belong to another
    provider. Needs no configuration: a domain is another provider's because its accounts are.

    Always allowed: the ``default`` provider; a username that is not an email address (a
    Kubernetes service account, a workload name), so a provider without domains keeps working; a
    domain listed in the provider's own ``allowed_email_domains``; and a domain with no accounts
    yet, or only this provider's. Fails closed when the owners cannot be read.
    """
    if provider.id == DEFAULT_PROVIDER_ID or providers_in_domain is None or "@" not in (username or ""):
        return None
    domain = _domain_of(username.strip().lower())
    if not domain:
        return f"username {username!r} is not a single email address; provider '{provider.id}' cannot create it"
    if domain in {allowed.lower() for allowed in getattr(provider, "allowed_email_domains", ()) or ()}:
        return None
    try:
        owners = set(providers_in_domain(domain))
    except Exception as e:
        logger.warning("Could not read which providers own email domain %s: %s", domain, type(e).__name__)
        return f"could not check who owns email domain {domain!r}; provider '{provider.id}' cannot create {username!r}"
    foreign = owners - {provider.id}
    if foreign:
        return (
            f"email domain {domain!r} belongs to accounts of provider(s) {', '.join(sorted(foreign))}; provider '{provider.id}' cannot create "
            f"{username!r} there. List the domain in its allowed_email_domains to permit it"
        )
    return None
