"""Regex grants come back from the database in ``(priority, id)`` order (issue #459).

Regex grants used to be ordered by ``priority`` alone, so equal-priority grants came back in
whatever physical row order the database chose. They are now ordered by ``(priority, id)``. Which
equal-priority match *decides* is a separate rule — permission rank, see
``tests/utils/test_regex_tie_break.py`` — but the row order still fixes which of equally ranked
matches is returned and logged, and it must not depend on the backend.

Rows are inserted with explicit ids, the higher id first, so insertion order disagrees with id
order. SQLite happens to scan in rowid order, which would hide a missing tie-break, so each test
also asserts the ``ORDER BY`` the repository sends to the database.

Covered: the shared base classes (via experiments) and the registered-model / prompt
repositories, which filter every list on the ``prompt`` flag (their ``extra_filter``).
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import event

from mlflow_oidc_auth.db.models import (
    SqlExperimentGroupRegexPermission,
    SqlExperimentRegexPermission,
    SqlRegisteredModelGroupRegexPermission,
    SqlRegisteredModelRegexPermission,
)
from mlflow_oidc_auth.utils.permissions import _match_regex_permission

LOW_ID, HIGH_ID = 10, 20
USER = "alice@example.com"
GROUP = "team"


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(USER, "Alice")
    s.group_repo.create_group(GROUP)
    s.add_user_to_group(USER, GROUP)
    yield s
    s.engine.dispose()


def _user_id(store) -> int:
    return store.user_repo.get(USER).id


def _group_ids(store) -> list:
    return store.get_groups_ids_for_user(USER)


def _insert_tied(store, model_class, owner: dict, **extra) -> None:
    """Two grants matching ``team-exp`` at equal priority, the higher id inserted first."""
    rows = [
        model_class(id=HIGH_ID, regex="^team-.*", priority=1, permission="MANAGE", workspace="*", **owner, **extra),
        model_class(id=LOW_ID, regex="^team-exp$", priority=1, permission="READ", workspace="*", **owner, **extra),
    ]
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


def _assert_ordered_by_priority_then_id(store, model_class, list_fn) -> None:
    regexes, statements = _select_statements(store, list_fn)

    assert [r.id for r in regexes] == [LOW_ID, HIGH_ID]

    table = model_class.__tablename__
    order_bys = [s.split("ORDER BY", 1)[1] for s in statements if f"FROM {table}" in s and "ORDER BY" in s]
    assert order_bys, f"no ordered SELECT on {table} in {statements}"
    for clause in order_bys:
        normalized = " ".join(clause.split())
        assert normalized.startswith(f"{table}.priority, {table}.id"), normalized


# --- shared base classes (experiment, scorer, gateway, workspace repositories) ---------------


def test_user_regex_equal_priority_ordered_by_id(store):
    _insert_tied(store, SqlExperimentRegexPermission, {"user_id": _user_id(store)})
    _assert_ordered_by_priority_then_id(store, SqlExperimentRegexPermission, lambda: store.list_experiment_regex_permissions(USER))


def test_group_regex_equal_priority_ordered_by_id(store):
    group_ids = _group_ids(store)
    _insert_tied(store, SqlExperimentGroupRegexPermission, {"group_id": group_ids[0]})
    _assert_ordered_by_priority_then_id(
        store, SqlExperimentGroupRegexPermission, lambda: store.list_group_experiment_regex_permissions_for_groups_ids(group_ids)
    )


# --- registered models and prompts (repositories filtering on the prompt flag) -----------------


@pytest.mark.parametrize("prompt", [False, True], ids=["registered_model", "prompt"])
def test_model_user_regex_equal_priority_ordered_by_id(store, prompt):
    _insert_tied(store, SqlRegisteredModelRegexPermission, {"user_id": _user_id(store)}, prompt=prompt)
    repo = store.prompt_regex_repo if prompt else store.registered_model_regex_repo
    _assert_ordered_by_priority_then_id(store, SqlRegisteredModelRegexPermission, lambda: repo.list_regex_for_user(USER))


@pytest.mark.parametrize("prompt", [False, True], ids=["registered_model", "prompt"])
@pytest.mark.parametrize("method", ["list_permissions_for_group", "list_permissions_for_groups", "list_permissions_for_groups_ids"])
def test_model_group_regex_equal_priority_ordered_by_id(store, prompt, method):
    group_ids = _group_ids(store)
    _insert_tied(store, SqlRegisteredModelGroupRegexPermission, {"group_id": group_ids[0]}, prompt=prompt)
    repo = store.prompt_group_regex_repo if prompt else store.registered_model_group_regex_repo
    argument = {"list_permissions_for_group": GROUP, "list_permissions_for_groups": [GROUP], "list_permissions_for_groups_ids": group_ids}[method]
    _assert_ordered_by_priority_then_id(store, SqlRegisteredModelGroupRegexPermission, lambda: getattr(repo, method)(argument))


def test_regex_lower_priority_value_still_wins_over_lower_id(store):
    """Priority decides first: a better priority wins over a lower id and a higher rank alike."""
    user_id = _user_id(store)
    with store.ManagedSessionMaker(read_only=False) as session:
        session.add(SqlExperimentRegexPermission(id=HIGH_ID, regex="^team-.*", priority=0, user_id=user_id, permission="MANAGE", workspace="*"))
        session.flush()
        session.add(SqlExperimentRegexPermission(id=LOW_ID, regex="^team-exp$", priority=1, user_id=user_id, permission="READ", workspace="*"))
        session.flush()

    regexes = store.list_experiment_regex_permissions(USER)

    assert [r.id for r in regexes] == [HIGH_ID, LOW_ID]
    assert _match_regex_permission(regexes, "team-exp", "name") == "MANAGE"


def test_list_all_regex_equal_priority_ordered_by_id(store):
    """The admin listing of every pattern uses the same order."""
    _insert_tied(store, SqlExperimentRegexPermission, {"user_id": _user_id(store)})
    regexes, statements = _select_statements(store, store.experiment_regex_repo.list)

    assert [r.id for r in regexes] == [LOW_ID, HIGH_ID]
    table = SqlExperimentRegexPermission.__tablename__
    assert any(" ".join(s.split("ORDER BY", 1)[1].split()).startswith(f"{table}.priority, {table}.id") for s in statements if "ORDER BY" in s)


# --- the shared order helper -------------------------------------------------------------------


def _rule(id_, priority, permission, regex=".*"):
    return SimpleNamespace(id=id_, priority=priority, permission=permission, regex=regex, workspace="*")


def test_in_regex_grant_order_returns_ordered_input_unsorted():
    """Already-ordered input (what the repositories return) is checked, not copied or sorted."""
    from mlflow_oidc_auth.permissions import in_regex_grant_order

    rules = [_rule(LOW_ID, 1, "READ"), _rule(HIGH_ID, 1, "MANAGE"), _rule(5, 2, "EDIT")]

    assert in_regex_grant_order(rules) is rules


def test_in_regex_grant_order_sorts_unordered_input():
    from mlflow_oidc_auth.permissions import in_regex_grant_order

    rules = [_rule(HIGH_ID, 1, "MANAGE"), _rule(5, 2, "EDIT"), _rule(LOW_ID, 1, "READ")]

    assert [r.id for r in in_regex_grant_order(rules)] == [LOW_ID, HIGH_ID, 5]
    assert [r.id for r in rules] == [HIGH_ID, 5, LOW_ID]  # the caller's list is not reordered
