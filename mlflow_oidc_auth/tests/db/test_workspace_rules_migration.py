"""Workspace group rules migration (issue #418): the rules table, ``rule_id`` on group grants, and a downgrade that never refuses.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped
otherwise) — the same fixture as the Phase 0 migration tests.
"""

from datetime import datetime

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

PREVIOUS_REVISION = "f6a7b8c9d0e1"
RULES_REVISION = "a7b8c9d0e1f2"


def _seed_grants(engine) -> None:
    """Manual workspace group grants as they exist at the previous revision."""
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO groups (group_name, managed_by) VALUES ('team-acme', 'manual'), ('team-beta', 'manual')"))
        conn.execute(
            text(
                "INSERT INTO workspace_group_permissions (workspace, group_id, permission) "
                "SELECT 'acme', id, 'EDIT' FROM groups WHERE group_name = 'team-acme'"
            )
        )
        conn.execute(
            text(
                "INSERT INTO workspace_group_permissions (workspace, group_id, permission) "
                "SELECT 'beta', id, 'READ' FROM groups WHERE group_name = 'team-beta'"
            )
        )


def _insert_rule(conn, name: str = "tenants") -> int:
    now = datetime(2026, 9, 30, 12, 0, 0)
    conn.execute(
        text(
            "INSERT INTO workspace_group_rules (name, pattern, permission, mode, enabled, created_by, created_at, updated_at) "
            "VALUES (:n, '^team-(?P<ws>.+)$', 'EDIT', 'enforce', :t, 'admin', :now, :now)"
        ),
        {"n": name, "t": True, "now": now},
    )
    return conn.execute(text("SELECT id FROM workspace_group_rules WHERE name = :n"), {"n": name}).scalar_one()


def _grants(engine) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT p.workspace, g.group_name, p.permission, p.rule_id FROM workspace_group_permissions p JOIN groups g ON g.id = p.group_id")
        )
        return {(r.workspace, r.group_name): (r.permission, r.rule_id) for r in rows}


class TestRevisionChain:
    def test_follows_the_previous_head(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(RULES_REVISION)
        assert script.down_revision == PREVIOUS_REVISION

    def test_single_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert heads == [RULES_REVISION], f"expected a single head, got {heads}"


class TestUpgrade:
    def test_creates_the_table_and_the_column(self, engine):
        _upgrade(engine, RULES_REVISION)

        inspector = inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns("workspace_group_rules")}
        assert set(columns) == {"id", "name", "pattern", "permission", "mode", "enabled", "created_by", "created_at", "updated_at"}
        assert columns["created_by"]["nullable"] is True
        assert all(not columns[c]["nullable"] for c in ("name", "pattern", "permission", "mode", "enabled", "created_at", "updated_at"))

        grant_columns = {c["name"]: c for c in inspector.get_columns("workspace_group_permissions")}
        assert grant_columns["rule_id"]["nullable"] is True
        fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("workspace_group_permissions")}
        assert fks["fk_workspace_group_permissions_rule_id"]["referred_table"] == "workspace_group_rules"
        assert any(fk["referred_table"] == "groups" for fk in fks.values()), "the rebuild must keep the group foreign key"
        assert inspector.get_pk_constraint("workspace_group_permissions")["constrained_columns"] == ["workspace", "group_id"]

    def test_existing_grants_keep_rule_id_null(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_grants(engine)

        _upgrade(engine, RULES_REVISION)

        assert _grants(engine) == {("acme", "team-acme"): ("EDIT", None), ("beta", "team-beta"): ("READ", None)}

    def test_rule_names_are_unique(self, engine):
        _upgrade(engine, RULES_REVISION)
        with engine.begin() as conn:
            _insert_rule(conn, "tenants")
        with pytest.raises(IntegrityError), engine.begin() as conn:
            _insert_rule(conn, "tenants")


class TestDowngrade:
    def test_drops_rule_grants_and_keeps_manual_ones(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_grants(engine)
        _upgrade(engine, RULES_REVISION)
        with engine.begin() as conn:
            rule_id = _insert_rule(conn)
            conn.execute(text("INSERT INTO groups (group_name, managed_by) VALUES ('team-gamma', 'scim')"))
            conn.execute(
                text(
                    "INSERT INTO workspace_group_permissions (workspace, group_id, permission, rule_id) "
                    "SELECT 'gamma', id, 'EDIT', :r FROM groups WHERE group_name = 'team-gamma'"
                ),
                {"r": rule_id},
            )

        _downgrade(engine, PREVIOUS_REVISION)

        inspector = inspect(engine)
        assert "workspace_group_rules" not in inspector.get_table_names()
        assert "rule_id" not in {c["name"] for c in inspector.get_columns("workspace_group_permissions")}
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT p.workspace, g.group_name, p.permission FROM workspace_group_permissions p JOIN groups g ON g.id = p.group_id"))
            assert {(r.workspace, r.group_name): r.permission for r in rows} == {("acme", "team-acme"): "EDIT", ("beta", "team-beta"): "READ"}

    def test_round_trip(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_grants(engine)

        _upgrade(engine, RULES_REVISION)
        _downgrade(engine, PREVIOUS_REVISION)
        _upgrade(engine, RULES_REVISION)

        assert _grants(engine) == {("acme", "team-acme"): ("EDIT", None), ("beta", "team-beta"): ("READ", None)}
        fks = {fk["name"] for fk in inspect(engine).get_foreign_keys("workspace_group_permissions")}
        assert "fk_workspace_group_permissions_rule_id" in fks
