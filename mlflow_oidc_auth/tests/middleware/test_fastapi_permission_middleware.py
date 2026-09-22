"""
Tests for FastAPI Permission Middleware.

This module tests the OIDC-aware permission middleware for FastAPI-native routes
(gateway invocations, OTel trace ingestion, assistant, job API) that bypass Flask.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

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

    def test_chat_completions_mlflow(self):
        """Test MLflow chat completions passthrough."""
        result = self._extract("/gateway/mlflow/v1/chat/completions", {"model": "my-model"})
        assert result == "my-model"

    def test_chat_completions_openai(self):
        """Test OpenAI chat completions passthrough."""
        result = self._extract("/gateway/openai/v1/chat/completions", {"model": "gpt-4"})
        assert result == "gpt-4"

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
# Unit tests: MCP server registry validator
# ---------------------------------------------------------------------------


class TestMCPServerRegistryValidator:
    """Test the MCP server registry validator: reads open, writes admin-only."""

    def _validator(self):
        from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
            _get_mcp_server_registry_validator,
        )

        return _get_mcp_server_registry_validator()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["GET", "HEAD"])
    async def test_reads_allowed_for_any_user(self, method):
        """Test that a non-admin authenticated user may read the registry."""
        validator = self._validator()
        request = MagicMock(spec=Request)
        request.method = method
        assert await validator("user@example.com", request) is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "PUT"])
    async def test_writes_denied_for_non_admin(self, method):
        """Test that a non-admin authenticated user may not mutate the registry.

        Admins never reach this validator, so denying here is what makes
        mutation admin-only.
        """
        validator = self._validator()
        request = MagicMock(spec=Request)
        request.method = method
        assert await validator("user@example.com", request) is False


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

    @app.get("/api/2.0/mlflow/experiments/list")
    async def flask_passthrough():
        return {"experiments": []}

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

    def test_authenticated_user_jobs_passes(self):
        """Test that any authenticated user passes jobs check."""
        app = _create_app_with_auth(username="user@example.com", is_admin=False)
        client = TestClient(app)
        response = client.get("/ajax-api/3.0/jobs")
        assert response.status_code == 200

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
    def _workspace_env(workspace_grants: dict):
        from contextlib import ExitStack

        from mlflow_oidc_auth.models import PermissionResult
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS
        from mlflow_oidc_auth.utils import permissions as perms

        stack = ExitStack()
        stack.enter_context(patch.object(perms.config, "MLFLOW_ENABLE_WORKSPACES", True))
        stack.enter_context(patch.object(perms, "get_permission_from_store_or_default", return_value=PermissionResult(NO_PERMISSIONS, "fallback")))
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
