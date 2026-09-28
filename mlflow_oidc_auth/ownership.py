"""Who may write a row that another source owns (issue #319).

``managed_by`` (#311) records which source a user row belongs to — ``manual``, ``scim``, or
``oidc:<provider>``. Since #360 each group membership (``user_groups.managed_by``) records its
own owner too, and membership removal, user deletion and user creation go through the same guard
(see :mod:`mlflow_oidc_auth.repository.group` and ``UserRepository.create`` / ``delete``). Per-provider policy (#318) is a promise about what each source *should* do;
this is what stops one source silently overwriting another's row when it does something else.

**Staged, because the failure mode is lockout.** A guard that refuses writes cannot be recovered
from inside the system once it has refused the write that would have fixed it — and a
directory sync that suddenly stops updating the accounts it has always updated is the same
outage from the other direction. So enforcement has three states and defaults to the middle one:

``off``
    No evaluation. What a deployment that has never heard of this gets.

``report``
    The guard evaluates and records what it *would* have refused, and changes nothing. The
    default, so the telemetry ships a release before the enforcement does and an operator can
    look at real traffic before turning it on.

``enforce``
    The refusal is real.

**The break-glass rule.** An explicit administrator action is always permitted, in every mode,
and is always audited: ``PATCH /api/2.0/mlflow/users/ownership`` hands a row to another source,
and ``mlflow-oidc db reconcile-ownership`` does it in bulk. A guard whose only recovery needs
database access has produced the state it exists to prevent.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: Row owner meaning "no external source claims this" — a hand-created account, or one whose
#: source was turned off. Writable by any source, with one exception: a directory may not touch a
#: hand-made *administrator* (see :func:`evaluate_write`).
MANUAL = "manual"

#: The directory source (SCIM, #322).
SCIM = "scim"

#: Every owner a source presents. The break-glass paths (``PATCH /users/ownership``,
#: ``reconcile-ownership``) refuse anything else: under ``enforce`` an owner no source presents
#: conflicts with every writer forever.
OWNER_PATTERN = r"manual|scim|(?:oidc|saml):[A-Za-z0-9._-]+"

#: Writers that are identity providers performing a login, as ``<kind>:<provider-id>``.
LOGIN_SOURCE_PREFIXES = ("oidc:", "saml:")

#: Fields a login may change on a row the directory owns. Only ``is_admin``, and only because the
#: login path writes it solely for a provider whose ``admin_source`` is ``claims`` (#318) — the
#: admin decision is the provider's by explicit policy, and a directory never confers admin.
#: Display name and group membership are not ``users``-row writes and are governed by the
#: provider's ``group_sync`` policy instead. ``managed_by``, ``active``, the credential and the
#: service-account flag are never login-writable.
LOGIN_WRITABLE_FIELDS = frozenset({"is_admin"})


def is_login_source(writer: Optional[str]) -> bool:
    """Whether ``writer`` names an identity provider performing a login."""
    return isinstance(writer, str) and writer.startswith(LOGIN_SOURCE_PREFIXES)


class Enforcement(str, Enum):
    """How seriously a cross-source write is taken."""

    OFF = "off"
    REPORT = "report"
    ENFORCE = "enforce"


@dataclass(frozen=True)
class OwnershipDecision:
    """Whether a write may proceed, and what to say about it.

    Attributes:
        allowed: Whether the caller may write.
        conflict: Whether the write crosses ownership — true even when ``allowed`` is, which is
            exactly the ``report`` case worth counting.
        reason: Human-readable explanation. Empty when there is nothing to say.
        owner: The row's current owner, when there is a conflict.
    """

    allowed: bool
    conflict: bool = False
    reason: str = ""
    owner: Optional[str] = None


def parse_enforcement(value) -> Enforcement:
    """Read the configured enforcement mode, defaulting to ``report``.

    An unrecognised value reports rather than enforces: getting this wrong should not be the
    thing that starts refusing writes.
    """
    if value is None:
        return Enforcement.REPORT
    try:
        return Enforcement(str(value).strip().lower())
    except ValueError:
        logger.warning("Unrecognised MANAGED_BY_ENFORCEMENT %r; using 'report'. Expected one of: off, report, enforce.", value)
        return Enforcement.REPORT


def evaluate_write(
    current_owner: Optional[str],
    writer: Optional[str],
    *,
    enforcement: Enforcement,
    admin_override: bool = False,
    fields: Optional[Iterable[str]] = None,
    target_is_admin: bool = False,
) -> OwnershipDecision:
    """Decide whether ``writer`` may write a row owned by ``current_owner``.

    Rules, in order:

    1. A source may always write its own rows.
    2. **Login allowance.** An identity provider (``oidc:*`` / ``saml:*``) logging a user in may
       write a ``scim``-owned row when every field it *changes* is in
       :data:`LOGIN_WRITABLE_FIELDS`. Login is not an ownership change; refusing it would lock
       every directory-provisioned user out of SSO under ``enforce``. Needs ``fields``: when the
       caller does not say what changes, the allowance does not apply.
    3. A ``manual`` row is writable by anyone — except that the directory may not write a
       hand-made administrator. A directory that could modify, deactivate or claim the break-glass
       admin an operator created by hand would make that account only as safe as the SCIM token.
    4. An administrator override is always permitted, and always recorded.
    5. Otherwise the configured enforcement decides.

    Parameters:
        current_owner: The row's ``managed_by``. None or ``manual`` means unowned.
        writer: The source attempting the write. None means an unattributed internal write, which
            is treated as manual.
        enforcement: The configured mode.
        admin_override: Whether an administrator asked for this explicitly.
        fields: The fields this write actually changes, when known.
        target_is_admin: Whether the row is currently an administrator.

    Returns:
        OwnershipDecision: ``allowed`` says whether to proceed; ``conflict`` says whether it
        crossed ownership, which is what ``report`` mode exists to count.
    """
    writer = writer or MANUAL
    owner = current_owner or MANUAL

    if owner == writer:
        # The same source owns it. The overwhelmingly common case, and it is deliberately not
        # audited: a guard that logs every ordinary write teaches operators to ignore it.
        return OwnershipDecision(allowed=True)

    if owner == SCIM and is_login_source(writer) and fields is not None and set(fields) <= LOGIN_WRITABLE_FIELDS:
        return OwnershipDecision(allowed=True)

    if owner == MANUAL and not (writer == SCIM and target_is_admin):
        # Nothing owns it.
        return OwnershipDecision(allowed=True)

    if admin_override:
        # Break glass. Always permitted, always recorded — an operator who cannot repair
        # ownership from the admin UI is left with the database, which is how a guard turns into
        # an outage.
        return OwnershipDecision(
            allowed=True,
            conflict=True,
            owner=owner,
            reason=f"administrator override: writing a row owned by {owner!r} as {writer!r}",
        )

    if owner == MANUAL:
        reason = f"{writer!r} may not write a hand-made administrator"
    else:
        reason = f"{writer!r} may not write a row owned by {owner!r}"
    # ``==`` rather than ``is``: ``Enforcement`` is a str-Enum, so a caller holding the raw
    # configured string — a plugin, a config reload, a test helper mirroring the environment —
    # would miss both identity checks and fall through to "allowed", leaving the guard silently
    # off while every log line said ``enforce``.
    if enforcement == Enforcement.ENFORCE:
        return OwnershipDecision(allowed=False, conflict=True, owner=owner, reason=reason)

    if enforcement == Enforcement.OFF:
        return OwnershipDecision(allowed=True)

    # Anything else reports, including a value that is neither of the three: an unreadable
    # setting must not be the thing that turns the guard off.
    return OwnershipDecision(allowed=True, conflict=True, owner=owner, reason=f"{reason} (report mode: permitted, and recorded)")


def evaluate_group_delete(
    membership_owner: Optional[str],
    writer: Optional[str],
    *,
    enforcement: Enforcement,
    admin_override: bool = False,
) -> OwnershipDecision:
    """Decide whether ``writer`` may delete a group that holds a membership owned by ``membership_owner``.

    Stricter than :func:`evaluate_write` in one respect: a ``manual`` membership counts as owned.
    Removing one membership row is a revocation any source may make of an unowned grant; deleting the
    group takes the group away from every member *and* drops every permission granted to it, so a
    directory deleting a group that an administrator or a login also populates is deleting
    something that is not only its own (#323). The three enforcement states and the override apply
    as everywhere else.

    Parameters:
        membership_owner: ``managed_by`` of one of the group's membership rows.
        writer: The source deleting the group.
        enforcement: The configured mode.
        admin_override: Whether an administrator asked for this explicitly.

    Returns:
        OwnershipDecision: As for :func:`evaluate_write`.
    """
    return _evaluate_strict(membership_owner, writer, enforcement, admin_override, "delete a group holding memberships owned by")


def _evaluate_strict(owner: Optional[str], writer: Optional[str], enforcement: Enforcement, admin_override: bool, action: str) -> OwnershipDecision:
    """Only the owner writes without a conflict; ``manual`` counts as owned. Modes as usual."""
    writer = writer or MANUAL
    owner = owner or MANUAL
    if owner == writer:
        return OwnershipDecision(allowed=True)
    if admin_override:
        return OwnershipDecision(allowed=True, conflict=True, owner=owner, reason=f"administrator override: {writer!r} may {action} {owner!r}")
    reason = f"{writer!r} may not {action} {owner!r}"
    if enforcement == Enforcement.ENFORCE:
        return OwnershipDecision(allowed=False, conflict=True, owner=owner, reason=reason)
    if enforcement == Enforcement.OFF:
        return OwnershipDecision(allowed=True)
    return OwnershipDecision(allowed=True, conflict=True, owner=owner, reason=f"{reason} (report mode: permitted, and recorded)")


def evaluate_group_write(
    group_owner: Optional[str],
    writer: Optional[str],
    *,
    enforcement: Enforcement,
    admin_override: bool = False,
) -> OwnershipDecision:
    """Decide whether ``writer`` may write a *group* — its membership, its external id, or the
    group itself — owned by ``group_owner`` (``groups.managed_by``).

    Deny by default, stricter than :func:`evaluate_write`: only the owning source writes without a
    conflict. A ``manual`` group is an administrator's (or predates ownership), and group names are
    the permission boundary, so a directory putting users into it, or deleting it, is a write to
    something it does not own. Adding a user to a group is how a group's grants reach them, so this
    is what keeps a SCIM token out of a login-derived or Kubernetes namespace group under ``enforce``.

    Parameters:
        group_owner: The group's ``managed_by``. None means ``manual``.
        writer: The source writing.
        enforcement: The configured mode.
        admin_override: Whether an administrator asked for this explicitly.

    Returns:
        OwnershipDecision: As for :func:`evaluate_write`.
    """
    return _evaluate_strict(group_owner, writer, enforcement, admin_override, "write a group owned by")
