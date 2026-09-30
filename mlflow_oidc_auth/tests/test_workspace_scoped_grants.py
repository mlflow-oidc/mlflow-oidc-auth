"""Grants on name-keyed resources are scoped to the resource's workspace.

MLflow keeps registered models (and prompts), gateway endpoints, secrets and model definitions
unique per ``(workspace, name)``. These tests use a real store and the real permission resolution,
with the caller's workspace set the way the middleware sets it, and pin that a grant in one
workspace never reaches a same-named resource in another — including the three ways it used to:
a grant on the name, the creator grant of a same-named resource created elsewhere, and delete or
rename cascades.
"""

from contextlib import contextmanager

import pytest

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AuthContext

ALICE = "alice@example.com"
VICTOR = "victor@example.com"


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils import permissions, workspace_cache

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ALICE, "Alice")
    s.create_user(VICTOR, "Victor")
    s.populate_groups(["team"])
    s.set_user_groups(ALICE, ["team"])
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    permissions._get_permission_cache().clear()
    workspace_cache.flush_workspace_cache()
    yield s
    permissions._get_permission_cache().clear()
    workspace_cache.flush_workspace_cache()
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@contextmanager
def in_workspace(workspace, username=ALICE):
    """Run as ``username`` on a request naming ``workspace``, as the middleware would set it up."""
    token = set_auth_context(AuthContext(username=username, is_admin=False, workspace=workspace))
    try:
        yield
    finally:
        clear_auth_context(token)


def model_permission(name, username=ALICE):
    from mlflow_oidc_auth.utils import effective_registered_model_permission

    return effective_registered_model_permission(name, username).permission.name


# Each kind: (grant as user, grant as group, resolve, wipe, rename or None)
def _kinds(store):
    from mlflow_oidc_auth.utils.permissions import (
        effective_gateway_endpoint_permission,
        effective_gateway_model_definition_permission,
        effective_gateway_secret_permission,
        effective_prompt_permission,
        effective_registered_model_permission,
    )

    return {
        "registered_model": (
            lambda n, u, p: store.create_registered_model_permission(n, u, p),
            lambda g, n, p: store.create_group_model_permission(g, n, p),
            effective_registered_model_permission,
            store.wipe_registered_model_permissions,
        ),
        "prompt": (
            lambda n, u, p: store.create_registered_model_permission(n, u, p),
            lambda g, n, p: store.create_group_prompt_permission(g, n, p),
            effective_prompt_permission,
            store.wipe_registered_model_permissions,
        ),
        "gateway_endpoint": (
            lambda n, u, p: store.create_gateway_endpoint_permission(n, u, p),
            lambda g, n, p: store.create_group_gateway_endpoint_permission(g, n, p),
            effective_gateway_endpoint_permission,
            store.wipe_gateway_endpoint_permissions,
        ),
        "gateway_secret": (
            lambda n, u, p: store.create_gateway_secret_permission(n, u, p),
            lambda g, n, p: store.create_group_gateway_secret_permission(g, n, p),
            effective_gateway_secret_permission,
            store.wipe_gateway_secret_permissions,
        ),
        "gateway_model_definition": (
            lambda n, u, p: store.create_gateway_model_definition_permission(n, u, p),
            lambda g, n, p: store.create_group_gateway_model_definition_permission(g, n, p),
            effective_gateway_model_definition_permission,
            store.wipe_gateway_model_definition_permissions,
        ),
    }


KINDS = ["registered_model", "prompt", "gateway_endpoint", "gateway_secret", "gateway_model_definition"]


def _clear_cache():
    from mlflow_oidc_auth.utils import permissions

    permissions._get_permission_cache().clear()


