"""Resolve an external identity to a local user (issue #309).

``users.username`` is the only identity key today, so with more than one provider configured two
IdPs asserting the same email would silently share an account. This module decides, for a given
``(provider_id, subject, claims)``, whether an existing user is reached, a new one should be
created, or the attempt is refused.

**Nothing calls this yet.** Wiring it into login and bearer authentication is #316; this lands
the decision and its tests.

The rule that matters:

``identity_binding: subject``
    Only ``(provider_id, sub)`` reaches a user. A claim asserting somebody else's email cannot
    link to their account, because email is never consulted.

``identity_binding: email``
    May link to an existing user by email, but only when the email's domain is in the provider's
    ``allowed_email_domains``. A provider is trusted to speak for the domains an operator listed
    and no others — otherwise any IdP able to assert ``admin@yourcompany.com`` would take over
    that account.

Both modes refuse to move an identity that is already bound to a different user. Once
``(provider_id, subject)`` names a user, only that user answers to it.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.provider_registry import ProviderConfig
from mlflow_oidc_auth.repository.user import normalize_username

logger = get_logger()


class Resolution(Enum):
    """What the caller should do with the identity it presented."""

    MATCHED = "matched"
    """An existing user answers to this identity."""

    LINK = "link"
    """An existing user was reached by policy; bind the identity to them before use."""

    CREATE = "create"
    """No user matched. Create one, subject to the provider's provisioning policy."""

    REFUSED = "refused"
    """Policy forbids reaching any user this way. Never fall through to create."""


@dataclass(frozen=True)
class IdentityDecision:
    """The outcome of resolving one identity.

    Attributes:
        resolution: What to do next.
        username: The user reached, for ``MATCHED`` and ``LINK``. None otherwise — in
            particular it is None for ``REFUSED``, so a caller that ignores ``resolution`` and
            reads ``username`` gets nothing rather than the account it was refused.
        reason: Why, for logs and audit. Always set for ``REFUSED``.
    """

    resolution: Resolution
    username: Optional[str] = None
    reason: str = ""

    @property
    def is_allowed(self) -> bool:
        """Whether the caller may proceed to authenticate this principal."""
        return self.resolution is not Resolution.REFUSED


def _email_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    """Pull a usable email out of the claims, normalised.

    Only the ``email`` claim is consulted. Accepting alternatives such as ``upn`` or
    ``preferred_username`` here would widen what a provider can assert about a person's identity
    beyond the one claim operators expect to be checked against ``allowed_email_domains``.
    """
    email = claims.get("email")
    if not isinstance(email, str):
        return None
    email = email.strip().lower()
    return email or None


def _domain_of(email: str) -> Optional[str]:
    """Return the domain part of ``email``, or None when it is not a single usable address.

    Rejecting anything but exactly one ``@`` is deliberate: ``a@b@evil.com`` splits differently
    depending on which end you parse from, and a mismatch between this check and whatever reads
    the address later is how a domain allowlist gets bypassed.

    Both halves must be non-empty. ``@example.com`` has an authorised-looking domain and no
    local part, so accepting it would let a provider claim an account named for the bare
    domain — the check has to be about the whole address, not just the half being compared.
    """
    if email.count("@") != 1:
        return None
    local, domain = email.split("@", 1)
    if not local.strip() or not domain.strip():
        return None
    return domain.strip()


def resolve_identity(
    provider: ProviderConfig,
    subject: str,
    claims: Dict[str, Any],
    identity_repo,
    user_lookup,
) -> IdentityDecision:
    """Decide which local user, if any, an external identity reaches.

    Parameters:
        provider: The asserting provider's registry entry, which carries the binding policy.
        subject: The provider's stable identifier for the principal (``sub``).
        claims: The validated token or userinfo claims.
        identity_repo: A :class:`~mlflow_oidc_auth.repository.user_identity.UserIdentityRepository`.
        user_lookup: Callable ``(username) -> bool`` answering whether a local user exists.
            Injected rather than taken from the store singleton so this stays a pure decision
            that tests can drive without a database.

    Returns:
        IdentityDecision: What the caller should do. Check ``resolution`` — never read
        ``username`` alone.
    """
    if not isinstance(subject, str) or not subject.strip():
        return _refuse(provider, subject, "the provider asserted no subject")
    subject = subject.strip()

    # An identity that already exists wins outright, before any claim is consulted. This is what
    # makes a second provider unable to talk its way into an account that is already bound.
    existing = identity_repo.get_username_by_identity(provider.id, subject)
    if existing:
        return IdentityDecision(Resolution.MATCHED, username=existing, reason="identity already bound")

    if provider.identity_binding == "email":
        return _resolve_by_email(provider, subject, claims, identity_repo, user_lookup)

    # subject binding: an unknown (provider, subject) is a new principal, full stop. It is never
    # matched to an existing user by anything the token says about them.
    return IdentityDecision(Resolution.CREATE, reason="no identity bound for this provider and subject")


def _resolve_by_email(
    provider: ProviderConfig,
    subject: str,
    claims: Dict[str, Any],
    identity_repo,
    user_lookup,
) -> IdentityDecision:
    """Link by email, but only within the domains this provider is trusted for."""
    email = _email_from_claims(claims)
    if not email:
        return _refuse(provider, subject, "identity_binding is 'email' but the claims carry no usable email")

    domain = _domain_of(email)
    if not domain:
        return _refuse(provider, subject, f"email {email!r} is not a single address")

    # Compared case-insensitively; the configured list is already stripped by the registry.
    allowed = {allowed_domain.lower() for allowed_domain in provider.allowed_email_domains}
    if domain not in allowed:
        # Not merely "no match" — refused. Falling through to create would hand the caller an
        # account for a domain the operator never authorised this provider to speak for.
        return _refuse(provider, subject, f"provider is not authorised for email domain {domain!r}")

    username = normalize_username(email)
    if not user_lookup(username):
        return IdentityDecision(Resolution.CREATE, reason="no local user for this authorised email")

    # The user exists and the provider may speak for the domain — but if some *other* provider
    # already owns this account, linking would let this one inherit it. Refuse instead.
    bound_providers = identity_repo.list_providers_for_username(username)
    foreign = [bound for bound in bound_providers if bound != provider.id]
    if foreign:
        return _refuse(
            provider,
            subject,
            f"user is already bound to provider(s) {', '.join(sorted(foreign))}; refusing to link a second provider by email",
        )

    return IdentityDecision(Resolution.LINK, username=username, reason="authorised email domain, no competing provider")


def _refuse(provider: ProviderConfig, subject: Any, reason: str) -> IdentityDecision:
    """Build a refusal, and record it.

    Refusals are audited rather than only logged: each one is a provider failing to reach an
    account it asked for, which is exactly the signal an operator investigating a suspected
    takeover attempt needs. ``subject`` is included; claim contents are not.
    """
    logger.warning("Identity refused for provider %s: %s", provider.id, reason)
    emit_audit_event(
        "identity.refused",
        actor=str(subject),
        resource_type="identity_provider",
        resource_id=provider.id,
        detail={"reason": reason},
        status="denied",
    )
    return IdentityDecision(Resolution.REFUSED, username=None, reason=reason)
