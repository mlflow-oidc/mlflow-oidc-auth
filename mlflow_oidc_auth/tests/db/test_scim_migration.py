"""SCIM token table migration (issue #321): single head, round trip, and no effect on existing data.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped
otherwise) — the same fixture as the Phase 0 migration tests.
"""

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from mlflow_oidc_auth.db.utils import _get_alembic_config
from mlflow_oidc_auth.tests.db.test_phase0_migration import (  # noqa: F401  (fixtures)
    PHASE0_REVISION,
    _downgrade,
    _sqlite_uri,
    _upgrade,
    db_uri,
    engine,
)

SCIM_REVISION = "a0d1e2f34567"


class TestRevisionChain:
    def test_scim_follows_phase0(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(SCIM_REVISION)
        assert script.down_revision == PHASE0_REVISION

    def test_exactly_one_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"


class TestUpgrade:
    def test_creates_the_table_and_indexes(self, engine):
        _upgrade(engine, SCIM_REVISION)

        inspector = inspect(engine)
        assert "scim_tokens" in inspector.get_table_names()
        columns = {c["name"]: c for c in inspector.get_columns("scim_tokens")}
        assert {"id", "name", "token_hash", "token_prefix", "created_at", "created_by", "last_used_at", "expires_at", "revoked_at"} == set(columns)
        assert columns["token_hash"]["nullable"] is False
        assert columns["expires_at"]["nullable"] is True
        assert columns["revoked_at"]["nullable"] is True
        indexes = {i["name"]: i for i in inspector.get_indexes("scim_tokens")}
        assert indexes["ix_scim_tokens_token_prefix"]["unique"]

    def test_names_are_unique(self, engine):
        from sqlalchemy.exc import IntegrityError

        _upgrade(engine, SCIM_REVISION)
        insert = text("INSERT INTO scim_tokens (name, token_hash, token_prefix) VALUES (:n, 'h', :p)")
        with engine.begin() as conn:
            conn.execute(insert, {"n": "entra", "p": "aaaaaaaa"})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(insert, {"n": "entra", "p": "bbbbbbbb"})

    def test_upgrade_over_existing_data_touches_nothing(self, engine):
        _upgrade(engine, PHASE0_REVISION)

        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account) VALUES ('a@example.com', 'a', 'h', :t, :f)"),
                {"t": True, "f": False},
            )

        _upgrade(engine, SCIM_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 1
            assert conn.execute(text("SELECT count(*) FROM scim_tokens")).scalar() == 0


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        _upgrade(engine, SCIM_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO scim_tokens (name, token_hash, token_prefix) VALUES ('entra', 'h', 'aaaaaaaa')"))

        _downgrade(engine, PHASE0_REVISION)

        inspector = inspect(engine)
        assert "scim_tokens" not in inspector.get_table_names()
        assert "users" in inspector.get_table_names(), "the downgrade must only remove what this revision added"

        _upgrade(engine, SCIM_REVISION)
        assert "scim_tokens" in inspect(engine).get_table_names()
