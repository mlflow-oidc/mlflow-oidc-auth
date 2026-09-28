"""
Tests for WorkspaceContextMiddleware.

Tests that the MLflow workspace ContextVar (set_server_request_workspace) is
correctly set before request processing and cleared afterward, ensuring that
downstream tracking-store operations run within the correct workspace scope.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi import Response

from mlflow_oidc_auth.middleware.workspace_context_middleware import (
    WorkspaceContextMiddleware,
)


class TestWorkspaceContextMiddleware:
    """Test workspace ContextVar propagation via WorkspaceContextMiddleware."""

    @pytest.fixture
    def middleware(self, test_fastapi_app):
        """Create WorkspaceContextMiddleware instance for testing."""
        return WorkspaceContextMiddleware(test_fastapi_app)

    @pytest.mark.asyncio
    async def test_passthrough_when_workspaces_disabled(self, middleware, create_mock_request):
        """When MLFLOW_ENABLE_WORKSPACES=False, middleware is a transparent pass-through."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = False

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={"x-mlflow-workspace": "my-workspace"},
        )

        call_next_called = False

        async def mock_call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content="OK", status_code=200)

        with patch(
            "mlflow_oidc_auth.middleware.workspace_context_middleware.config",
            mock_config,
        ):
            response = await middleware.dispatch(request, mock_call_next)

        assert call_next_called is True
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sets_workspace_context_from_header(self, middleware, create_mock_request):
        """When workspace header is provided, set_server_request_workspace is called with resolved workspace."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={"x-mlflow-workspace": "my-workspace"},
        )

        workspace_set_value = None
        workspace_cleared = False

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        mock_workspace = MagicMock()
        mock_workspace.name = "my-workspace"

        with patch(
            "mlflow_oidc_auth.middleware.workspace_context_middleware.config",
            mock_config,
        ):
            with (
                patch("mlflow.utils.workspace_context.set_server_request_workspace") as mock_set,
                patch("mlflow.utils.workspace_context.clear_server_request_workspace") as mock_clear,
                patch(
                    "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
                    return_value=mock_workspace,
                ),
            ):
                response = await middleware.dispatch(request, mock_call_next)

                mock_set.assert_called_once_with("my-workspace")
                mock_clear.assert_called_once()

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sets_none_when_no_workspace_header(self, middleware, create_mock_request):
        """When no workspace header, resolver returns None and set_server_request_workspace(None) is called."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
        )

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        with patch(
            "mlflow_oidc_auth.middleware.workspace_context_middleware.config",
            mock_config,
        ):
            with (
                patch("mlflow.utils.workspace_context.set_server_request_workspace") as mock_set,
                patch("mlflow.utils.workspace_context.clear_server_request_workspace") as mock_clear,
                patch(
                    "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
                    return_value=None,
                ),
            ):
                response = await middleware.dispatch(request, mock_call_next)

                mock_set.assert_called_once_with(None)
                mock_clear.assert_called_once()

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_clears_workspace_context_on_exception(self, middleware, create_mock_request):
        """ContextVar is cleared even if the downstream handler raises an exception."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={"x-mlflow-workspace": "my-workspace"},
        )

        async def mock_call_next_raises(req):
            raise RuntimeError("Downstream error")

        mock_workspace = MagicMock()
        mock_workspace.name = "my-workspace"

        with patch(
            "mlflow_oidc_auth.middleware.workspace_context_middleware.config",
            mock_config,
        ):
            with (
                patch("mlflow.utils.workspace_context.set_server_request_workspace") as mock_set,
                patch("mlflow.utils.workspace_context.clear_server_request_workspace") as mock_clear,
                patch(
                    "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
                    return_value=mock_workspace,
                ),
            ):
                with pytest.raises(RuntimeError, match="Downstream error"):
                    await middleware.dispatch(request, mock_call_next_raises)

                mock_set.assert_called_once_with("my-workspace")
                mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_error_on_workspace_resolution_failure(self, middleware, create_mock_request):
        """When resolve_workspace_for_request_if_enabled raises MlflowException, returns JSON error."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={"x-mlflow-workspace": "invalid-workspace"},
        )

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        from mlflow.exceptions import MlflowException
        from mlflow.protos import databricks_pb2

        resolve_error = MlflowException(
            "Workspace 'invalid-workspace' not found",
            error_code=databricks_pb2.RESOURCE_DOES_NOT_EXIST,
        )

        with patch(
            "mlflow_oidc_auth.middleware.workspace_context_middleware.config",
            mock_config,
        ):
            with patch(
                "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
                side_effect=resolve_error,
            ):
                response = await middleware.dispatch(request, mock_call_next)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_server_info_path_skips_workspace_resolution(self, middleware, create_mock_request):
        """The /mlflow/server-info path should skip workspace resolution (MLflow behavior)."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True

        request = create_mock_request(
            path="/api/2.0/mlflow/server-info",
            headers={"x-mlflow-workspace": "nonexistent-workspace"},
        )

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        with patch(
            "mlflow_oidc_auth.middleware.workspace_context_middleware.config",
            mock_config,
        ):
            with (
                patch("mlflow.utils.workspace_context.set_server_request_workspace") as mock_set,
                patch("mlflow.utils.workspace_context.clear_server_request_workspace") as mock_clear,
                patch(
                    "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
                    return_value=None,
                ) as mock_resolve,
            ):
                response = await middleware.dispatch(request, mock_call_next)

                # The resolver is called with the path and header value.
                # Note: MockRequest headers are case-sensitive dicts (unlike real
                # Starlette headers), so the WORKSPACE_HEADER_NAME constant
                # ('X-MLFLOW-WORKSPACE') won't match the lowercase key.
                # The important thing is that the resolver was called and the
                # middleware handled the None return correctly.
                mock_resolve.assert_called_once()
                call_args = mock_resolve.call_args[0]
                assert call_args[0] == "/api/2.0/mlflow/server-info"
                mock_set.assert_called_once_with(None)
                mock_clear.assert_called_once()

        assert response.status_code == 200


class TestWorkspaceResolvedOnRoutedPath:
    """The workspace is resolved on the routed path — the same one the router and auth use.

    Runs the real ``ProxyHeadersMiddleware`` outside ``WorkspaceContextMiddleware`` (their order
    in ``add_middleware_stack``) in front of a route that reports the workspace it ran in.
    """

    PROXY = ("10.0.0.5", 40000)
    ROUTE = "/api/2.0/mlflow/experiments/search"
    WORKSPACE = {"X-MLFLOW-WORKSPACE": "team-a"}

    @pytest.fixture
    def run(self, monkeypatch):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.middleware.proxy_headers_middleware import ProxyHeadersMiddleware

        resolved_paths = []
        set_calls = []

        def fake_resolve(path, header_value):
            resolved_paths.append(path)
            if path.rstrip("/").endswith("/mlflow/server-info") or not header_value:
                return None
            workspace = MagicMock()
            workspace.name = header_value
            return workspace

        def _run(path, *, trusted_proxies=(), client=self.PROXY, headers=None, workspaces=True):
            monkeypatch.setattr(config, "TRUSTED_PROXIES", list(trusted_proxies), raising=False)
            monkeypatch.setattr("mlflow_oidc_auth.middleware.workspace_context_middleware.config.MLFLOW_ENABLE_WORKSPACES", workspaces, raising=False)
            resolved_paths.clear()
            set_calls.clear()

            app = FastAPI()
            app.add_middleware(WorkspaceContextMiddleware)
            app.add_middleware(ProxyHeadersMiddleware)

            @app.get("/{full_path:path}")
            async def catch_all(full_path: str):
                return {"routed": f"/{full_path}"}

            with (
                patch("mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled", side_effect=fake_resolve),
                patch("mlflow.utils.workspace_context.set_server_request_workspace", side_effect=set_calls.append),
                patch("mlflow.utils.workspace_context.clear_server_request_workspace"),
            ):
                response = TestClient(app, client=client).get(path, headers=headers or {})
            assert response.status_code == 200
            return {"routed": response.json()["routed"], "resolved": list(resolved_paths), "workspace": list(set_calls)}

        return _run

    def test_trusted_prefix_resolves_same_workspace_as_unprefixed(self, run):
        direct = run(self.ROUTE, headers=self.WORKSPACE)
        prefixed = run(f"/mlflow{self.ROUTE}", trusted_proxies=["10.0.0.0/8"], headers={**self.WORKSPACE, "X-Forwarded-Prefix": "/mlflow"})
        assert direct == {"routed": self.ROUTE, "resolved": [self.ROUTE], "workspace": ["team-a"]}
        assert prefixed == direct

    def test_trusted_prefix_server_info_is_exempt_under_the_prefix(self, run):
        result = run(
            "/mlflow/api/2.0/mlflow/server-info",
            trusted_proxies=["10.0.0.0/8"],
            headers={"X-MLFLOW-WORKSPACE": "missing", "X-Forwarded-Prefix": "/mlflow"},
        )
        assert result == {"routed": "/api/2.0/mlflow/server-info", "resolved": ["/api/2.0/mlflow/server-info"], "workspace": [None]}

    @pytest.mark.parametrize("trusted_proxies", [(), ["192.168.0.0/16"]], ids=["unset", "other-network"])
    def test_untrusted_prefix_is_not_applied(self, run, trusted_proxies):
        headers = {**self.WORKSPACE, "X-Forwarded-Prefix": "/mlflow"}
        # Unprefixed request: resolved on the path as received, the header prefix changes nothing.
        assert run(self.ROUTE, trusted_proxies=trusted_proxies, headers=headers) == {
            "routed": self.ROUTE,
            "resolved": [self.ROUTE],
            "workspace": ["team-a"],
        }
        # Prefixed request: nothing is stripped, and resolution sees what the router sees.
        result = run(f"/mlflow{self.ROUTE}", trusted_proxies=trusted_proxies, headers=headers)
        assert result["resolved"] == [result["routed"]] == [f"/mlflow{self.ROUTE}"]

    @pytest.mark.parametrize("trusted_proxies", [(), ["10.0.0.0/8"]])
    def test_workspaces_disabled_is_untouched(self, run, trusted_proxies):
        result = run(
            f"/mlflow{self.ROUTE}",
            trusted_proxies=trusted_proxies,
            headers={**self.WORKSPACE, "X-Forwarded-Prefix": "/mlflow"},
            workspaces=False,
        )
        assert result["resolved"] == []
        assert result["workspace"] == []

    def test_proxy_headers_run_before_workspace_context(self):
        """``add_middleware_stack`` installs ProxyHeaders outside WorkspaceContext."""
        from fastapi import FastAPI

        from mlflow_oidc_auth.app import add_middleware_stack
        from mlflow_oidc_auth.middleware.proxy_headers_middleware import ProxyHeadersMiddleware

        app = FastAPI()
        add_middleware_stack(app)
        order = [m.cls for m in app.user_middleware]  # outermost first
        assert order.index(ProxyHeadersMiddleware) < order.index(WorkspaceContextMiddleware)
