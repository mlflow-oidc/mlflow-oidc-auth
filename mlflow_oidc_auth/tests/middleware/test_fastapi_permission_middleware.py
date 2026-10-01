"""
Tests for FastAPI Permission Middleware.

This module tests the OIDC-aware permission middleware for FastAPI-native routes
(gateway invocations, OTel trace ingestion, assistant, job API) that bypass Flask.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Unit tests: _extract_gateway_endpoint_name
# ---------------------------------------------------------------------------


class TestExtractGatewayEndpointName:
    """Test endpoint name extraction from gateway URL patterns."""

    def _extract(self, path, body=None):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
            _extract_gateway_endpoint_name,
        )

        return _extract_gateway_endpoint_name(path, body)

    def test_invocations_route(self):
        """Test /gateway/{endpoint_name}/mlflow/invocations pattern."""
        assert self._extract("/gateway/my-endpoint/mlflow/invocations") == "my-endpoint"

    def test_invocations_route_complex_name(self):
        """Test invocations route with complex endpoint name."""
        assert self._extract("/gateway/gpt-4-turbo/mlflow/invocations") == "gpt-4-turbo"

    def test_invocations_route_no_match(self):
        """Test invocations pattern with wrong suffix."""
        assert self._extract("/gateway/my-endpoint/mlflow/other") is None

    def test_raw_proxy_route(self):
        """``/gateway/proxy/{endpoint_name}/{path}``: the endpoint is the segment after /proxy/."""
        assert self._extract("/gateway/proxy/my-endpoint/v1/chat/completions") == "my-endpoint"
        assert self._extract("/gateway/proxy/my-endpoint/v1/embeddings", {"model": "someone-else"}) == "my-endpoint"

    def test_raw_proxy_route_provider_path_may_be_empty(self):
        """Like MLflow's ``{path:path}``, the provider path may be empty — but the slash after the
        endpoint is part of the route, and without an endpoint nothing is extracted."""
        assert self._extract("/gateway/proxy/my-endpoint/") == "my-endpoint"
        assert self._extract("/gateway/proxy/my-endpoint") is None
        assert self._extract("/gateway/proxy/") is None
        assert self._extract("/gateway/proxy//v1/chat") is None

    def test_an_endpoint_named_proxy_is_resolved_like_the_router(self):
        """MLflow registers the invocations route before the raw proxy, so it serves this path as the
        invocations of an endpoint named ``proxy``; authorization must judge that same endpoint."""
        assert self._extract("/gateway/proxy/mlflow/invocations") == "proxy"

    def test_chat_completions_mlflow(self):
        """Test MLflow chat completions passthrough."""
        result = self._extract("/gateway/mlflow/v1/chat/completions", {"model": "my-model"})
        assert result == "my-model"

    def test_chat_completions_openai(self):
        """Test OpenAI chat completions passthrough."""
        result = self._extract("/gateway/openai/v1/chat/completions", {"model": "gpt-4"})
        assert result == "gpt-4"

    def test_typesafe_system_one(self):
        """MLflow 3.17+ TypeSafe System One passthrough: endpoint in the body's ``model``."""
        assert self._extract("/gateway/typesafe/v1/systemone", {"model": "typesafe-ep"}) == "typesafe-ep"
        assert self._extract("/gateway/typesafe/v1/systemone", None) is None

    def test_embeddings_openai(self):
        """Test OpenAI embeddings passthrough."""
        result = self._extract("/gateway/openai/v1/embeddings", {"model": "text-embedding-ada"})
        assert result == "text-embedding-ada"

    def test_responses_openai(self):
        """Test OpenAI responses passthrough."""
        result = self._extract("/gateway/openai/v1/responses", {"model": "gpt-4o"})
        assert result == "gpt-4o"

    def test_anthropic_messages(self):
        """Test Anthropic messages passthrough."""
        result = self._extract("/gateway/anthropic/v1/messages", {"model": "claude-3"})
        assert result == "claude-3"

    def test_passthrough_no_body(self):
        """Test passthrough route with no body returns None."""
        assert self._extract("/gateway/mlflow/v1/chat/completions", None) is None

    def test_passthrough_no_model_in_body(self):
        """Test passthrough route with body missing 'model' key."""
        assert self._extract("/gateway/mlflow/v1/chat/completions", {"prompt": "hi"}) is None

    def test_gemini_generate_content(self):
        """Test Gemini generateContent pattern."""
        result = self._extract("/gateway/gemini/v1beta/models/gemini-pro:generateContent")
        assert result == "gemini-pro"

    def test_gemini_stream_generate_content(self):
        """Test Gemini streamGenerateContent pattern."""
        result = self._extract("/gateway/gemini/v1beta/models/gemini-ultra:streamGenerateContent")
        assert result == "gemini-ultra"

    def test_gemini_no_match(self):
        """Test Gemini pattern with wrong action."""
        assert self._extract("/gateway/gemini/v1beta/models/foo:otherAction") is None

    def test_unrelated_path(self):
        """Test unrelated paths return None."""
        assert self._extract("/api/experiments") is None
        assert self._extract("/v1/traces") is None


# ---------------------------------------------------------------------------
# Unit tests: _find_fastapi_validator
# ---------------------------------------------------------------------------


