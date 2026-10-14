"""Equal-priority regex grants resolve in id order (issue #459).

Regex grants used to be ordered by ``priority`` alone, so two matching grants with the same
priority came back in whatever physical row order the database chose, and the first match — the
effective permission — was not deterministic. They are now ordered by ``(priority, id)``: of two
equal-priority matches, the older grant (lower id) wins.

Rows are inserted with explicit ids, the higher id first, so insertion order disagrees with id
order. SQLite happens to scan in rowid order, which would hide a missing tie-break, so each test
also asserts the ``ORDER BY`` the repository sends to the database.
"""

import pytest
from sqlalchemy import event

from mlflow_oidc_auth.db.models import SqlExperimentGroupRegexPermission, SqlExperimentRegexPermission
from mlflow_oidc_auth.utils.permissions import _match_regex_permission

LOW_ID, HIGH_ID = 10, 20


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield s
    s.engine.dispose()


def _insert(store, rows) -> None:
    with store.ManagedSessionMaker(read_only=False) as session:
        for row in rows:
            session.add(row)
            session.flush()


def _select_statements(store, fn):
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(store.engine, "before_cursor_execute", capture)
    try:
        result = fn()
    finally:
        event.remove(store.engine, "before_cursor_execute", capture)
    return result, statements


def _assert_ordered_by_priority_then_id(statements, table: str) -> None:
    order_bys = [s.split("ORDER BY", 1)[1] for s in statements if f"FROM {table}" in s and "ORDER BY" in s]
    assert order_bys, f"no ordered SELECT on {table} in {statements}"
    for clause in order_bys:
        normalized = " ".join(clause.split())
        assert normalized.startswith(f"{table}.priority, {table}.id"), normalized


def test_user_regex_equal_priority_ordered_by_id(store):
    store.create_user("alice@example.com", "Alice")
    user_id = store.user_repo.get("alice@example.com").id
    # Higher id inserted first, both match "team-exp", same priority.
    _insert(
        store,
        [
            SqlExperimentRegexPermission(id=HIGH_ID, regex="^team-.*", priority=1, user_id=user_id, permission="MANAGE", workspace="*"),
            SqlExperimentRegexPermission(id=LOW_ID, regex="^team-exp$", priority=1, user_id=user_id, permission="READ", workspace="*"),
        ],
    )

    regexes, statements = _select_statements(store, lambda: store.list_experiment_regex_permissions("alice@example.com"))

    assert [r.id for r in regexes] == [LOW_ID, HIGH_ID]
    assert _match_regex_permission(regexes, "team-exp", "experiment") == "READ"
    _assert_ordered_by_priority_then_id(statements, SqlExperimentRegexPermission.__tablename__)


def test_group_regex_equal_priority_ordered_by_id(store):
    store.create_user("bob@example.com", "Bob")
    store.group_repo.create_group("team")
    store.add_user_to_group("bob@example.com", "team")
    group_ids = store.get_groups_ids_for_user("bob@example.com")
    _insert(
        store,
        [
            SqlExperimentGroupRegexPermission(id=HIGH_ID, regex="^team-.*", priority=1, group_id=group_ids[0], permission="MANAGE", workspace="*"),
            SqlExperimentGroupRegexPermission(id=LOW_ID, regex="^team-exp$", priority=1, group_id=group_ids[0], permission="READ", workspace="*"),
        ],
    )

    regexes, statements = _select_statements(store, lambda: store.list_group_experiment_regex_permissions_for_groups_ids(group_ids))

    assert [r.id for r in regexes] == [LOW_ID, HIGH_ID]
    assert _match_regex_permission(regexes, "team-exp", "experiment") == "READ"
    _assert_ordered_by_priority_then_id(statements, SqlExperimentGroupRegexPermission.__tablename__)


def test_regex_lower_priority_value_still_wins_over_lower_id(store):
    """The tie-break applies to ties only: priority still decides first."""
    store.create_user("carol@example.com", "Carol")
    user_id = store.user_repo.get("carol@example.com").id
    _insert(
        store,
        [
            SqlExperimentRegexPermission(id=HIGH_ID, regex="^team-.*", priority=0, user_id=user_id, permission="MANAGE", workspace="*"),
            SqlExperimentRegexPermission(id=LOW_ID, regex="^team-exp$", priority=1, user_id=user_id, permission="READ", workspace="*"),
        ],
    )

    regexes = store.list_experiment_regex_permissions("carol@example.com")

    assert [r.id for r in regexes] == [HIGH_ID, LOW_ID]
    assert _match_regex_permission(regexes, "team-exp", "experiment") == "MANAGE"
