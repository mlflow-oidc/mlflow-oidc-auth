"""Group pattern grants on registered models and prompts, which share one table (issue #459).

The two repositories differ only in ``extra_filter`` (``prompt`` False / True). Run against a real
SQLite database so the filter is exercised in SQL, not in a mock.
"""

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupRegexPermission
from mlflow_oidc_auth.repository import PromptGroupRegexPermissionRepository, RegisteredModelGroupRegexPermissionRepository

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


def _rows(store):
    model = SqlRegisteredModelGroupRegexPermission
    with store.ManagedSessionMaker() as session:
        return [(r.regex, bool(r.prompt)) for r in session.query(model).order_by(model.id).all()]


def test_store_wires_one_repository_per_kind(store):
    assert type(store.registered_model_group_regex_repo) is RegisteredModelGroupRegexPermissionRepository
    assert type(store.prompt_group_regex_repo) is PromptGroupRegexPermissionRepository
    assert dict(store.registered_model_group_regex_repo.extra_filter) == {"prompt": False}
    assert dict(store.prompt_group_regex_repo.extra_filter) == {"prompt": True}


def test_grant_records_the_kind(store):
    store.create_group_registered_model_regex_permission(GROUP, "^model-.*", 1, "READ")
    store.create_group_prompt_regex_permission("^prompt-.*", 1, "EDIT", GROUP)

    assert _rows(store) == [("^model-.*", False), ("^prompt-.*", True)]


def test_lists_only_their_own_kind(store):
    store.create_group_registered_model_regex_permission(GROUP, "^model-.*", 1, "READ")
    store.create_group_prompt_regex_permission("^prompt-.*", 1, "EDIT", GROUP)
    group_ids = store.get_groups_ids_for_user(USER)

    assert [r.regex for r in store.list_group_registered_model_regex_permissions(GROUP)] == ["^model-.*"]
    assert [r.regex for r in store.list_group_registered_model_regex_permissions_for_groups([GROUP])] == ["^model-.*"]
    assert [r.regex for r in store.list_group_registered_model_regex_permissions_for_groups_ids(group_ids)] == ["^model-.*"]
    assert [r.regex for r in store.list_group_prompt_regex_permissions(GROUP)] == ["^prompt-.*"]
    assert [r.regex for r in store.list_group_prompt_regex_permissions_for_groups([GROUP])] == ["^prompt-.*"]
    assert [r.regex for r in store.list_group_prompt_regex_permissions_for_groups_ids(group_ids)] == ["^prompt-.*"]


def test_prompt_get_update_revoke_cannot_reach_a_model_pattern(store):
    grant_id = store.create_group_registered_model_regex_permission(GROUP, ".*", 1, "READ").id

    for call in (
        lambda: store.get_group_prompt_regex_permission(grant_id, GROUP),
        lambda: store.update_group_prompt_regex_permission(grant_id, ".*", 1, "MANAGE", GROUP),
        lambda: store.delete_group_prompt_regex_permission(grant_id, GROUP),
    ):
        with pytest.raises(MlflowException) as exc:
            call()
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    assert store.get_group_registered_model_regex_permission(GROUP, grant_id).permission == "READ"


def test_model_get_update_revoke_cannot_reach_a_prompt_pattern(store):
    grant_id = store.create_group_prompt_regex_permission(".*", 1, "READ", GROUP).id

    for call in (
        lambda: store.get_group_registered_model_regex_permission(GROUP, grant_id),
        lambda: store.update_group_registered_model_regex_permission(grant_id, GROUP, ".*", 1, "MANAGE"),
        lambda: store.delete_group_registered_model_regex_permission(GROUP, grant_id),
    ):
        with pytest.raises(MlflowException) as exc:
            call()
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    assert store.get_group_prompt_regex_permission(grant_id, GROUP).permission == "READ"


def test_prompt_update_and_revoke(store):
    grant_id = store.create_group_prompt_regex_permission("^old-.*", 1, "READ", GROUP).id

    updated = store.update_group_prompt_regex_permission(grant_id, "^new-.*", 3, "EDIT", GROUP)

    assert (updated.regex, updated.priority, updated.permission) == ("^new-.*", 3, "EDIT")
    assert _rows(store) == [("^new-.*", True)]
    store.delete_group_prompt_regex_permission(grant_id, GROUP)
    assert _rows(store) == []


def test_update_to_an_existing_pattern_is_a_conflict(store):
    store.create_group_prompt_regex_permission("^a-.*", 1, "READ", GROUP)
    grant_id = store.create_group_prompt_regex_permission("^b-.*", 1, "READ", GROUP).id

    with pytest.raises(MlflowException) as exc:
        store.update_group_prompt_regex_permission(grant_id, "^a-.*", 1, "EDIT", GROUP)
    assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"
    assert sorted(regex for regex, _ in _rows(store)) == ["^a-.*", "^b-.*"]


def test_invalid_regex_is_rejected(store):
    with pytest.raises(MlflowException):
        store.create_group_prompt_regex_permission("(", 1, "READ", GROUP)
    with pytest.raises(MlflowException):
        store.create_group_registered_model_regex_permission(GROUP, "(", 1, "READ")
    assert _rows(store) == []


def test_duplicate_pattern_is_rejected_within_a_kind(store):
    store.create_group_prompt_regex_permission(".*", 1, "READ", GROUP)
    store.create_group_registered_model_regex_permission(GROUP, ".*", 1, "READ")

    with pytest.raises(MlflowException) as exc:
        store.create_group_prompt_regex_permission(".*", 2, "EDIT", GROUP)
    assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"