class TestFindFastapiValidator:
    """Test route-to-validator dispatcher."""

    def _find(self, path):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
            _find_fastapi_validator,
        )

        return _find_fastapi_validator(path)

    def test_gateway_route_returns_validator(self):
        """Test gateway routes return a validator."""
        assert self._find("/gateway/my-endpoint/mlflow/invocations") is not None

    def test_otel_route_returns_validator(self):
        """Test OTel routes return a validator."""
        assert self._find("/v1/traces") is not None
        assert self._find("/v1/traces/something") is not None

    def test_jobs_route_returns_validator(self):
        """Test job API routes return a validator."""
        assert self._find("/ajax-api/3.0/jobs") is not None
        assert self._find("/ajax-api/3.0/jobs/some-job") is not None

    def test_assistant_route_returns_validator(self):
        """Test assistant routes return a validator."""
        assert self._find("/ajax-api/3.0/mlflow/assistant") is not None
        assert self._find("/ajax-api/3.0/mlflow/assistant/chat") is not None

    @pytest.mark.parametrize(
        "path",
        [
            "/mlflow/api/3.0/mlflow/mcp-servers",
            "/mlflow/api/3.0/mlflow/mcp-servers/com.example/server",
            "/mlflow/ajax-api/3.0/mlflow/mcp-servers/endpoints",
        ],
    )
    def test_mcp_server_registry_routes_behind_a_static_prefix_return_validator(self, path, monkeypatch):
        """MLflow mounts the registry behind its static prefix; the validator must still apply there."""
        from mlflow.server.handlers import STATIC_PREFIX_ENV_VAR

        monkeypatch.setenv(STATIC_PREFIX_ENV_VAR, "/mlflow")
        assert self._find(path) is not None

    def test_mcp_server_registry_routes_return_validator(self):
        """Test MCP server registry routes return a validator on both prefixes."""
        assert self._find("/api/3.0/mlflow/mcp-servers") is not None
        assert self._find("/api/3.0/mlflow/mcp-servers/com.example/server") is not None
        assert self._find("/ajax-api/3.0/mlflow/mcp-servers") is not None
        assert self._find("/ajax-api/3.0/mlflow/mcp-servers/endpoints") is not None

    def test_flask_route_returns_none(self):
        """Test Flask-handled routes return None (pass-through)."""
        assert self._find("/api/2.0/mlflow/experiments/list") is None
        assert self._find("/health") is None
        assert self._find("/oidc/ui") is None

    def test_root_returns_none(self):
        """Test root path returns None."""
        assert self._find("/") is None


# ---------------------------------------------------------------------------
# Unit tests: gateway validator logic
# ---------------------------------------------------------------------------


class TestGatewayValidator:
    """Test gateway validator permission checking."""

    def _get_gateway_validator(self, path):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
            _get_gateway_validator,
        )

        return _get_gateway_validator(path)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    async def test_invocations_allowed(self, mock_can_use):
        """Test gateway invocation with USE permission succeeds."""
        mock_can_use.return_value = True
        validator = self._get_gateway_validator("/gateway/my-endpoint/mlflow/invocations")
        request = MagicMock(spec=Request)
        result = await validator("user@example.com", request)
        assert result is True
        mock_can_use.assert_called_once_with("my-endpoint", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    async def test_invocations_denied(self, mock_can_use):
        """Test gateway invocation without USE permission fails."""
        mock_can_use.return_value = False
        validator = self._get_gateway_validator("/gateway/my-endpoint/mlflow/invocations")
        request = MagicMock(spec=Request)
        result = await validator("user@example.com", request)
        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("allowed", [True, False])
    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    async def test_raw_proxy_requires_use_on_the_endpoint_in_the_path(self, mock_can_use, allowed):
        """The raw proxy is judged by the endpoint in its path, never by the body it forwards."""
        mock_can_use.return_value = allowed
        validator = self._get_gateway_validator("/gateway/proxy/my-endpoint/v1/chat/completions")
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value={"model": "another-endpoint"})

        assert await validator("user@example.com", request) is allowed
        mock_can_use.assert_called_once_with("my-endpoint", "user@example.com")
        request.json.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    async def test_passthrough_reads_body(self, mock_can_use):
        """Test passthrough route reads body to extract model name."""
        mock_can_use.return_value = True
        validator = self._get_gateway_validator("/gateway/openai/v1/chat/completions")
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value={"model": "gpt-4"})
        request.state = MagicMock()

        result = await validator("user@example.com", request)
        assert result is True
        mock_can_use.assert_called_once_with("gpt-4", "user@example.com")

    @pytest.mark.asyncio
    async def test_passthrough_bad_json(self):
        """Test passthrough route with unparseable body returns False."""
        validator = self._get_gateway_validator("/gateway/openai/v1/chat/completions")
        request = MagicMock(spec=Request)
        request.json = AsyncMock(side_effect=ValueError("bad json"))
        request.state = MagicMock()

        result = await validator("user@example.com", request)
        assert result is False

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    async def test_gemini_route(self, mock_can_use):
        """Test Gemini generateContent route extracts endpoint name."""
        mock_can_use.return_value = True
        validator = self._get_gateway_validator("/gateway/gemini/v1beta/models/gemini-pro:generateContent")
        request = MagicMock(spec=Request)
        result = await validator("user@example.com", request)
        assert result is True
        mock_can_use.assert_called_once_with("gemini-pro", "user@example.com")


# ---------------------------------------------------------------------------
# Unit tests: OTel validator logic
# ---------------------------------------------------------------------------


class TestOtelValidator:
    """Test OTel trace ingestion validator."""

    def _get_otel_validator(self, path):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
            _get_otel_validator,
        )

        return _get_otel_validator(path)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    async def test_otel_with_experiment_id_allowed(self, mock_perm):
        """Test OTel with valid experiment ID and UPDATE permission."""
        mock_result = MagicMock()
        mock_result.permission.can_update = True
        mock_perm.return_value = mock_result

        validator = self._get_otel_validator("/v1/traces")
        request = MagicMock(spec=Request)
        request.headers = {"x-mlflow-experiment-id": "42"}

        result = await validator("user@example.com", request)
        assert result is True
        mock_perm.assert_called_once_with("42", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    async def test_otel_with_experiment_id_denied(self, mock_perm):
        """Test OTel with valid experiment ID but no UPDATE permission."""
        mock_result = MagicMock()
        mock_result.permission.can_update = False
        mock_perm.return_value = mock_result

        validator = self._get_otel_validator("/v1/traces")
        request = MagicMock(spec=Request)
        request.headers = {"x-mlflow-experiment-id": "42"}

        result = await validator("user@example.com", request)
        assert result is False

    @pytest.mark.asyncio
    async def test_otel_missing_experiment_header(self):
        """Test OTel without X-Mlflow-Experiment-Id header returns False."""
        validator = self._get_otel_validator("/v1/traces")
        request = MagicMock(spec=Request)
        request.headers = {}

        result = await validator("user@example.com", request)
        assert result is False


# ---------------------------------------------------------------------------
# Unit tests: require-authentication validator
# ---------------------------------------------------------------------------


class TestRequireAuthenticationValidator:
    """Test the simple authentication-only validator."""

    @pytest.mark.asyncio
    async def test_any_user_allowed(self):
        """Test that any authenticated user passes."""
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
            _get_require_authentication_validator,
        )

        validator = _get_require_authentication_validator()
        request = MagicMock(spec=Request)
        result = await validator("user@example.com", request)
        assert result is True


