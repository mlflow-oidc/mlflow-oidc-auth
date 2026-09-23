"""Encryption for the provider tokens a server-side session holds (issue #367).

The refresh token and the IdP-issued expiry used to live in the signed Starlette cookie. Signed is
not encrypted, and — the defect behind #367 — a cookie is written by *every* response: two
concurrent requests that both refreshed would each send back their own cookie, and whichever the
browser stored last won. Under refresh-token rotation with reuse detection, the loser's cookie
carried a refresh token the IdP had already retired, and the next refresh ended the session.

The tokens now live on the ``auth_sessions`` row, in ``encrypted_tokens``, and the cookie carries
only the opaque session id. This module is the only thing that turns that column into tokens and
back.

**Key.** ``SESSION_TOKEN_ENCRYPTION_KEY`` when set: one or more comma-separated urlsafe-base64
32-byte Fernet keys, the first used to encrypt and all accepted to decrypt, so a key can be
rotated without ending every session at once. Otherwise a key is derived from ``SECRET_KEY`` with
HKDF-SHA256 under a purpose-specific ``info``, so the cookie-signing key is never used directly as
an encryption key. Rotating ``SECRET_KEY`` without a dedicated key therefore makes every stored
blob unreadable — ``decrypt`` then returns None and the session falls back to a normal re-login
once its IdP expiry passes. That is the fail-closed direction.

**Logging.** Nothing here logs a blob, a token or a key — not even on failure.
"""

from __future__ import annotations

import base64
import functools
import json
import time
from dataclasses import asdict, dataclass, fields
from typing import Any, Mapping, Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# Purpose-bound derivation label. Changing it invalidates every stored blob, so it is versioned
# rather than edited.
HKDF_INFO = b"mlflow-oidc-auth/session-tokens/v1"


