"""``auth_state.binding_hash`` migration (issue #374): single head, round trip, existing rows untouched.

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

SAML_REVISION = "e4f5a6b7c8d9"
BINDING_REVISION = "c2f3a4b56789"

_INSERT = text("INSERT INTO auth_state (state, provider_id, expires_at) VALUES (:s, 'corp', '2030-01-01 00:00:00')")


def _columns(engine):
    return {c["name"]: c for c in inspect(engine).get_columns("auth_state")}


class TestRevisionChain:
    def test_binding_follows_group_ownership(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(BINDING_REVISION)
        assert script.down_revision == SAML_REVISION

    def test_exactly_one_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"


class TestUpgrade:
    def test_adds_a_nullable_column(self, engine):
        _upgrade(engine, BINDING_REVISION)

        columns = _columns(engine)
        assert "binding_hash" in columns
        assert columns["binding_hash"]["nullable"] is True

    def test_existing_rows_are_kept_and_unbound(self, engine):
        _upgrade(engine, SAML_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT, {"s": "in-flight"})

        _upgrade(engine, BINDING_REVISION)

        with engine.connect() as conn:
            rows = conn.execute(text("SELECT state, provider_id, binding_hash FROM auth_state")).all()
        assert [tuple(row) for row in rows] == [("in-flight", "corp", None)]


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        _upgrade(engine, BINDING_REVISION)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO auth_state (state, provider_id, binding_hash, expires_at) VALUES ('s1', 'corp', :h, '2030-01-01 00:00:00')"), {"h": "a" * 64}
            )

        _downgrade(engine, SAML_REVISION)

        assert "binding_hash" not in _columns(engine)
        with engine.connect() as conn:
            # The downgrade drops only the column: the row, and every other table, stay.
            assert conn.execute(text("SELECT state FROM auth_state")).scalars().all() == ["s1"]
        assert "saml_assertions" in inspect(engine).get_table_names()

        _upgrade(engine, BINDING_REVISION)
        assert "binding_hash" in _columns(engine)