# ---------------------------------------------------------------------------
# MCP server registry through this middleware (full coverage: test_mcp_server_registry.py)
# ---------------------------------------------------------------------------


class TestMCPServerRegistryThroughTheMiddleware:
    """The registry's per-server checks run here, on the routed path, whatever MLflow's version."""

    @staticmethod
    def _app(username, is_admin, workspace, prefix=""):
        app = _create_app_with_auth(username=username, is_admin=is_admin, workspace=workspace)

        @app.api_route(prefix + "/api/3.0/mlflow/mcp-servers", methods=["GET", "POST"])
        async def mcp_root():
            return {"mcp_servers": [{"name": "com.example/a"}, {"name": "com.example/b"}], "next_page_token": None}

        @app.api_route(prefix + "/api/3.0/mlflow/mcp-servers/{name:path}", methods=["GET", "PATCH", "DELETE"])
        async def mcp_server(name: str):
            return {"name": name}

        # Route order matters: the catch-all Flask mount was added first, so move these routes ahead of it.
        app.router.routes.insert(0, app.router.routes.pop())
        app.router.routes.insert(0, app.router.routes.pop())
        return app

    @staticmethod
    def _grants(workspace_grants, server_grants=None):
        """Workspaces on; workspace grants by (user, workspace); server permissions by name."""
        from contextlib import ExitStack

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.models import PermissionResult
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS

        server_grants = server_grants or {}
        stack = ExitStack()
        stack.enter_context(patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True))
        stack.enter_context(
            patch(
                "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                side_effect=lambda username, ws: workspace_grants.get((username, ws)),
            )
        )
        stack.enter_context(
            patch(
                "mlflow_oidc_auth.utils.permissions.effective_mcp_server_permission",
                side_effect=lambda name, username: PermissionResult(server_grants.get(name, NO_PERMISSIONS), "user"),
            )
        )
        return stack

    def test_another_tenants_server_is_403(self):
        from mlflow_oidc_auth.permissions import MANAGE

        with self._grants({("user@example.com", "team-a"): MANAGE}):
            client = TestClient(self._app("user@example.com", False, "team-b"))
            response = client.get("/api/3.0/mlflow/mcp-servers/com.example/a")
            assert response.status_code == 403
            response = client.patch("/api/3.0/mlflow/mcp-servers/com.example/a", json={})
            assert response.status_code == 403
            response = client.delete("/api/3.0/mlflow/mcp-servers/com.example/a")
            assert response.status_code == 403
            response = client.post("/api/3.0/mlflow/mcp-servers", json={"name": "com.example/new"})
            assert response.status_code == 403

    def test_the_search_is_narrowed_to_readable_servers(self):
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS, READ

        # A member of team-a (searching a registry needs READ on its workspace).
        with self._grants({("user@example.com", "team-a"): READ}, {"com.example/a": READ, "com.example/b": NO_PERMISSIONS}):
            response = TestClient(self._app("user@example.com", False, "team-a")).get("/api/3.0/mlflow/mcp-servers")

        assert response.status_code == 200
        assert [s["name"] for s in response.json()["mcp_servers"]] == ["com.example/a"]

    def test_static_prefix_does_not_bypass_the_check(self, monkeypatch):
        """With ``--static-prefix`` the registry is mounted under it: reads and writes are still judged."""
        from mlflow.server.handlers import STATIC_PREFIX_ENV_VAR

        from mlflow_oidc_auth.permissions import MANAGE

        monkeypatch.setenv(STATIC_PREFIX_ENV_VAR, "/mlflow")
        client = TestClient(self._app("user@example.com", False, "team-b", prefix="/mlflow"))
        with self._grants({("user@example.com", "team-a"): MANAGE}):
            response = client.get("/mlflow/api/3.0/mlflow/mcp-servers/com.example/a")
            assert response.status_code == 403
            response = client.post("/mlflow/api/3.0/mlflow/mcp-servers", json={"name": "com.example/new"})
            assert response.status_code == 403
            response = client.get("/mlflow/api/3.0/mlflow/mcp-servers")
            assert response.status_code == 403

    def test_admin_reads_any_workspace_unfiltered(self):
        with self._grants({}):
            response = TestClient(self._app("admin@example.com", True, "team-b")).get("/api/3.0/mlflow/mcp-servers")

        assert response.status_code == 200
        assert len(response.json()["mcp_servers"]) == 2


# ---------------------------------------------------------------------------
# Helper: create app with auth context injection + permission middleware
# ---------------------------------------------------------------------------


