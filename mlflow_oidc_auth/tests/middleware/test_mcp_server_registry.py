"""Per-server permissions on MLflow's MCP server registry.

The installed MLflow may predate the registry (it arrived in 3.15), so these tests serve a stand-in
with the same route table, mounted the way ``app.py`` mounts MLflow's, behind the production
middleware stack, a real auth store and the real permission resolution. The stand-in keeps servers
per ``(workspace, name)`` exactly like MLflow, reading the workspace from MLflow's request context.
"""

from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AuthContext
from mlflow_oidc_auth.middleware.mcp_server_registry import (
    CREATE,
    CREATE_VERSION,
    DELETE,
    DELETE_SERVER,
    READ,
    READ_SERVER,
    SEARCH,
    SEARCH_ENDPOINTS,
    UPDATE,
    MCPRoute,
    resolve_mcp_route,
)

ADMIN = "admin@example.com"
ALICE = "alice@example.com"
BOB = "bob@example.com"
# Not credentials: only ever seeded into a tmp_path database.
PASSWORDS = {ADMIN: "mcp-admin-pw", ALICE: "mcp-alice-pw", BOB: "mcp-bob-pw"}

API = "/api/3.0/mlflow/mcp-servers"
AJAX = "/ajax-api/3.0/mlflow/mcp-servers"
PERMS = "/api/2.0/mlflow/permissions/mcp-servers"
USERS = "/api/2.0/mlflow/permissions/users"
GROUPS = "/api/2.0/mlflow/permissions/groups"
SERVER = "com.example/weather"


# ---------------------------------------------------------------------------
# Route resolution mirrors MLflow's route table
# ---------------------------------------------------------------------------


class TestRouteResolution:
    @pytest.mark.parametrize(
        "method,suffix,expected",
        [
            ("POST", "", MCPRoute(CREATE)),
            ("GET", "", MCPRoute(SEARCH)),
            ("GET", "/endpoints", MCPRoute(SEARCH_ENDPOINTS)),
            ("GET", "/com.example/weather", MCPRoute(READ_SERVER, SERVER)),
            ("HEAD", "/com.example/weather", MCPRoute(READ_SERVER, SERVER)),
            ("PATCH", "/com.example/weather", MCPRoute(UPDATE, SERVER)),
            ("DELETE", "/com.example/weather", MCPRoute(DELETE_SERVER, SERVER)),
            ("POST", "/com.example/weather/tags", MCPRoute(UPDATE, SERVER)),
            ("DELETE", "/com.example/weather/tags/team", MCPRoute(DELETE, SERVER)),
            ("POST", "/com.example/weather/aliases", MCPRoute(UPDATE, SERVER)),
            ("GET", "/com.example/weather/aliases/prod", MCPRoute(READ, SERVER)),
            ("DELETE", "/com.example/weather/aliases/prod", MCPRoute(DELETE, SERVER)),
            ("POST", "/com.example/weather/versions", MCPRoute(CREATE_VERSION, SERVER)),
            ("GET", "/com.example/weather/versions", MCPRoute(READ, SERVER)),
            ("GET", "/com.example/weather/versions/1.0.0", MCPRoute(READ, SERVER)),
            ("PATCH", "/com.example/weather/versions/1.0.0", MCPRoute(UPDATE, SERVER)),
            ("DELETE", "/com.example/weather/versions/1.0.0", MCPRoute(DELETE, SERVER)),
            ("POST", "/com.example/weather/versions/1.0.0/tags", MCPRoute(UPDATE, SERVER)),
            ("DELETE", "/com.example/weather/versions/1.0.0/tags/k", MCPRoute(DELETE, SERVER)),
            ("POST", "/com.example/weather/endpoints", MCPRoute(UPDATE, SERVER)),
            ("GET", "/com.example/weather/endpoints", MCPRoute(READ, SERVER)),
            ("GET", "/com.example/weather/endpoints/e1", MCPRoute(READ, SERVER)),
            ("PATCH", "/com.example/weather/endpoints/e1", MCPRoute(UPDATE, SERVER)),
            ("DELETE", "/com.example/weather/endpoints/e1", MCPRoute(DELETE, SERVER)),
        ],
    )
    def test_each_route_resolves_to_its_action_and_server(self, method, suffix, expected):
        assert resolve_mcp_route(API + suffix, method) == expected
        assert resolve_mcp_route(AJAX + suffix, method) == expected

    def test_the_name_is_the_one_mlflows_router_extracts(self):
        """``{name:path}`` is greedy: a version path that itself contains ``/versions/`` belongs to
        a longer name, which MLflow could never have stored — so it is denied, not judged as another server."""
        assert resolve_mcp_route(API + "/com.example/weather/versions/1/versions/2", "GET") is None

    @pytest.mark.parametrize(
        "method,suffix",
        [
            ("GET", "/weather"),  # not <namespace>/<slug>
            ("GET", "/"),  # empty name
            ("GET", "/a/b/c"),  # three segments: MLflow never stores such a name
            ("PUT", "/com.example/weather"),  # no such route
            ("POST", "/endpoints"),  # no such route
            ("DELETE", ""),
        ],
    )
    def test_anything_else_resolves_to_nothing(self, method, suffix):
        assert resolve_mcp_route(API + suffix, method) is None

    def test_a_path_merely_starting_with_the_prefix_is_not_the_registry(self):
        assert resolve_mcp_route(API + "-other", "GET") is None

    def test_static_prefix(self, monkeypatch):
        from mlflow.server.handlers import STATIC_PREFIX_ENV_VAR

        monkeypatch.setenv(STATIC_PREFIX_ENV_VAR, "/mlflow")
        assert resolve_mcp_route("/mlflow" + API + "/com.example/weather", "DELETE") == MCPRoute(DELETE_SERVER, SERVER)


