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

    @pytest.mark.parametrize("kind", KINDS)
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


class TestAnOldReplicasDuplicateDuringARollingUpgrade:
    """A replica on a release before the column can add an unassigned grant beside an existing one;
    with workspaces disabled both match. Lookups pick one instead of failing, and the backfill merges."""

    def _duplicate(self, store, model, principal_col, principal_id, **fields):
        with store.ManagedSessionMaker(read_only=False) as session:
            session.add(model(**{principal_col: principal_id, "workspace": None, **fields}))

    def test_the_default_grant_wins_and_changes_go_to_it(self, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission, SqlUser

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        store.create_registered_model_permission("churn", ALICE, "READ")
        with store.ManagedSessionMaker() as session:
            alice_id = session.query(SqlUser.id).filter(SqlUser.username == ALICE).scalar()
        self._duplicate(store, SqlRegisteredModelPermission, "user_id", alice_id, name="churn", permission="MANAGE")
        _clear_cache()

        assert model_permission("churn") == "READ"
        store.update_registered_model_permission("churn", ALICE, "EDIT")
        _clear_cache()
        assert model_permission("churn") == "EDIT"

    def test_a_group_grant_with_two_unassigned_rows_can_still_be_changed(self, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission, SqlGroup

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        with store.ManagedSessionMaker() as session:
            team_id = session.query(SqlGroup.id).filter(SqlGroup.group_name == "team").scalar()
        self._duplicate(store, SqlRegisteredModelGroupPermission, "group_id", team_id, name="churn", permission="READ", prompt=False)
        self._duplicate(store, SqlRegisteredModelGroupPermission, "group_id", team_id, name="churn", permission="EDIT", prompt=False)

        store.update_group_model_permission("team", "churn", "MANAGE")  # applies to both copies
        _clear_cache()

        assert model_permission("churn") == "MANAGE"

    def test_without_a_default_grant_the_lookup_keeps_what_the_backfill_keeps(self, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission, SqlUser
        from mlflow_oidc_auth.grant_workspace_backfill import backfill_grant_workspaces

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        with store.ManagedSessionMaker() as session:
            alice_id = session.query(SqlUser.id).filter(SqlUser.username == ALICE).scalar()
        for permission in ("READ", "MANAGE"):
            self._duplicate(store, SqlRegisteredModelPermission, "user_id", alice_id, name="churn", permission=permission)
        _clear_cache()
        before = store.get_registered_model_permission("churn", ALICE).permission

        backfill_grant_workspaces(store)
        _clear_cache()

        assert before == store.get_registered_model_permission("churn", ALICE).permission == "READ"

    def test_a_group_revoke_removes_copies_with_either_prompt_flag(self, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission, SqlGroup

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        store.create_group_model_permission("team", "churn", "MANAGE")
        with store.ManagedSessionMaker() as session:
            team_id = session.query(SqlGroup.id).filter(SqlGroup.group_name == "team").scalar()
        self._duplicate(store, SqlRegisteredModelGroupPermission, "group_id", team_id, name="churn", permission="READ", prompt=True)

        store.delete_group_model_permission("team", "churn")
        _clear_cache()

        assert model_permission("churn") == "NO_PERMISSIONS"

    def test_revoking_removes_every_copy_so_none_keeps_granting(self, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission, SqlRegisteredModelPermission, SqlGroup, SqlUser

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        store.create_registered_model_permission("churn", ALICE, "READ")
        store.create_group_model_permission("team", "fraud", "READ")
        with store.ManagedSessionMaker() as session:
            alice_id = session.query(SqlUser.id).filter(SqlUser.username == ALICE).scalar()
            team_id = session.query(SqlGroup.id).filter(SqlGroup.group_name == "team").scalar()
        self._duplicate(store, SqlRegisteredModelPermission, "user_id", alice_id, name="churn", permission="MANAGE")
        self._duplicate(store, SqlRegisteredModelGroupPermission, "group_id", team_id, name="fraud", permission="MANAGE", prompt=False)

        store.delete_registered_model_permission("churn", ALICE)
        store.delete_group_model_permission("team", "fraud")
        _clear_cache()

        assert model_permission("churn") == "NO_PERMISSIONS"
        assert model_permission("fraud") == "NO_PERMISSIONS"

    def test_the_backfill_merges_the_duplicates(self, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission, SqlUser
        from mlflow_oidc_auth.grant_workspace_backfill import backfill_grant_workspaces

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        with store.ManagedSessionMaker() as session:
            alice_id = session.query(SqlUser.id).filter(SqlUser.username == ALICE).scalar()
        for permission in ("READ", "MANAGE"):
            self._duplicate(store, SqlRegisteredModelPermission, "user_id", alice_id, name="churn", permission=permission)

        backfill_grant_workspaces(store)

        assert [(p.name, p.workspace, p.permission) for p in store.list_registered_model_permissions(ALICE)] == [("churn", "default", "READ")]


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


# ---------------------------------------------------------------------------
# Through HTTP: the permission API routes carry no AuthContext bridge, so the grant workspace
# comes from MLflow's resolved request workspace (WorkspaceContextMiddleware).
# ---------------------------------------------------------------------------

ADMIN = "admin@example.com"
ADMIN_PASSWORD = "scoped-grants-admin"  # not a credential: only ever seeded into a tmp_path database
ALICE_PASSWORD = "scoped-grants-alice"  # likewise
USERS_API = "/api/2.0/mlflow/permissions/users"
MODELS_API = "/api/2.0/mlflow/permissions/registered-models"
GROUPS_API = "/api/2.0/mlflow/permissions/groups"


@pytest.fixture
def api(store, monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from mlflow_oidc_auth.exceptions import register_exception_handlers
    from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
    from mlflow_oidc_auth.routers.registered_model_permissions import registered_model_permissions_router
    from mlflow_oidc_auth.routers.user_permissions import user_permissions_router
    from mlflow_oidc_auth.tests.scim.conftest import basic
    from mlflow_oidc_auth.tests.token_helpers import set_known_token

    store.create_user(ADMIN, "Admin", is_admin=True)
    set_known_token(store, ADMIN, ADMIN_PASSWORD)
    set_known_token(store, ALICE, ALICE_PASSWORD)
    # MLflow resolves the header to a workspace (default when absent); no workspace store here.
    monkeypatch.setattr(
        "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
        lambda path, header: SimpleNamespace(name=(header or "").strip() or "default"),
    )
    from mlflow_oidc_auth.app import add_middleware_stack

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(user_permissions_router)
    app.include_router(registered_model_permissions_router)
    app.include_router(group_permissions_router)
    # The production order: Proxy -> Session -> WorkspaceContext -> Auth -> Permission.
    add_middleware_stack(app)
    return SimpleNamespace(
        admin=TestClient(app, headers=basic(ADMIN, ADMIN_PASSWORD)),
        alice=TestClient(app, headers=basic(ALICE, ALICE_PASSWORD)),
    )


def _rows(store):
    from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission, SqlUser

    with store.ManagedSessionMaker() as session:
        rows = session.query(
            SqlUser.username, SqlRegisteredModelPermission.name, SqlRegisteredModelPermission.workspace, SqlRegisteredModelPermission.permission
        )
        return sorted(rows.join(SqlUser, SqlUser.id == SqlRegisteredModelPermission.user_id).all())


class TestThePermissionApiUsesTheRequestsWorkspace:
    def test_a_grant_is_written_in_the_workspace_the_request_names(self, api, store):
        response = api.admin.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"}, headers={"X-MLFLOW-WORKSPACE": "team-b"})
        assert response.status_code == 201, response.text

        assert _rows(store) == [(VICTOR, "churn", "team-b", "READ")]

    def test_listing_changing_and_revoking_stay_in_the_requests_workspace(self, api, store):
        for workspace, permission in (("team-a", "MANAGE"), ("team-b", "READ")):
            api.admin.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": permission}, headers={"X-MLFLOW-WORKSPACE": workspace})

        users_b = api.admin.get(f"{MODELS_API}/churn/users", headers={"X-MLFLOW-WORKSPACE": "team-b"}).json()
        assert [(u["name"], u["permission"]) for u in users_b] == [(VICTOR, "READ")]

        api.admin.patch(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "EDIT"}, headers={"X-MLFLOW-WORKSPACE": "team-b"})
        response = api.admin.delete(f"{USERS_API}/{VICTOR}/registered-models/churn", headers={"X-MLFLOW-WORKSPACE": "team-a"})
        assert response.status_code == 200
        assert _rows(store) == [(VICTOR, "churn", "team-b", "EDIT")]

    def test_no_header_is_the_default_workspace(self, api, store):
        api.admin.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"})
        assert _rows(store) == [(VICTOR, "churn", "default", "READ")]

    def test_managing_a_model_in_one_workspace_gives_no_say_over_its_namesake(self, api, store):
        """Alice manages team-a's churn: she may grant on it, but not on team-b's — and the decision
        cached for one is not served for the other."""
        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        _clear_cache()

        allowed = api.alice.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"}, headers={"X-MLFLOW-WORKSPACE": "team-a"})
        denied = api.alice.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"}, headers={"X-MLFLOW-WORKSPACE": "team-b"})

        assert allowed.status_code == 201, allowed.text
        assert denied.status_code == 403, denied.text
        assert _rows(store) == [(ALICE, "churn", "team-a", "MANAGE"), (VICTOR, "churn", "team-a", "READ")]


class TestThePermissionApiFallsBackToTheWorkspacePermission:
    """With no grant on the resource itself, the permission API's manage check uses the caller's
    permission on the request's workspace — as every other route does — not the global default."""

    def test_no_permission_on_the_workspace_is_denied_whatever_the_global_default(self, api, store, monkeypatch):
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        _clear_cache()

        response = api.alice.post(f"{USERS_API}/{ALICE}/registered-models/churn", json={"permission": "MANAGE"}, headers={"X-MLFLOW-WORKSPACE": "team-b"})

        assert response.status_code == 403, response.text
        assert _rows(store) == []

    def test_manage_on_the_workspace_allows_managing_its_resources(self, api, store):
        store.create_workspace_permission("team-a", ALICE, "MANAGE")
        _clear_cache()

        response = api.alice.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"}, headers={"X-MLFLOW-WORKSPACE": "team-a"})

        assert response.status_code == 201, response.text
        assert _rows(store) == [(VICTOR, "churn", "team-a", "READ")]

    def test_the_group_routes_fall_back_the_same_way(self, api, store, monkeypatch):
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        _clear_cache()

        response = api.alice.post(f"{GROUPS_API}/team/registered-models/churn", json={"permission": "MANAGE"}, headers={"X-MLFLOW-WORKSPACE": "team-b"})

        assert response.status_code == 403, response.text

    def test_a_request_naming_no_workspace_keeps_the_global_default(self, api, store, monkeypatch):
        """As on every route: with no workspace named there is no workspace permission to defer to."""
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        _clear_cache()

        response = api.alice.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"})

        assert response.status_code == 201, response.text
        assert _rows(store) == [(VICTOR, "churn", "default", "READ")]

    def test_with_workspaces_disabled_the_global_default_applies(self, api, store, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        _clear_cache()

        response = api.alice.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"})

        assert response.status_code == 201, response.text

    def test_the_bridged_context_does_not_outlive_the_request(self, api, store):
        from mlflow_oidc_auth.bridge.user import _auth_context_var

        api.alice.get(f"{MODELS_API}/churn/users", headers={"X-MLFLOW-WORKSPACE": "team-a"})

        assert _auth_context_var.get() is None

    def test_read_on_the_workspace_does_not_allow_managing(self, api, store, monkeypatch):
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        store.create_workspace_permission("team-a", ALICE, "READ")
        _clear_cache()

        response = api.alice.post(f"{USERS_API}/{VICTOR}/registered-models/churn", json={"permission": "READ"}, headers={"X-MLFLOW-WORKSPACE": "team-a"})

        assert response.status_code == 403, response.text


class TestAnExperimentIsJudgedInItsOwnWorkspace:
    """Experiment ids are unique across workspaces: a permission on the workspace a request names
    reaches an experiment only when that experiment is in it."""

    @pytest.fixture
    def experiments(self, monkeypatch):
        from types import SimpleNamespace

        from mlflow.utils.workspace_context import get_request_workspace

        from mlflow_oidc_auth.utils import permissions

        homes = {"42": "team-a", "7": "team-b"}

        class _Store:
            def get_experiment(self, experiment_id):
                if homes.get(experiment_id) != (get_request_workspace() or "default"):
                    from mlflow.exceptions import MlflowException
                    from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

                    raise MlflowException(f"No experiment {experiment_id} in this workspace", RESOURCE_DOES_NOT_EXIST)
                return SimpleNamespace(experiment_id=experiment_id, name=f"exp-{experiment_id}")

        monkeypatch.setattr(permissions, "_get_tracking_store", lambda: _Store())

    def test_manage_on_one_workspace_does_not_reach_another_workspaces_experiment(self, api, store, experiments):
        store.create_workspace_permission("team-b", ALICE, "MANAGE")
        _clear_cache()

        response = api.alice.post(f"{USERS_API}/{ALICE}/experiments/42", json={"permission": "MANAGE"}, headers={"X-MLFLOW-WORKSPACE": "team-b"})

        assert response.status_code == 403, response.text

    def test_it_reaches_its_own_workspaces_experiment(self, api, store, experiments):
        store.create_workspace_permission("team-b", ALICE, "MANAGE")
        _clear_cache()

        response = api.alice.post(f"{USERS_API}/{VICTOR}/experiments/7", json={"permission": "READ"}, headers={"X-MLFLOW-WORKSPACE": "team-b"})

        assert response.status_code == 200, response.text


class TestRenamingAModelThroughTheHook:
    def test_group_grants_follow_a_rename_when_the_workspace_has_no_user_grants(self, store):
        """The user rename finds nothing to move in this workspace; the group rename must still run."""
        from flask import Flask

        from mlflow_oidc_auth.hooks.after_request import _rename_registered_model_permission

        with in_workspace("team-a"):
            store.create_group_model_permission("team", "churn", "EDIT")
            with Flask(__name__).test_request_context(json={"name": "churn", "new_name": "churn-v2"}):
                _rename_registered_model_permission(None)
        _clear_cache()
        with in_workspace("team-a"):
            assert model_permission("churn-v2") == "EDIT"
            assert model_permission("churn") == "NO_PERMISSIONS"


class TestWorkspaceDeletion:
    def test_deleting_a_workspace_removes_its_resource_grants(self, store):
        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
            store.create_group_gateway_endpoint_permission("team", "chat", "USE")
        with in_workspace("team-b"):
            store.create_registered_model_permission("churn", ALICE, "READ")

        store.wipe_workspace_permissions("team-a")

        _clear_cache()
        with in_workspace("team-a"):
            assert model_permission("churn") == "NO_PERMISSIONS"
            assert store.list_group_gateway_endpoint_permissions("team") == []
        _clear_cache()
        with in_workspace("team-b"):
            assert model_permission("churn") == "READ"

    def test_deleting_a_workspace_drops_cached_decisions_on_its_resources(self, store, monkeypatch):
        """A workspace recreated under the same name must not inherit a decision cached before.

        The store flushes the permission cache on ``wipe_workspace_permissions`` (it is one of the
        permission CUD methods), so the hook needs no flush of its own."""
        from flask import Flask, g

        from mlflow_oidc_auth.hooks.after_request import _cascade_delete_workspace_permissions

        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
            assert model_permission("churn") == "MANAGE"  # now cached
            response = Flask(__name__).response_class(status=204)
            with Flask(__name__).test_request_context():
                g._deleting_workspace_name = "team-a"
                _cascade_delete_workspace_permissions(response)
            assert model_permission("churn") == "NO_PERMISSIONS"


class TestTheGrantWorkspaceIsMlflowsWorkspace:
    def test_a_request_naming_no_workspace_uses_the_one_mlflow_serves_it_from(self, store, monkeypatch):
        """With a workspace provider that has no default, MLflow serves header-less requests from
        ``MLFLOW_WORKSPACE``; grants must follow it rather than assume ``default``."""
        from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace

        monkeypatch.setenv("MLFLOW_WORKSPACE", "team-a")
        with in_workspace(None):
            assert current_grant_workspace() == "team-a"
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        _clear_cache()
        with in_workspace("team-a"):
            assert model_permission("churn") == "MANAGE"
        _clear_cache()
        with in_workspace("default"):
            assert model_permission("churn") == "NO_PERMISSIONS"

    def test_a_workspace_the_request_names_wins(self, store, monkeypatch):
        from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace

        monkeypatch.setenv("MLFLOW_WORKSPACE", "team-a")
        with in_workspace("team-b"):
            assert current_grant_workspace() == "team-b"

    def test_nothing_resolved_is_the_default_workspace(self, store, monkeypatch):
        from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace

        monkeypatch.delenv("MLFLOW_WORKSPACE", raising=False)
        assert current_grant_workspace() == "default"


class TestTheCachedDecisionStaysInItsWorkspace:
    def test_a_cached_manage_decision_is_not_served_for_the_namesake(self, api, store):
        """Reads flush nothing: a decision cached for team-a's churn must not answer for team-b's."""
        with in_workspace("team-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        _clear_cache()

        first = api.alice.get(f"{MODELS_API}/churn/users", headers={"X-MLFLOW-WORKSPACE": "team-a"})
        second = api.alice.get(f"{MODELS_API}/churn/users", headers={"X-MLFLOW-WORKSPACE": "team-b"})

        assert first.status_code == 200, first.text
        assert second.status_code == 403, second.text


class TestGatewayGroupGrantsCount:
    """Group grants on gateway resources used to be looked up under the user's name as if it were a
    group name, so they never counted. They now resolve like model and prompt group grants."""

    @pytest.mark.parametrize("kind", ["gateway_endpoint", "gateway_secret", "gateway_model_definition"])
    def test_a_group_grant_counts_with_workspaces_off(self, store, monkeypatch, kind):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        _, grant_group, resolve, _ = _kinds(store)[kind]
        grant_group("team", "chat", "USE")
        _clear_cache()

        assert resolve("chat", ALICE).permission.name == "USE"
        assert resolve("chat", VICTOR).permission.name == "NO_PERMISSIONS", "not a member of the group"

    def test_the_strongest_of_several_group_grants_wins(self, store, monkeypatch):
        from mlflow_oidc_auth.utils.permissions import effective_gateway_endpoint_permission

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        store.populate_groups(["ops"])
        store.set_user_groups(ALICE, ["team", "ops"])
        store.create_group_gateway_endpoint_permission("team", "chat", "READ")
        store.create_group_gateway_endpoint_permission("ops", "chat", "MANAGE")
        _clear_cache()

        assert effective_gateway_endpoint_permission("chat", ALICE).permission.name == "MANAGE"


class TestWorkspacesSwitchedOffAgain:
    """A deployment that had workspaces enabled and turns them off again serves only default."""

    def test_only_the_default_workspaces_grant_counts_and_nothing_is_ambiguous(self, store, monkeypatch):
        with in_workspace("tenant-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        with in_workspace("default"):
            store.create_registered_model_permission("churn", ALICE, "READ")
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        _clear_cache()

        assert model_permission("churn") == "READ"
        assert [(p.name, p.workspace) for p in store.list_registered_model_permissions(ALICE)] == [("churn", "default")]

    def test_another_workspaces_grant_does_not_reach_default(self, store, monkeypatch):
        with in_workspace("tenant-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        _clear_cache()

        assert model_permission("churn") == "NO_PERMISSIONS"
        store.create_registered_model_permission("churn", ALICE, "EDIT")  # no clash with tenant-a's row
        _clear_cache()
        assert model_permission("churn") == "EDIT"

    def test_orphan_hand_over_ignores_other_workspaces_grants(self, store, monkeypatch):
        from mlflow_oidc_auth.orphans import find_orphaned_resources

        with in_workspace("tenant-a"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")
        with in_workspace("default"):
            store.create_registered_model_permission("forecast", ALICE, "MANAGE")
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)

        assert find_orphaned_resources(ALICE, store=store) == [("registered_model", "forecast")]