def _create_app_with_auth(username=None, is_admin=False, workspace=None):
    """Create a test FastAPI app with auth context and permission middleware.

    Starlette ``@app.middleware("http")`` uses LIFO ordering: the last middleware
    registered wraps the outermost layer and runs first.  We must register the
    permission middleware FIRST, then the auth-context middleware, so that
    auth context is set before the permission middleware reads it.
    """
    from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
    from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
        add_fastapi_permission_middleware,
    )

    app = FastAPI()

    @app.get("/gateway/{endpoint_name}/mlflow/invocations")
    async def gateway_invocations(endpoint_name: str):
        return {"endpoint": endpoint_name}

    @app.get("/v1/traces")
    async def otel_traces():
        # Report whether the bridge ContextVar is still set once the route handler runs.
        # The permission middleware must clear it before ``call_next``; asserting this
        # from the TestClient thread would always see ``None`` and prove nothing.
        from mlflow_oidc_auth.bridge.user import _auth_context_var

        return {"traces": [], "auth_context_var_set": _auth_context_var.get() is not None}

    @app.get("/ajax-api/3.0/jobs")
    async def list_jobs():
        return {"jobs": []}

    @app.get("/ajax-api/3.0/mlflow/assistant/chat")
    async def assistant_chat():
        return {"response": "hello"}

    @app.get("/api/2.0/mlflow/plugin-native")
    async def fastapi_route_without_validator():
        return {"served_by": "fastapi"}

    # Stand-in for MLflow's Flask app, mounted the way ``create_app`` mounts the real one.
    # The Flask side authorizes on its own, so the permission middleware passes it through.
    from flask import Flask

    from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware

    flask_app = Flask("permission-middleware-test")

    @flask_app.route("/api/2.0/mlflow/experiments/list")
    def flask_passthrough():
        return {"experiments": []}

    app.mount("/", AuthAwareWSGIMiddleware(flask_app))

    # Register permission middleware FIRST (will be inner)
    add_fastapi_permission_middleware(app)

    # Register auth context SECOND (will be outer — runs first)
    if username is not None:

        @app.middleware("http")
        async def inject_auth_context(request: Request, call_next):
            request.state.username = username
            request.state.is_admin = is_admin
            request.scope[AUTH_CONTEXT_KEY] = AuthContext(username=username, is_admin=is_admin, workspace=workspace)
            return await call_next(request)

    return app


# ---------------------------------------------------------------------------
# Integration tests: full middleware with TestClient
# ---------------------------------------------------------------------------


class TestFastapiPermissionMiddlewareIntegration:
    """Integration tests for the middleware using FastAPI TestClient."""

    def _create_app_with_middleware(self):
        """Create a test app with no auth context (unauthenticated)."""
        return _create_app_with_auth(username=None)

    def test_unauthenticated_gateway_returns_401(self):
        """Test that gateway route without auth returns 401."""
        app = self._create_app_with_middleware()
        client = TestClient(app)
        response = client.get("/gateway/my-ep/mlflow/invocations")
        assert response.status_code == 401

    def test_unauthenticated_otel_returns_401(self):
        """Test that OTel route without auth returns 401."""
        app = self._create_app_with_middleware()
        client = TestClient(app)
        response = client.get("/v1/traces")
        assert response.status_code == 401

    def test_unauthenticated_jobs_returns_401(self):
        """Test that jobs route without auth returns 401."""
        app = self._create_app_with_middleware()
        client = TestClient(app)
        response = client.get("/ajax-api/3.0/jobs")
        assert response.status_code == 401

    def test_unauthenticated_assistant_returns_401(self):
        """Test that assistant route without auth returns 401."""
        app = self._create_app_with_middleware()
        client = TestClient(app)
        response = client.get("/ajax-api/3.0/mlflow/assistant/chat")
        assert response.status_code == 401

    def test_admin_gateway_passes(self):
        """Test that admin user passes gateway check."""
        app = _create_app_with_auth(username="admin@example.com", is_admin=True)
        client = TestClient(app)
        response = client.get("/gateway/my-ep/mlflow/invocations")
        assert response.status_code == 200
        assert response.json() == {"endpoint": "my-ep"}

    def test_admin_otel_passes(self):
        """Test that admin user passes OTel check."""
        app = _create_app_with_auth(username="admin@example.com", is_admin=True)
        client = TestClient(app)
        response = client.get("/v1/traces")
        assert response.status_code == 200

    def test_admin_jobs_passes(self):
        """Test that admin user passes jobs check."""
        app = _create_app_with_auth(username="admin@example.com", is_admin=True)
        client = TestClient(app)
        response = client.get("/ajax-api/3.0/jobs")
        assert response.status_code == 200

    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    def test_regular_user_gateway_with_permission(self, mock_can_use):
        """Test that non-admin user with USE permission passes gateway."""
        mock_can_use.return_value = True
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/gateway/my-ep/mlflow/invocations")
        assert response.status_code == 200
        mock_can_use.assert_called_once_with("my-ep", "user@example.com")

    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    def test_regular_user_gateway_without_permission(self, mock_can_use):
        """Test that non-admin user without USE permission gets 403."""
        mock_can_use.return_value = False
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/gateway/my-ep/mlflow/invocations")
        assert response.status_code == 403

    def test_flask_route_passes_through(self):
        """Test that Flask-handled routes pass through without permission check."""
        app = self._create_app_with_middleware()
        client = TestClient(app)
        response = client.get("/api/2.0/mlflow/experiments/list")
        assert response.status_code == 200

    def test_unauthenticated_fastapi_route_without_validator_returns_401(self):
        """A FastAPI route with no validator mapping still requires an authenticated user."""
        app = self._create_app_with_middleware()
        client = TestClient(app)
        response = client.get("/api/2.0/mlflow/plugin-native")
        assert response.status_code == 401

    def test_authenticated_fastapi_route_without_validator_passes(self):
        """With a user, a FastAPI route with no validator is left to its own dependencies."""
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/api/2.0/mlflow/plugin-native")
        assert response.status_code == 200
        assert response.json() == {"served_by": "fastapi"}

    def test_unauthenticated_unmatched_path_returns_401(self):
        """A path no route serves is not passed through unauthenticated either."""
        app = FastAPI()
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import add_fastapi_permission_middleware

        add_fastapi_permission_middleware(app)
        response = TestClient(app).get("/api/2.0/mlflow/not-a-route")
        assert response.status_code == 401

    def test_authenticated_user_other_method_on_jobs_prefix_is_denied(self):
        """Only POST (submit) is served on the job API prefix; other methods are refused."""
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/ajax-api/3.0/jobs")
        assert response.status_code == 403

    def test_authenticated_user_assistant_passes(self):
        """Test that any authenticated user passes assistant check."""
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/ajax-api/3.0/mlflow/assistant/chat")
        assert response.status_code == 200

    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    def test_regular_user_otel_with_update_permission(self, mock_perm):
        """Test that non-admin user with UPDATE permission passes OTel."""
        mock_result = MagicMock()
        mock_result.permission.can_update = True
        mock_perm.return_value = mock_result

        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})
        assert response.status_code == 200
        mock_perm.assert_called_once_with("42", "user@example.com")

    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    def test_regular_user_otel_without_update_permission(self, mock_perm):
        """Test that non-admin user without UPDATE permission gets 403."""
        mock_result = MagicMock()
        mock_result.permission.can_update = False
        mock_perm.return_value = mock_result

        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})
        assert response.status_code == 403

    def test_regular_user_otel_missing_experiment_header(self):
        """Test OTel without experiment header gets 403."""
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/v1/traces")
        assert response.status_code == 403

    @patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint")
    def test_validator_exception_returns_403(self, mock_can_use):
        """Test that an exception in validator returns 403 (fail closed)."""
        mock_can_use.side_effect = RuntimeError("unexpected error")
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/gateway/my-ep/mlflow/invocations")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Integration tests: AuthContext ContextVar bridging for workspace resolution
# ---------------------------------------------------------------------------


