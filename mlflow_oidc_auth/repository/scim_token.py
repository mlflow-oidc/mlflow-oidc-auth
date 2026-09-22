"""Issue, rotate, revoke and verify SCIM bearer tokens (issue #321).

Plaintext format: ``scim_<prefix>_<secret>``.

* ``prefix`` is 8 random hex characters. It is not secret: it is stored in clear so that
  :meth:`ScimTokenRepository.authenticate` can fetch the one candidate row by index and verify a
  single hash, rather than hashing the presented value against every token on every request.
* ``secret`` is ``secrets.token_urlsafe(32)`` — 256 bits.

Only a Werkzeug hash of the full plaintext is stored, using the same method as user tokens
(:data:`mlflow_oidc_auth.repository.user.TOKEN_HASH_METHOD`). That method is a deliberately
cheap PBKDF2 because the input is a high-entropy random value, not a human password; the
justification recorded next to the constant applies here with more margin (256 bits against
143). ``check_password_hash`` compares in constant time.

The plaintext is returned exactly once, from :meth:`create` and :meth:`rotate`, and never again.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional, Tuple

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from mlflow_oidc_auth.db.models import SqlScimToken
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.repository.user import TOKEN_HASH_METHOD

logger = get_logger()

TOKEN_SCHEME = "scim"
PREFIX_LENGTH = 8

#: ``last_used_at`` is refreshed at most this often per token. Writing it on every request would
#: turn every SCIM read into a write; to the minute is all an operator needs to tell a live token
#: from a forgotten one.
LAST_USED_RESOLUTION_SECONDS = 60


def _now() -> datetime:
    """Naive UTC, matching how every other timestamp in this schema is stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


@dataclass(frozen=True)
class ScimTokenRecord:
    """A SCIM token as the rest of the system sees it. Deliberately carries no hash."""

    id: int
    name: str
    token_prefix: str
    created_at: Optional[datetime]
    created_by: Optional[str]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]

    def is_live(self, now: Optional[datetime] = None) -> bool:
        now = now or _now()
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > now

    def to_json(self) -> dict:
        def iso(value: Optional[datetime]) -> Optional[str]:
            return value.replace(tzinfo=timezone.utc).isoformat() if value else None

        return {
            "id": self.id,
            "name": self.name,
            "token_prefix": self.token_prefix,
            "created_at": iso(self.created_at),
            "created_by": self.created_by,
            "last_used_at": iso(self.last_used_at),
            "expires_at": iso(self.expires_at),
            "revoked_at": iso(self.revoked_at),
            "active": self.is_live(),
        }


