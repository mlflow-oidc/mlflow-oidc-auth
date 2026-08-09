"""Tests for the "/ajax-api" aliasing of this plugin's own routers.

MLflow's web UI calls "/ajax-api/..." while API clients call "/api/...".
Registering only the latter left UI endpoints such as
``GET /ajax-api/2.0/mlflow/users/current`` returning 404.
"""

import inspect
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import BaseModel

from mlflow_oidc_auth.routers import _COPIED_ROUTE_FIELDS, ajax_alias_router
from mlflow_oidc_auth.routers._prefix import (
    HEALTH_CHECK_ROUTER_PREFIX,
    USERS_ROUTER_PREFIX,
    to_ajax_path,
)


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


class _Status(BaseModel):
    status: str
    detail: Optional[str] = None


class TestAliasFidelity:
    """A twin must behave exactly like the "/api" route it mirrors."""

    def test_preserves_response_model_serialization_options(self):
        # Several handlers set response_model_exclude_none=True; dropping it on
        # the twin would hand the UI a different payload than API clients get.
        router = APIRouter(prefix="/api/2.0/mlflow/users")

        @router.delete("/{username}", response_model=_Status, response_model_exclude_none=True)
        async def delete_user(username: str):
            return _Status(status="ok")

        app = FastAPI()
        app.include_router(router)
        app.include_router(ajax_alias_router(router))
        client = TestClient(app)

        assert client.delete("/api/2.0/mlflow/users/alice").json() == {"status": "ok"}
        assert client.delete("/ajax-api/2.0/mlflow/users/alice").json() == {"status": "ok"}

    def test_preserves_router_level_dependencies(self):
        # Router-level dependencies are where the admin checks live; a twin
        # without them would be an unauthenticated copy of a guarded endpoint.
        calls = []

        async def guard():
            calls.append(True)

        router = APIRouter(prefix="/api/2.0/mlflow/users", dependencies=[Depends(guard)])

        @router.get("/current")
        async def current():
            return {}

        app = FastAPI()
        app.include_router(ajax_alias_router(router))
        TestClient(app).get("/ajax-api/2.0/mlflow/users/current")

        assert calls == [True]

    def test_preserves_status_code(self):
        router = APIRouter(prefix="/api/2.0/mlflow/users")

        @router.post("/", status_code=201)
        async def create():
            return {}

        (route,) = ajax_alias_router(router).routes
        assert route.status_code == 201

    def test_preserves_a_custom_route_class(self):
        class CustomRoute(APIRoute):
            pass

        router = APIRouter(prefix="/api/2.0/mlflow/users", route_class=CustomRoute)

        @router.get("/current")
        async def current():  # pragma: no cover
            return {}

        (route,) = ajax_alias_router(router).routes
        assert isinstance(route, CustomRoute)

    def test_copied_fields_cover_every_route_option(self):
        """Guard against a FastAPI upgrade adding a route option we silently drop.

        Every ``add_api_route`` keyword is either copied from the original route
        or set deliberately by ``ajax_alias_router``. If this fails, decide which
        bucket the new keyword belongs in rather than just widening the list.
        """
        # Keywords that describe where/how the twin is mounted, not the route.
        mount_fields = {
            "self",
            "path",
            "endpoint",
            "methods",
            "name",
            "include_in_schema",
            "route_class_override",
        }
        signature_fields = set(inspect.signature(APIRouter.add_api_route).parameters)

        assert signature_fields - mount_fields == set(_COPIED_ROUTE_FIELDS)


class TestAppRegistration:
    """The app-level helper must register both prefixes for real routers.

    These assert through the app's routing rather than by walking ``app.routes``:
    FastAPI 0.141 wraps each ``include_router()`` call in an internal router
    object, so the leaf routes are no longer reachable by inspection. What
    matters is where a request actually lands, and that holds either way.
    """

    @staticmethod
    def _status_for(app: FastAPI, path: str) -> int:
        # Server exceptions become 500s instead of propagating: these handlers
        # need an auth context that a bare TestClient request does not set up,
        # and the question here is only which of them the request reaches.
        return TestClient(app, raise_server_exceptions=False).get(path).status_code

    def test_include_router_registers_both_prefixes(self):
        from mlflow_oidc_auth.app import _include_router
        from mlflow_oidc_auth.routers.users import users_router

        app = FastAPI()
        _include_router(app, users_router)

        api_status = self._status_for(app, f"{USERS_ROUTER_PREFIX}/current")
        ajax_status = self._status_for(app, "/ajax-api/2.0/mlflow/users/current")

        assert api_status != 404, "the canonical /api route should be registered"
        # Same handler, same outcome - the twin must not 404 or diverge.
        assert ajax_status == api_status

    def test_include_router_skips_an_empty_alias(self):
        from mlflow_oidc_auth.app import _include_router
        from mlflow_oidc_auth.routers.health import health_check_router

        app = FastAPI()
        _include_router(app, health_check_router)

        assert self._status_for(app, HEALTH_CHECK_ROUTER_PREFIX) != 404
        # Health checks are not part of the REST surface, so there is no twin.
        assert self._status_for(app, f"/ajax-api{HEALTH_CHECK_ROUTER_PREFIX}") == 404
