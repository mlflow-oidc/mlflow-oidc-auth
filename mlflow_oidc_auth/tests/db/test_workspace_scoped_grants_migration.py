"""Workspace-scoped resource grants migration: the column, the widened constraints, and a downgrade that never refuses.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped
otherwise) — the same fixtures as the Phase 0 migration tests.
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

PREVIOUS_REVISION = "a7b8c9d0e1f2"
REVISION = "b8c9d0e1f2a3"

TABLES = {
    "registered_model_permissions": ("name", "user_id"),
    "registered_model_group_permissions": ("name", "group_id"),
    "gateway_endpoint_permissions": ("endpoint_id", "user_id"),
    "gateway_endpoint_group_permissions": ("endpoint_id", "group_id"),
    "gateway_secret_permissions": ("secret_id", "user_id"),
    "gateway_secret_group_permissions": ("secret_id", "group_id"),
    "gateway_model_definition_permissions": ("model_definition_id", "user_id"),
    "gateway_model_definition_group_permissions": ("model_definition_id", "group_id"),
}


def _seed(engine) -> None:
    """A user, a group and one grant per table, as they exist at the previous revision."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (username, display_name, is_admin, is_service_account, active, managed_by) VALUES ('u', 'u', :f, :f, :t, 'manual')"),
            {"f": False, "t": True},
        )
        conn.execute(text("INSERT INTO groups (group_name, managed_by) VALUES ('g', 'manual')"))
        for table, (resource, principal) in TABLES.items():
            source = "users" if principal == "user_id" else "groups"
            conn.execute(text(f"INSERT INTO {table} ({resource}, {principal}, permission) SELECT 'churn', id, 'EDIT' FROM {source}"))


def _grants(engine, table):
    resource, principal = TABLES[table]
    with engine.connect() as conn:
        return sorted(conn.execute(text(f"SELECT {resource}, workspace, permission FROM {table}")).fetchall())


class TestRevisionChain:
    def test_follows_the_previous_head(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(REVISION)
        assert script.down_revision == PREVIOUS_REVISION

    def test_single_head(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path)))
        heads = script.get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"
        assert REVISION in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}


class TestUpgrade:
    def test_adds_the_column_and_keeps_existing_grants_unassigned(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed(engine)

        _upgrade(engine, REVISION)

        inspector = inspect(engine)
        for table, (resource, principal) in TABLES.items():
            columns = {c["name"]: c for c in inspector.get_columns(table)}
            assert columns["workspace"]["nullable"] is True, table
            uniques = {tuple(u["column_names"]) for u in inspector.get_unique_constraints(table)}
            assert ("workspace", resource, principal) in uniques, table
            assert (resource, principal) not in uniques, table
            assert _grants(engine, table) == [("churn", None, "EDIT")], table

    def test_the_same_name_may_be_granted_once_per_workspace(self, engine):
        _upgrade(engine, REVISION)
        _seed(engine)  # no grants to clash with: seeding at the new revision adds unassigned ones
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO registered_model_permissions (name, user_id, permission, workspace) SELECT 'm', id, 'READ', 'team-a' FROM users"))
            conn.execute(text("INSERT INTO registered_model_permissions (name, user_id, permission, workspace) SELECT 'm', id, 'MANAGE', 'team-b' FROM users"))
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text("INSERT INTO registered_model_permissions (name, user_id, permission, workspace) SELECT 'm', id, 'EDIT', 'team-a' FROM users"))


class TestDowngrade:
    def test_collapses_per_workspace_grants_keeping_the_default_one(self, engine):
        _upgrade(engine, REVISION)
        _seed(engine)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM registered_model_permissions"))
            for workspace, permission in (("team-a", "MANAGE"), ("default", "READ"), ("team-b", "EDIT")):
                conn.execute(
                    text("INSERT INTO registered_model_permissions (name, user_id, permission, workspace) SELECT 'churn', id, :p, :w FROM users"),
                    {"p": permission, "w": workspace},
                )

        _downgrade(engine, PREVIOUS_REVISION)

        inspector = inspect(engine)
        for table, (resource, principal) in TABLES.items():
            assert "workspace" not in {c["name"] for c in inspector.get_columns(table)}, table
            assert (resource, principal) in {tuple(u["column_names"]) for u in inspector.get_unique_constraints(table)}, table
        with engine.connect() as conn:
            assert conn.execute(text("SELECT name, permission FROM registered_model_permissions")).fetchall() == [("churn", "READ")]

    def test_never_widens_a_non_default_grant_and_drops_unassigned_duplicates(self, engine):
        _upgrade(engine, REVISION)
        _seed(engine)  # an unassigned grant per table
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO registered_model_permissions (name, user_id, permission, workspace) SELECT 'churn', id, 'READ', 'default' FROM users")
            )
            conn.execute(
                text("INSERT INTO registered_model_permissions (name, user_id, permission, workspace) SELECT 'only-b', id, 'MANAGE', 'team-b' FROM users")
            )

        _downgrade(engine, PREVIOUS_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT name, permission FROM registered_model_permissions")).fetchall() == [("churn", "READ")]

    def test_duplicate_unassigned_grants_do_not_block_the_downgrade(self, engine):
        _upgrade(engine, REVISION)
        _seed(engine)  # an unassigned grant per table
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO registered_model_permissions (name, user_id, permission) SELECT 'churn', id, 'MANAGE' FROM users"))

        _downgrade(engine, PREVIOUS_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT name, permission FROM registered_model_permissions")).fetchall() == [("churn", "EDIT")]

    def test_round_trip(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed(engine)

        _upgrade(engine, REVISION)
        _downgrade(engine, PREVIOUS_REVISION)
        _upgrade(engine, REVISION)

        for table in TABLES:
            assert _grants(engine, table) == [("churn", None, "EDIT")], table
