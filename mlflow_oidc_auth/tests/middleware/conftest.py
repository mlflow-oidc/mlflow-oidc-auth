"""
Pytest configuration and fixtures for middleware tests.

This module provides comprehensive fixtures for testing middleware components
including authentication mocking, ASGI/WSGI setup, and request/response simulation.
"""

import pytest
from unittest.mock import MagicMock
from typing import Dict, Any, Optional
import base64

from fastapi import FastAPI, Request

from mlflow_oidc_auth.entities import User


@pytest.fixture
def mock_config():
    """Mock configuration for middleware tests."""
    config_mock = MagicMock()
    config_mock.AUTOMATIC_LOGIN_REDIRECT = True
    config_mock.OIDC_DISCOVERY_URL = "https://provider.com/.well-known/openid_configuration"
    config_mock.OIDC_CLIENT_ID = "test_client_id"
    config_mock.OIDC_CLIENT_SECRET = "test_client_secret"
    return config_mock


@pytest.fixture
def mock_store():
    """Mock store for middleware tests."""
    store_mock = MagicMock()

    # Mock users
    admin_user = User(
        id_=1,
        username="admin@example.com",
        password_hash="admin_hash",
        password_expiration=None,
        is_admin=True,
        is_service_account=False,
        display_name="Admin User",
    )

    regular_user = User(
        id_=2,
        username="user@example.com",
        password_hash="user_hash",
        password_expiration=None,
        is_admin=False,
        is_service_account=False,
        display_name="Regular User",
    )

    # Mock store methods
    store_mock.get_user.side_effect = lambda username: {"admin@example.com": admin_user, "user@example.com": regular_user}.get(username)

    store_mock.authenticate_user.side_effect = lambda username, password: {
        ("admin@example.com", "admin_pass"): True,
        ("user@example.com", "user_pass"): True,
    }.get((username, password), False)

    return store_mock


@pytest.fixture
def mock_validate_token():
    """Mock token validation function."""

    def _validate_token(token: str) -> Dict[str, Any]:
        if token == "valid_token":
            return {"email": "user@example.com", "preferred_username": "user@example.com", "exp": 9999999999, "iat": 1000000000}
        elif token == "admin_token":
            return {"email": "admin@example.com", "preferred_username": "admin@example.com", "exp": 9999999999, "iat": 1000000000}
        elif token == "invalid_payload_token":
            return {}
        else:
            raise ValueError("Invalid token")

    return _validate_token


@pytest.fixture
def mock_logger():
    """Mock logger for middleware tests."""
    logger_mock = MagicMock()
    return logger_mock


@pytest.fixture
def sample_asgi_scope():
    """Sample ASGI scope for testing."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "query_string": b"",
        "headers": [],
        "server": ("localhost", 8000),
        "client": ("127.0.0.1", 12345),
        "http_version": "1.1",
        "scheme": "http",
    }


@pytest.fixture
def sample_wsgi_environ():
    """Sample WSGI environ for testing."""
    return {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/api/test",
        "QUERY_STRING": "",
        "CONTENT_TYPE": "",
        "CONTENT_LENGTH": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8000",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": None,
        "wsgi.errors": None,
        "wsgi.multithread": False,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
    }


@pytest.fixture
def mock_flask_app():
    """Mock Flask application for WSGI middleware tests."""

    def flask_app(environ, start_response):
        status = "200 OK"
        headers = [("Content-Type", "application/json")]
        start_response(status, headers)
        return [b'{"message": "Hello from Flask"}']

    return flask_app


@pytest.fixture
def mock_receive():
    """Mock ASGI receive callable."""

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return receive


@pytest.fixture
def mock_send():
    """Mock ASGI send callable."""
    messages = []

    async def send(message):
        messages.append(message)

    send.messages = messages
    return send


@pytest.fixture
def test_fastapi_app():
    """Create a test FastAPI application for middleware testing."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected(request: Request):
        username = getattr(request.state, "username", None)
        is_admin = getattr(request.state, "is_admin", False)
        return {"username": username, "is_admin": is_admin}

    @app.get("/login")
    async def login():
        return {"message": "login page"}

    @app.get("/oidc/ui")
    async def oidc_ui():
        return {"message": "oidc ui"}

    return app


class MockRequest:
    """Mock FastAPI Request for testing."""

    def __init__(self, scope, session=None, has_session_middleware=True):
        self.scope = scope
        self.url = MagicMock()
        self.url.path = scope.get("path", "/")
        self.headers = {}

        # Convert headers from scope
        for name, value in scope.get("headers", []):
            self.headers[name.decode()] = value.decode()

        # Create a proper state object that can have attributes set
        class State:
            pass

        self.state = State()
        self._session_data = session
        self._has_session_middleware = has_session_middleware

    @property
    def session(self):
        if not self._has_session_middleware:
            raise AssertionError("SessionMiddleware must be installed to access request.session")
        return self._session_data or {}


@pytest.fixture
def create_mock_request():
    """Factory for creating mock FastAPI requests."""

    def _create_request(
        path: str = "/test",
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        session: Optional[Dict[str, Any]] = None,
        has_session_middleware: bool = True,
    ) -> MockRequest:
        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
            "server": ("localhost", 8000),
            "client": ("127.0.0.1", 12345),
        }

        return MockRequest(scope, session, has_session_middleware)

    return _create_request


@pytest.fixture
def basic_auth_header():
    """Create basic auth header for testing."""

    def _create_header(username: str, password: str) -> str:
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"

    return _create_header


@pytest.fixture
def bearer_auth_header():
    """Create bearer auth header for testing."""

    def _create_header(token: str) -> str:
        return f"Bearer {token}"

    return _create_header
