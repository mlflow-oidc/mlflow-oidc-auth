"""Hashing of stored access tokens (issues #336, #189).

``user_tokens.token_hash`` never holds a human-chosen password — every value comes from
``generate_token()`` (``mlf_<prefix>_<secret>``, a 256-bit secret), and no endpoint accepts an
operator-supplied one. Werkzeug's default scrypt would therefore cost ~48 ms per
basic-authenticated request to protect something with nothing to brute-force.

These tests pin the things that make the cheap method safe:

1. new hashes use the cheap method,
2. hashes written *before* #336 (scrypt), carried over into ``user_tokens`` by the migration,
   still verify and are never silently re-hashed,
3. the token's entropy, which is the premise the cost factor rests on.

The second is the one that matters. If it ever fails, an upgrade has either locked existing
users out or quietly weakened a stored secret.
"""

from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from mlflow_oidc_auth.repository.user_token import TOKEN_HASH_METHOD, generate_token

LEGACY_METHOD = "scrypt:32768:8:1"
LEGACY_SECRET = "aB3dE6gH9jK2mN5pQ8sT1vW4"  # shaped like a pre-#189 secret; only ever in a tmp db


def _in(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _stored_hashes(store, username: str) -> list:
    """Read the raw hashes, which no repository method returns."""
    from mlflow_oidc_auth.db.models import SqlUser, SqlUserToken

    with store.engine.connect() as conn:
        user_id = conn.execute(SqlUser.__table__.select().where(SqlUser.__table__.c.username == username)).fetchone().id
        rows = conn.execute(SqlUserToken.__table__.select().where(SqlUserToken.__table__.c.user_id == user_id)).fetchall()
    return [row.token_hash for row in rows]


def _method_of(pwhash: str) -> str:
    """Werkzeug encodes the method as the first ``$``-delimited field."""
    return pwhash.split("$", 1)[0]


@pytest.fixture
def store(tmp_path):
    """A real store on a temporary SQLite database."""
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    return s


def _write_legacy_token(store, username: str, secret: str, method: str = LEGACY_METHOD, expires_at=None) -> None:
    """Insert a prefix-less ``default`` token, as the migration carries over a pre-#189 secret."""
    from mlflow_oidc_auth.db.models import SqlUser, SqlUserToken

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with store.engine.begin() as conn:
        user_id = conn.execute(SqlUser.__table__.select().where(SqlUser.__table__.c.username == username)).fetchone().id
        conn.execute(
            SqlUserToken.__table__.insert().values(
                user_id=user_id,
                name="default",
                token_prefix=None,
                token_hash=generate_password_hash(secret, method=method),
                created_at=now,
                expires_at=expires_at if expires_at is not None else now + timedelta(days=30),
            )
        )


class TestNewHashesUseTheCheapMethod:
    def test_created_token_uses_the_token_hash_method(self, store):
        store.create_user("new@example.com", "New User")
        store.create_user_token("new@example.com", "ci", _in(30), created_by="new@example.com")

        assert [_method_of(h) for h in _stored_hashes(store, "new@example.com")] == [TOKEN_HASH_METHOD]

    def test_replaced_legacy_token_uses_the_token_hash_method(self, store):
        store.create_user("rot@example.com", "Rot User")
        _write_legacy_token(store, "rot@example.com", LEGACY_SECRET)

        store.replace_user_token("rot@example.com", "default", _in(30), created_by="rot@example.com")

        assert [_method_of(h) for h in _stored_hashes(store, "rot@example.com")] == [TOKEN_HASH_METHOD]

    def test_new_hash_authenticates(self, store):
        store.create_user("auth@example.com", "Auth User")
        _, plaintext = store.create_user_token("auth@example.com", "ci", _in(30), created_by=None)

        assert store.authenticate_user("auth@example.com", plaintext) is True

    def test_new_hash_rejects_a_wrong_secret(self, store):
        """The negative case: a cheaper hash must not become a permissive one."""
        store.create_user("neg@example.com", "Neg User")
        _, plaintext = store.create_user_token("neg@example.com", "ci", _in(30), created_by=None)
        prefix = plaintext.split("_")[1]

        assert store.authenticate_user("neg@example.com", f"mlf_{prefix}_wrong-secret") is False


class TestLegacyHashesKeepWorking:
    """Back-compat: a deployment that upgrades and changes nothing must be unaffected."""

    def test_legacy_scrypt_hash_still_authenticates(self, store):
        store.create_user("old@example.com", "Old User")
        _write_legacy_token(store, "old@example.com", LEGACY_SECRET)

        assert store.authenticate_user("old@example.com", LEGACY_SECRET) is True

    def test_legacy_scrypt_hash_rejects_a_wrong_secret(self, store):
        store.create_user("oldneg@example.com", "Old Neg User")
        _write_legacy_token(store, "oldneg@example.com", LEGACY_SECRET)

        assert store.authenticate_user("oldneg@example.com", "wrong-secret") is False

    def test_successful_auth_does_not_rehash_a_legacy_secret(self, store):
        """No silent downgrade.

        A stored secret cannot be distinguished from a hypothetical operator-set password, so
        authenticating against a legacy hash must leave it exactly as it was. A secret moves to
        the cheap method only by being replaced, which issues a generated token.
        """
        store.create_user("keep@example.com", "Keep User")
        _write_legacy_token(store, "keep@example.com", LEGACY_SECRET)
        before = _stored_hashes(store, "keep@example.com")

        assert store.authenticate_user("keep@example.com", LEGACY_SECRET) is True

        after = _stored_hashes(store, "keep@example.com")
        assert after == before, "legacy hash was rewritten on successful authentication"
        assert _method_of(after[0]) == LEGACY_METHOD

    def test_failed_auth_does_not_rehash_a_legacy_secret(self, store):
        store.create_user("keepneg@example.com", "Keep Neg User")
        _write_legacy_token(store, "keepneg@example.com", LEGACY_SECRET)
        before = _stored_hashes(store, "keepneg@example.com")

        assert store.authenticate_user("keepneg@example.com", "wrong-secret") is False

        assert _stored_hashes(store, "keepneg@example.com") == before


class TestExpiryStillEnforced:
    """The cheaper hash must not disturb the expiration gate that runs alongside it."""

    def test_expired_legacy_secret_is_rejected(self, store):
        store.create_user("expold@example.com", "Exp Old User")
        _write_legacy_token(store, "expold@example.com", LEGACY_SECRET, expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1))

        assert store.authenticate_user("expold@example.com", LEGACY_SECRET) is False

    def test_expired_new_token_is_rejected(self, store):
        from mlflow_oidc_auth.db.models import SqlUserToken

        store.create_user("exp@example.com", "Exp User")
        record, plaintext = store.create_user_token("exp@example.com", "ci", _in(30), created_by=None)
        with store.engine.begin() as conn:
            conn.execute(
                SqlUserToken.__table__.update()
                .where(SqlUserToken.__table__.c.id == record.id)
                .values(expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1))
            )

        assert store.authenticate_user("exp@example.com", plaintext) is False


