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
    assert not store.registered_model_group_repo.extra_filter


def test_grant_records_the_prompt_flag(store):
    store.create_group_prompt_permission(GROUP, "my-prompt", "READ")
    store.create_group_model_permission(GROUP, "my-model", "EDIT")

    assert _rows(store) == [("my-prompt", "READ", True), ("my-model", "EDIT", False)]


def test_prompt_management_sees_only_prompt_grants(store):
    store.create_group_prompt_permission(GROUP, "my-prompt", "READ")
    store.create_group_model_permission(GROUP, "my-model", "EDIT")

    assert [p.name for p in store.get_group_prompts(GROUP)] == ["my-prompt"]
    assert store.prompt_group_repo.list_groups_for_resource("my-prompt") == [(GROUP, "READ")]
    assert store.prompt_group_repo.list_groups_for_resource("my-model") == []
    assert store.prompt_group_repo.list_permissions_for_user_groups(USER)[0].name == "my-prompt"
    assert len(store.prompt_group_repo.list_permissions_for_user_groups(USER)) == 1
    with pytest.raises(MlflowException):
        store.prompt_group_repo.get_group_permission_for_user_resource("my-model", USER)


def test_model_group_management_sees_exactly_what_enforcement_counts(store):
    """A prompt-flagged group grant on a name authorizes that name; the model side can see and revoke it."""
    store.create_group_prompt_permission(GROUP, "shared-name", "EDIT")
    store.create_group_model_permission(GROUP, "my-model", "READ")

    enforced = store.registered_model_group_repo.get_for_user("shared-name", USER)
    assert enforced.permission == "EDIT"
    assert store.registered_model_group_repo.list_groups_for_resource("shared-name") == [(GROUP, enforced.permission)]
    assert sorted(p.name for p in store.get_group_models(GROUP)) == sorted(p.name for p in store.registered_model_group_repo.list_for_user(USER))

    store.update_group_model_permission(GROUP, "shared-name", "READ")
    assert store.registered_model_group_repo.get_for_user("shared-name", USER).permission == "READ"
    store.delete_group_model_permission(GROUP, "shared-name")
    with pytest.raises(MlflowException):
        store.registered_model_group_repo.get_for_user("shared-name", USER)


def test_update_and_revoke(store):
    store.create_group_prompt_permission(GROUP, "my-prompt", "READ")

    store.update_group_prompt_permission(GROUP, "my-prompt", "MANAGE")
    assert _rows(store) == [("my-prompt", "MANAGE", True)]

    store.delete_group_prompt_permission(GROUP, "my-prompt")
    assert _rows(store) == []


def test_update_and_revoke_cannot_reach_a_model_grant(store):
    store.create_group_model_permission(GROUP, "my-model", "READ")

    # Not found, reported like a missing grant of any other kind.
    for call in (lambda: store.update_group_prompt_permission(GROUP, "my-model", "MANAGE"), lambda: store.delete_group_prompt_permission(GROUP, "my-model")):
        with pytest.raises(MlflowException) as exc:
            call()
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"
    assert _rows(store) == [("my-model", "READ", False)]


def _add_rows(store, *rows):
    """Insert group grant rows directly: ``(name, group_name, prompt, workspace)``."""
    from mlflow_oidc_auth.db.models import SqlGroup

    with store.ManagedSessionMaker(read_only=False) as session:
        for name, group_name, prompt, workspace in rows:
            group_id = session.query(SqlGroup.id).filter(SqlGroup.group_name == group_name).scalar()
            session.add(SqlRegisteredModelGroupPermission(name=name, group_id=group_id, permission="READ", prompt=prompt, workspace=workspace))
            session.flush()


@pytest.fixture
def effective(store, monkeypatch):
    """``(prompt permission, registered model permission)`` of USER on a name, as requests resolve them."""
    from mlflow_oidc_auth.utils import permissions

    monkeypatch.setattr(permissions, "store", store)
    # The grant context (issue #460) reads the store through ``grant_context._store``.
    monkeypatch.setattr("mlflow_oidc_auth.utils.grant_context._store", lambda: store)

    def resolve(name):
        permissions.flush_permission_cache()
        prompt, model = permissions.effective_prompt_permission(name, USER), permissions.effective_registered_model_permission(name, USER)
        return (prompt.kind, prompt.permission.name), (model.kind, model.permission.name)

    yield resolve
    permissions.flush_permission_cache()


def test_prompt_update_and_revoke_reach_an_unassigned_duplicate_of_either_flag(store, effective):
    """With workspaces disabled, unassigned (NULL-workspace) rows of one group on one name are one grant.

    Permission checks count both rows whatever their flag, so lowering or revoking through the prompt
    side must reach both — a duplicate left behind would keep granting what was revoked.
    """
    _add_rows(store, ("dup", GROUP, True, None), ("dup", GROUP, False, None))
    assert effective("dup") == (("group", "READ"), ("group", "READ"))

    store.update_group_prompt_permission(GROUP, "dup", "NO_PERMISSIONS")
    assert sorted(_rows(store)) == [("dup", "NO_PERMISSIONS", False), ("dup", "NO_PERMISSIONS", True)]
    assert effective("dup") == (("group", "NO_PERMISSIONS"), ("group", "NO_PERMISSIONS"))

    store.delete_group_prompt_permission(GROUP, "dup")
    assert _rows(store) == []
    assert effective("dup")[0][0] == "fallback" and effective("dup")[1][0] == "fallback"


def test_model_revoke_reaches_an_unassigned_prompt_duplicate(store, effective):
    _add_rows(store, ("dup", GROUP, False, None), ("dup", GROUP, True, None))
    assert effective("dup") == (("group", "READ"), ("group", "READ"))

    store.delete_group_model_permission(GROUP, "dup")

    assert _rows(store) == []
    assert effective("dup")[0][0] == "fallback" and effective("dup")[1][0] == "fallback"


def test_prompt_wipe_and_rename_leave_model_rows(store):
    store.group_repo.create_group("other")
    _add_rows(store, ("shared", GROUP, True, "default"), ("shared", "other", False, "default"))

    store.prompt_group_repo.rename("shared", "renamed")
    assert sorted(_rows(store)) == [("renamed", "READ", True), ("shared", "READ", False)]

    store.prompt_group_repo.wipe("renamed")
    store.prompt_group_repo.wipe("shared")
    assert _rows(store) == [("shared", "READ", False)]


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