class TestAuthContextBridging:
    """Test that the middleware bridges AuthContext via ContextVar for FastAPI-native routes."""

    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    def test_otel_validator_receives_workspace_via_contextvar(self, mock_perm):
        """Workspace is available via get_request_workspace during OTel validation."""
        from mlflow_oidc_auth.bridge.user import get_request_workspace

        captured_workspace = {}

        def capture_workspace(experiment_id, username):
            captured_workspace["value"] = get_request_workspace()
            result = MagicMock()
            result.permission.can_update = True
            return result

        mock_perm.side_effect = capture_workspace

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="team-ws")
        client = TestClient(app)
        response = client.get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 200
        assert captured_workspace["value"] == "team-ws"

    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    def test_contextvar_cleared_before_route_handler(self, mock_perm):
        """The ContextVar is cleared before ``call_next``, so the route handler never sees it.

        Asserted from inside the app: the TestClient thread has its own context and
        would read ``None`` regardless.
        """
        mock_result = MagicMock()
        mock_result.permission.can_update = True
        mock_perm.return_value = mock_result

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="team-ws")
        client = TestClient(app)
        response = client.get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 200
        assert response.json()["auth_context_var_set"] is False

    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    def test_contextvar_cleared_on_validator_exception(self, mock_perm):
        """ContextVar is cleared when the validator raises, observed from the app's own context."""
        from mlflow_oidc_auth.bridge.user import _auth_context_var, clear_auth_context

        mock_perm.side_effect = RuntimeError("boom")
        seen_after_clear = {}

        def spy_clear(token=None):
            clear_auth_context(token)
            seen_after_clear["value"] = _auth_context_var.get()

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="team-ws")
        client = TestClient(app)
        with patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.clear_auth_context", side_effect=spy_clear):
            response = client.get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 403
        assert seen_after_clear == {"value": None}

    @patch("mlflow_oidc_auth.utils.effective_experiment_permission")
    def test_no_workspace_header_contextvar_has_none_workspace(self, mock_perm):
        """Without a workspace header, the bridged AuthContext reports workspace=None."""
        from mlflow_oidc_auth.bridge.user import get_request_workspace

        captured_workspace = {}

        def capture_workspace(experiment_id, username):
            captured_workspace["value"] = get_request_workspace()
            result = MagicMock()
            result.permission.can_update = True
            return result

        mock_perm.side_effect = capture_workspace

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace=None)
        client = TestClient(app)
        response = client.get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 200
        assert captured_workspace["value"] is None


# ---------------------------------------------------------------------------
# Issue #369 end to end: workspace-level grants must reach FastAPI-native routes
# ---------------------------------------------------------------------------


class TestWorkspaceFallbackEndToEnd:
    """Drive the real ``effective_experiment_permission`` / ``_apply_workspace_fallback`` path.

    Only the store lookups are stubbed: the resource-level lookup finds nothing
    (a ``fallback`` result), and the workspace permission comes from a dict.
    """

    @staticmethod
    def _workspace_env(workspace_grants: dict, experiment_in_workspace: bool = True):
        from contextlib import ExitStack

        from mlflow_oidc_auth.models import PermissionResult
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS
        from mlflow_oidc_auth.utils import permissions as perms

        stack = ExitStack()
        stack.enter_context(patch.object(perms.config, "MLFLOW_ENABLE_WORKSPACES", True))
        stack.enter_context(patch.object(perms, "get_permission_from_store_or_default", return_value=PermissionResult(NO_PERMISSIONS, "fallback")))
        # Experiment 42 is (or is not) one of the request workspace's experiments.
        stack.enter_context(patch.object(perms, "_experiment_in_request_workspace", return_value=experiment_in_workspace))
        stack.enter_context(
            patch(
                "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                side_effect=lambda username, workspace: workspace_grants.get((username, workspace)),
            )
        )
        perms._get_permission_cache().clear()
        return stack

    def test_workspace_manage_grants_update_on_otel_route(self):
        """A user whose only grant is workspace MANAGE may post traces to that workspace (issue #369)."""
        from mlflow_oidc_auth.permissions import MANAGE

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="team-ws")
        with self._workspace_env({("user@example.com", "team-ws"): MANAGE}):
            response = TestClient(app).get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 200

    def test_workspace_manage_does_not_reach_another_workspaces_experiment(self):
        """Experiment ids are global: MANAGE on the header's workspace reaches only its experiments."""
        from mlflow_oidc_auth.permissions import MANAGE

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="team-ws")
        with self._workspace_env({("user@example.com", "team-ws"): MANAGE}, experiment_in_workspace=False):
            response = TestClient(app).get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 403

    def test_no_workspace_grant_is_denied_on_otel_route(self):
        """Negative path: the same request against a workspace the user has no grant on is 403."""
        from mlflow_oidc_auth.permissions import MANAGE

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="other-ws")
        with self._workspace_env({("user@example.com", "team-ws"): MANAGE}):
            response = TestClient(app).get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 403

    def test_read_only_workspace_grant_is_denied_on_otel_route(self):
        """Negative path: workspace READ does not satisfy the UPDATE the OTel validator requires."""
        from mlflow_oidc_auth.permissions import READ

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="team-ws")
        with self._workspace_env({("user@example.com", "team-ws"): READ}):
            response = TestClient(app).get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 403

    def test_without_the_bridge_the_workspace_grant_is_invisible(self):
        """Regression guard: with the ContextVar bridging disabled the grant cannot be seen and the request is 403."""
        from mlflow_oidc_auth.permissions import MANAGE

        app = _create_app_with_auth(username="user@example.com", is_admin=False, workspace="team-ws")
        with (
            self._workspace_env({("user@example.com", "team-ws"): MANAGE}),
            patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.set_auth_context", return_value=None),
        ):
            response = TestClient(app).get("/v1/traces", headers={"X-Mlflow-Experiment-Id": "42"})

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Job API: ownership on get/cancel, search narrowed to the caller's jobs
# ---------------------------------------------------------------------------

