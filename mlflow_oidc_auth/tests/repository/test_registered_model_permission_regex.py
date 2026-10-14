"""User pattern grants on registered models and prompts, which share one table (issue #459).

The two repositories differ only in ``extra_filter`` (``prompt`` False / True). Run against a real
SQLite database so the filter is exercised in SQL, not in a mock.
"""

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.db.models import SqlRegisteredModelRegexPermission
from mlflow_oidc_auth.repository import PromptPermissionRegexRepository, RegisteredModelPermissionRegexRepository

USER = "alice@example.com"


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(USER, "Alice")
    yield s
    s.engine.dispose()


def _rows(store):
    with store.ManagedSessionMaker() as session:
        return [(r.regex, bool(r.prompt)) for r in session.query(SqlRegisteredModelRegexPermission).order_by(SqlRegisteredModelRegexPermission.id).all()]


def test_store_wires_one_repository_per_kind(store):
    assert type(store.registered_model_regex_repo) is RegisteredModelPermissionRegexRepository
    assert type(store.prompt_regex_repo) is PromptPermissionRegexRepository
    assert dict(store.registered_model_regex_repo.extra_filter) == {"prompt": False}
    assert dict(store.prompt_regex_repo.extra_filter) == {"prompt": True}


def test_grant_records_the_kind(store):
    store.create_registered_model_regex_permission("^model-.*", 1, "READ", USER)
    store.create_prompt_regex_permission("^prompt-.*", 1, "EDIT", USER)

    assert _rows(store) == [("^model-.*", False), ("^prompt-.*", True)]


def test_same_pattern_may_exist_once_per_kind(store):
    store.create_registered_model_regex_permission(".*", 1, "READ", USER)
    store.create_prompt_regex_permission(".*", 1, "READ", USER)

    with pytest.raises(MlflowException) as exc:
        store.create_prompt_regex_permission(".*", 2, "EDIT", USER)
    assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


def test_lists_only_their_own_kind(store):
    store.create_registered_model_regex_permission("^model-.*", 1, "READ", USER)
    store.create_prompt_regex_permission("^prompt-.*", 1, "EDIT", USER)

    assert [r.regex for r in store.list_registered_model_regex_permissions(USER)] == ["^model-.*"]
    assert [r.regex for r in store.list_prompt_regex_permissions(USER)] == ["^prompt-.*"]
    assert [r.regex for r in store.registered_model_regex_repo.list()] == ["^model-.*"]
    assert [r.regex for r in store.prompt_regex_repo.list()] == ["^prompt-.*"]


@pytest.mark.parametrize("own, other", [("registered_model", "prompt"), ("prompt", "registered_model")])
def test_get_update_revoke_cannot_reach_the_other_kind(store, own, other):
    create = {"registered_model": store.create_registered_model_regex_permission, "prompt": store.create_prompt_regex_permission}
    get = {"registered_model": store.get_registered_model_regex_permission, "prompt": store.get_prompt_regex_permission}
    update = {"registered_model": store.update_registered_model_regex_permission, "prompt": store.update_prompt_regex_permission}
    delete = {"registered_model": store.delete_registered_model_regex_permission, "prompt": store.delete_prompt_regex_permission}
    grant_id = create[other](".*", 1, "READ", USER).id

    for call in (
        lambda: get[own](grant_id, USER),
        lambda: update[own](grant_id, ".*", 1, "MANAGE", USER),
        lambda: delete[own](grant_id, USER),
    ):
        with pytest.raises(MlflowException) as exc:
            call()
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    assert get[other](grant_id, USER).permission == "READ"


@pytest.mark.parametrize("kind", ["registered_model", "prompt"])
def test_update_and_revoke(store, kind):
    create = getattr(store, f"create_{kind}_regex_permission")
    update = getattr(store, f"update_{kind}_regex_permission")
    delete = getattr(store, f"delete_{kind}_regex_permission")
    get = getattr(store, f"get_{kind}_regex_permission")
    grant_id = create("^old-.*", 1, "READ", USER).id

    updated = update(grant_id, "^new-.*", 2, "EDIT", USER)

    assert (updated.regex, updated.priority, updated.permission) == ("^new-.*", 2, "EDIT")
    assert get(grant_id, USER).regex == "^new-.*"
    delete(grant_id, USER)
    with pytest.raises(MlflowException):
        get(grant_id, USER)


@pytest.mark.parametrize("kind", ["registered_model", "prompt"])
def test_update_to_an_existing_pattern_is_a_conflict(store, kind):
    create = getattr(store, f"create_{kind}_regex_permission")
    update = getattr(store, f"update_{kind}_regex_permission")
    create("^a-.*", 1, "READ", USER)
    grant_id = create("^b-.*", 1, "READ", USER).id

    with pytest.raises(MlflowException) as exc:
        update(grant_id, "^a-.*", 1, "EDIT", USER)
    assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"
    assert sorted(regex for regex, _ in _rows(store)) == ["^a-.*", "^b-.*"]


def test_invalid_regex_is_rejected(store):
    with pytest.raises(MlflowException):
        store.create_prompt_regex_permission("(", 1, "READ", USER)
    assert _rows(store) == []


def test_unknown_user_lists_nothing(store):
    assert store.list_prompt_regex_permissions("nobody@example.com") == []
    assert store.list_registered_model_regex_permissions("nobody@example.com") == []
