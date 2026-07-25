"""Fixtures for query-count performance tests (issue #253).

These tests measure ROUND-TRIPS — the number of SQL statements a code path issues —
because that is what the reported production symptom actually is. The auth tables are
tiny (25-150 rows), so per-query cost is negligible and Postgres correctly seq-scans
them; what hurts is issuing many statements per request against a remote database.

Counts are asserted so that both regressions and silent improvements fail loudly and
have to be acknowledged in a diff.

Note: statement counts transfer between SQLite and Postgres, but query PLANS and
pg_stat seq_scan counters do not. Nothing here should be read as a claim about
Postgres planner behaviour.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import event

from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

# SQLite connection setup statements that are not application queries.
_IGNORED_PREFIXES = ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")


class QueryCounter:
    """Counts SQL statements issued while active."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    @property
    def count(self) -> int:
        return len(self.statements)

    def for_table(self, table: str) -> int:
        """How many statements referenced ``table``."""
        return sum(1 for s in self.statements if table in s.lower())

    def reset(self) -> None:
        self.statements.clear()

    def report(self) -> str:
        """Human-readable dump, useful when an assertion fails."""
        lines = [f"{len(self.statements)} statement(s):"]
        for i, stmt in enumerate(self.statements, 1):
            lines.append(f"  {i:2d}. {' '.join(stmt.split())[:140]}")
        return "\n".join(lines)


@pytest.fixture
def store(tmp_path: Path):
    """A real SqlAlchemyStore backed by a temporary SQLite database."""
    db_path = tmp_path / "auth.db"
    db_uri = f"sqlite:///{db_path}"
    s = SqlAlchemyStore()
    s.init_db(db_uri)
    return s


@pytest.fixture
def counter(store):
    """Attach a statement counter to the store's engine.

    Yields a QueryCounter that is already recording; call ``reset()`` after any
    setup you do not want to measure.
    """
    c = QueryCounter()

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        stripped = statement.lstrip()
        if not stripped.upper().startswith(_IGNORED_PREFIXES):
            c.statements.append(statement)

    engine = store.engine
    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield c
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)


@pytest.fixture
def seeded_store(store):
    """A store with a user in several groups, for group-resolution measurements.

    Returns (store, username, group_names).
    """
    username = "alice@example.com"
    group_names = [f"group-{i}" for i in range(1, 9)]  # 8 groups
    store.create_user(username, "pw", "Alice")
    store.populate_groups(group_names)
    store.set_user_groups(username, group_names)
    return store, username, group_names
