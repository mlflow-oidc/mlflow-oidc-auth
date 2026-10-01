"""MCP server permissions migration: two workspace-scoped grant tables, and a downgrade that drops them.

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

PREVIOUS_REVISION = "c9d0e1f2a3b4"
REVISION = "d0e1f2a3b4c5"

TABLES = {
    "mcp_server_permissions": ("user_id", "users", "uq_mcp_server_perm_workspace_name_user"),
    "mcp_server_group_permissions": ("group_id", "groups", "uq_mcp_server_group_perm_workspace_name_group"),
}


def _seed_principals(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (username, display_name, is_admin, is_service_account, active, managed_by) VALUES ('u', 'u', :f, :f, :t, 'manual')"),
            {"f": False, "t": True},
        )
        conn.execute(text("INSERT INTO groups (group_name, managed_by) VALUES ('g', 'manual')"))


def _grant(conn, table: str, name: str, workspace, permission: str = "READ") -> None:
    principal, source, _ = TABLES[table]
    conn.execute(
        text(f"INSERT INTO {table} (name, {principal}, permission, workspace) SELECT :n, id, :p, :w FROM {source}"),
        {"n": name, "p": permission, "w": workspace},
    )


class TestRevisionChain:
    def test_follows_the_previous_revision(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(REVISION)
        assert script.down_revision == PREVIOUS_REVISION

    def test_single_head(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path)))
        heads = script.get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"
        assert REVISION in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}

    def test_constraint_names_fit_postgres(self):
        # PostgreSQL truncates identifiers past 63 bytes, which would make two constraints collide.
        assert all(len(name) <= 63 for _, _, name in TABLES.values())


class TestUpgrade:
    def test_creates_both_tables_with_the_workspace_scoped_unique_constraint(self, engine):
        _upgrade(engine, REVISION)

        inspector = inspect(engine)
        for table, (principal, source, unique) in TABLES.items():
            columns = {c["name"]: c for c in inspector.get_columns(table)}
            assert set(columns) == {"id", "name", principal, "permission", "workspace"}, table
            assert columns["workspace"]["nullable"] is True, table
            assert columns["name"]["nullable"] is False, table
            uniques = {u["name"]: tuple(u["column_names"]) for u in inspector.get_unique_constraints(table)}
            assert uniques.get(unique) == ("workspace", "name", principal), table
            foreign = {(tuple(fk["constrained_columns"]), fk["referred_table"]) for fk in inspector.get_foreign_keys(table)}
            assert ((principal,), source) in foreign, table

    def test_the_same_name_may_be_granted_once_per_workspace(self, engine):
        _upgrade(engine, REVISION)
        _seed_principals(engine)
        for table in TABLES:
            with engine.begin() as conn:
                _grant(conn, table, "com.example/weather", "team-a")
                _grant(conn, table, "com.example/weather", "team-b", "MANAGE")
            with pytest.raises(IntegrityError), engine.begin() as conn:
                _grant(conn, table, "com.example/weather", "team-a", "EDIT")

    def test_the_model_matches_the_migrated_schema(self, engine):
        """The ORM models write into the migrated tables (catches a drifted column or constraint)."""
        from sqlalchemy.orm import Session

        from mlflow_oidc_auth.db.models import SqlMCPServerGroupPermission, SqlMCPServerPermission

        _upgrade(engine, REVISION)
        _seed_principals(engine)
        with Session(engine) as session, session.begin():
            user_id = session.execute(text("SELECT id FROM users")).scalar_one()
            group_id = session.execute(text("SELECT id FROM groups")).scalar_one()
            session.add(SqlMCPServerPermission(name="com.example/weather", user_id=user_id, permission="MANAGE", workspace="team-a"))
            session.add(SqlMCPServerGroupPermission(name="com.example/weather", group_id=group_id, permission="READ", workspace="team-a"))
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM mcp_server_permissions")).scalar_one() == 1
            assert conn.execute(text("SELECT count(*) FROM mcp_server_group_permissions")).scalar_one() == 1


class TestDowngrade:
    def test_drops_both_tables_and_leaves_the_rest(self, engine):
        _upgrade(engine, REVISION)
        _seed_principals(engine)
        with engine.begin() as conn:
            for table in TABLES:
                _grant(conn, table, "com.example/weather", "team-a")

        _downgrade(engine, PREVIOUS_REVISION)

        tables = set(inspect(engine).get_table_names())
        assert not tables & set(TABLES)
        assert {"users", "groups", "registered_model_permissions"} <= tables

    def test_round_trip(self, engine):
        _upgrade(engine, REVISION)
        _downgrade(engine, PREVIOUS_REVISION)
        _upgrade(engine, REVISION)
        _seed_principals(engine)

        with engine.begin() as conn:
            for table in TABLES:
                _grant(conn, table, "com.example/weather", "default", "EDIT")
        with engine.connect() as conn:
            for table in TABLES:
                assert conn.execute(text(f"SELECT name, workspace, permission FROM {table}")).fetchall() == [("com.example/weather", "default", "EDIT")]