def _record(row: SqlScimToken) -> ScimTokenRecord:
    return ScimTokenRecord(
        id=row.id,
        name=row.name,
        token_prefix=row.token_prefix,
        created_at=row.created_at,
        created_by=row.created_by,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


def _generate() -> Tuple[str, str]:
    """Return ``(prefix, plaintext)``."""
    prefix = secrets.token_hex(PREFIX_LENGTH // 2)
    return prefix, f"{TOKEN_SCHEME}_{prefix}_{secrets.token_urlsafe(32)}"


def parse_prefix(plaintext: str) -> Optional[str]:
    """Extract the lookup prefix from a presented token, or None if it is not one of ours."""
    if not isinstance(plaintext, str):
        return None
    parts = plaintext.split("_", 2)
    if len(parts) != 3 or parts[0] != TOKEN_SCHEME or len(parts[1]) != PREFIX_LENGTH or not parts[2]:
        return None
    return parts[1]


class ScimTokenRepository:
    """Reads and writes ``scim_tokens``."""

    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _insert(self, session, name: str, created_by: Optional[str], expires_at: Optional[datetime]) -> Tuple[SqlScimToken, str]:
        # A 32-bit prefix collides rarely but not never. Checked before inserting; the unique
        # index is the backstop for a concurrent insert, surfacing as an error rather than as
        # two rows sharing a lookup handle.
        for _ in range(5):
            prefix, plaintext = _generate()
            if session.query(SqlScimToken.id).filter(SqlScimToken.token_prefix == prefix).first() is not None:
                continue
            row = SqlScimToken(
                name=name,
                token_hash=generate_password_hash(plaintext, method=TOKEN_HASH_METHOD),
                token_prefix=prefix,
                created_by=created_by,
                expires_at=_naive_utc(expires_at),
                created_at=_now(),
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as e:
                raise MlflowException(f"could not issue SCIM token '{name}': {e.orig}", RESOURCE_ALREADY_EXISTS) from e
            return row, plaintext
        raise MlflowException("could not allocate a unique SCIM token prefix", INVALID_STATE)

    def create(self, name: str, created_by: Optional[str], expires_at: Optional[datetime] = None) -> Tuple[ScimTokenRecord, str]:
        """Issue a token. Returns the record and the plaintext, which is never retrievable again.

        Raises:
            MlflowException: If the name is empty or already used, or ``expires_at`` is past.
        """
        name = (name or "").strip()
        if not name:
            raise MlflowException("a SCIM token needs a name", INVALID_PARAMETER_VALUE)
        expires_at = _naive_utc(expires_at)
        if expires_at is not None and expires_at <= _now():
            raise MlflowException("expires_at must be in the future", INVALID_PARAMETER_VALUE)
        with self._Session(read_only=False) as session:
            if session.query(SqlScimToken.id).filter(SqlScimToken.name == name).first() is not None:
                raise MlflowException(f"a SCIM token named '{name}' already exists", RESOURCE_ALREADY_EXISTS)
            row, plaintext = self._insert(session, name, created_by, expires_at)
            return _record(row), plaintext

    def list(self) -> List[ScimTokenRecord]:
        with self._Session() as session:
            return [_record(row) for row in session.query(SqlScimToken).order_by(SqlScimToken.id).all()]

    def get(self, token_id: int) -> ScimTokenRecord:
        with self._Session() as session:
            row = session.get(SqlScimToken, token_id)
            if row is None:
                raise MlflowException(f"SCIM token {token_id} not found", RESOURCE_DOES_NOT_EXIST)
            return _record(row)

    def revoke(self, token_id: int) -> ScimTokenRecord:
        """Revoke a token immediately. Idempotent: revoking a revoked token keeps the first time."""
        with self._Session(read_only=False) as session:
            row = session.get(SqlScimToken, token_id)
            if row is None:
                raise MlflowException(f"SCIM token {token_id} not found", RESOURCE_DOES_NOT_EXIST)
            if row.revoked_at is None:
                row.revoked_at = _now()
                session.flush()
            return _record(row)

    def rotate(self, token_id: int, overlap_seconds: int) -> Tuple[ScimTokenRecord, str]:
        """Issue a replacement and let the old token live on for ``overlap_seconds``.

        The overlap is what makes rotation safe for a directory that is mid-sync: the new token
        can be pasted into the IdP while the old one keeps working, and the old one then expires
        on its own. The old row is renamed so the replacement can keep the name operators know.

        Returns:
            The replacement's record and its plaintext.

        Raises:
            MlflowException: If the token does not exist or is no longer live — rotating a
                revoked or expired token would resurrect access that was deliberately ended.
        """
        now = _now()
        with self._Session(read_only=False) as session:
            old = session.get(SqlScimToken, token_id)
            if old is None:
                raise MlflowException(f"SCIM token {token_id} not found", RESOURCE_DOES_NOT_EXIST)
            if not _record(old).is_live(now):
                raise MlflowException(f"SCIM token {token_id} is revoked or expired and cannot be rotated", INVALID_STATE)

            name = old.name
            # The replacement inherits the original lifetime policy, never a longer one.
            replacement_expiry = old.expires_at
            overlap_end = now + timedelta(seconds=max(0, int(overlap_seconds)))
            old.expires_at = min(old.expires_at, overlap_end) if old.expires_at else overlap_end
            old.name = f"{name} (rotated #{old.id})"[:255]
            session.flush()

            row, plaintext = self._insert(session, name, old.created_by, replacement_expiry)
            return _record(row), plaintext

    def authenticate(self, plaintext: str) -> Optional[ScimTokenRecord]:
        """Return the live token matching ``plaintext``, or None.

        One indexed lookup by prefix, then one constant-time hash verification. The prefix is
        not secret, so an early return for an unknown prefix leaks nothing an attacker could not
        already read off a token they hold.
        """
        prefix = parse_prefix(plaintext)
        if prefix is None:
            return None
        now = _now()
        with self._Session(read_only=False) as session:
            row = session.query(SqlScimToken).filter(SqlScimToken.token_prefix == prefix).one_or_none()
            if row is None:
                return None
            if not check_password_hash(row.token_hash, plaintext):
                return None
            if not _record(row).is_live(now):
                return None
            if row.last_used_at is None or (now - row.last_used_at).total_seconds() >= LAST_USED_RESOLUTION_SECONDS:
                row.last_used_at = now
                session.flush()
            return _record(row)
