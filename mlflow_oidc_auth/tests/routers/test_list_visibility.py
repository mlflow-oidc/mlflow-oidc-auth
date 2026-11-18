"""RESTRICT_USER_AND_GROUP_LISTING: who a caller sees in the user, service account, group and workspace member lists.

Runs against a real SQLite store: the visible set is computed from the workspace grants it holds.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.dependencies import check_workspace_member_list_permission
from mlflow_oidc_auth.permissions import MANAGE, READ
from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
from mlflow_oidc_auth.routers.users import users_router
from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
from mlflow_oidc_auth.utils import get_is_admin, get_username

CALLER = "caller@example.com"
#: Workspace grants seeded below: the caller manages "ws-managed" and only reads "ws-read".
WORKSPACE_PERMISSIONS = {"ws-managed": MANAGE, "ws-read": READ}


@pytest.fixture
def store(tmp_path):
    db = SqlAlchemyStore()
    db.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    for username in (CALLER, "alice@example.com", "bob@example.com", "carol@example.com"):
        db.create_user(username, username)
    for account in ("svc-managed", "svc-read"):
        db.create_user(account, account, is_service_account=True)
    db.populate_groups(["own-group", "team-managed", "team-read", "unrelated"])
    db.add_user_to_group(CALLER, "own-group")
    db.create_workspace_permission("ws-managed", CALLER, "MANAGE")
    db.create_workspace_permission("ws-managed", "alice@example.com", "READ")
    db.create_workspace_permission("ws-managed", "svc-managed", "EDIT")
    db.create_workspace_group_permission("ws-managed", "team-managed", "READ")
    db.create_workspace_permission("ws-read", CALLER, "READ")
    db.create_workspace_permission("ws-read", "bob@example.com", "MANAGE")
    db.create_workspace_permission("ws-read", "svc-read", "READ")
    db.create_workspace_group_permission("ws-read", "team-read", "READ")
    with patch("mlflow_oidc_auth.store.store", db):
        yield db


@pytest.fixture
def workspaces(monkeypatch):
    """Workspaces on, with the caller's effective permission taken from WORKSPACE_PERMISSIONS."""
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    lookup = MagicMock(side_effect=lambda username, workspace: WORKSPACE_PERMISSIONS.get(workspace) if username == CALLER else None)
    with patch("mlflow_oidc_auth.utils.directory_visibility.get_workspace_permission_cached", lookup):
        yield lookup


def _get(router, path: str, is_admin: bool, **params):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_username] = lambda: CALLER
    app.dependency_overrides[get_is_admin] = lambda: is_admin
    with TestClient(app) as client:
        return client.get(path, params=params)


def _users(is_admin: bool = False, **params) -> list[str]:
    response = _get(users_router, "/api/2.0/mlflow/users", is_admin, **params)
    assert response.status_code == 200
    return response.json()


def _groups(is_admin: bool = False, **params) -> list[str]:
    response = _get(group_permissions_router, "/api/2.0/mlflow/permissions/groups", is_admin, **params)
    assert response.status_code == 200
    return response.json()


EVERY_USER = sorted([CALLER, "alice@example.com", "bob@example.com", "carol@example.com"])
EVERY_ACCOUNT = ["svc-managed", "svc-read"]
EVERY_GROUP = ["own-group", "team-managed", "team-read", "unrelated"]


class TestSettingOff:
    """The default: every caller sees everyone, as before the setting existed."""

    @pytest.mark.parametrize("is_admin", [False, True])
    def test_everyone_is_listed(self, store, workspaces, monkeypatch, is_admin):
        monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", False)
        assert sorted(_users(is_admin)) == EVERY_USER
        assert sorted(_users(is_admin, service="true")) == EVERY_ACCOUNT
        assert sorted(_groups(is_admin)) == EVERY_GROUP
        workspaces.assert_not_called()


