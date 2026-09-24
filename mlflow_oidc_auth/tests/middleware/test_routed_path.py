"""
Authorization decisions are made on the routed path.

These tests run the plugin's real middleware stack (``add_middleware_stack``, the same function
``create_app`` uses) in front of stand-in routes, and check that the unprotected-route list and
the FastAPI validator mapping are applied to the path the router dispatches — the request path
with any recorded ``root_path`` prefix removed — including when that prefix comes from
``X-Forwarded-Prefix``.
"""

import base64
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from flask import Flask, jsonify, request as flask_request
from starlette.requests import Request
from starlette.testclient import TestClient

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY
from mlflow_oidc_auth.middleware import route_path as route_path_module
from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware
from mlflow_oidc_auth.middleware.fastapi_permission_middleware import _dispatches_to_flask_mount
from mlflow_oidc_auth.middleware.route_path import is_unprotected_route, routed_path

TRUSTED = {"trusted_proxies": ["10.0.0.0/8"], "client": ("10.0.0.5", 40000)}
USER_BASIC = "Basic " + base64.b64encode(b"user@example.com:user_pass").decode()
JOBS = "/ajax-api/3.0/jobs"
GATEWAY = "/gateway/my-ep/mlflow/invocations"
FLASK_API = "/api/2.0/mlflow/experiments/search"


def _flask_stand_in() -> Flask:
    """A Flask app that, like MLflow's with the plugin's hooks, denies without an AuthContext."""
    flask_app = Flask("routed-path-test")

    @flask_app.before_request
    def require_auth_context():
        if AUTH_CONTEXT_KEY not in flask_request.environ:
            return jsonify({"detail": "Authentication required"}), 401
        return None

    @flask_app.route(FLASK_API)
    def search():
        return jsonify({"experiments": [], "served_by": "flask"})

    return flask_app


def _build_app() -> FastAPI:
    from mlflow_oidc_auth.app import add_middleware_stack

    app = FastAPI()
    add_middleware_stack(app)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/login")
    async def login():
        return {"login": True}

    @app.get(JOBS)
    async def jobs():
        return {"jobs": []}

    @app.get("/gateway/{endpoint_name}/mlflow/invocations")
    async def gateway(endpoint_name: str):
        return {"endpoint": endpoint_name}

    from mlflow_oidc_auth.routers.ui import ui_router

    app.include_router(ui_router)
    app.mount("/", AuthAwareWSGIMiddleware(_flask_stand_in()))
    return app