_GET_JOB = "mlflow.server.jobs.get_job"


def _job(creator):
    job = MagicMock()
    job.creator = creator
    return job


def _create_jobs_app(username, is_admin=False, jobs=None):
    """App serving stand-ins for MLflow's job API routes behind the permission middleware."""
    from mlflow_oidc_auth.middleware.fastapi_permission_middleware import add_fastapi_permission_middleware

    app = FastAPI()

    @app.post("/ajax-api/3.0/jobs/")
    async def submit_job(request: Request):
        # Echo the body so tests can see it still reaches the handler after authorization.
        return {"job_id": "new", "received": await request.json()}

    @app.post("/ajax-api/3.0/jobs/search")
    async def search_jobs():
        return {"jobs": jobs if jobs is not None else []}

    @app.patch("/ajax-api/3.0/jobs/cancel/{job_id}")
    async def cancel_job(job_id: str):
        return {"job_id": job_id, "status": "CANCELED"}

    @app.get("/ajax-api/3.0/jobs/{job_id}")
    async def get_job(job_id: str):
        return {"job_id": job_id}

    add_fastapi_permission_middleware(app)

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.username = username
        request.state.is_admin = is_admin
        return await call_next(request)

    return TestClient(app)


class TestJobIdFromPath:
    def _id(self, path):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import _job_id_from_path

        return _job_id_from_path(path)

    def test_submit_and_search_carry_no_id(self):
        assert self._id("/ajax-api/3.0/jobs") is None
        assert self._id("/ajax-api/3.0/jobs/") is None
        assert self._id("/ajax-api/3.0/jobs/search") is None

    def test_get_and_cancel_carry_the_id(self):
        assert self._id("/ajax-api/3.0/jobs/j1") == "j1"
        assert self._id("/ajax-api/3.0/jobs/cancel/j1") == "j1"


class TestJobOwnership:
    def test_creator_can_get_job(self):
        with patch(_GET_JOB, return_value=_job("alice@example.com")):
            response = _create_jobs_app("alice@example.com").get("/ajax-api/3.0/jobs/j1")
        assert response.status_code == 200

    def test_other_user_cannot_get_job(self):
        with patch(_GET_JOB, return_value=_job("alice@example.com")):
            response = _create_jobs_app("bob@example.com").get("/ajax-api/3.0/jobs/j1")
        assert response.status_code == 403

    def test_creator_can_cancel_job(self):
        with patch(_GET_JOB, return_value=_job("alice@example.com")):
            response = _create_jobs_app("alice@example.com").patch("/ajax-api/3.0/jobs/cancel/j1")
        assert response.status_code == 200

    def test_other_user_cannot_cancel_job(self):
        with patch(_GET_JOB, return_value=_job("alice@example.com")):
            response = _create_jobs_app("bob@example.com").patch("/ajax-api/3.0/jobs/cancel/j1")
        assert response.status_code == 403

    def test_job_without_creator_is_denied(self):
        with patch(_GET_JOB, return_value=_job(None)):
            response = _create_jobs_app("alice@example.com").get("/ajax-api/3.0/jobs/j1")
        assert response.status_code == 403

    def test_unknown_job_is_denied(self):
        with patch(_GET_JOB, side_effect=Exception("not found")):
            response = _create_jobs_app("alice@example.com").get("/ajax-api/3.0/jobs/missing")
        assert response.status_code == 403

    def test_admin_can_get_any_job(self):
        with patch(_GET_JOB, return_value=_job("alice@example.com")) as get_job:
            response = _create_jobs_app("root@example.com", is_admin=True).get("/ajax-api/3.0/jobs/j1")
        assert response.status_code == 200
        get_job.assert_not_called()

    def test_submit_allowed_when_payload_is_authorized(self):
        payload = {"job_name": "invoke_scorer", "params": {"experiment_id": "1", "serialized_scorer": "{}", "trace_ids": []}}
        with patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_submit_job", return_value=True) as check:
            response = _create_jobs_app("bob@example.com").post("/ajax-api/3.0/jobs/", json=payload)
        assert response.status_code == 200
        assert response.json()["received"] == payload
        check.assert_called_once_with(payload, "bob@example.com")

    def test_submit_denied_when_payload_is_not_authorized(self):
        with patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_submit_job", return_value=False):
            response = _create_jobs_app("bob@example.com").post("/ajax-api/3.0/jobs/", json={"job_name": "invoke_scorer", "params": {}})
        assert response.status_code == 403

    def test_submit_with_unparseable_body_is_denied(self):
        response = _create_jobs_app("bob@example.com").post("/ajax-api/3.0/jobs/", content=b"not json", headers={"content-type": "application/json"})
        assert response.status_code == 403

    def test_admin_submit_is_not_checked(self):
        with patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_submit_job", return_value=False) as check:
            response = _create_jobs_app("root@example.com", is_admin=True).post("/ajax-api/3.0/jobs/", json={"job_name": "x", "params": {}})
        assert response.status_code == 200
        check.assert_not_called()

    def test_search_path_with_other_method_is_denied(self):
        response = _create_jobs_app("bob@example.com").get("/ajax-api/3.0/jobs/search")
        assert response.status_code == 403


