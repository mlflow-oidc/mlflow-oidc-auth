"""SAML assertion replay table migration (issue #328): single head, round trip, no effect on existing data.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped
otherwise) — the same fixture as the Phase 0 migration tests.
"""

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.db.utils import _get_alembic_config
from mlflow_oidc_auth.tests.db.test_phase0_migration import (  # noqa: F401  (fixtures)
    _downgrade,
    _sqlite_uri,
    _upgrade,
    db_uri,
    engine,
)

SCIM_REVISION = "a0d1e2f34567"
SAML_REVISION = "b1e2f3a45678"

_INSERT = text("INSERT INTO saml_assertions (assertion_id, provider_id, not_on_or_after) VALUES (:a, 'corp', '2030-01-01 00:00:00')")


class TestRevisionChain:
    def test_saml_follows_scim(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(SAML_REVISION)
        assert script.down_revision == SCIM_REVISION

    def test_exactly_one_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"


class TestUpgrade:
    def test_creates_the_table_and_indexes(self, engine):
        _upgrade(engine, SAML_REVISION)

        inspector = inspect(engine)
        assert "saml_assertions" in inspector.get_table_names()
        columns = {c["name"]: c for c in inspector.get_columns("saml_assertions")}
        assert {"id", "assertion_id", "provider_id", "not_on_or_after", "created_at"} == set(columns)
        assert all(columns[name]["nullable"] is False for name in ("assertion_id", "provider_id", "not_on_or_after", "created_at"))
        indexes = {i["name"]: i for i in inspector.get_indexes("saml_assertions")}
        assert indexes["ix_saml_assertions_assertion_id"]["unique"]
        assert not indexes["ix_saml_assertions_not_on_or_after"]["unique"]

    def test_an_assertion_id_can_be_recorded_only_once(self, engine):
        """The unique index is the replay check itself."""
        _upgrade(engine, SAML_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT, {"a": "_assertion-1"})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(_INSERT, {"a": "_assertion-1"})

    def test_upgrade_over_existing_data_touches_nothing(self, engine):
        _upgrade(engine, SCIM_REVISION)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account) VALUES ('a@example.com', 'a', 'h', :t, :f)"),
                {"t": True, "f": False},
            )

        _upgrade(engine, SAML_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 1
            assert conn.execute(text("SELECT count(*) FROM saml_assertions")).scalar() == 0


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        _upgrade(engine, SAML_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT, {"a": "_assertion-1"})

        _downgrade(engine, SCIM_REVISION)

        inspector = inspect(engine)
        assert "saml_assertions" not in inspector.get_table_names()
        assert "scim_tokens" in inspector.get_table_names(), "the downgrade must only remove what this revision added"

        _upgrade(engine, SAML_REVISION)
        assert "saml_assertions" in inspect(engine).get_table_names()
