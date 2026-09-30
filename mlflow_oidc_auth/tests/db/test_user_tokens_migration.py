"""User token migration (issue #189): carry-over, column drop, and a downgrade that never refuses.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped
otherwise) — the same fixture as the Phase 0 migration tests.
"""

from datetime import datetime, timedelta, timezone

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

from mlflow_oidc_auth.db.utils import _get_alembic_config
from mlflow_oidc_auth.tests.db.test_phase0_migration import (  # noqa: F401  (fixtures)
    _downgrade,
    _sqlite_uri,
    _upgrade,
    db_uri,
    engine,
)

PREVIOUS_REVISION = "d3a4b5c6e7f8"
TOKENS_REVISION = "f6a7b8c9d0e1"
METHOD = "pbkdf2:sha256:1000"
# Shaped like pre-#189 secrets; hashed into a throwaway test database only.
LIVE_SECRET = "aB3dE6gH9jK2mN5pQ8sT1vW4"
FOREVER_SECRET = "zY9xW8vU7tS6rQ5pO4nM3lK2"
EXPIRED_SECRET = "qW1eR2tY3uI4oP5aS6dF7gH8"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _seed_users(engine) -> dict:
    """Users as they exist at the previous revision, with every kind of secret."""
    rows = {
        "live@example.com": (generate_password_hash(LIVE_SECRET, method=METHOD), _now() + timedelta(days=30)),
        "forever@example.com": (generate_password_hash(FOREVER_SECRET, method=METHOD), None),
        "expired@example.com": (generate_password_hash(EXPIRED_SECRET, method=METHOD), _now() - timedelta(days=1)),
        "blank@example.com": ("", None),
    }
    with engine.begin() as conn:
        for username, (pwhash, expiration) in rows.items():
            conn.execute(
                text(
                    "INSERT INTO users (username, display_name, password_hash, password_expiration, is_admin, is_service_account, active, managed_by) "
                    "VALUES (:u, :u, :h, :e, :f, :f, :t, 'manual')"
                ),
                {"u": username, "h": pwhash, "e": expiration, "f": False, "t": True},
            )
        # An account from before display_name was required everywhere: the rebuild must keep it.
        conn.execute(
            text(
                "INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account, active, managed_by) "
                "VALUES ('nodisplay@example.com', NULL, 'h', :f, :f, :t, 'manual')"
            ),
            {"f": False, "t": True},
        )
        conn.execute(text("INSERT INTO groups (group_name, managed_by) VALUES ('team', 'manual')"))
        conn.execute(
            text(
                "INSERT INTO user_groups (user_id, group_id, managed_by) "
                "SELECT u.id, g.id, 'manual' FROM users u, groups g WHERE u.username = 'live@example.com' AND g.group_name = 'team'"
            )
        )
    return rows


def _tokens(engine) -> dict:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT u.username, t.name, t.token_prefix, t.token_hash, t.expires_at FROM user_tokens t JOIN users u ON u.id = t.user_id ORDER BY t.id")
        )
        return {row.username: row for row in result}


def _users(engine) -> dict:
    with engine.connect() as conn:
        return {row.username: row for row in conn.execute(text("SELECT * FROM users"))}