@pytest.fixture
def stack(mock_store, monkeypatch):
    """Build the app with the given TRUSTED_PROXIES and connecting client address."""
    monkeypatch.setattr("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store)
    monkeypatch.setattr(config, "AUTOMATIC_LOGIN_REDIRECT", False, raising=False)

    def _make(trusted_proxies=None, client=("testclient", 50000)):
        monkeypatch.setattr(config, "TRUSTED_PROXIES", list(trusted_proxies or []), raising=False)
        return TestClient(_build_app(), client=client, follow_redirects=False)

    return _make


class TestRoutedPathHelper:
    @pytest.mark.parametrize(
        "path, root_path, expected",
        [
            ("/api/2.0/x", "", "/api/2.0/x"),
            ("/mlflow/api/2.0/x", "/mlflow", "/api/2.0/x"),
            ("/api/2.0/x", "/mlflow", "/api/2.0/x"),
            ("/mlflowx/api", "/mlflow", "/mlflowx/api"),
            ("/mlflow", "/mlflow", "/"),
            ("/health/ajax-api/3.0/jobs", "/health", "/ajax-api/3.0/jobs"),
        ],
    )
    def test_routed_path(self, path, root_path, expected):
        assert routed_path({"type": "http", "path": path, "root_path": root_path}) == expected

    @pytest.mark.parametrize(
        "path, root_path",
        [("/a/b", ""), ("/p/a", "/p"), ("/p", "/p"), ("/px/a", "/p"), ("/a", "/p"), ("/p/", "/p")],
    )
    def test_fallback_matches_starlette(self, path, root_path):
        from starlette._utils import get_route_path

        scope = {"type": "http", "path": path, "root_path": root_path}
        assert route_path_module._get_route_path(scope) == get_route_path(scope)


class TestForwardedPrefixWithoutTrustedProxies:
    """TRUSTED_PROXIES unset: a forwarded prefix is ignored from every client, including loopback."""

    @pytest.fixture(params=[("testclient", 50000), ("127.0.0.1", 50000), ("10.0.0.5", 40000)])
    def client(self, request, stack):
        return stack(client=request.param)

    def test_prefix_does_not_change_the_routed_path(self, client):
        # Routed as-is: /health/ajax-api/... is no FastAPI route, so it never reaches the jobs
        # handler; it falls through to the Flask mount and is denied there.
        for headers in ({"X-Forwarded-Prefix": "/health"}, {"X-Forwarded-Prefix": "/health", "Authorization": USER_BASIC}):
            response = client.get(f"/health{JOBS}", headers=headers)
            assert response.status_code == 401
            assert "jobs" not in response.json()

    def test_prefixed_unprotected_route_is_not_stripped(self, client):
        response = client.get("/mlflow/health", headers={"X-Forwarded-Prefix": "/mlflow"})
        assert response.status_code == 401

    def test_unprefixed_routes_unchanged(self, client):
        assert client.get("/health", headers={"X-Forwarded-Prefix": "/mlflow"}).json() == {"status": "ok"}
        assert client.get(JOBS, headers={"X-Forwarded-Prefix": "/mlflow"}).status_code == 401
        response = client.get(JOBS, headers={"X-Forwarded-Prefix": "/mlflow", "Authorization": USER_BASIC})
        assert response.status_code == 200
        assert response.json() == {"jobs": []}

    def test_login_redirect_uses_no_prefix(self, client):
        headers = {"Accept": "text/html", "Sec-Fetch-Dest": "document", "X-Forwarded-Prefix": "/mlflow"}
        response = client.get("/experiments", headers=headers)
        assert response.status_code == 302
        assert response.headers["location"] == "/oidc/ui"


class TestForwardedPrefixFromTrustedProxy:
    """A trusted proxy's forwarded prefix is honoured, and decisions follow the routed path."""

    def test_protected_fastapi_route_under_unprotected_prefix_requires_credentials(self, stack):
        client = stack(**TRUSTED)
        response = client.get(f"/health{JOBS}", headers={"X-Forwarded-Prefix": "/health"})
        assert response.status_code == 401

    def test_protected_fastapi_route_under_unprotected_prefix_serves_authenticated_user(self, stack):
        client = stack(**TRUSTED)
        response = client.get(f"/health{JOBS}", headers={"X-Forwarded-Prefix": "/health", "Authorization": USER_BASIC})
        assert response.status_code == 200
        assert response.json() == {"jobs": []}

    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint", return_value=False)
    def test_validator_applied_on_routed_path_denies(self, mock_can_use, stack):
        client = stack(**TRUSTED)
        response = client.get(f"/login{GATEWAY}", headers={"X-Forwarded-Prefix": "/login", "Authorization": USER_BASIC})
        assert response.status_code == 403
        mock_can_use.assert_called_once_with("my-ep", "user@example.com")

    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint", return_value=True)
    def test_validator_applied_on_routed_path_allows(self, mock_can_use, stack):
        client = stack(**TRUSTED)
        response = client.get(f"/login{GATEWAY}", headers={"X-Forwarded-Prefix": "/login", "Authorization": USER_BASIC})
        assert response.status_code == 200
        assert response.json() == {"endpoint": "my-ep"}

    def test_gateway_route_under_unprotected_prefix_requires_credentials(self, stack):
        client = stack(**TRUSTED)
        response = client.get(f"/static-files{GATEWAY}", headers={"X-Forwarded-Prefix": "/static-files"})
        assert response.status_code == 401

    def test_flask_route_under_unprotected_prefix_requires_credentials(self, stack):
        client = stack(**TRUSTED)
        response = client.get(f"/health{FLASK_API}", headers={"X-Forwarded-Prefix": "/health"})
        assert response.status_code == 401

    def test_flask_route_under_prefix_serves_authenticated_user(self, stack):
        client = stack(**TRUSTED)
        response = client.get(f"/health{FLASK_API}", headers={"X-Forwarded-Prefix": "/health", "Authorization": USER_BASIC})
        assert response.status_code == 200
        assert response.json()["served_by"] == "flask"

    @pytest.mark.parametrize(
        "path, headers",
        [
            ("/health", {}),
            ("/mlflow/health", {"X-Forwarded-Prefix": "/mlflow"}),
            ("/health", {"X-Forwarded-Prefix": "/mlflow"}),
        ],
    )
    def test_unprotected_route_with_and_without_prefix(self, stack, path, headers):
        client = stack(**TRUSTED)
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_protected_route_without_prefix_requires_credentials(self, stack):
        client = stack(**TRUSTED)
        assert client.get(JOBS).status_code == 401
        assert client.get(FLASK_API).status_code == 401


class TestMountedDeploymentBehindTrustedProxy:
    """A deployment served under /mlflow by a proxy listed in TRUSTED_PROXIES."""

    PROXY = ("10.0.0.5", 40000)
    PREFIX = {"X-Forwarded-Prefix": "/mlflow"}

    @pytest.mark.parametrize("path", ["/mlflow/login", "/login"])
    def test_login_reachable_with_and_without_prefix_stripping(self, stack, path):
        client = stack(trusted_proxies=["10.0.0.0/8"], client=self.PROXY)
        response = client.get(path, headers=self.PREFIX)
        assert response.status_code == 200
        assert response.json() == {"login": True}

    @pytest.mark.parametrize("path", [f"/mlflow{JOBS}", JOBS])
    def test_protected_fastapi_route_requires_credentials(self, stack, path):
        client = stack(trusted_proxies=["10.0.0.0/8"], client=self.PROXY)
        assert client.get(path, headers=self.PREFIX).status_code == 401

    @pytest.mark.parametrize("path", [f"/mlflow{JOBS}", JOBS])
    def test_protected_fastapi_route_serves_authenticated_user(self, stack, path):
        client = stack(trusted_proxies=["10.0.0.0/8"], client=self.PROXY)
        response = client.get(path, headers={**self.PREFIX, "Authorization": USER_BASIC})
        assert response.status_code == 200
        assert response.json() == {"jobs": []}

    @pytest.mark.parametrize("path", [f"/mlflow{FLASK_API}", FLASK_API])
    def test_flask_route_under_prefix(self, stack, path):
        client = stack(trusted_proxies=["10.0.0.0/8"], client=self.PROXY)
        assert client.get(path, headers=self.PREFIX).status_code == 401
        response = client.get(path, headers={**self.PREFIX, "Authorization": USER_BASIC})
        assert response.status_code == 200
        assert response.json()["served_by"] == "flask"

    def test_prefix_from_untrusted_client_is_ignored(self, stack):
        client = stack(trusted_proxies=["10.0.0.0/8"], client=("192.0.2.10", 40000))
        response = client.get(f"/health{JOBS}", headers={"X-Forwarded-Prefix": "/health"})
        # Without a recorded prefix the request is routed as-is; it reaches no FastAPI route,
        # falls through to the Flask mount and is denied there for lack of an AuthContext.
        assert response.status_code == 401
        assert client.get("/health").status_code == 200


class TestEveryFastapiRouteRequiresAUser:
    """Every FastAPI route of the real application that is not an unprotected route answers 401
    when a request reaches the permission middleware without an authenticated user.

    Enumerates the live route table, so a router MLflow or this plugin adds later is covered
    without editing this test.
    """

    @staticmethod
    def _concrete(path_template: str) -> str:
        import re

        return re.sub(r"\{[^}]+\}", "x", path_template)

    def _routes(self):
        """Return the real app and its FastAPI routes as ``(path_template, methods)`` pairs.

        Newer FastAPI keeps included routers as nested entries in ``app.router.routes``;
        ``iter_route_contexts`` flattens them with their full prefixed path.
        """
        from mlflow_oidc_auth.app import app as real_app

        try:
            from fastapi.routing import iter_route_contexts
        except ImportError:  # older FastAPI: included routes are already flat
            flat = [(r.path, set(r.methods)) for r in real_app.router.routes if isinstance(r, APIRoute)]
        else:
            flat = [(c.path, set(c.methods or ())) for c in iter_route_contexts(real_app.router.routes) if isinstance(c.original_route, APIRoute)]
        return real_app, flat

    def test_route_table_contains_fastapi_routes(self):
        _, routes = self._routes()
        assert routes, "expected the application to serve FastAPI routes"

    def test_unauthenticated_request_is_refused_on_every_protected_route(self):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import add_fastapi_permission_middleware

        real_app, routes = self._routes()
        # The real route table behind the permission middleware alone: this is what a request
        # without a user would meet if it ever got past AuthMiddleware.
        probe = FastAPI()
        probe.router.routes = list(real_app.router.routes)
        add_fastapi_permission_middleware(probe)
        client = TestClient(probe, raise_server_exceptions=False)

        checked = 0
        not_refused = []
        for template, methods in routes:
            path = self._concrete(template)
            if is_unprotected_route(path):
                continue
            for method in sorted(methods - {"HEAD", "OPTIONS"}):
                response = client.request(method, path)
                checked += 1
                if response.status_code != 401:
                    not_refused.append((method, template, response.status_code))

        assert checked > 0
        assert not_refused == []

    def test_flask_mount_is_recognised(self):
        real_app, _ = self._routes()
        scope = {"type": "http", "method": "GET", "path": FLASK_API, "root_path": "", "headers": [], "app": real_app}
        assert _dispatches_to_flask_mount(Request(scope)) is True

    def test_fastapi_route_is_not_mistaken_for_the_flask_mount(self):
        real_app, routes = self._routes()
        template = next(t for t, methods in routes if "GET" in methods and not is_unprotected_route(self._concrete(t)))
        scope = {"type": "http", "method": "GET", "path": self._concrete(template), "root_path": "", "headers": [], "app": real_app}
        assert _dispatches_to_flask_mount(Request(scope)) is False


class TestRedirectPrefixFollowsProxyTrust:
    """Redirect targets use the prefix recorded for a trusted hop, never the raw header."""

    DOCUMENT = {"Accept": "text/html", "Sec-Fetch-Dest": "document"}

    def test_untrusted_client_prefix_not_applied_to_login_redirect(self, stack):
        client = stack(trusted_proxies=["10.0.0.0/8"], client=("192.0.2.10", 40000))
        response = client.get("/experiments", headers={**self.DOCUMENT, "X-Forwarded-Prefix": "/mlflow"})
        assert response.status_code == 302
        assert response.headers["location"] == "/oidc/ui"

    def test_trusted_proxy_prefix_applied_to_login_redirect(self, stack):
        client = stack(trusted_proxies=["10.0.0.0/8"], client=("10.0.0.5", 40000))
        response = client.get("/mlflow/experiments", headers={**self.DOCUMENT, "X-Forwarded-Prefix": "/mlflow"})
        assert response.status_code == 302
        assert response.headers["location"] == "/mlflow/oidc/ui"

    def test_non_path_prefix_dropped_from_login_redirect(self, stack):
        client = stack(**TRUSTED)
        response = client.get("/experiments", headers={**self.DOCUMENT, "X-Forwarded-Prefix": "//other.example"})
        assert response.status_code == 302
        assert response.headers["location"] == "/oidc/ui"

    @pytest.mark.parametrize(
        "trusted, client_addr, prefix, expected",
        [
            (["10.0.0.0/8"], ("192.0.2.10", 40000), "/mlflow", "/oidc/ui/"),
            (["10.0.0.0/8"], ("10.0.0.5", 40000), "/mlflow", "/mlflow/oidc/ui/"),
            ([], ("testclient", 50000), "/mlflow", "/oidc/ui/"),
            (["10.0.0.0/8"], ("10.0.0.5", 40000), "//other.example", "/oidc/ui/"),
        ],
    )
    def test_ui_redirect_prefix(self, stack, trusted, client_addr, prefix, expected):
        client = stack(trusted_proxies=trusted, client=client_addr)
        response = client.get("/oidc/ui", headers={"X-Forwarded-Prefix": prefix})
        assert response.status_code == 307
        assert response.headers["location"] == expected
