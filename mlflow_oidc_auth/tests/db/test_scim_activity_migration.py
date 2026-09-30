"""``scim_activity`` migration (issue #325): single head, round trip, existing data untouched.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped
otherwise) — the same fixture as the Phase 0 migration tests.
"""

from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from mlflow_oidc_auth.db.utils import _get_alembic_config
from mlflow_oidc_auth.tests.db.test_phase0_migration import (  # noqa: F401  (fixtures)
    _downgrade,
    _sqlite_uri,
    _upgrade,
    db_uri,
    engine,
)

BINDING_REVISION = "c2f3a4b56789"
ACTIVITY_REVISION = "d3a4b5c6e7f8"

_INSERT = text(
    "INSERT INTO scim_activity (at, token_id, token_name, method, path, status, outcome) VALUES ('2030-01-01 00:00:00', 1, 'entra', 'GET', '/Users', 200, 'ok')"
)


class TestRevisionChain:
    def test_activity_follows_the_binding_migration(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(ACTIVITY_REVISION)
        assert script.down_revision == BINDING_REVISION

    def test_exactly_one_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"


class TestUpgrade:
    def test_creates_the_table_and_indexes(self, engine):
        _upgrade(engine, ACTIVITY_REVISION)

        inspector = inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns("scim_activity")}
        assert set(columns) == {"id", "at", "token_id", "token_name", "method", "path", "resource_id", "status", "outcome", "error", "duration_ms"}
        assert columns["token_id"]["nullable"] is True
        assert columns["error"]["nullable"] is True
        assert columns["outcome"]["nullable"] is False
        assert {i["name"] for i in inspector.get_indexes("scim_activity")} == {"ix_scim_activity_at", "ix_scim_activity_token_id_at"}

    def test_upgrade_over_existing_data_touches_nothing(self, engine):
        _upgrade(engine, BINDING_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO scim_tokens (name, token_hash, token_prefix) VALUES ('entra', 'h', 'aaaaaaaa')"))

        _upgrade(engine, ACTIVITY_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT name FROM scim_tokens")).scalars().all() == ["entra"]
            assert conn.execute(text("SELECT count(*) FROM scim_activity")).scalar() == 0


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        _upgrade(engine, ACTIVITY_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT)

        _downgrade(engine, BINDING_REVISION)

        tables = inspect(engine).get_table_names()
        assert "scim_activity" not in tables
        assert "scim_tokens" in tables and "auth_state" in tables

        _upgrade(engine, ACTIVITY_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT)
            assert conn.execute(text("SELECT count(*) FROM scim_activity")).scalar() == 1
