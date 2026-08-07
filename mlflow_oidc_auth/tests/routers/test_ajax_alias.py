"""Tests for the "/ajax-api" aliasing of this plugin's own routers.

MLflow's web UI calls "/ajax-api/..." while API clients call "/api/...".
Registering only the latter left UI endpoints such as
``GET /ajax-api/2.0/mlflow/users/current`` returning 404.
"""

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.routers import ajax_alias_router
from mlflow_oidc_auth.routers._prefix import USERS_ROUTER_PREFIX, to_ajax_path


class TestToAjaxPath:
    """Test the "/api" -> "/ajax-api" path mapping."""

    def test_maps_v2_path(self):
        assert to_ajax_path("/api/2.0/mlflow/users/current") == "/ajax-api/2.0/mlflow/users/current"

    def test_maps_v3_path(self):
        assert to_ajax_path("/api/3.0/mlflow/permissions/workspaces") == "/ajax-api/3.0/mlflow/permissions/workspaces"

    def test_returns_none_for_non_api_paths(self):
        # Health checks and the "/oidc/*" routes have no UI-facing twin.
        assert to_ajax_path("/health") is None
        assert to_ajax_path("/oidc/ui/index.html") is None

    def test_does_not_double_prefix_an_ajax_path(self):
        assert to_ajax_path("/ajax-api/2.0/mlflow/users/current") is None

    def test_matches_the_real_users_prefix(self):
        # Guards against MLflow changing its prefixes underneath us.
        assert to_ajax_path(f"{USERS_ROUTER_PREFIX}/current") == "/ajax-api/2.0/mlflow/users/current"


class TestAjaxAliasRouter:
    """Test mirroring of router routes onto the "/ajax-api" prefix."""

    def test_mirrors_api_routes(self):
        router = APIRouter(prefix="/api/2.0/mlflow/users")

        @router.get("/current")
        async def current():  # pragma: no cover - never invoked, only routed
            return {}

        paths = {route.path for route in ajax_alias_router(router).routes}
        assert paths == {"/ajax-api/2.0/mlflow/users/current"}

    def test_preserves_methods(self):
        router = APIRouter(prefix="/api/2.0/mlflow/users")

        @router.patch("/access-token")
        async def token():  # pragma: no cover
            return {}

        (route,) = ajax_alias_router(router).routes
        assert route.methods == {"PATCH"}

    def test_skips_non_api_routes(self):
        router = APIRouter(prefix="/oidc/ui")

        @router.get("/index.html")
        async def index():  # pragma: no cover
            return {}

        assert ajax_alias_router(router).routes == []

    def test_aliases_are_hidden_from_the_openapi_schema(self):
        # The "/api" paths stay the documented ones so the schema is not doubled.
        router = APIRouter(prefix="/api/2.0/mlflow/users")

        @router.get("/current")
        async def current():  # pragma: no cover
            return {}

        (route,) = ajax_alias_router(router).routes
        assert route.include_in_schema is False

    def test_both_prefixes_are_served_by_the_same_handler(self):
        router = APIRouter(prefix="/api/2.0/mlflow/users")

        @router.get("/current")
        async def current():
            return {"username": "alice", "is_admin": True}

        app = FastAPI()
        app.include_router(router)
        app.include_router(ajax_alias_router(router))
        client = TestClient(app)

        expected = {"username": "alice", "is_admin": True}
        assert client.get("/api/2.0/mlflow/users/current").json() == expected
        # This is the request MLflow's UI actually makes; before the alias it 404'd.
        ajax = client.get("/ajax-api/2.0/mlflow/users/current")
        assert ajax.status_code == 200
        assert ajax.json() == expected