class TestJobSearchFiltering:
    _JOBS = [
        {"job_id": "a1", "creator": "alice@example.com"},
        {"job_id": "b1", "creator": "bob@example.com"},
        {"job_id": "n1", "creator": None},
    ]

    def test_non_admin_sees_only_own_jobs(self):
        client = _create_jobs_app("alice@example.com", jobs=self._JOBS)
        response = client.post("/ajax-api/3.0/jobs/search", json={})
        assert response.status_code == 200
        assert [j["job_id"] for j in response.json()["jobs"]] == ["a1"]

    def test_admin_sees_all_jobs(self):
        client = _create_jobs_app("root@example.com", is_admin=True, jobs=self._JOBS)
        response = client.post("/ajax-api/3.0/jobs/search", json={})
        assert [j["job_id"] for j in response.json()["jobs"]] == ["a1", "b1", "n1"]

    def test_creator_looked_up_when_response_omits_it(self):
        jobs = [{"job_id": "a1"}, {"job_id": "b1"}, {"job_id": "gone"}]
        creators = {"a1": "alice@example.com", "b1": "bob@example.com"}

        def fake_get_job(job_id):
            if job_id not in creators:
                raise Exception("not found")
            return _job(creators[job_id])

        client = _create_jobs_app("alice@example.com", jobs=jobs)
        with patch(_GET_JOB, side_effect=fake_get_job):
            response = client.post("/ajax-api/3.0/jobs/search", json={})
        assert [j["job_id"] for j in response.json()["jobs"]] == ["a1"]

    def test_unparseable_response_is_not_returned(self):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import _filter_job_search_response

        with pytest.raises(ValueError):
            _filter_job_search_response("alice@example.com", b'{"unexpected": true}')


# ---------------------------------------------------------------------------
# Gateway routes never see this plugin's credentials
# ---------------------------------------------------------------------------


class TestGatewayCredentialStripping:
    """MLflow's gateway copies the caller's headers onto the request it sends to the provider on its
    passthrough and proxy routes, so this plugin's credentials must be gone before those handlers run."""

    SENT = {
        "Cookie": "mlflow_oidc_session=not-a-real-session",
        "Authorization": "Bearer not-a-real-token",
        "X-Custom": "kept",
    }

    @staticmethod
    def _app(is_admin, route):
        app = _create_app_with_auth(username="user@example.com", is_admin=is_admin)

        @app.post(route)
        async def gateway_echo(request: Request):
            return {"headers": {k.lower(): v for k, v in request.headers.items()}}

        app.router.routes.insert(0, app.router.routes.pop())
        return app

    def _received(self, is_admin, route, path, body=None):
        with patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint", return_value=True):
            response = TestClient(self._app(is_admin, route)).post(path, headers=self.SENT, json=body or {})
        assert response.status_code == 200, response.text
        return response.json()["headers"]

    @pytest.mark.parametrize("is_admin", [False, True])
    @pytest.mark.parametrize(
        "route,path,body",
        [
            ("/gateway/openai/v1/chat/completions", "/gateway/openai/v1/chat/completions", {"model": "my-endpoint"}),
            ("/gateway/anthropic/v1/messages", "/gateway/anthropic/v1/messages", {"model": "my-endpoint"}),
        ],
    )
    def test_forwarding_routes_see_neither_cookie_nor_authorization(self, is_admin, route, path, body):
        received = self._received(is_admin, route, path, body)

        assert "cookie" not in received
        assert "authorization" not in received
        assert received["x-custom"] == "kept"

    @pytest.mark.parametrize("is_admin", [False, True])
    def test_the_raw_proxy_sees_neither_cookie_nor_authorization(self, is_admin):
        """The raw proxy forwards every header it gets to the provider — for a permitted non-admin too."""
        received = self._received(is_admin, "/gateway/proxy/{endpoint}/{rest:path}", "/gateway/proxy/my-endpoint/v1/chat/completions")

        assert "cookie" not in received
        assert "authorization" not in received

    @pytest.mark.parametrize("is_admin", [False, True])
    @pytest.mark.parametrize(
        "route,path,body",
        [
            ("/gateway/{endpoint}/mlflow/invocations", "/gateway/my-endpoint/mlflow/invocations", None),
            ("/gateway/mlflow/v1/chat/completions", "/gateway/mlflow/v1/chat/completions", {"model": "my-endpoint"}),
        ],
    )
    def test_typed_routes_keep_authorization_for_guardrails_but_never_the_cookie(self, is_admin, route, path, body):
        """These routes never forward headers; a sanitize guardrail calls back into MLflow with the caller's token."""
        received = self._received(is_admin, route, path, body)

        assert "cookie" not in received
        assert received["authorization"] == "Bearer not-a-real-token"

    def test_a_denied_request_is_refused(self):
        with patch("mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint", return_value=False):
            response = TestClient(self._app(False, "/gateway/{endpoint}/mlflow/invocations")).post(
                "/gateway/my-endpoint/mlflow/invocations", headers=self.SENT, json={}
            )

        assert response.status_code == 403

    @pytest.mark.parametrize(
        "path,kept",
        [
            ("/gateway/openai/v1/responses", [(b"x-other", b"d")]),
            ("/gateway/some-future/route", [(b"x-other", b"d")]),
            ("/gateway/ep/mlflow/invocations", [(b"Authorization", b"b"), (b"authorization", b"c"), (b"x-other", b"d")]),
        ],
    )
    def test_the_strip_is_case_insensitive_and_unknown_routes_lose_authorization(self, path, kept):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import _strip_client_credentials

        request = MagicMock(spec=Request)
        request.scope = {"headers": [(b"cookie", b"a"), (b"Authorization", b"b"), (b"authorization", b"c"), (b"x-other", b"d")]}
        _strip_client_credentials(request, path)

        assert request.scope["headers"] == kept


# ---------------------------------------------------------------------------
# Model discovery (MLflow 3.17+): listing narrowed to the endpoints the caller may USE
# ---------------------------------------------------------------------------

_MODELS = "/gateway/mlflow/v1/models"
_CAN_USE = "mlflow_oidc_auth.middleware.fastapi_permission_middleware.can_use_gateway_endpoint"


