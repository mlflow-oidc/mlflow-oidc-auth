"""``users.is_service_account`` migration (issue #151): dialect-portable backfill.

The original migration backfilled and reverted the column with raw ``UPDATE ... = FALSE`` /
``DELETE ... = TRUE`` SQL. SQLite and PostgreSQL accept those literals; SQL Server does not, since
T-SQL has no boolean literal keywords. The migration now builds the UPDATE/DELETE through
SQLAlchemy Core (``sa.table`` + ``.update()``/``.delete()``) so each dialect renders the bound
value the way it expects.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped
otherwise) — the same fixture as the Phase 0 migration tests. A separate, connection-free test
below compiles the migration's statements for the ``mssql`` dialect to catch a regression back to
a bare ``TRUE``/``FALSE`` literal without needing a live SQL Server.
"""

import importlib.util
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.dialects import mssql

from mlflow_oidc_auth.db.utils import _get_alembic_config
from mlflow_oidc_auth.tests.db.test_phase0_migration import (  # noqa: F401  (fixtures)
    _downgrade,
    _sqlite_uri,
    _upgrade,
    db_uri,
    engine,
)

PREVIOUS_REVISION = "913635c83867"
SERVICE_ACCOUNTS_REVISION = "8c1cf75c5314"

# The revision file's name starts with a digit (the revision id), so it cannot be imported with a
# normal dotted path — load it directly from its path instead, the way Alembic itself would.
_MIGRATION_PATH = Path(__file__).resolve().parents[2] / "db" / "migrations" / "versions" / f"{SERVICE_ACCOUNTS_REVISION}_add_service_accounts.py"
_spec = importlib.util.spec_from_file_location("service_accounts_migration", _MIGRATION_PATH)
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)
users_table = _migration.users_table

_INSERT_USER = text("INSERT INTO users (username, display_name, password_hash, is_admin) VALUES (:u, :u, :h, :a)")


def _columns(engine):
    return {c["name"]: c for c in inspect(engine).get_columns("users")}


class TestRevisionChain:
    def test_service_accounts_follows_add_prompt(self, tmp_path):
        script = ScriptDirectory.from_config(_get_alembic_config(_sqlite_uri(tmp_path))).get_revision(SERVICE_ACCOUNTS_REVISION)
        assert script.down_revision == PREVIOUS_REVISION


class TestUpgrade:
    def test_adds_a_nullable_column(self, engine):
        _upgrade(engine, SERVICE_ACCOUNTS_REVISION)

        columns = _columns(engine)
        assert "is_service_account" in columns
        assert columns["is_service_account"]["nullable"] is True

    def test_existing_users_are_backfilled_to_false(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        with engine.begin() as conn:
            conn.execute(_INSERT_USER, {"u": "alice@example.com", "h": "not-a-real-hash", "a": True})
            conn.execute(_INSERT_USER, {"u": "bob@example.com", "h": "not-a-real-hash", "a": False})

        _upgrade(engine, SERVICE_ACCOUNTS_REVISION)

        with engine.connect() as conn:
            flags = conn.execute(text("SELECT is_service_account FROM users ORDER BY username")).scalars().all()
        assert [bool(f) for f in flags] == [False, False]

    def test_backfill_does_not_fail_on_an_empty_table(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)

        _upgrade(engine, SERVICE_ACCOUNTS_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 0


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        _upgrade(engine, SERVICE_ACCOUNTS_REVISION)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account) VALUES (:u, :u, :h, :a, :s)"),
                {"u": "human@example.com", "h": "not-a-real-hash", "a": False, "s": False},
            )
            conn.execute(
                text("INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account) VALUES (:u, :u, :h, :a, :s)"),
                {"u": "svc@example.com", "h": "not-a-real-hash", "a": False, "s": True},
            )

        _downgrade(engine, PREVIOUS_REVISION)

        assert "is_service_account" not in _columns(engine)
        with engine.connect() as conn:
            # The downgrade removes only rows that were service accounts.
            assert conn.execute(text("SELECT username FROM users")).scalars().all() == ["human@example.com"]

        _upgrade(engine, SERVICE_ACCOUNTS_REVISION)
        assert "is_service_account" in _columns(engine)


class TestMssqlCompilation:
    """No live SQL Server needed: compile the statements the migration issues and check them.

    T-SQL has no ``TRUE``/``FALSE`` literal keywords, so a bare one in the compiled SQL means the
    statement would fail against a real SQL Server before it ever runs there.
    """

    def test_update_statement_has_no_bare_boolean_literal(self):
        stmt = users_table.update().values(is_service_account=False)
        compiled = str(stmt.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))

        assert "TRUE" not in compiled.upper() and "FALSE" not in compiled.upper()
        assert "IS_SERVICE_ACCOUNT=0" in compiled.upper().replace(" ", "")

    def test_delete_statement_has_no_bare_boolean_literal(self):
        stmt = users_table.delete().where(users_table.c.is_service_account == True)  # noqa: E712
        compiled = str(stmt.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))

        assert "TRUE" not in compiled.upper() and "FALSE" not in compiled.upper()
        assert "IS_SERVICE_ACCOUNT=1" in compiled.upper().replace(" ", "")