class TestAGrantStaysInItsWorkspace:
    @pytest.mark.parametrize("kind", KINDS)
    def test_a_user_grant_does_not_reach_the_same_name_elsewhere(self, store, kind):
        grant_user, _, resolve, _ = _kinds(store)[kind]
        with in_workspace("team-a"):
            grant_user("churn", ALICE, "MANAGE")
            assert resolve("churn", ALICE).permission.name == "MANAGE"
        _clear_cache()
        with in_workspace("team-b"):
            assert resolve("churn", ALICE).permission.name == "NO_PERMISSIONS"

    @pytest.mark.parametrize("kind", ["registered_model", "prompt"])
    def test_a_group_grant_does_not_reach_the_same_name_elsewhere(self, store, kind):
        _, grant_group, resolve, _ = _kinds(store)[kind]
        with in_workspace("team-a"):
            grant_group("team", "churn", "EDIT")
            assert resolve("churn", ALICE).permission.name == "EDIT"
        _clear_cache()
        with in_workspace("team-b"):
            assert resolve("churn", ALICE).permission.name == "NO_PERMISSIONS"

    @pytest.mark.parametrize(
        "kind,getter",
        [
            ("gateway_endpoint", "get_user_groups_gateway_endpoint_permission"),
            ("gateway_secret", "get_user_groups_gateway_secret_permission"),
            ("gateway_model_definition", "get_user_groups_gateway_model_definition_permission"),
        ],
    )
    def test_a_gateway_group_grant_does_not_reach_the_same_name_elsewhere(self, store, kind, getter):
        """Read through the per-group getter the group permission API uses."""
        from mlflow.exceptions import MlflowException

        _, grant_group, _, _ = _kinds(store)[kind]
        with in_workspace("team-a"):
            grant_group("team", "churn", "EDIT")
            assert getattr(store, getter)("churn", "team").permission == "EDIT"
        with in_workspace("team-b"), pytest.raises(MlflowException):
            getattr(store, getter)("churn", "team")

    def test_a_request_naming_no_workspace_is_the_default_workspace(self, store):
        with in_workspace(None):
            store.create_registered_model_permission("churn", ALICE, "READ")
        _clear_cache()
        with in_workspace("default"):
            assert model_permission("churn") == "READ"
        _clear_cache()
        with in_workspace("team-b"):
            assert model_permission("churn") == "NO_PERMISSIONS"

    def test_the_same_name_holds_separate_grants_per_workspace(self, store):
        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "READ")
        with in_workspace("team-b"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        _clear_cache()
        with in_workspace("team-a"):
            assert model_permission("churn") == "READ"
            assert [p.permission for p in store.list_registered_model_permissions(ALICE)] == ["READ"]
        _clear_cache()
        with in_workspace("team-b"):
            assert model_permission("churn") == "MANAGE"


class TestTheCreatorGrantOfASameNamedResourceElsewhere:
    def test_creating_the_same_name_in_your_workspace_gives_nothing_in_another(self, store):
        """A tenant admin of team-b creates "churn" there: the creator grant must not reach team-a's."""
        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        with in_workspace("team-b", VICTOR):
            store.create_registered_model_permission("churn", VICTOR, "MANAGE")  # what grant-on-create writes
        _clear_cache()
        with in_workspace("team-a", VICTOR):
            assert model_permission("churn", VICTOR) == "NO_PERMISSIONS"


class TestCascadesStayInTheirWorkspace:
    @pytest.mark.parametrize("kind", KINDS)
    def test_deleting_in_one_workspace_leaves_the_others_grants(self, store, kind):
        grant_user, grant_group, resolve, wipe = _kinds(store)[kind]
        with in_workspace("team-a"):
            grant_user("churn", ALICE, "MANAGE")
        with in_workspace("team-b"):
            grant_user("churn", ALICE, "READ")
            wipe("churn")
        _clear_cache()
        with in_workspace("team-a"):
            assert resolve("churn", ALICE).permission.name == "MANAGE"

    def test_renaming_in_one_workspace_leaves_the_others_grants(self, store):
        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        with in_workspace("team-b"):
            store.create_registered_model_permission("churn", ALICE, "READ")
            store.rename_registered_model_permissions("churn", "churn-v2")
        _clear_cache()
        with in_workspace("team-a"):
            assert model_permission("churn") == "MANAGE"
            assert model_permission("churn-v2") == "NO_PERMISSIONS"
        _clear_cache()
        with in_workspace("team-b"):
            assert model_permission("churn-v2") == "READ"

    def test_renaming_a_gateway_endpoint_in_one_workspace_leaves_the_others(self, store):
        from mlflow_oidc_auth.utils.permissions import effective_gateway_endpoint_permission

        with in_workspace("team-a"):
            store.create_gateway_endpoint_permission("chat", ALICE, "USE")
        with in_workspace("team-b"):
            store.create_gateway_endpoint_permission("chat", ALICE, "MANAGE")
            store.rename_gateway_endpoint_permissions("chat", "chat-v2")
        _clear_cache()
        with in_workspace("team-a"):
            assert effective_gateway_endpoint_permission("chat", ALICE).permission.name == "USE"


class TestWorkspacesDisabled:
    def test_nothing_is_filtered_and_legacy_grants_still_count(self, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission, SqlUser

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        with store.ManagedSessionMaker(read_only=False) as session:
            alice = session.query(SqlUser).filter(SqlUser.username == ALICE).one()
            session.add(SqlRegisteredModelPermission(name="legacy", user_id=alice.id, permission="EDIT", workspace=None))
        store.create_registered_model_permission("fresh", ALICE, "READ")
        _clear_cache()

        assert model_permission("legacy") == "EDIT"
        assert model_permission("fresh") == "READ"
        assert {p.name: p.workspace for p in store.list_registered_model_permissions(ALICE)} == {"legacy": None, "fresh": "default"}

    def test_a_legacy_grant_matches_nothing_once_workspaces_are_on(self, store):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission, SqlUser

        with store.ManagedSessionMaker(read_only=False) as session:
            alice = session.query(SqlUser).filter(SqlUser.username == ALICE).one()
            session.add(SqlRegisteredModelPermission(name="legacy", user_id=alice.id, permission="EDIT", workspace=None))
        with in_workspace("default"):
            assert model_permission("legacy") == "NO_PERMISSIONS"


class TestWhoHasAccessLists:
    def test_the_per_model_user_list_shows_only_this_workspaces_grants(self, store):
        import asyncio

        from mlflow_oidc_auth.routers.registered_model_permissions import get_registered_model_users

        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        with in_workspace("team-b"):
            store.create_registered_model_permission("churn", VICTOR, "READ")
            listed = asyncio.run(get_registered_model_users(name="churn", _=None))
        assert [(u.name, u.permission) for u in listed] == [(VICTOR, "READ")]

    def test_the_per_model_group_list_shows_only_this_workspaces_grants(self, store):
        with in_workspace("team-a"):
            store.create_group_model_permission("team", "churn", "EDIT")
        with in_workspace("team-b"):
            assert store.registered_model_group_repo.list_groups_for_model("churn") == []
        with in_workspace("team-a"):
            assert store.registered_model_group_repo.list_groups_for_model("churn") == [("team", "EDIT")]
