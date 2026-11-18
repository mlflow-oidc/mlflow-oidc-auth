"""``issue_detection_schedule_authors`` migration: single head, round trip, existing data untouched.

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

PREVIOUS_REVISION = "f2a3b4c5d6e7"
AUTHORS_REVISION = "a1b2c3d4e5f7"

_INSERT = text(
    "INSERT INTO issue_detection_schedule_authors (experiment_id, author, model_fingerprint, recorded_at) VALUES ('1', 'alice', 'f', '2030-01-01 00:00:00')"
)


class TestRevisionChain:
    def test_follows_the_skill_permissions_migration(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(AUTHORS_REVISION)
        assert script.down_revision == PREVIOUS_REVISION

    def test_exactly_one_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert heads == [AUTHORS_REVISION], f"expected a single head, got {heads}"


class TestUpgrade:
    def test_creates_the_table(self, engine):
        _upgrade(engine, AUTHORS_REVISION)

        inspector = inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns("issue_detection_schedule_authors")}
        assert set(columns) == {"id", "experiment_id", "workspace", "author", "model_fingerprint", "recorded_at", "guard_paused_at", "guard_reason"}
        assert columns["experiment_id"]["nullable"] is False
        assert columns["recorded_at"]["nullable"] is False
        assert columns["author"]["nullable"] is True
        unique = {u["name"]: u["column_names"] for u in inspector.get_unique_constraints("issue_detection_schedule_authors")}
        assert unique == {"uq_issue_detection_schedule_authors_experiment": ["experiment_id"]}

    def test_constraint_names_fit_postgresql(self):
        assert len("uq_issue_detection_schedule_authors_experiment".encode()) <= 63

    def test_one_row_per_experiment(self, engine):
        import pytest
        from sqlalchemy.exc import IntegrityError

        _upgrade(engine, AUTHORS_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT)
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(_INSERT)

    def test_upgrade_over_existing_data_touches_nothing_and_backfills_nothing(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (username, display_name, is_admin, is_service_account) VALUES ('alice', 'Alice', false, false)"))

        _upgrade(engine, AUTHORS_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT username FROM users")).scalars().all() == ["alice"]
            assert conn.execute(text("SELECT count(*) FROM issue_detection_schedule_authors")).scalar() == 0


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        _upgrade(engine, AUTHORS_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT)

        _downgrade(engine, PREVIOUS_REVISION)

        tables = inspect(engine).get_table_names()
        assert "issue_detection_schedule_authors" not in tables
        assert "users" in tables

        _upgrade(engine, AUTHORS_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT)
            assert conn.execute(text("SELECT count(*) FROM issue_detection_schedule_authors")).scalar() == 1