# ---------------------------------------------------------------------------
# A stand-in for MLflow's registry, per (workspace, name)
# ---------------------------------------------------------------------------


class FakeRegistry:
    def __init__(self) -> None:
        self.servers: Dict[Tuple[str, str], Dict[str, Any]] = {}

    @staticmethod
    def workspace() -> str:
        from mlflow.utils.workspace_context import get_request_workspace

        return get_request_workspace() or "default"

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self.servers.get((self.workspace(), name))

    def add(self, name: str, created_by: Optional[str], workspace: Optional[str] = None) -> Dict[str, Any]:
        workspace = workspace or self.workspace()
        server = {"name": name, "workspace": workspace, "created_by": created_by, "tags": {}, "versions": []}
        self.servers[(workspace, name)] = server
        return server

    def in_workspace(self):
        ws = self.workspace()
        return [s for (w, _), s in sorted(self.servers.items()) if w == ws]

    # The two tracking-store methods the plugin calls.
    def get_mcp_server(self, name: str):
        from mlflow.exceptions import MlflowException
        from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

        server = self.get(name)
        if server is None:
            raise MlflowException(f"MCP server '{name}' not found", error_code=RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(**server)

    def search_mcp_servers(self, max_results=100, page_token=None, **_):
        page = [SimpleNamespace(**s, display_name=None, description=None, status=None, latest_version=None) for s in self.in_workspace()]
        return _Paged(page)


class _Paged(list):
    token = None


def _public(server: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": server["name"], "workspace": server["workspace"], "created_by": server["created_by"], "tags": server["tags"]}


def _not_found():
    return JSONResponse(status_code=404, content={"error_code": "RESOURCE_DOES_NOT_EXIST"})


def registry_router(registry: FakeRegistry) -> APIRouter:
    """MLflow's route table (same templates, same order) over ``registry``."""
    router = APIRouter()

    @router.post("")
    async def create(request: Request):
        body = await request.json()
        if registry.get(body["name"]) is not None:
            return JSONResponse(status_code=400, content={"error_code": "RESOURCE_ALREADY_EXISTS"})
        return _public(registry.add(body["name"], request.state.username))

    @router.get("")
    async def search():
        return {"mcp_servers": [_public(s) for s in registry.in_workspace()], "next_page_token": None}

    @router.get("/endpoints")
    async def search_endpoints():
        return {"mcp_access_endpoints": [{"id": f"e-{s['name']}", "server_name": s["name"]} for s in registry.in_workspace()]}

    @router.post("/{name:path}/versions")
    async def create_version(name: str, request: Request):
        # What MLflow's handler reads to create the parent itself and recheck on a race.
        registry.parent_flag = getattr(request.state, "mcp_server_parent_auto_created", None)
        recheck = getattr(request.state, "mcp_server_can_update_existing_recheck", None)
        registry.recheck = recheck() if recheck is not None else None
        if registry.get(name) is None:
            # MLflow creates the parent; with an auth plugin's flag set it does so explicitly first.
            registry.add(name, request.state.username)
        registry.get(name)["versions"].append("1.0.0")
        return {"name": name, "version": "1.0.0"}

    @router.post("/{name:path}/tags")
    async def set_tag(name: str, request: Request):
        server = registry.get(name)
        if server is None:
            return _not_found()
        body = await request.json()
        server["tags"][body["key"]] = body["value"]
        return {}

    @router.delete("/{name:path}/tags/{key:path}")
    async def delete_tag(name: str, key: str):
        server = registry.get(name)
        if server is None:
            return _not_found()
        server["tags"].pop(key, None)
        return {}

    @router.get("/{name:path}")
    async def get(name: str):
        server = registry.get(name)
        return _not_found() if server is None else _public(server)

    @router.patch("/{name:path}")
    async def update(name: str):
        server = registry.get(name)
        return _not_found() if server is None else _public(server)

    @router.delete("/{name:path}")
    async def delete(name: str):
        if registry.get(name) is None:
            return _not_found()
        del registry.servers[(registry.workspace(), name)]
        return {}

    return router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.tests.token_helpers import set_known_token
    from mlflow_oidc_auth.utils import permissions, workspace_cache

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ADMIN, "Admin", is_admin=True)
    s.create_user(ALICE, "Alice")
    s.create_user(BOB, "Bob")
    s.populate_groups(["team"])
    s.set_user_groups(BOB, ["team"])
    for user, password in PASSWORDS.items():
        set_known_token(s, user, password)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    permissions._get_permission_cache().clear()
    workspace_cache.flush_workspace_cache()
    yield s
    permissions._get_permission_cache().clear()
    workspace_cache.flush_workspace_cache()
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture
def registry(monkeypatch):
    reg = FakeRegistry()
    import mlflow.server.handlers as handlers

    monkeypatch.setattr(handlers, "_get_tracking_store", lambda: reg)
    monkeypatch.setattr("mlflow_oidc_auth.utils.data_fetching._get_tracking_store", lambda: reg)
    return reg


@pytest.fixture
def api(store, registry, monkeypatch):
    from mlflow_oidc_auth.app import add_middleware_stack
    from mlflow_oidc_auth.exceptions import register_exception_handlers
    from mlflow_oidc_auth.routers.mcp_server_permissions import (
        group_mcp_server_permissions_router,
        mcp_server_permissions_router,
        user_mcp_server_permissions_router,
    )
    from mlflow_oidc_auth.tests.scim.conftest import basic

    # MLflow resolves the header to a workspace (default when absent); no workspace store here.
    monkeypatch.setattr(
        "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
        lambda path, header: SimpleNamespace(name=(header or "").strip() or "default"),
    )
    app = FastAPI()
    register_exception_handlers(app)
    router = registry_router(registry)
    app.include_router(router, prefix=API)
    app.include_router(router, prefix=AJAX)
    app.include_router(mcp_server_permissions_router)
    app.include_router(user_mcp_server_permissions_router)
    app.include_router(group_mcp_server_permissions_router)
    add_middleware_stack(app)
    return SimpleNamespace(**{name: TestClient(app, headers=basic(user, PASSWORDS[user])) for name, user in (("admin", ADMIN), ("alice", ALICE), ("bob", BOB))})


def ws(name: str) -> Dict[str, str]:
    return {"X-MLFLOW-WORKSPACE": name}


def _clear_cache():
    from mlflow_oidc_auth.utils import permissions, workspace_cache

    permissions._get_permission_cache().clear()
    workspace_cache.flush_workspace_cache()


def _grants(store):
    from mlflow_oidc_auth.db.models import SqlMCPServerPermission, SqlUser

    with store.ManagedSessionMaker() as session:
        rows = session.query(SqlUser.username, SqlMCPServerPermission.name, SqlMCPServerPermission.workspace, SqlMCPServerPermission.permission)
        return sorted(rows.join(SqlUser, SqlUser.id == SqlMCPServerPermission.user_id).all())


@pytest.fixture
def members(store):
    """Alice may create in team-a (EDIT); Bob only reads team-a."""
    store.create_workspace_permission("team-a", ALICE, "EDIT")
    store.create_workspace_permission("team-a", BOB, "READ")
    _clear_cache()


# ---------------------------------------------------------------------------
# Creation and the creator grant
# ---------------------------------------------------------------------------


class TestCreate:
    def test_edit_on_the_workspace_creates_and_the_creator_gets_manage_there(self, api, store, members, registry):
        response = api.alice.post(API, json={"name": SERVER}, headers=ws("team-a"))

        assert response.status_code == 200, response.text
        assert registry.servers[("team-a", SERVER)]["created_by"] == ALICE
        assert _grants(store) == [(ALICE, SERVER, "team-a", "MANAGE")]

    def test_read_on_the_workspace_cannot_create(self, api, store, members, registry):
        response = api.bob.post(API, json={"name": SERVER}, headers=ws("team-a"))

        assert response.status_code == 403
        assert registry.servers == {}
        assert _grants(store) == []

    def test_a_non_member_cannot_create(self, api, store, members, registry):
        response = api.alice.post(API, json={"name": SERVER}, headers=ws("team-b"))

        assert response.status_code == 403
        assert registry.servers == {}

    def test_no_workspace_named_is_judged_against_default(self, api, store, members, registry):
        assert api.alice.post(API, json={"name": SERVER}).status_code == 403
        store.create_workspace_permission("default", ALICE, "EDIT")
        _clear_cache()
        assert api.alice.post(API, json={"name": SERVER}).status_code == 200
        assert _grants(store) == [(ALICE, SERVER, "default", "MANAGE")]

    def test_no_grant_when_mlflow_refuses_the_create(self, api, store, members, registry):
        registry.add(SERVER, BOB, workspace="team-a")

        response = api.alice.post(API, json={"name": SERVER}, headers=ws("team-a"))

        assert response.status_code == 400
        assert _grants(store) == []

    def test_a_version_on_a_new_server_is_a_creation(self, api, store, members, registry):
        assert api.bob.post(f"{API}/{SERVER}/versions", json={}, headers=ws("team-a")).status_code == 403
        assert registry.servers == {}

        response = api.alice.post(f"{API}/{SERVER}/versions", json={}, headers=ws("team-a"))

        assert response.status_code == 200, response.text
        assert _grants(store) == [(ALICE, SERVER, "team-a", "MANAGE")]
        # MLflow's handler is told to create the parent itself; its race recheck resolves in the
        # caller's workspace although it runs after the middleware's bridged context is gone
        # (Alice's EDIT on team-a).
        assert registry.parent_flag is True
        assert registry.recheck is True

    def test_a_version_on_someone_elses_server_needs_edit_on_it_and_grants_nothing(self, api, store, members, registry):
        with _as(BOB, "team-a"):
            store.create_mcp_server_permission(SERVER, BOB, "MANAGE")
        registry.add(SERVER, BOB, workspace="team-a")
        _clear_cache()

        # Alice has EDIT on the workspace, but Bob's server has grants of its own: hers comes from the workspace.
        response = api.alice.post(f"{API}/{SERVER}/versions", json={}, headers=ws("team-a"))

        assert response.status_code == 200
        assert registry.parent_flag is False
        assert _grants(store) == [(BOB, SERVER, "team-a", "MANAGE")]

    def test_a_version_on_a_server_someone_else_created_first_grants_nothing(self, api, store, members, registry, monkeypatch):
        """The race MLflow's recheck covers: the server appeared between the check and the handler,
        created by someone else — the caller is not its creator and gets no MANAGE."""
        from mlflow_oidc_auth.middleware import mcp_server_registry

        monkeypatch.setattr(mcp_server_registry, "_mcp_server_exists", lambda name: False)
        registry.add(SERVER, BOB, workspace="team-a")

        response = api.alice.post(f"{API}/{SERVER}/versions", json={}, headers=ws("team-a"))

        assert response.status_code == 200
        assert _grants(store) == []

    def test_workspaces_disabled_anyone_creates_and_the_grant_is_in_default(self, api, store, registry, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        _clear_cache()

        response = api.alice.post(API, json={"name": SERVER})

        assert response.status_code == 200
        assert _grants(store) == [(ALICE, SERVER, "default", "MANAGE")]

    def test_workspaces_disabled_restrict_resource_creation_denies(self, api, store, registry, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "RESTRICT_RESOURCE_CREATION", True)
        _clear_cache()

        assert api.alice.post(API, json={"name": SERVER}).status_code == 403
        assert registry.servers == {}


# ---------------------------------------------------------------------------
# Reading, writing, deleting one server
# ---------------------------------------------------------------------------


class TestPerServerChecks:
    @pytest.fixture
    def alices_server(self, api, store, members, registry):
        assert api.alice.post(API, json={"name": SERVER}, headers=ws("team-a")).status_code == 200
        return SERVER

    def test_the_creator_reads_writes_and_deletes(self, api, store, alices_server, registry):
        assert api.alice.get(f"{API}/{SERVER}", headers=ws("team-a")).status_code == 200
        assert api.alice.post(f"{API}/{SERVER}/tags", json={"key": "k", "value": "v"}, headers=ws("team-a")).status_code == 200
        assert api.alice.patch(f"{API}/{SERVER}", json={}, headers=ws("team-a")).status_code == 200
        assert api.alice.delete(f"{API}/{SERVER}/tags/k", headers=ws("team-a")).status_code == 200
        assert api.alice.delete(f"{API}/{SERVER}", headers=ws("team-a")).status_code == 200
        # The grants go with the server.
        assert _grants(store) == []

    def test_the_server_carries_allowed_actions(self, api, store, alices_server):
        assert api.alice.get(f"{API}/{SERVER}", headers=ws("team-a")).json()["allowed_actions"] == ["USE", "UPDATE", "DELETE", "MANAGE"]
        assert api.bob.get(f"{API}/{SERVER}", headers=ws("team-a")).json()["allowed_actions"] == []

    def test_workspace_read_reads_but_does_not_write_or_delete(self, api, store, alices_server, registry):
        assert api.bob.get(f"{API}/{SERVER}", headers=ws("team-a")).status_code == 200
        assert api.bob.post(f"{API}/{SERVER}/tags", json={"key": "k", "value": "v"}, headers=ws("team-a")).status_code == 403
        assert api.bob.patch(f"{API}/{SERVER}", json={}, headers=ws("team-a")).status_code == 403
        assert api.bob.post(f"{API}/{SERVER}/versions", json={}, headers=ws("team-a")).status_code == 403
        assert api.bob.delete(f"{API}/{SERVER}", headers=ws("team-a")).status_code == 403
        assert registry.servers[("team-a", SERVER)]["tags"] == {}

    def test_edit_writes_but_does_not_delete(self, api, store, alices_server, registry):
        with _as(ALICE, "team-a"):
            store.create_mcp_server_permission(SERVER, BOB, "EDIT")
        _clear_cache()

        assert api.bob.post(f"{API}/{SERVER}/tags", json={"key": "k", "value": "v"}, headers=ws("team-a")).status_code == 200
        # MLflow's own plugin: every DELETE on a server's routes needs MANAGE (can_delete).
        assert api.bob.delete(f"{API}/{SERVER}/tags/k", headers=ws("team-a")).status_code == 403
        assert api.bob.delete(f"{API}/{SERVER}", headers=ws("team-a")).status_code == 403
        assert ("team-a", SERVER) in registry.servers

    def test_a_non_member_without_a_grant_gets_nothing(self, api, store, alices_server, monkeypatch):
        carol = "carol@example.com"
        store.create_user(carol, "Carol")
        from mlflow_oidc_auth.tests.scim.conftest import basic
        from mlflow_oidc_auth.tests.token_helpers import set_known_token

        set_known_token(store, carol, "mcp-carol-pw")
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")  # a permissive global default must not help
        _clear_cache()
        headers = {**basic(carol, "mcp-carol-pw"), **ws("team-a")}
        client = api.alice
        assert client.get(f"{API}/{SERVER}", headers=headers).status_code == 403
        assert client.post(f"{API}/{SERVER}/tags", json={"key": "k", "value": "v"}, headers=headers).status_code == 403
        assert client.delete(f"{API}/{SERVER}", headers=headers).status_code == 403
        assert client.get(API, headers=headers).json()["mcp_servers"] == []

    def test_a_grant_shares_a_server_with_a_non_member(self, api, store, alices_server):
        """As for every resource here: a grant on the server applies without workspace membership."""
        carol = "carol@example.com"
        store.create_user(carol, "Carol")
        from mlflow_oidc_auth.tests.scim.conftest import basic
        from mlflow_oidc_auth.tests.token_helpers import set_known_token

        set_known_token(store, carol, "mcp-carol-pw")
        with _as(ALICE, "team-a"):
            store.create_mcp_server_permission(SERVER, carol, "READ")
        _clear_cache()
        headers = {**basic(carol, "mcp-carol-pw"), **ws("team-a")}

        assert api.alice.get(f"{API}/{SERVER}", headers=headers).status_code == 200
        assert api.alice.patch(f"{API}/{SERVER}", json={}, headers=headers).status_code == 403
        assert [s["name"] for s in api.alice.get(API, headers=headers).json()["mcp_servers"]] == [SERVER]

    def test_the_ajax_prefix_is_judged_the_same(self, api, store, alices_server):
        assert api.bob.patch(f"{AJAX}/{SERVER}", json={}, headers=ws("team-a")).status_code == 403
        assert api.alice.patch(f"{AJAX}/{SERVER}", json={}, headers=ws("team-a")).status_code == 200

    def test_admin_bypasses_and_an_admin_delete_takes_the_grants_too(self, api, store, alices_server, registry):
        assert api.admin.patch(f"{API}/{SERVER}", json={}, headers=ws("team-a")).status_code == 200
        assert api.admin.delete(f"{API}/{SERVER}", headers=ws("team-a")).status_code == 200
        assert _grants(store) == []


# ---------------------------------------------------------------------------
# Cross-workspace: same name, different servers
# ---------------------------------------------------------------------------


class TestSameNameInAnotherWorkspace:
    def test_a_grant_on_team_as_server_gives_nothing_on_team_bs(self, api, store, members, registry):
        assert api.alice.post(API, json={"name": SERVER}, headers=ws("team-a")).status_code == 200
        registry.add(SERVER, "someone-else", workspace="team-b")
        _clear_cache()

        assert api.alice.get(f"{API}/{SERVER}", headers=ws("team-b")).status_code == 403
        assert api.alice.patch(f"{API}/{SERVER}", json={}, headers=ws("team-b")).status_code == 403
        assert api.alice.delete(f"{API}/{SERVER}", headers=ws("team-b")).status_code == 403
        assert api.alice.get(API, headers=ws("team-b")).json()["mcp_servers"] == []
        assert ("team-b", SERVER) in registry.servers

    def test_deleting_team_bs_namesake_leaves_team_as_grants(self, api, store, members, registry):
        assert api.alice.post(API, json={"name": SERVER}, headers=ws("team-a")).status_code == 200
        registry.add(SERVER, "someone-else", workspace="team-b")

        assert api.admin.delete(f"{API}/{SERVER}", headers=ws("team-b")).status_code == 200

        assert _grants(store) == [(ALICE, SERVER, "team-a", "MANAGE")]


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


class TestSearchIsFiltered:
    def test_only_readable_servers_are_listed(self, api, store, registry):
        registry.add("com.example/one", ADMIN, workspace="team-a")
        registry.add("com.example/two", ADMIN, workspace="team-a")
        with _as(ADMIN, "team-a"):
            store.create_mcp_server_permission("com.example/one", ALICE, "READ")
        _clear_cache()

        servers = api.alice.get(API, headers=ws("team-a")).json()["mcp_servers"]
        assert [(s["name"], s["allowed_actions"]) for s in servers] == [("com.example/one", [])]

        endpoints = api.alice.get(f"{API}/endpoints", headers=ws("team-a")).json()["mcp_access_endpoints"]
        assert [e["server_name"] for e in endpoints] == ["com.example/one"]

    def test_a_group_grant_counts(self, api, store, registry):
        registry.add("com.example/one", ADMIN, workspace="team-a")
        with _as(ADMIN, "team-a"):
            store.create_group_mcp_server_permission("team", "com.example/one", "EDIT")
        _clear_cache()

        assert [s["name"] for s in api.bob.get(API, headers=ws("team-a")).json()["mcp_servers"]] == ["com.example/one"]
        assert api.bob.patch(f"{API}/com.example/one", json={}, headers=ws("team-a")).status_code == 200

    def test_admin_sees_everything(self, api, store, registry):
        registry.add("com.example/one", ADMIN, workspace="team-a")
        registry.add("com.example/two", ADMIN, workspace="team-a")

        assert len(api.admin.get(API, headers=ws("team-a")).json()["mcp_servers"]) == 2

    def test_an_unfilterable_body_is_an_error_not_the_list(self):
        import asyncio

        from starlette.responses import StreamingResponse

        from mlflow_oidc_auth.middleware.mcp_server_registry import finalize_mcp_response

        request = SimpleNamespace(method="GET", state=SimpleNamespace())
        response = StreamingResponse(iter([b'{"servers": [{"name": "com.example/one"}]}']), media_type="application/json")
        result = asyncio.run(finalize_mcp_response(API, ALICE, request, response, None))
        assert result.status_code == 500
        assert b"com.example" not in result.body


class TestWorkspacesDisabled:
    def test_one_registry_and_server_grants_still_decide(self, api, store, registry, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        _clear_cache()
        assert api.alice.post(API, json={"name": SERVER}).status_code == 200

        # Bob has no grant and the global default is NO_PERMISSIONS.
        assert api.bob.get(f"{API}/{SERVER}").status_code == 403
        assert api.bob.get(API).json()["mcp_servers"] == []
        assert api.alice.delete(f"{API}/{SERVER}").status_code == 200


# ---------------------------------------------------------------------------
# The permission API
# ---------------------------------------------------------------------------


class TestPermissionApi:
    @pytest.fixture
    def alices_server(self, api, store, members, registry):
        assert api.alice.post(API, json={"name": SERVER}, headers=ws("team-a")).status_code == 200
        return SERVER

    def test_the_manager_shares_and_revokes(self, api, store, alices_server):
        created = api.alice.post(f"{USERS}/{BOB}/mcp-servers/{SERVER}", json={"permission": "EDIT"}, headers=ws("team-a"))
        assert created.status_code == 201, created.text
        assert (BOB, SERVER, "team-a", "EDIT") in _grants(store)

        users = api.alice.get(f"{PERMS}/{SERVER}/users", headers=ws("team-a")).json()
        assert sorted((u["name"], u["permission"]) for u in users) == [(ALICE, "MANAGE"), (BOB, "EDIT")]

        assert api.alice.patch(f"{USERS}/{BOB}/mcp-servers/{SERVER}", json={"permission": "READ"}, headers=ws("team-a")).status_code == 200
        assert api.alice.get(f"{USERS}/{BOB}/mcp-servers/{SERVER}", headers=ws("team-a")).json()["permission"] == "READ"
        assert api.alice.delete(f"{USERS}/{BOB}/mcp-servers/{SERVER}", headers=ws("team-a")).status_code == 200
        assert _grants(store) == [(ALICE, SERVER, "team-a", "MANAGE")]

    def test_group_grants(self, api, store, alices_server):
        assert api.alice.post(f"{GROUPS}/team/mcp-servers/{SERVER}", json={"permission": "READ"}, headers=ws("team-a")).status_code == 201
        groups = api.alice.get(f"{PERMS}/{SERVER}/groups", headers=ws("team-a")).json()
        assert [(g["name"], g["permission"]) for g in groups] == [("team", "READ")]
        assert api.alice.patch(f"{GROUPS}/team/mcp-servers/{SERVER}", json={"permission": "EDIT"}, headers=ws("team-a")).status_code == 200
        assert api.alice.get(f"{GROUPS}/team/mcp-servers/{SERVER}", headers=ws("team-a")).json()["permission"] == "EDIT"
        assert [g["name"] for g in api.alice.get(f"{GROUPS}/team/mcp-servers", headers=ws("team-a")).json()] == [SERVER]
        assert api.alice.delete(f"{GROUPS}/team/mcp-servers/{SERVER}", headers=ws("team-a")).status_code == 200
        assert api.alice.get(f"{PERMS}/{SERVER}/groups", headers=ws("team-a")).json() == []

    def test_without_manage_nothing_can_be_granted_or_listed(self, api, store, alices_server):
        assert api.bob.post(f"{USERS}/{BOB}/mcp-servers/{SERVER}", json={"permission": "MANAGE"}, headers=ws("team-a")).status_code == 403
        assert api.bob.post(f"{GROUPS}/team/mcp-servers/{SERVER}", json={"permission": "MANAGE"}, headers=ws("team-a")).status_code == 403
        assert api.bob.get(f"{PERMS}/{SERVER}/users", headers=ws("team-a")).status_code == 403
        assert api.bob.get(f"{PERMS}/{SERVER}/groups", headers=ws("team-a")).status_code == 403
        assert api.bob.get(PERMS, headers=ws("team-a")).json() == []
        assert (BOB, SERVER, "team-a", "MANAGE") not in _grants(store)

    def test_managing_team_as_server_gives_no_say_over_team_bs_namesake(self, api, store, alices_server, registry):
        registry.add(SERVER, ADMIN, workspace="team-b")

        denied = api.alice.post(f"{USERS}/{BOB}/mcp-servers/{SERVER}", json={"permission": "READ"}, headers=ws("team-b"))

        assert denied.status_code == 403
        assert _grants(store) == [(ALICE, SERVER, "team-a", "MANAGE")]

    def test_admin_grants_in_the_requests_workspace(self, api, store, registry):
        response = api.admin.post(f"{USERS}/{BOB}/mcp-servers/{SERVER}", json={"permission": "READ"}, headers=ws("team-b"))

        assert response.status_code == 201
        assert _grants(store) == [(BOB, SERVER, "team-b", "READ")]

    def test_listing_servers(self, api, store, alices_server, registry):
        registry.add("com.example/other", ADMIN, workspace="team-a")

        assert [s["name"] for s in api.alice.get(PERMS, headers=ws("team-a")).json()] == [SERVER]
        assert sorted(s["name"] for s in api.admin.get(PERMS, headers=ws("team-a")).json()) == ["com.example/other", SERVER]
        listed = api.alice.get(f"{USERS}/{ALICE}/mcp-servers", headers=ws("team-a")).json()
        assert {s["name"]: s["permission"] for s in listed} == {SERVER: "MANAGE", "com.example/other": "EDIT"}

    def test_an_invalid_level_is_400_and_a_duplicate_409(self, api, store, alices_server):
        assert api.alice.post(f"{USERS}/{BOB}/mcp-servers/{SERVER}", json={"permission": "OWNER"}, headers=ws("team-a")).status_code == 400
        assert api.alice.post(f"{USERS}/{ALICE}/mcp-servers/{SERVER}", json={"permission": "READ"}, headers=ws("team-a")).status_code == 409


# ---------------------------------------------------------------------------
# Lifecycle: workspace, user and group deletion
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_deleting_a_workspace_removes_its_mcp_grants(self, store):
        with _as(ADMIN, "team-a"):
            store.create_mcp_server_permission(SERVER, ALICE, "MANAGE")
            store.create_group_mcp_server_permission("team", SERVER, "READ")
        with _as(ADMIN, "team-b"):
            store.create_mcp_server_permission(SERVER, ALICE, "READ")

        store.wipe_workspace_permissions("team-a")

        assert _grants(store) == [(ALICE, SERVER, "team-b", "READ")]
        with _as(ADMIN, "team-a"):
            assert store.list_mcp_server_groups(SERVER) == []

    def test_deleting_a_user_or_group_removes_their_grants(self, store):
        with _as(ADMIN, "team-a"):
            store.create_mcp_server_permission(SERVER, ALICE, "MANAGE")
            store.create_group_mcp_server_permission("team", SERVER, "READ")

        store.delete_user(ALICE)
        store.delete_directory_group("team", written_by="manual", admin_override=True)

        assert _grants(store) == []
        with _as(ADMIN, "team-a"):
            assert store.list_mcp_server_groups(SERVER) == []

    def test_the_last_manager_leaving_is_reported_as_an_orphan(self, store):
        from mlflow_oidc_auth.orphans import find_orphaned_resources

        with _as(ADMIN, "team-a"):
            store.create_mcp_server_permission(SERVER, ALICE, "MANAGE")

        assert ("mcp_server", f"team-a/{SERVER}") in find_orphaned_resources(ALICE, store=store)


class _as:
    """Run as ``username`` on a request naming ``workspace``, as the middleware sets it up."""

    def __init__(self, username: str, workspace: str):
        self.ctx = AuthContext(username=username, is_admin=False, workspace=workspace)

    def __enter__(self):
        self.token = set_auth_context(self.ctx)

    def __exit__(self, *exc):
        clear_auth_context(self.token)
