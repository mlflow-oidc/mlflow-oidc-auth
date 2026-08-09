"""Hashing of stored token secrets (issue #336).

``users.password_hash`` never holds a human-chosen password — every value comes from
``generate_token()`` (24 characters, 62-character alphabet, ~143 bits of entropy), and no
endpoint accepts an operator-supplied one. Werkzeug's default scrypt therefore cost ~48 ms per
basic-authenticated request to protect something with nothing to brute-force.

These tests pin the two things that make the change safe:

1. new hashes use the cheap method, and
2. hashes written *before* the change still verify, and are never silently re-hashed down to it.

The second is the one that matters. If it ever fails, an upgrade has either locked existing
users out or quietly weakened a stored secret.
"""

from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from mlflow_oidc_auth.repository.user import TOKEN_HASH_METHOD

LEGACY_METHOD = "scrypt:32768:8:1"
TOKEN = "aB3dE6gH9jK2mN5pQ8sT1vW4"  # shaped like generate_token() output; only ever in a tmp db


def _stored_hash(store, username: str) -> str:
    """Read the raw hash, which ``get_profile`` deliberately redacts."""
    from mlflow_oidc_auth.db.models import SqlUser

    with store.engine.connect() as conn:
        row = conn.execute(SqlUser.__table__.select().where(SqlUser.__table__.c.username == username)).fetchone()
    assert row is not None, f"user {username} not found"
    return row.password_hash


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


def _write_legacy_hash(store, username: str, secret: str) -> None:
    """Overwrite a user's hash with a scrypt one, simulating a pre-#336 row."""
    from mlflow_oidc_auth.db.models import SqlUser

    legacy = generate_password_hash(secret, method=LEGACY_METHOD)
    with store.engine.begin() as conn:
        conn.execute(SqlUser.__table__.update().where(SqlUser.__table__.c.username == username).values(password_hash=legacy))
    assert _method_of(_stored_hash(store, username)) == LEGACY_METHOD


class TestNewHashesUseTheCheapMethod:
    def test_created_user_uses_the_token_hash_method(self, store):
        store.create_user("new@example.com", TOKEN, "New User")

        assert _method_of(_stored_hash(store, "new@example.com")) == TOKEN_HASH_METHOD

    def test_rotated_token_uses_the_token_hash_method(self, store):
        store.create_user("rot@example.com", TOKEN, "Rot User")
        _write_legacy_hash(store, "rot@example.com", TOKEN)

        store.update_user(username="rot@example.com", password="nEwT0ken4567890abcdefghij")

        assert _method_of(_stored_hash(store, "rot@example.com")) == TOKEN_HASH_METHOD

    def test_new_hash_authenticates(self, store):
        store.create_user("auth@example.com", TOKEN, "Auth User")

        assert store.authenticate_user("auth@example.com", TOKEN) is True

    def test_new_hash_rejects_a_wrong_secret(self, store):
        """The negative case: a cheaper hash must not become a permissive one."""
        store.create_user("neg@example.com", TOKEN, "Neg User")

        assert store.authenticate_user("neg@example.com", "wrong-secret") is False


class TestLegacyHashesKeepWorking:
    """Back-compat: a deployment that upgrades and changes nothing must be unaffected."""

    def test_legacy_scrypt_hash_still_authenticates(self, store):
        store.create_user("old@example.com", TOKEN, "Old User")
        _write_legacy_hash(store, "old@example.com", TOKEN)

        assert store.authenticate_user("old@example.com", TOKEN) is True

    def test_legacy_scrypt_hash_rejects_a_wrong_secret(self, store):
        store.create_user("oldneg@example.com", TOKEN, "Old Neg User")
        _write_legacy_hash(store, "oldneg@example.com", TOKEN)

        assert store.authenticate_user("oldneg@example.com", "wrong-secret") is False

    def test_successful_auth_does_not_rehash_a_legacy_secret(self, store):
        """No silent downgrade.

        A stored secret cannot be distinguished from a hypothetical operator-set password, so
        authenticating against a legacy hash must leave it exactly as it was. A secret moves to
        the cheap method only by being rotated, which replaces it with a generated token.
        """
        store.create_user("keep@example.com", TOKEN, "Keep User")
        _write_legacy_hash(store, "keep@example.com", TOKEN)
        before = _stored_hash(store, "keep@example.com")

        assert store.authenticate_user("keep@example.com", TOKEN) is True

        after = _stored_hash(store, "keep@example.com")
        assert after == before, "legacy hash was rewritten on successful authentication"
        assert _method_of(after) == LEGACY_METHOD

    def test_failed_auth_does_not_rehash_a_legacy_secret(self, store):
        store.create_user("keepneg@example.com", TOKEN, "Keep Neg User")
        _write_legacy_hash(store, "keepneg@example.com", TOKEN)
        before = _stored_hash(store, "keepneg@example.com")

        assert store.authenticate_user("keepneg@example.com", "wrong-secret") is False

        assert _stored_hash(store, "keepneg@example.com") == before


