"""Workspace-scoped resource patterns migration: existing patterns apply everywhere, downgrade never widens.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped otherwise).
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

PREVIOUS_REVISION = "b8c9d0e1f2a3"
REVISION = "c9d0e1f2a3b4"

#: table -> (principal column, extra key columns)
TABLES = {
    "experiment_regex_permissions": ("user_id", ()),
    "experiment_group_regex_permissions": ("group_id", ()),
    "registered_model_regex_permissions": ("user_id", ("prompt",)),
    "registered_model_group_regex_permissions": ("group_id", ("prompt",)),
    "scorer_regex_permissions": ("user_id", ()),
    "scorer_group_regex_permissions": ("group_id", ()),
    "gateway_endpoint_regex_permissions": ("user_id", ()),
    "gateway_endpoint_group_regex_permissions": ("group_id", ()),
    "gateway_secret_regex_permissions": ("user_id", ()),
    "gateway_secret_group_regex_permissions": ("group_id", ()),
    "gateway_model_definition_regex_permissions": ("user_id", ()),
    "gateway_model_definition_group_regex_permissions": ("group_id", ()),
}


def _seed(engine) -> None:
    """A user, a group and one pattern per table, as they exist at the previous revision."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (username, display_name, is_admin, is_service_account, active, managed_by) VALUES ('u', 'u', :f, :f, :t, 'manual')"),
            {"f": False, "t": True},
        )
        conn.execute(text("INSERT INTO groups (group_name, managed_by) VALUES ('g', 'manual')"))
        for table, (principal, extra) in TABLES.items():
            source = "users" if principal == "user_id" else "groups"
            extra_cols = "".join(f", {c}" for c in extra)
            extra_vals = "".join(", :f" for _ in extra)
            conn.execute(
                text(f"INSERT INTO {table} (regex, priority, {principal}, permission{extra_cols}) SELECT '^x', 1, id, 'READ'{extra_vals} FROM {source}"),
                {"f": False},
            )


def _patterns(engine, table):
    with engine.connect() as conn:
        return sorted(conn.execute(text(f"SELECT regex, workspace FROM {table}")).fetchall())


class TestRevisionChain:
    def test_follows_the_previous_revision(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(REVISION)
        assert script.down_revision == PREVIOUS_REVISION


class TestUpgrade:
    def test_existing_patterns_apply_in_every_workspace(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed(engine)

        _upgrade(engine, REVISION)

        inspector = inspect(engine)
        for table, (principal, extra) in TABLES.items():
            columns = {c["name"]: c for c in inspector.get_columns(table)}
            assert columns["workspace"]["nullable"] is False, table
            uniques = {tuple(u["column_names"]) for u in inspector.get_unique_constraints(table)}
            assert ("regex", principal, *extra, "workspace") in uniques, table
            assert _patterns(engine, table) == [("^x", "*")], table

    def test_a_pattern_may_be_recorded_once_per_workspace(self, engine):
        _upgrade(engine, REVISION)
        _seed(engine)  # one pattern per table, for every workspace
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO experiment_regex_permissions (regex, priority, user_id, permission, workspace) SELECT '^x', 1, id, 'EDIT', 'team-a' FROM users"
                )
            )
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO experiment_regex_permissions (regex, priority, user_id, permission, workspace) SELECT '^x', 1, id, 'EDIT', 'team-a' FROM users"
                )
            )


class TestDowngrade:
    def test_keeps_only_patterns_for_every_workspace(self, engine):
        _upgrade(engine, REVISION)
        _seed(engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO experiment_regex_permissions (regex, priority, user_id, permission, workspace) SELECT '^team', 1, id, 'MANAGE', 'team-a' FROM users"
                )
            )

        _downgrade(engine, PREVIOUS_REVISION)

        inspector = inspect(engine)
        for table in TABLES:
            assert "workspace" not in {c["name"] for c in inspector.get_columns(table)}, table
        with engine.connect() as conn:
            assert conn.execute(text("SELECT regex FROM experiment_regex_permissions")).fetchall() == [("^x",)]

    def test_round_trip(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed(engine)

        _upgrade(engine, REVISION)
        _downgrade(engine, PREVIOUS_REVISION)
        _upgrade(engine, REVISION)

        for table in TABLES:
            assert _patterns(engine, table) == [("^x", "*")], table
