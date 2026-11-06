"""
Comprehensive tests for AuthAwareWSGIMiddleware and AuthInjectingWSGIApp.

Updated to use AuthContext pattern instead of individual environ keys.

This module tests WSGI middleware functionality including:
- ASGI to WSGI conversion with authentication context
- AuthContext injection into WSGI environ
- WSGI application wrapping and execution
- Error handling and edge cases
- Non-HTTP request handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mlflow_oidc_auth.entities.auth_context import AuthContext
from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import (
    AuthAwareWSGIMiddleware,
    AuthInjectingWSGIApp,
)


class TestAuthInjectingWSGIApp:
    """Test suite for AuthInjectingWSGIApp functionality."""

    def test_init(self, mock_flask_app, sample_asgi_scope):
        """Test AuthInjectingWSGIApp initialization."""
        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        assert app.flask_app == mock_flask_app
        assert app.scope == sample_asgi_scope

    def test_call_with_auth_context(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call with AuthContext in scope."""
        auth_ctx = AuthContext(username="user@example.com", is_admin=False)
        sample_asgi_scope["mlflow_oidc_auth"] = auth_ctx

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Verify AuthContext was injected as a single object
            assert sample_wsgi_environ["mlflow_oidc_auth"] is auth_ctx
            assert isinstance(sample_wsgi_environ["mlflow_oidc_auth"], AuthContext)
            assert sample_wsgi_environ["mlflow_oidc_auth"].username == "user@example.com"
            assert sample_wsgi_environ["mlflow_oidc_auth"].is_admin is False

            # Verify Flask app was called with enhanced environ
            assert result == [b'{"message": "Hello from Flask"}']

            # Verify debug logging
            mock_logger.debug.assert_called_once()
            log_message = mock_logger.debug.call_args[0][0]
            assert "Injecting AuthContext into WSGI environ" in log_message
            assert "username=user@example.com" in log_message
            assert "is_admin=False" in log_message

    def test_call_with_admin_auth_context(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call with admin AuthContext."""
        auth_ctx = AuthContext(username="admin@example.com", is_admin=True)
        sample_asgi_scope["mlflow_oidc_auth"] = auth_ctx

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            assert sample_wsgi_environ["mlflow_oidc_auth"] is auth_ctx
            assert sample_wsgi_environ["mlflow_oidc_auth"].username == "admin@example.com"
            assert sample_wsgi_environ["mlflow_oidc_auth"].is_admin is True

            assert result == [b'{"message": "Hello from Flask"}']

            mock_logger.debug.assert_called_once()
            log_message = mock_logger.debug.call_args[0][0]
            assert "username=admin@example.com" in log_message
            assert "is_admin=True" in log_message

    def test_call_with_workspace_in_auth_context(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call with workspace in AuthContext."""
        auth_ctx = AuthContext(username="user@example.com", is_admin=False, workspace="my-ws")
        sample_asgi_scope["mlflow_oidc_auth"] = auth_ctx

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            assert sample_wsgi_environ["mlflow_oidc_auth"].workspace == "my-ws"
            assert result == [b'{"message": "Hello from Flask"}']

    def test_call_without_auth_info(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call without authentication information in scope."""
        # No auth info in scope
        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Verify no auth info was injected into environ
            assert "mlflow_oidc_auth" not in sample_wsgi_environ

            # Verify Flask app was still called
            assert result == [b'{"message": "Hello from Flask"}']

            # Verify no debug logging for auth injection
            mock_logger.debug.assert_not_called()

    def test_call_with_non_auth_context_type(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call when scope has a dict instead of AuthContext (should not inject)."""
        # Old-style dict — should NOT be injected since isinstance check fails
        sample_asgi_scope["mlflow_oidc_auth"] = {
            "username": "user@example.com",
            "is_admin": False,
        }

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Dict should not be injected — isinstance(dict, AuthContext) is False
            assert "mlflow_oidc_auth" not in sample_wsgi_environ

            assert result == [b'{"message": "Hello from Flask"}']
            mock_logger.debug.assert_not_called()

    def test_call_preserves_existing_environ(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ):
        """Test that existing environ variables are preserved."""
        sample_wsgi_environ["EXISTING_VAR"] = "existing_value"
        sample_wsgi_environ["HTTP_AUTHORIZATION"] = "Bearer token"

        auth_ctx = AuthContext(username="user@example.com", is_admin=True)
        sample_asgi_scope["mlflow_oidc_auth"] = auth_ctx

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        app(sample_wsgi_environ, start_response)

        # Verify existing environ variables are preserved
        assert sample_wsgi_environ["EXISTING_VAR"] == "existing_value"
        assert sample_wsgi_environ["HTTP_AUTHORIZATION"] == "Bearer token"

        # Verify auth info was added
        assert sample_wsgi_environ["mlflow_oidc_auth"] is auth_ctx

    def test_call_flask_app_exception(self, sample_asgi_scope, sample_wsgi_environ):
        """Test handling when Flask app raises an exception."""

        def failing_flask_app(environ, start_response):
            raise RuntimeError("Flask app error")

        app = AuthInjectingWSGIApp(failing_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        with pytest.raises(RuntimeError, match="Flask app error"):
            app(sample_wsgi_environ, start_response)

    def test_call_start_response_called(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ):
        """Test that start_response is properly called by Flask app."""
        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)
        start_response = MagicMock()

        result = app(sample_wsgi_environ, start_response)

        assert result == [b'{"message": "Hello from Flask"}']


class TestAuthAwareWSGIMiddleware:
    """Test suite for AuthAwareWSGIMiddleware functionality."""

    def test_init(self, mock_flask_app):
        """Test AuthAwareWSGIMiddleware initialization."""
        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        assert middleware.flask_app == mock_flask_app

    @pytest.mark.asyncio
    async def test_call_http_request(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware call with HTTP request."""
        sample_asgi_scope["type"] = "http"
        auth_ctx = AuthContext(username="user@example.com", is_admin=False)
        sample_asgi_scope["mlflow_oidc_auth"] = auth_ctx

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            await middleware(sample_asgi_scope, mock_receive, mock_send)

            mock_wsgi_middleware.assert_called_once()
            created_app = mock_wsgi_middleware.call_args[0][0]
            assert isinstance(created_app, AuthInjectingWSGIApp)
            assert created_app.flask_app == mock_flask_app
            assert created_app.scope == sample_asgi_scope

            mock_wsgi_instance.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_non_http_request(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware call with non-HTTP request."""
        sample_asgi_scope["type"] = "websocket"

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        mock_asgi_flask_app = AsyncMock()
        middleware.flask_app = mock_asgi_flask_app

        await middleware(sample_asgi_scope, mock_receive, mock_send)

        mock_asgi_flask_app.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_lifespan_request(self, mock_flask_app, mock_receive, mock_send):
        """Test middleware call with lifespan request."""
        sample_asgi_scope = {
            "type": "lifespan",
            "asgi": {"version": "3.0"},
        }

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        mock_asgi_flask_app = AsyncMock()
        middleware.flask_app = mock_asgi_flask_app

        await middleware(sample_asgi_scope, mock_receive, mock_send)

        mock_asgi_flask_app.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_http_with_auth_context_including_workspace(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware with AuthContext including workspace."""
        sample_asgi_scope["type"] = "http"
        auth_ctx = AuthContext(username="admin@example.com", is_admin=True, workspace="prod-ws")
        sample_asgi_scope["mlflow_oidc_auth"] = auth_ctx

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            await middleware(sample_asgi_scope, mock_receive, mock_send)

            created_app = mock_wsgi_middleware.call_args[0][0]
            assert created_app.scope["mlflow_oidc_auth"] is auth_ctx
            assert created_app.scope["mlflow_oidc_auth"].workspace == "prod-ws"

    @pytest.mark.asyncio
    async def test_call_http_without_auth_info(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware with HTTP request but no authentication information."""
        sample_asgi_scope["type"] = "http"

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            await middleware(sample_asgi_scope, mock_receive, mock_send)

            mock_wsgi_middleware.assert_called_once()
            created_app = mock_wsgi_middleware.call_args[0][0]
            assert isinstance(created_app, AuthInjectingWSGIApp)
            assert created_app.scope == sample_asgi_scope

            mock_wsgi_instance.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_wsgi_middleware_exception(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test handling when WSGIMiddleware raises an exception."""
        sample_asgi_scope["type"] = "http"

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_instance.side_effect = RuntimeError("WSGI middleware error")
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            with pytest.raises(RuntimeError, match="WSGI middleware error"):
                await middleware(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_multiple_http_requests(self, mock_flask_app, mock_receive, mock_send):
        """Test middleware handles multiple HTTP requests correctly."""
        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        auth_ctx1 = AuthContext(username="user1@example.com", is_admin=False)
        auth_ctx2 = AuthContext(username="admin@example.com", is_admin=True)

        scope1 = {
            "type": "http",
            "path": "/api/users",
            "mlflow_oidc_auth": auth_ctx1,
        }

        scope2 = {
            "type": "http",
            "path": "/api/admin",
            "mlflow_oidc_auth": auth_ctx2,
        }

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            await middleware(scope1, mock_receive, mock_send)
            await middleware(scope2, mock_receive, mock_send)

            assert mock_wsgi_middleware.call_count == 2

            first_app = mock_wsgi_middleware.call_args_list[0][0][0]
            second_app = mock_wsgi_middleware.call_args_list[1][0][0]

            assert first_app.scope["mlflow_oidc_auth"].username == "user1@example.com"
            assert second_app.scope["mlflow_oidc_auth"].username == "admin@example.com"

    @pytest.mark.asyncio
    async def test_integration_auth_context_injection_flow(self, sample_asgi_scope, sample_wsgi_environ, mock_receive, mock_send):
        """Test complete integration flow from ASGI scope to WSGI environ injection."""
        sample_asgi_scope["type"] = "http"
        auth_ctx = AuthContext(username="integration@example.com", is_admin=True, workspace="test-ws")
        sample_asgi_scope["mlflow_oidc_auth"] = auth_ctx

        captured_environ = {}

        def capturing_flask_app(environ, start_response):
            captured_environ.update(environ)
            status = "200 OK"
            headers = [("Content-Type", "application/json")]
            start_response(status, headers)
            return [b'{"status": "ok"}']

        middleware = AuthAwareWSGIMiddleware(capturing_flask_app)

        await middleware(sample_asgi_scope, mock_receive, mock_send)

        # Verify AuthContext was properly injected into WSGI environ
        assert isinstance(captured_environ["mlflow_oidc_auth"], AuthContext)
        assert captured_environ["mlflow_oidc_auth"].username == "integration@example.com"
        assert captured_environ["mlflow_oidc_auth"].is_admin is True
        assert captured_environ["mlflow_oidc_auth"].workspace == "test-ws"


class TestWSGIBridgeConcurrency:
    """The bridge must not run all Flask requests of a process on one thread."""

    @staticmethod
    def _scope(path):
        return {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 1234),
        }

    @staticmethod
    async def _call(middleware, path):
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        await middleware(TestWSGIBridgeConcurrency._scope(path), receive, send)
        return sent

    async def test_slow_request_does_not_block_another(self):
        """A request that blocks its thread must not delay a second request on the same middleware.

        asgiref's stock WsgiToAsgi runs every call on one shared thread, so the fast request
        below would wait for the slow one to finish.
        """
        import asyncio
        import threading

        slow_started = threading.Event()
        release_slow = threading.Event()

        def app(environ, start_response):
            if environ["PATH_INFO"] == "/slow":
                slow_started.set()
                release_slow.wait(timeout=10)
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [environ["PATH_INFO"].encode()]

        middleware = AuthAwareWSGIMiddleware(app)
        slow = asyncio.create_task(self._call(middleware, "/slow"))
        fast = None
        try:
            assert await asyncio.to_thread(slow_started.wait, 5)
            fast = asyncio.create_task(self._call(middleware, "/fast"))
            # Wait without cancelling: a cancelled call can stay queued on asgiref's shared thread.
            done, _ = await asyncio.wait({fast}, timeout=5)
            fast_finished_first = fast in done
        finally:
            release_slow.set()
        slow_sent, fast_sent = await asyncio.gather(slow, fast)
        assert fast_finished_first, "the fast request waited for the slow one: the bridge ran them one at a time"
        assert fast_sent[0]["status"] == 200
        assert b"".join(m.get("body", b"") for m in fast_sent if m["type"] == "http.response.body") == b"/fast"
        assert slow_sent[0]["status"] == 200

    async def test_auth_context_reaches_each_concurrent_request(self):
        """Concurrent requests each see their own AuthContext, never another request's."""
        import asyncio

        seen = {}

        def app(environ, start_response):
            ctx = environ.get("mlflow_oidc_auth")
            seen[environ["PATH_INFO"]] = ctx.username if ctx else None
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

        middleware = AuthAwareWSGIMiddleware(app)

        async def call_as(user):
            scope = self._scope(f"/{user}")
            scope["mlflow_oidc_auth"] = AuthContext(username=f"{user}@example.com", is_admin=False)

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                pass

            await middleware(scope, receive, send)

        users = [f"user{i}" for i in range(20)]
        await asyncio.gather(*(call_as(u) for u in users))
        assert seen == {f"/{u}": f"{u}@example.com" for u in users}

    def test_pool_size_follows_wsgi_threads(self):
        """The Flask requests run on a pool of WSGI_THREADS threads, not on the event loop's default executor."""
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.middleware import auth_aware_wsgi_middleware as bridge

        assert bridge._WSGI_EXECUTOR._max_workers == config.WSGI_THREADS

    async def test_pool_caps_concurrent_requests(self):
        """No more Flask requests run at once than WSGI_THREADS; the next one waits for a free thread."""
        import asyncio
        import threading

        from mlflow_oidc_auth.config import config

        size = config.WSGI_THREADS
        lock = threading.Lock()
        running, peak = [0], [0]
        pool_full, release = threading.Event(), threading.Event()

        def app(environ, start_response):
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
                if running[0] == size:
                    pool_full.set()
            release.wait(timeout=10)
            with lock:
                running[0] -= 1
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

        middleware = AuthAwareWSGIMiddleware(app)
        calls = [asyncio.create_task(self._call(middleware, f"/r{i}")) for i in range(size + 1)]
        try:
            filled = await asyncio.to_thread(pool_full.wait, 5)
            await asyncio.sleep(0.2)
            peak_while_full = peak[0]
        finally:
            # Let every request finish before any assertion fails: a request left running would
            # wait forever on the closed event loop to send its response.
            release.set()
            results = await asyncio.gather(*calls)
        assert filled, "the pool never ran WSGI_THREADS requests at once"
        assert peak_while_full == size, "one request more than WSGI_THREADS ran while every pool thread was busy"
        assert all(sent[0]["status"] == 200 for sent in results)


class TestWSGIThreadsSetting:
    """WSGI_THREADS sizes the thread pool that runs the Flask requests (issue #482)."""

    def test_default_is_four(self, monkeypatch):
        from mlflow_oidc_auth.config import AppConfig

        monkeypatch.delenv("WSGI_THREADS", raising=False)
        assert AppConfig().WSGI_THREADS == 4

    def test_env_value_is_read(self, monkeypatch):
        from mlflow_oidc_auth.config import AppConfig

        monkeypatch.setenv("WSGI_THREADS", "2")
        assert AppConfig().WSGI_THREADS == 2

    @pytest.mark.parametrize("bad", ["0", "-1", "many"])
    def test_invalid_value_uses_the_default(self, monkeypatch, bad):
        from mlflow_oidc_auth.config import AppConfig

        monkeypatch.setenv("WSGI_THREADS", bad)
        assert AppConfig().WSGI_THREADS == 4