class TestExpiryStillEnforced:
    """The cheaper hash must not disturb the expiration gate that runs alongside it."""

    def test_expired_secret_is_rejected_under_the_new_method(self, store):
        store.create_user("exp@example.com", TOKEN, "Exp User")
        store.update_user(username="exp@example.com", password=TOKEN, password_expiration=datetime.now(timezone.utc) - timedelta(days=1))

        assert store.authenticate_user("exp@example.com", TOKEN) is False

    def test_unexpired_secret_is_accepted_under_the_new_method(self, store):
        store.create_user("live@example.com", TOKEN, "Live User")
        store.update_user(username="live@example.com", password=TOKEN, password_expiration=datetime.now(timezone.utc) + timedelta(days=1))

        assert store.authenticate_user("live@example.com", TOKEN) is True

    def test_expired_legacy_secret_is_still_rejected(self, store):
        store.create_user("expold@example.com", TOKEN, "Exp Old User")
        store.update_user(username="expold@example.com", password=TOKEN, password_expiration=datetime.now(timezone.utc) - timedelta(days=1))
        _write_legacy_hash(store, "expold@example.com", TOKEN)

        assert store.authenticate_user("expold@example.com", TOKEN) is False


class TestTokenEntropyPremise:
    """The premise ``TOKEN_HASH_METHOD`` rests on, pinned so it cannot erode silently.

    A cost factor of 1000 PBKDF2 iterations is only defensible because the secret being
    hashed is high-entropy. That property lives in ``generate_token()``, in a different
    module, with nothing previously connecting the two: shortening the token for usability
    would quietly make every stored hash brute-forceable, and no test would fail.

    These are the tests that fail instead. If one of them breaks, ``TOKEN_HASH_METHOD``
    has to be re-justified in the same diff, not discovered later.
    """

    MIN_ENTROPY_BITS = 128

    def test_token_length_is_pinned(self):
        from mlflow_oidc_auth.user import generate_token

        assert len(generate_token()) == 24

    def test_token_alphabet_is_pinned(self):
        """Narrowing the alphabet lowers entropy just as shortening the token does."""
        import string

        from mlflow_oidc_auth.user import generate_token

        expected = set(string.ascii_letters + string.digits)
        # Enough samples that a dropped character class shows up rather than passing by luck.
        seen = set("".join(generate_token() for _ in range(200)))

        assert seen <= expected, f"token uses characters outside the expected alphabet: {sorted(seen - expected)}"
        assert seen == expected, f"token alphabet appears narrowed; never observed: {sorted(expected - seen)}"

    def test_token_entropy_clears_the_bar_the_hash_cost_assumes(self):
        """The number that justifies TOKEN_HASH_METHOD, asserted rather than asserted-in-prose."""
        import math
        import string

        from mlflow_oidc_auth.user import generate_token

        bits = len(generate_token()) * math.log2(len(set(string.ascii_letters + string.digits)))

        assert bits >= self.MIN_ENTROPY_BITS, f"token entropy {bits:.1f} bits is below the {self.MIN_ENTROPY_BITS}-bit floor that {TOKEN_HASH_METHOD} assumes"

    def test_tokens_are_not_repeated(self):
        """A deterministic or poorly seeded generator would defeat the entropy argument."""
        from mlflow_oidc_auth.user import generate_token

        tokens = [generate_token() for _ in range(500)]

        assert len(set(tokens)) == len(tokens)


class TestHashProperties:
    """Properties the chosen method must keep, independent of its cost factor."""

    def test_hashes_are_salted(self, store):
        """Two users with the same secret must not share a hash."""
        store.create_user("salt1@example.com", TOKEN, "Salt One")
        store.create_user("salt2@example.com", TOKEN, "Salt Two")

        assert _stored_hash(store, "salt1@example.com") != _stored_hash(store, "salt2@example.com")

    def test_secret_is_not_stored_in_clear(self, store):
        store.create_user("clear@example.com", TOKEN, "Clear User")

        assert TOKEN not in _stored_hash(store, "clear@example.com")

    def test_profile_never_exposes_the_hash(self, store):
        """``get_profile`` is what the auth path calls; it must keep redacting."""
        store.create_user("prof@example.com", TOKEN, "Prof User")

        profile = store.get_user_profile("prof@example.com")

        assert profile.password_hash == "REDACTED"