def _as_datetime(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value


class TestRevisionChain:
    def test_follows_the_previous_head(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(TOKENS_REVISION)
        assert script.down_revision == PREVIOUS_REVISION

    def test_exactly_one_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"


class TestUpgrade:
    def test_creates_the_table_and_drops_the_columns(self, engine):
        _upgrade(engine, TOKENS_REVISION)

        inspector = inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns("user_tokens")}
        assert {"id", "user_id", "name", "token_prefix", "token_hash", "created_at", "created_by", "expires_at", "last_used_at"} == set(columns)
        assert columns["expires_at"]["nullable"] is False, "tokens must expire"
        assert columns["token_prefix"]["nullable"] is True, "a carried-over secret has no prefix"
        indexes = {i["name"]: i for i in inspector.get_indexes("user_tokens")}
        assert indexes["ix_user_tokens_token_prefix"]["unique"]
        user_columns = {c["name"] for c in inspector.get_columns("users")}
        assert "password_hash" not in user_columns and "password_expiration" not in user_columns

    def test_the_users_table_keeps_its_indexes_and_constraints(self, engine):
        from sqlalchemy.exc import IntegrityError

        _upgrade(engine, TOKENS_REVISION)

        indexes = {i["name"]: i for i in inspect(engine).get_indexes("users")}
        assert indexes["ix_users_external_id"]["unique"]
        insert = text("INSERT INTO users (username, display_name, active, managed_by) VALUES ('dup@example.com', 'd', :t, 'manual')")
        with engine.begin() as conn:
            conn.execute(insert, {"t": True})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(insert, {"t": True})

    def test_live_secrets_are_carried_over_and_still_verify(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        seeded = _seed_users(engine)

        _upgrade(engine, TOKENS_REVISION)

        tokens = _tokens(engine)
        live = tokens["live@example.com"]
        assert live.name == "default" and live.token_prefix is None
        assert live.token_hash == seeded["live@example.com"][0], "the hash is copied, never re-hashed"
        assert check_password_hash(live.token_hash, LIVE_SECRET)
        assert abs(_as_datetime(live.expires_at) - seeded["live@example.com"][1]) < timedelta(seconds=1)

    def test_a_non_expiring_secret_gets_one_year(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_users(engine)
        before = _now()

        _upgrade(engine, TOKENS_REVISION)

        expires_at = _as_datetime(_tokens(engine)["forever@example.com"].expires_at)
        assert before + timedelta(days=364) < expires_at <= _now() + timedelta(days=365)

    def test_expired_and_empty_secrets_are_not_carried_over(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_users(engine)

        _upgrade(engine, TOKENS_REVISION)

        tokens = _tokens(engine)
        assert "expired@example.com" not in tokens
        assert "blank@example.com" not in tokens

    def test_users_and_their_memberships_survive_the_rebuild(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_users(engine)
        ids_before = {name: row.id for name, row in _users(engine).items()}

        _upgrade(engine, TOKENS_REVISION)

        users = _users(engine)
        assert {name: row.id for name, row in users.items()} == ids_before
        assert users["nodisplay@example.com"].display_name is None
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM user_groups")).scalar() == 1


class TestDowngrade:
    def _insert_token(self, engine, username, name, secret, expires_at, created_at, prefix=None):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO user_tokens (user_id, name, token_prefix, token_hash, created_at, expires_at) "
                    "SELECT id, :n, :p, :h, :c, :e FROM users WHERE username = :u"
                ),
                {"u": username, "n": name, "p": prefix, "h": generate_password_hash(secret, method=METHOD), "c": created_at, "e": expires_at},
            )

    def test_the_default_token_is_restored(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_users(engine)
        _upgrade(engine, TOKENS_REVISION)

        _downgrade(engine, PREVIOUS_REVISION)

        live = _users(engine)["live@example.com"]
        assert check_password_hash(live.password_hash, LIVE_SECRET)
        assert live.password_expiration is not None

    def test_without_a_live_default_the_newest_live_token_is_restored(self, engine):
        _upgrade(engine, TOKENS_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (username, display_name, active, managed_by) VALUES ('n@example.com', 'n', :t, 'manual')"), {"t": True})
        now = _now()
        self._insert_token(engine, "n@example.com", "default", "old-default", now - timedelta(days=1), now - timedelta(days=90))
        self._insert_token(engine, "n@example.com", "ci", "older-live", now + timedelta(days=10), now - timedelta(days=5), prefix="aaaaaaaa")
        self._insert_token(engine, "n@example.com", "laptop", "newest-live", now + timedelta(days=20), now - timedelta(days=1), prefix="bbbbbbbb")

        _downgrade(engine, PREVIOUS_REVISION)

        restored = _users(engine)["n@example.com"]
        assert check_password_hash(restored.password_hash, "newest-live")

    def test_a_user_without_tokens_gets_an_undisclosed_secret(self, engine):
        _upgrade(engine, TOKENS_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (username, display_name, active, managed_by) VALUES ('none@example.com', 'n', :t, 'manual')"), {"t": True})

        _downgrade(engine, PREVIOUS_REVISION)

        restored = _users(engine)["none@example.com"]
        assert restored.password_hash and restored.password_hash.startswith("pbkdf2:")
        assert restored.password_expiration is None

    def test_the_downgrade_never_refuses_when_tokens_would_be_lost(self, engine):
        """The operator rolling back in an incident must not be blocked by data the new version made."""
        _upgrade(engine, TOKENS_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (username, display_name, active, managed_by) VALUES ('m@example.com', 'm', :t, 'manual')"), {"t": True})
        now = _now()
        for i in range(3):
            self._insert_token(engine, "m@example.com", f"t{i}", f"secret-{i}", now + timedelta(days=10), now - timedelta(days=i), prefix=f"{i:08d}")

        _downgrade(engine, PREVIOUS_REVISION)

        assert "user_tokens" not in inspect(engine).get_table_names()
        assert check_password_hash(_users(engine)["m@example.com"].password_hash, "secret-0")


class TestRoundTrip:
    def test_upgrade_downgrade_upgrade_keeps_a_live_secret_working(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_users(engine)

        _upgrade(engine, TOKENS_REVISION)
        _downgrade(engine, PREVIOUS_REVISION)
        _upgrade(engine, TOKENS_REVISION)

        assert check_password_hash(_tokens(engine)["live@example.com"].token_hash, LIVE_SECRET)