@dataclass(frozen=True)
class SessionTokens:
    """Provider token material held by one server-side session.

    Attributes:
        provider_id: Registry id of the provider that issued the tokens, when known.
        expires_at: IdP-issued token expiry, Unix seconds. None means the IdP gave none.
        refresh_token: The refresh token, when ``OIDC_USE_REFRESH_TOKEN`` retains one.
        id_token: The raw ID token, for ``id_token_hint`` on RP-initiated logout.
        saml_name_id: SAML ``NameID`` of the subject, for single logout.
        saml_name_id_format: Format of ``saml_name_id``.
        saml_session_index: SAML ``SessionIndex``, for single logout.
    """

    provider_id: Optional[str] = None
    expires_at: Optional[int] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    saml_name_id: Optional[str] = None
    saml_name_id_format: Optional[str] = None
    saml_session_index: Optional[str] = None

    @property
    def has_refresh_token(self) -> bool:
        """Whether a refresh token is held."""
        return bool(self.refresh_token)

    def is_expired(self, leeway_seconds: int = 0, now: Optional[float] = None) -> bool:
        """Whether the IdP-issued expiry, less ``leeway_seconds``, has passed.

        No recorded expiry is *not* expired: the IdP gave none, and the session's own lifetime
        still bounds it.

        Parameters:
            leeway_seconds: Clock-skew allowance; negative values are treated as zero.
            now: Unix seconds to compare against; defaults to the current time.

        Returns:
            True when expired.
        """
        if self.expires_at is None or isinstance(self.expires_at, bool) or not isinstance(self.expires_at, (int, float)):
            return False
        current = time.time() if now is None else now
        return current >= float(self.expires_at) - max(0, leeway_seconds)

    def to_dict(self) -> dict[str, Any]:
        """The tokens as a JSON-serialisable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SessionTokens":
        """Build from a dict, ignoring keys this version does not know.

        Unknown keys are dropped rather than refused so a blob written by a newer release — with
        a field added — still decrypts on an older replica during a rolling deploy.

        Parameters:
            data: A mapping as produced by ``to_dict``.

        Returns:
            The tokens.
        """
        known = {f.name for f in fields(cls)}
        values = {key: value for key, value in data.items() if key in known}
        expires_at = values.get("expires_at")
        if expires_at is not None and not isinstance(expires_at, (int, float)):
            values["expires_at"] = None
        elif isinstance(expires_at, float):
            values["expires_at"] = int(expires_at)
        return cls(**values)

    def __repr__(self) -> str:
        # Never render token material: a dataclass repr would, and reprs end up in logs and
        # tracebacks.
        return (
            f"SessionTokens(provider_id={self.provider_id!r}, expires_at={self.expires_at!r}, "
            f"has_refresh_token={self.has_refresh_token}, has_id_token={bool(self.id_token)}, "
            f"has_saml_session={bool(self.saml_session_index or self.saml_name_id)})"
        )


def _derive_key(secret_key: str) -> bytes:
    """HKDF-SHA256 a Fernet key from ``SECRET_KEY``, bound to this purpose."""
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=HKDF_INFO)
    return base64.urlsafe_b64encode(hkdf.derive(secret_key.encode("utf-8")))


def _parse_dedicated_keys(value: str) -> list[bytes]:
    """Parse ``SESSION_TOKEN_ENCRYPTION_KEY``: comma-separated Fernet keys, first one current.

    Raises:
        ValueError: If any entry is not a urlsafe-base64 encoding of 32 bytes. The message does
            not include the value.
    """
    keys = [part.strip() for part in value.split(",") if part.strip()]
    if not keys:
        raise ValueError("SESSION_TOKEN_ENCRYPTION_KEY is set but empty")
    parsed = []
    for index, key in enumerate(keys):
        try:
            raw = base64.urlsafe_b64decode(key.encode("ascii"))
        except Exception:
            raw = b""
        if len(raw) != 32:
            raise ValueError(f"SESSION_TOKEN_ENCRYPTION_KEY entry {index} is not a urlsafe-base64 32-byte Fernet key")
        parsed.append(key.encode("ascii"))
    return parsed


def validate_encryption_key(value: Optional[str]) -> None:
    """Check ``SESSION_TOKEN_ENCRYPTION_KEY`` at startup, so a bad key fails fast.

    Unset (None or empty) is valid: the key is then derived from ``SECRET_KEY``.

    Parameters:
        value: The configured value.

    Raises:
        ValueError: If it is set but not one or more urlsafe-base64 32-byte Fernet keys. The
            message names the setting and the offending entry's position, never the value.
    """
    if value:
        _parse_dedicated_keys(value)


class TokenVault:
    """Encrypts and decrypts ``SessionTokens`` for the ``encrypted_tokens`` column.

    Parameters:
        secret_key: ``SECRET_KEY``, used to derive a key when no dedicated key is configured.
        dedicated_key: ``SESSION_TOKEN_ENCRYPTION_KEY``, when set.

    Raises:
        ValueError: If ``dedicated_key`` is set but malformed, or neither key is available.
    """

    def __init__(self, secret_key: Optional[str], dedicated_key: Optional[str] = None) -> None:
        if dedicated_key:
            keys = _parse_dedicated_keys(dedicated_key)
        elif secret_key:
            keys = [_derive_key(secret_key)]
        else:
            raise ValueError("No key available to encrypt session tokens")
        self._fernet = MultiFernet([Fernet(key) for key in keys])

    def encrypt(self, tokens: SessionTokens) -> str:
        """Encrypt ``tokens`` into an opaque, authenticated string.

        Parameters:
            tokens: What to store.

        Returns:
            The Fernet token, as text.
        """
        payload = json.dumps(tokens.to_dict(), separators=(",", ":"), sort_keys=True).encode("utf-8")
        return self._fernet.encrypt(payload).decode("ascii")

    def decrypt(self, blob: Optional[str]) -> Optional[SessionTokens]:
        """Decrypt a stored blob, or None when there is none or it cannot be trusted.

        A blob that fails authentication — written under a key since rotated away, or tampered
        with — is treated exactly like an absent one. The caller then has no refresh token and
        no expiry, and the session ends through the ordinary paths; it is never honoured with
        partially-trusted data.

        Parameters:
            blob: The column value.

        Returns:
            The tokens, or None.
        """
        if not blob or not isinstance(blob, (str, bytes)):
            return None
        try:
            payload = self._fernet.decrypt(blob.encode("ascii") if isinstance(blob, str) else blob)
            data = json.loads(payload.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("unexpected payload shape")
            return SessionTokens.from_dict(data)
        except (InvalidToken, ValueError, TypeError, UnicodeError) as exc:
            # The blob is deliberately not logged: it is ciphertext of a live credential.
            logger.debug("Stored session tokens could not be decrypted (%s); treating as absent", type(exc).__name__)
            return None


@functools.lru_cache(maxsize=4)
def _vault_for(secret_key: Optional[str], dedicated_key: Optional[str]) -> TokenVault:
    return TokenVault(secret_key, dedicated_key)


def get_token_vault() -> TokenVault:
    """The vault for the current configuration.

    Cached per key material, so the HKDF derivation runs once per process rather than per
    request, while a configuration change (tests, a reload) still takes effect.

    Returns:
        The vault.

    Raises:
        ValueError: If ``SESSION_TOKEN_ENCRYPTION_KEY`` is malformed.
    """
    from mlflow_oidc_auth.config import config

    secret_key = getattr(config, "SECRET_KEY", None)
    dedicated_key = getattr(config, "SESSION_TOKEN_ENCRYPTION_KEY", None)
    return _vault_for(
        secret_key if isinstance(secret_key, str) else None,
        dedicated_key if isinstance(dedicated_key, str) and dedicated_key else None,
    )
