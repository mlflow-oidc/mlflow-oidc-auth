"""Group ownership migration (#323 review): single head, backfill, round trip.

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

SAML_REVISION = "b1e2f3a45678"
GROUP_OWNERSHIP_REVISION = "e4f5a6b7c8d9"


def _columns(engine):
    return {c["name"]: c for c in inspect(engine).get_columns("groups")}


class TestRevisionChain:
    def test_follows_saml(self, tmp_path):
        # Another revision in this stack also builds on the SAML head; whichever lands second is
        # re-chained onto the first, so this only pins that SAML is an ancestor.
        script_dir = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path)))
        ancestors = {rev.revision for rev in script_dir.iterate_revisions(GROUP_OWNERSHIP_REVISION, "base")}
        assert SAML_REVISION in ancestors

    def test_exactly_one_head(self, tmp_path):
        heads = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_heads()
        assert len(heads) == 1, f"expected a single head, got {heads}"


class TestUpgrade:
    def test_existing_groups_become_manual(self, engine):
        _upgrade(engine, SAML_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO groups (group_name) VALUES ('legacy')"))

        _upgrade(engine, GROUP_OWNERSHIP_REVISION)

        column = _columns(engine)["managed_by"]
        assert column["nullable"] is False
        with engine.connect() as conn:
            assert conn.execute(text("SELECT managed_by FROM groups WHERE group_name = 'legacy'")).scalar() == "manual"

    def test_new_rows_default_to_manual(self, engine):
        _upgrade(engine, GROUP_OWNERSHIP_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO groups (group_name) VALUES ('fresh')"))
            conn.execute(text("INSERT INTO groups (group_name, managed_by) VALUES ('dir', 'scim')"))
        with engine.connect() as conn:
            rows = dict(conn.execute(text("SELECT group_name, managed_by FROM groups")).all())
        assert rows == {"fresh": "manual", "dir": "scim"}


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        _upgrade(engine, GROUP_OWNERSHIP_REVISION)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO groups (group_name, managed_by, external_id) VALUES ('dir', 'scim', 'ext-1')"))

        _downgrade(engine, SAML_REVISION)

        columns = _columns(engine)
        assert "managed_by" not in columns
        assert "external_id" in columns, "the downgrade must only remove what this revision added"
        with engine.connect() as conn:
            assert conn.execute(text("SELECT external_id FROM groups WHERE group_name = 'dir'")).scalar() == "ext-1"

        _upgrade(engine, GROUP_OWNERSHIP_REVISION)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT managed_by FROM groups WHERE group_name = 'dir'")).scalar() == "manual"