class TestSettingOn:
    @pytest.fixture(autouse=True)
    def _restrict(self, monkeypatch):
        monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", True)

    def test_admins_see_everyone(self, store, workspaces):
        assert sorted(_users(is_admin=True)) == EVERY_USER
        assert sorted(_users(is_admin=True, service="true")) == EVERY_ACCOUNT
        assert sorted(_groups(is_admin=True)) == EVERY_GROUP

    def test_without_workspaces_a_user_sees_only_itself_and_its_groups(self, store, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        assert _users() == [CALLER]
        assert _users(service="true") == []
        assert _groups() == ["own-group"]

    def test_a_workspace_manager_also_sees_that_workspace_s_members(self, store, workspaces):
        """Members of a workspace the caller only reads stay hidden: bob, svc-read, team-read."""
        assert sorted(_users()) == sorted([CALLER, "alice@example.com"])
        assert _users(service="true") == ["svc-managed"]
        assert sorted(_groups()) == ["own-group", "team-managed"]

    def test_an_unresolvable_workspace_permission_hides_its_members(self, store, workspaces):
        workspaces.side_effect = lambda username, workspace: None
        assert _users() == [CALLER]
        assert _groups() == ["own-group"]

    def test_totals_count_only_what_the_caller_sees(self, store, workspaces):
        response = _get(users_router, "/api/2.0/mlflow/users", False, limit=1)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.headers["X-Total-Count"] == "2"
        response = _get(group_permissions_router, "/api/2.0/mlflow/permissions/groups", False, limit=1)
        assert response.headers["X-Total-Count"] == "2"


class TestWorkspaceMemberLists:
    """The member lists need READ by default and MANAGE with the setting on."""

    @staticmethod
    def _check(workspace: str, *, is_admin: bool = False) -> str:
        async def _username(request=None):
            return CALLER

        async def _is_admin(request=None):
            return is_admin

        with (
            patch("mlflow_oidc_auth.dependencies.get_username", _username),
            patch("mlflow_oidc_auth.dependencies.get_is_admin", _is_admin),
            patch(
                "mlflow_oidc_auth.dependencies.get_workspace_permission_cached",
                lambda username, ws: WORKSPACE_PERMISSIONS.get(ws),
            ),
        ):
            return asyncio.run(check_workspace_member_list_permission(workspace=workspace, request=MagicMock()))

    @pytest.fixture(autouse=True)
    def _workspaces_on(self, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)

    def test_a_reader_lists_members_by_default(self, monkeypatch):
        monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", False)
        assert self._check("ws-read") == CALLER

    def test_a_reader_cannot_list_members_when_restricted(self, monkeypatch):
        monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", True)
        with pytest.raises(HTTPException) as denied:
            self._check("ws-read")
        assert denied.value.status_code == 403

    def test_no_permission_is_refused_either_way(self, monkeypatch):
        for restricted in (False, True):
            monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", restricted)
            with pytest.raises(HTTPException) as denied:
                self._check("ws-elsewhere")
            assert denied.value.status_code == 403

    def test_a_manager_and_an_admin_list_members_when_restricted(self, monkeypatch):
        monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", True)
        assert self._check("ws-managed") == CALLER
        assert self._check("ws-elsewhere", is_admin=True) == CALLER


def test_the_workspace_member_lists_use_the_member_list_check():
    from mlflow_oidc_auth.routers.workspace_permissions import WORKSPACE_GROUPS, WORKSPACE_USERS, workspace_permissions_router

    lists = [route for route in workspace_permissions_router.routes if route.path.endswith((WORKSPACE_USERS, WORKSPACE_GROUPS)) and "GET" in route.methods]
    assert len(lists) == 2
    for route in lists:
        assert [dependency.call for dependency in route.dependant.dependencies if dependency.call is check_workspace_member_list_permission]


def test_store_lists_each_workspace_with_grants_once(store):
    store.create_workspace_group_permission("ws-groups-only", "unrelated", "READ")
    assert store.list_workspaces_with_grants() == ["ws-groups-only", "ws-managed", "ws-read"]
