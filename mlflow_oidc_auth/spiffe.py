"""SPIFFE JWT-SVID workload identities."""

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Tuple
from urllib.parse import urlsplit


TRUST_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._~-]+$")
MAX_TRUST_DOMAIN_LENGTH = 255


class SpiffeIdError(Exception):
    """A subject that is not a well-formed SPIFFE ID."""


class SpiffeTrustDomainError(SpiffeIdError):
    """A well-formed SPIFFE ID from a different trust domain."""


@dataclass(frozen=True)
class SpiffeIdentity:
    """A validated SPIFFE workload identity."""

    spiffe_id: str
    trust_domain: str
    path: str

    @property
    def username(self) -> str:
        """Return the provider-independent, collision-resistant local username."""
        digest = hashlib.sha256(self.spiffe_id.encode("utf-8")).hexdigest()
        return f"workload.{digest}@spiffe.local"


def valid_trust_domain(value: Any) -> bool:
    """Whether ``value`` is a canonical SPIFFE trust domain."""
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= MAX_TRUST_DOMAIN_LENGTH
        and bool(TRUST_DOMAIN.fullmatch(value))
        and ".." not in value
    )


def parse_spiffe_id(subject: Any, expected_trust_domain: str | None = None) -> SpiffeIdentity:
    """Parse ``subject`` as an exact, non-normalized SPIFFE ID.

    Parameters:
        subject: The JWT-SVID ``sub`` claim.
        expected_trust_domain: Optional trust domain that must match exactly.

    Raises:
        SpiffeIdError: If the subject is not a well-formed SPIFFE ID.
        SpiffeTrustDomainError: If its trust domain does not match.
    """
    if not isinstance(subject, str) or not subject:
        raise SpiffeIdError("SPIFFE ID must be a non-empty string")
    if not subject.startswith("spiffe://"):
        raise SpiffeIdError("SPIFFE ID scheme must be exactly 'spiffe'")

    try:
        parsed = urlsplit(subject)
        port = parsed.port
    except ValueError as exc:
        raise SpiffeIdError("SPIFFE ID authority is malformed") from exc

    if parsed.scheme != "spiffe" or not parsed.netloc:
        raise SpiffeIdError("SPIFFE ID must contain a trust domain")
    if parsed.username is not None or parsed.password is not None or port is not None:
        raise SpiffeIdError("SPIFFE ID must not contain userinfo or a port")
    if parsed.query or parsed.fragment:
        raise SpiffeIdError("SPIFFE ID must not contain a query or fragment")
    if not valid_trust_domain(parsed.netloc):
        raise SpiffeIdError("SPIFFE ID trust domain is malformed")
    if expected_trust_domain is not None and parsed.netloc != expected_trust_domain:
        raise SpiffeTrustDomainError("SPIFFE ID trust domain does not match the provider")

    path = parsed.path
    if path:
        if not path.startswith("/") or path.endswith("/"):
            raise SpiffeIdError("SPIFFE ID path must be absolute and must not end with '/'")
        segments = path[1:].split("/")
        if any(not segment or segment in (".", "..") or not PATH_SEGMENT.fullmatch(segment) for segment in segments):
            raise SpiffeIdError("SPIFFE ID path contains an invalid segment")

    return SpiffeIdentity(spiffe_id=subject, trust_domain=parsed.netloc, path=path)


def validate_spiffe_allowlist(values: Tuple[str, ...], trust_domain: str) -> list[str]:
    """Return errors for allowlist entries that can never match this provider."""
    errors = []
    for value in values:
        try:
            parse_spiffe_id(value, trust_domain)
        except SpiffeIdError as exc:
            errors.append(f"SPIFFE ID allowlist entry {value!r} is invalid: {exc}")
    return errors


def spiffe_id_is_allowed(spiffe_id: str, allowlist: Tuple[str, ...]) -> bool:
    """Check exact membership without normalizing the SPIFFE path."""
    return spiffe_id in allowlist
