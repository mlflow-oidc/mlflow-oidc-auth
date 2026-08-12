"""Who may write a row that another source owns (issue #319).

``managed_by`` (#311) records which source a user row belongs to — ``manual``, ``scim``, or
``oidc:<provider>``. Per-provider policy (#318) is a promise about what each source *should* do;
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
from typing import Optional

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: Row owner meaning "no external source claims this" — a hand-created account, or one whose
#: source was turned off. Always writable.
MANUAL = "manual"


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


def evaluate_write(current_owner: Optional[str], writer: Optional[str], *, enforcement: Enforcement, admin_override: bool = False) -> OwnershipDecision:
    """Decide whether ``writer`` may write a row owned by ``current_owner``.

    Parameters:
        current_owner: The row's ``managed_by``. None or ``manual`` means unowned.
        writer: The source attempting the write. None means an unattributed internal write, which
            is treated as manual.
        enforcement: The configured mode.
        admin_override: Whether an administrator asked for this explicitly.

    Returns:
        OwnershipDecision: ``allowed`` says whether to proceed; ``conflict`` says whether it
        crossed ownership, which is what ``report`` mode exists to count.
    """
    writer = writer or MANUAL
    owner = current_owner or MANUAL

    if owner == writer or owner == MANUAL:
        # Nothing owns it, or the same source owns it. The overwhelmingly common case, and it is
        # deliberately not audited: a guard that logs every ordinary write teaches operators to
        # ignore it.
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