class TestGatewayModelDiscovery:
    """Mirrors MLflow's own ``_filter_list_gateway_models``: ``id`` is the endpoint name."""

    LISTING = {
        "object": "list",
        "data": [
            {"id": "allowed-endpoint", "object": "model", "created": 1, "owned_by": "mlflow"},
            {"id": "denied-endpoint", "object": "model", "created": 2, "owned_by": "mlflow"},
        ],
    }

    def _app(self, username="user@example.com", is_admin=False, workspace=None, body=None, status=200):
        from starlette.responses import JSONResponse, Response

        app = _create_app_with_auth(username=username, is_admin=is_admin, workspace=workspace)
        listing = self.LISTING if body is None else body

        @app.get(_MODELS)
        async def list_models():
            if isinstance(listing, bytes):
                response = Response(content=listing, status_code=status, media_type="application/json")
            else:
                response = JSONResponse(listing, status_code=status)
            response.raw_headers.extend([(b"x-model-metadata", b"first"), (b"x-model-metadata", b"second")])
            return response

        app.router.routes.insert(0, app.router.routes.pop())
        return app

    def test_models_route_requires_authentication(self):
        assert self._find(_MODELS) is not None
        response = TestClient(self._app(username=None)).get(_MODELS)
        assert response.status_code == 401

    @staticmethod
    def _find(path):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import _find_fastapi_validator

        return _find_fastapi_validator(path)

    def test_admin_sees_every_endpoint_without_checks(self):
        with patch(_CAN_USE) as can_use:
            response = TestClient(self._app(username="admin@example.com", is_admin=True)).get(_MODELS)

        assert response.status_code == 200
        assert [m["id"] for m in response.json()["data"]] == ["allowed-endpoint", "denied-endpoint"]
        can_use.assert_not_called()

    def test_regular_user_sees_only_usable_endpoints_and_headers_are_kept(self):
        with patch(_CAN_USE, side_effect=lambda endpoint, username: endpoint == "allowed-endpoint") as can_use:
            response = TestClient(self._app()).get(_MODELS)

        assert response.status_code == 200
        assert response.json() == {"object": "list", "data": [self.LISTING["data"][0]]}
        assert response.headers.get_list("x-model-metadata") == ["first", "second"]
        assert int(response.headers["content-length"]) == len(response.content)
        assert [c.args for c in can_use.call_args_list] == [("allowed-endpoint", "user@example.com"), ("denied-endpoint", "user@example.com")]

    def test_a_failed_permission_lookup_hides_that_endpoint(self):
        def check(endpoint, username):
            if endpoint == "denied-endpoint":
                raise RuntimeError("permission backend unavailable")
            return True

        with patch(_CAN_USE, side_effect=check):
            response = TestClient(self._app()).get(_MODELS)

        assert [m["id"] for m in response.json()["data"]] == ["allowed-endpoint"]

    @pytest.mark.parametrize("body", [b"not json", b'{"object": "list"}', b'["not", "a", "listing"]'])
    def test_a_body_that_cannot_be_filtered_is_500_never_the_unfiltered_list(self, body):
        with patch(_CAN_USE, return_value=True):
            response = TestClient(self._app(body=body)).get(_MODELS)

        assert response.status_code == 500
        assert "allowed-endpoint" not in response.text

    def test_an_error_response_is_returned_unchanged(self):
        with patch(_CAN_USE, return_value=True):
            response = TestClient(self._app(body={"error_code": "TEMPORARILY_UNAVAILABLE"}, status=503)).get(_MODELS)

        assert response.status_code == 503
        assert response.json() == {"error_code": "TEMPORARILY_UNAVAILABLE"}

    def test_the_callers_workspace_is_visible_while_filtering(self):
        """With workspaces on, an endpoint with no grant falls back to the caller's workspace
        permission — which needs the caller's AuthContext bridged during the filter."""
        from mlflow_oidc_auth.bridge.user import get_request_workspace

        seen = []

        def check(endpoint, username):
            seen.append(get_request_workspace())
            return get_request_workspace() == "team-a"

        with patch(_CAN_USE, side_effect=check):
            response = TestClient(self._app(workspace="team-a")).get(_MODELS)

        assert response.status_code == 200
        assert [m["id"] for m in response.json()["data"]] == ["allowed-endpoint", "denied-endpoint"]
        assert seen == ["team-a", "team-a"]

    def test_workspace_fallback_end_to_end(self):
        """The real resolution path: no endpoint grants, workspace MANAGE on team-a only."""
        from contextlib import ExitStack

        from mlflow_oidc_auth.models import PermissionResult
        from mlflow_oidc_auth.permissions import MANAGE, NO_PERMISSIONS
        from mlflow_oidc_auth.utils import permissions as perms

        grants = {("user@example.com", "team-a"): MANAGE}
        with ExitStack() as stack:
            stack.enter_context(patch.object(perms.config, "MLFLOW_ENABLE_WORKSPACES", True))
            stack.enter_context(patch.object(perms, "get_permission_from_store_or_default", return_value=PermissionResult(NO_PERMISSIONS, "fallback")))
            stack.enter_context(patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", side_effect=lambda u, ws: grants.get((u, ws))))
            perms._get_permission_cache().clear()
            member = TestClient(self._app(workspace="team-a")).get(_MODELS)
            perms._get_permission_cache().clear()
            outsider = TestClient(self._app(workspace="team-b")).get(_MODELS)

        assert [m["id"] for m in member.json()["data"]] == ["allowed-endpoint", "denied-endpoint"]
        assert outsider.json()["data"] == []

    def test_models_route_loses_plugin_credentials(self):
        """Discovery forwards nothing, but it is a /gateway/ route: the credential strip applies."""
        from starlette.responses import JSONResponse

        app = _create_app_with_auth(username="admin@example.com", is_admin=True)

        @app.get(_MODELS)
        async def echo(request: Request):
            return JSONResponse({"object": "list", "data": [], "headers": sorted(k.lower() for k in request.headers.keys())})

        app.router.routes.insert(0, app.router.routes.pop())
        received = TestClient(app).get(_MODELS, headers={"Cookie": "s=x", "Authorization": "Bearer y"}).json()["headers"]
        assert "cookie" not in received and "authorization" not in received