class TestTokenEntropyPremise:
    """The premise ``TOKEN_HASH_METHOD`` rests on, pinned so it cannot erode silently.

    A cost factor of 1000 PBKDF2 iterations is only defensible because the secret being hashed is
    high-entropy. Shortening the token for usability would quietly make every stored hash
    brute-forceable, and no test would fail. These are the tests that fail instead. If one of them
    breaks, ``TOKEN_HASH_METHOD`` has to be re-justified in the same diff, not discovered later.
    """

    MIN_ENTROPY_BITS = 128

    def test_token_format_is_pinned(self):
        prefix, plaintext = generate_token()
        scheme, token_prefix, secret = plaintext.split("_", 2)

        assert scheme == "mlf"
        assert token_prefix == prefix and len(prefix) == 8
        assert len(secret) == 43  # secrets.token_urlsafe(32)

    def test_secret_alphabet_is_pinned(self):
        """Narrowing the alphabet lowers entropy just as shortening the secret does."""
        import string

        expected = set(string.ascii_letters + string.digits + "-_")
        seen = set("".join(generate_token()[1].split("_", 2)[2] for _ in range(200)))

        assert seen <= expected, f"secret uses characters outside the expected alphabet: {sorted(seen - expected)}"
        assert seen == expected, f"secret alphabet appears narrowed; never observed: {sorted(expected - seen)}"

    def test_token_entropy_clears_the_bar_the_hash_cost_assumes(self):
        """The number that justifies TOKEN_HASH_METHOD, asserted rather than asserted-in-prose.

        Only the secret counts: the prefix is stored in clear.
        """
        import math

        secret = generate_token()[1].split("_", 2)[2]
        bits = len(secret) * math.log2(64)

        assert bits >= self.MIN_ENTROPY_BITS, f"token entropy {bits:.1f} bits is below the {self.MIN_ENTROPY_BITS}-bit floor that {TOKEN_HASH_METHOD} assumes"

    def test_tokens_are_not_repeated(self):
        """A deterministic or poorly seeded generator would defeat the entropy argument."""
        tokens = [generate_token()[1] for _ in range(500)]

        assert len(set(tokens)) == len(tokens)


class TestHashProperties:
    """Properties the chosen method must keep, independent of its cost factor."""

    def test_hashes_are_salted(self, store):
        """The same secret written twice must not produce the same hash."""
        store.create_user("salt1@example.com", "Salt One")
        store.create_user("salt2@example.com", "Salt Two")
        _write_legacy_token(store, "salt1@example.com", LEGACY_SECRET, method=TOKEN_HASH_METHOD)
        _write_legacy_token(store, "salt2@example.com", LEGACY_SECRET, method=TOKEN_HASH_METHOD)

        assert _stored_hashes(store, "salt1@example.com") != _stored_hashes(store, "salt2@example.com")

    def test_secret_is_not_stored_in_clear(self, store):
        store.create_user("clear@example.com", "Clear User")
        _, plaintext = store.create_user_token("clear@example.com", "ci", _in(30), created_by=None)

        assert all(plaintext.split("_", 2)[2] not in h for h in _stored_hashes(store, "clear@example.com"))

    def test_records_never_expose_the_hash(self, store):
        store.create_user("prof@example.com", "Prof User")
        store.create_user_token("prof@example.com", "ci", _in(30), created_by=None)

        (record,) = store.list_user_tokens("prof@example.com")

        assert "hash" not in " ".join(record.to_json())
        assert not hasattr(record, "token_hash")
