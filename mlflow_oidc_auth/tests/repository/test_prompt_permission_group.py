"""Group grants on prompts: the registered model group grant table, rows flagged ``prompt=True`` (issue #459).

Run against a real SQLite database so ``extra_filter`` is exercised in SQL, not in a mock.
"""

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission
from mlflow_oidc_auth.repository import PromptPermissionGroupRepository

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
    model = SqlRegisteredModelGroupPermission
    with store.ManagedSessionMaker() as session:
        return [(r.name, r.permission, bool(r.prompt)) for r in session.query(model).order_by(model.id).all()]


def test_store_wires_the_prompt_repository(store):
    assert type(store.prompt_group_repo) is PromptPermissionGroupRepository
    assert dict(store.prompt_group_repo.extra_filter) == {"prompt": True}
    assert dict(store.registered_model_group_repo.extra_filter) == {"prompt": False}


def test_grant_records_the_prompt_flag(store):
    store.create_group_prompt_permission(GROUP, "my-prompt", "READ")
    store.create_group_model_permission(GROUP, "my-model", "EDIT")

    assert _rows(store) == [("my-prompt", "READ", True), ("my-model", "EDIT", False)]


def test_each_kind_lists_only_its_own_group_grants(store):
    store.create_group_prompt_permission(GROUP, "my-prompt", "READ")
    store.create_group_model_permission(GROUP, "my-model", "EDIT")

    assert [p.name for p in store.get_group_prompts(GROUP)] == ["my-prompt"]
    assert [p.name for p in store.get_group_models(GROUP)] == ["my-model"]
    assert store.prompt_group_repo.list_groups_for_resource("my-prompt") == [(GROUP, "READ")]
    assert store.prompt_group_repo.list_groups_for_resource("my-model") == []
    assert store.registered_model_group_repo.list_groups_for_resource("my-model") == [(GROUP, "EDIT")]
    assert store.registered_model_group_repo.list_groups_for_resource("my-prompt") == []


def test_update_and_revoke(store):
    store.create_group_prompt_permission(GROUP, "my-prompt", "READ")

    store.update_group_prompt_permission(GROUP, "my-prompt", "MANAGE")
    assert _rows(store) == [("my-prompt", "MANAGE", True)]

    store.delete_group_prompt_permission(GROUP, "my-prompt")
    assert _rows(store) == []


def test_update_and_revoke_cannot_reach_a_model_grant(store):
    store.create_group_model_permission(GROUP, "my-model", "READ")

    # Not found, reported like a missing group grant of any other kind.
    with pytest.raises(MlflowException, match="No row was found"):
        store.update_group_prompt_permission(GROUP, "my-model", "MANAGE")
    with pytest.raises(MlflowException, match="No row was found"):
        store.delete_group_prompt_permission(GROUP, "my-model")
    assert _rows(store) == [("my-model", "READ", False)]


def test_model_endpoints_cannot_update_or_revoke_a_prompt_grant(store):
    store.create_group_prompt_permission(GROUP, "my-prompt", "READ")

    with pytest.raises(MlflowException, match="No row was found"):
        store.update_group_model_permission(GROUP, "my-prompt", "MANAGE")
    with pytest.raises(MlflowException, match="No row was found"):
        store.delete_group_model_permission(GROUP, "my-prompt")
    assert _rows(store) == [("my-prompt", "READ", True)]


def test_a_name_holds_one_group_grant_whatever_its_kind(store):
    """The table is unique per (workspace, name, group): the other kind's create is refused, not merged."""
    store.create_group_prompt_permission(GROUP, "shared-name", "READ")

    with pytest.raises(MlflowException) as exc:
        store.create_group_model_permission(GROUP, "shared-name", "MANAGE")
    assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"
    assert _rows(store) == [("shared-name", "READ", True)]


def test_unknown_group_is_reported(store):
    with pytest.raises(MlflowException):
        store.create_group_prompt_permission("no-such-group", "my-prompt", "READ")


def test_permission_lookup_counts_a_prompt_grant_on_its_name(store):
    """Exact grants on a name count for that name whatever the flag, as before (no filter on lookup)."""
    store.create_group_prompt_permission(GROUP, "shared-name", "EDIT")

    assert store.prompt_group_repo.get_group_permission_for_user_resource("shared-name", USER).permission == "EDIT"
    assert store.registered_model_group_repo.get_for_user("shared-name", USER).permission == "EDIT"
