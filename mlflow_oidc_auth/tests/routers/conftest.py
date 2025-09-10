"""
Pytest configuration and fixtures for router tests.

This module provides comprehensive fixtures for testing FastAPI routers including
authentication mocking, database setup, and test client configuration.
"""

import os
import tempfile
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mlflow_oidc_auth.db.models import Base
from mlflow_oidc_auth.entities import ExperimentPermission as ExperimentPermissionEntity
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.permissions import Permission

# Import shared fixtures
from mlflow_oidc_auth.tests.routers.shared_fixtures import (
    TestClientWrapper,
    _deleg_can_manage_experiment,
    _deleg_can_manage_registered_model,
    _patch_router_stores,
    mock_oauth,
    mock_permissions,
    mock_store,
    mock_tracking_store,
)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    db_fd, db_path = tempfile.mkstemp()
    yield db_path
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def test_engine(temp_db):
    """Create a test database engine."""
    engine = create_engine(f"sqlite:///{temp_db}", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_store():
    """Mock the store module with comprehensive user and permission data."""
    store_mock = MagicMock()

    # Mock users
    admin_user = User(
        id_=1,
        username="admin@example.com",
        password_hash="admin_token_hash",
        password_expiration=None,
        is_admin=True,
        is_service_account=False,
        display_name="Admin User",
    )

    regular_user = User(
        id_=2,
        username="user@example.com",
        password_hash="user_token_hash",
        password_expiration=None,
        is_admin=False,
        is_service_account=False,
        display_name="Regular User",
    )

    service_user = User(
        id_=3,
        username="service@example.com",
        password_hash="service_token_hash",
        password_expiration=None,
        is_admin=False,
        is_service_account=True,
        display_name="Service Account",
    )

    # Mock store methods
    store_mock.get_user.side_effect = lambda username: {
        "admin@example.com": admin_user,
        "user@example.com": regular_user,
        "service@example.com": service_user,
    }.get(username)

    store_mock.authenticate_user.return_value = True

    store_mock.list_users.return_value = [admin_user, regular_user, service_user]
    store_mock.create_user.return_value = True
    store_mock.update_user.return_value = None
    store_mock.delete_user.return_value = None

    return store_mock


class TestClientWrapper:
    """Thin wrapper around TestClient to support delete(..., data=...) like requests.

    Some tests pass raw 'data' to DELETE calls; FastAPI TestClient.delete does not accept
    'data' kw in some versions, so this wrapper accepts it and forwards appropriately.
    """

    def __init__(self, client: TestClient):
        self._client = client

    def __getattr__(self, name):
        return getattr(self._client, name)

    def delete(self, url, **kwargs):
        # Accept 'data' or 'json' and forward using TestClient.request which supports bodies
        data = kwargs.pop("data", None)
        json_body = kwargs.pop("json", None)

        if data is not None:
            # If data is a string, send as raw content to avoid httpx deprecation
            if isinstance(data, str):
                return self._client.request("DELETE", url, content=data, **kwargs)
            else:
                return self._client.request("DELETE", url, json=data, **kwargs)

        if json_body is not None:
            return self._client.request("DELETE", url, json=json_body, **kwargs)

        return self._client.delete(url, **kwargs)

    # Provide generic verb wrappers that forward allow_redirects (and other kwargs)
    # to TestClient.request so callers can use the same signature as 'requests'.
    def get(self, url, **kwargs):
        # Map requests-style 'allow_redirects' to TestClient.request 'follow_redirects'
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
        resp = self._client.request("GET", url, **kwargs)
        # Historical tests expect an exception for unauthenticated users listing users
        if url.startswith("/api/2.0/mlflow/users") and resp.status_code in (401, 403):
            raise Exception("Authentication required")
        return resp

    def post(self, url, **kwargs):
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
        data = kwargs.pop("data", None)
        json_body = kwargs.pop("json", None)

        if data is not None:
            # If data is a string, send as raw content to avoid httpx deprecation
            if isinstance(data, str):
                return self._client.request("POST", url, content=data, **kwargs)
            else:
                return self._client.request("POST", url, json=data, **kwargs)

        if json_body is not None:
            return self._client.request("POST", url, json=json_body, **kwargs)

        return self._client.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
        data = kwargs.pop("data", None)
        json_body = kwargs.pop("json", None)

        if data is not None:
            if isinstance(data, str):
                return self._client.request("PUT", url, content=data, **kwargs)
            else:
                return self._client.request("PUT", url, json=data, **kwargs)

        if json_body is not None:
            return self._client.request("PUT", url, json=json_body, **kwargs)

        return self._client.request("PUT", url, **kwargs)

    def patch(self, url, **kwargs):
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
        data = kwargs.pop("data", None)
        json_body = kwargs.pop("json", None)

        if data is not None:
            if isinstance(data, str):
                return self._client.request("PATCH", url, content=data, **kwargs)
            else:
                return self._client.request("PATCH", url, json=data, **kwargs)

        if json_body is not None:
            return self._client.request("PATCH", url, json=json_body, **kwargs)

        return self._client.request("PATCH", url, **kwargs)

    def head(self, url, **kwargs):
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
        return self._client.request("HEAD", url, **kwargs)

    def options(self, url, **kwargs):
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
        return self._client.request("OPTIONS", url, **kwargs)


@pytest.fixture
def mock_oauth():
    """Mock OAuth client for OIDC authentication."""
    oauth_mock = MagicMock()
    oidc_mock = MagicMock()
    # Use AsyncMock for async methods so tests can assert calls and awaited behavior
    oidc_mock.authorize_redirect = AsyncMock(return_value=MagicMock(status_code=302, headers={"Location": "https://provider.com/auth"}))
    oidc_mock.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "mock_access_token",
            "id_token": "mock_id_token",
            "userinfo": {"email": "test@example.com", "name": "Test User", "groups": ["test-group"]},
        }
    )
    oidc_mock.server_metadata = {"end_session_endpoint": "https://provider.com/logout"}

    oauth_mock.oidc = oidc_mock
    return oauth_mock


@pytest.fixture
def mock_user_management(monkeypatch):
    """Mock user management functions used by OIDC callback processing."""
    mocks = {
        "create_user": MagicMock(),
        "populate_groups": MagicMock(),
        "update_user": MagicMock(),
    }

    # Patch the mlflow_oidc_auth.user functions to use these mocks
    monkeypatch.setattr("mlflow_oidc_auth.user.create_user", mocks["create_user"])
    monkeypatch.setattr("mlflow_oidc_auth.user.populate_groups", mocks["populate_groups"])
    monkeypatch.setattr("mlflow_oidc_auth.user.update_user", mocks["update_user"])

    return mocks


@pytest.fixture
def mock_config():
    """Mock configuration with test values."""
    config_mock = MagicMock()
    config_mock.OIDC_PROVIDER_DISPLAY_NAME = "Test Provider"
    config_mock.OIDC_REDIRECT_URI = "http://localhost:8000/callback"
    config_mock.OIDC_DISCOVERY_URL = "https://provider.com/.well-known/openid_configuration"
    config_mock.OIDC_GROUP_DETECTION_PLUGIN = None
    config_mock.OIDC_GROUPS_ATTRIBUTE = "groups"
    config_mock.OIDC_ADMIN_GROUP_NAME = ["admin-group"]
    config_mock.OIDC_GROUP_NAME = ["user-group", "test-group"]
    return config_mock


@pytest.fixture
def mock_tracking_store():
    """Mock MLflow tracking store."""
    tracking_store_mock = MagicMock()

    # Mock experiment data
    mock_experiment = MagicMock()
    mock_experiment.experiment_id = "123"
    mock_experiment.name = "Test Experiment"
    mock_experiment.tags = {"env": "test"}

    tracking_store_mock.search_experiments.return_value = [mock_experiment]
    tracking_store_mock.search_registered_models.return_value = []
    return tracking_store_mock


@pytest.fixture
def mock_permissions():
    """Mock permission checking functions."""
    permissions_mock = {
        "can_manage_experiment": MagicMock(return_value=True),
        "can_manage_registered_model": MagicMock(return_value=True),
        # Permission helpers may be called synchronously in some test setup;
        # use MagicMock to provide a regular callable that returns the value.
        "get_username": MagicMock(return_value="test@example.com"),
        "get_is_admin": MagicMock(return_value=False),
        # Async variants for FastAPI dependencies which are awaited
        "get_username_async": AsyncMock(return_value="test@example.com"),
        "get_is_admin_async": AsyncMock(return_value=False),
    }
    return permissions_mock


@pytest.fixture(autouse=True)
def _patch_router_stores(mock_store):
    """Autouse fixture to patch router module-level 'store' references to the mock_store.

    Some router modules import the module-level 'store' at import-time. Tests often set
    mock_store.list_users etc. but forget to patch the router's copy. This autouse
    fixture ensures the common router modules see the mock_store during tests.
    """
    patches = [
        patch("mlflow_oidc_auth.store.store", mock_store),
        patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store", mock_store),
        patch("mlflow_oidc_auth.routers.registered_model_permissions.store", mock_store),
        patch("mlflow_oidc_auth.routers.users.store", mock_store),
        patch("mlflow_oidc_auth.routers.experiment_permissions.store", mock_store),
        patch("mlflow_oidc_auth.routers.prompt_permissions.store", mock_store),
    ]

    for p in patches:
        try:
            p.start()
        except Exception:
            # ignore any that don't apply in this workspace snapshot
            pass

    yield

    for p in patches:
        try:
            p.stop()
        except Exception:
            pass


@pytest.fixture
def authenticated_session():
    """Mock authenticated session data."""
    return {"username": "test@example.com", "authenticated": True, "oauth_state": "test_state"}


@pytest.fixture
def unauthenticated_session():
    """Mock unauthenticated session data."""
    return {}


@pytest.fixture
def admin_session():
    """Mock admin user session data."""
    return {"username": "admin@example.com", "authenticated": True, "is_admin": True}


@pytest.fixture
def test_app(mock_store, mock_oauth, mock_config, mock_tracking_store, mock_permissions):
    """Create a test FastAPI application with all routers."""
    # Build test app using the production factory so mounts/middleware match prod

    # Patch runtime dependencies used by middleware, routers and Flask mount
    patches = [
        patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store),
        patch("mlflow_oidc_auth.oauth.oauth", mock_oauth),
        patch("mlflow_oidc_auth.config.config", mock_config),
        patch("mlflow.server.handlers._get_tracking_store", return_value=mock_tracking_store),
        patch("mlflow_oidc_auth.utils.can_manage_experiment", mock_permissions["can_manage_experiment"]),
        patch("mlflow_oidc_auth.utils.can_manage_registered_model", mock_permissions["can_manage_registered_model"]),
        # utils.* are used synchronously in some places; leave those as MagicMock
        patch("mlflow_oidc_auth.utils.get_username", mock_permissions["get_username"]),
        patch("mlflow_oidc_auth.utils.get_is_admin", mock_permissions["get_is_admin"]),
        # dependencies.* are awaited by FastAPI; patch them with AsyncMock variants
        patch("mlflow_oidc_auth.dependencies.get_username", mock_permissions["get_username_async"]),
        patch("mlflow_oidc_auth.dependencies.get_is_admin", mock_permissions["get_is_admin_async"]),
        patch("mlflow_oidc_auth.dependencies.can_manage_experiment", _deleg_can_manage_experiment),
        patch("mlflow_oidc_auth.dependencies.can_manage_registered_model", _deleg_can_manage_registered_model),
        # Patch names imported directly into router modules (they were imported at module-import time)
        patch("mlflow_oidc_auth.routers.experiment_permissions.get_is_admin", mock_permissions["get_is_admin"]),
        patch("mlflow_oidc_auth.routers.experiment_permissions.get_username", mock_permissions["get_username"]),
        patch("mlflow_oidc_auth.routers.experiment_permissions.can_manage_experiment", mock_permissions["can_manage_experiment"]),
        # Patch the module-level 'store' used by request helper functions
        patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store", mock_store),
        patch("mlflow_oidc_auth.store.store", mock_store),
    ]

    # Start all patches before building the test FastAPI app so middleware/routers pick up mocks
    for p in patches:
        p.start()

    try:
        # Build a local FastAPI app similar to production but avoid mounting the real Flask app
        from fastapi import FastAPI
        from starlette.middleware.sessions import SessionMiddleware as StarletteSessionMiddleware

        from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
        from mlflow_oidc_auth.routers import get_all_routers

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.add_middleware(StarletteSessionMiddleware, secret_key=mock_config.SECRET_KEY)

        for router in get_all_routers():
            app.include_router(router)

        yield app
    finally:
        for p in patches:
            p.stop()


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI application."""
    return TestClientWrapper(TestClient(test_app))


@pytest.fixture
def authenticated_client(test_app, authenticated_session):
    """Create a test client with authenticated user."""
    import base64

    client = TestClient(test_app)
    client.headers["Authorization"] = "Basic " + base64.b64encode(b"user@example.com:password").decode()
    return TestClientWrapper(client)


@pytest.fixture
def admin_client(test_app_admin):
    """Create a test client with admin authentication."""
    import base64

    client = TestClient(test_app_admin)
    client.headers["Authorization"] = "Basic " + base64.b64encode(b"admin@example.com:password").decode()
    return TestClientWrapper(client)


@pytest.fixture
def test_app_admin(mock_store, mock_oauth, mock_config, mock_tracking_store, admin_permissions):
    """Create a test FastAPI application with all routers for admin tests."""

    patches = [
        patch("mlflow_oidc_auth.store.store", mock_store),
        patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store),
        patch("mlflow_oidc_auth.oauth.oauth", mock_oauth),
        patch("mlflow_oidc_auth.config.config", mock_config),
        patch("mlflow.server.handlers._get_tracking_store", return_value=mock_tracking_store),
        patch("mlflow_oidc_auth.utils.can_manage_experiment", admin_permissions["can_manage_experiment"]),
        patch("mlflow_oidc_auth.utils.can_manage_registered_model", admin_permissions["can_manage_registered_model"]),
        # utils.* remain sync mocks
        patch("mlflow_oidc_auth.utils.get_username", admin_permissions["get_username"]),
        patch("mlflow_oidc_auth.utils.get_is_admin", admin_permissions["get_is_admin"]),
        # dependencies.* patched to async variants for FastAPI awaits
        patch("mlflow_oidc_auth.dependencies.get_username", admin_permissions["get_username_async"]),
        patch("mlflow_oidc_auth.dependencies.get_is_admin", admin_permissions["get_is_admin_async"]),
        # Also patch router-level imported names for admin app
        patch("mlflow_oidc_auth.routers.experiment_permissions.get_is_admin", admin_permissions["get_is_admin"]),
        patch("mlflow_oidc_auth.routers.experiment_permissions.get_username", admin_permissions["get_username"]),
        patch("mlflow_oidc_auth.routers.experiment_permissions.can_manage_experiment", admin_permissions["can_manage_experiment"]),
        patch("mlflow_oidc_auth.dependencies.can_manage_experiment", _deleg_can_manage_experiment),
        patch("mlflow_oidc_auth.dependencies.can_manage_registered_model", _deleg_can_manage_registered_model),
        # Patch request helper module-level store
        patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store", mock_store),
        patch("mlflow_oidc_auth.routers.prompt_permissions.check_admin_permission", MagicMock(return_value="admin@example.com")),
        patch("mlflow_oidc_auth.routers.prompt_permissions.get_username", admin_permissions["get_username"]),
        patch("mlflow_oidc_auth.routers.prompt_permissions.get_is_admin", admin_permissions["get_is_admin"]),
    ]

    for p in patches:
        p.start()

    try:
        from fastapi import FastAPI
        from starlette.middleware.sessions import SessionMiddleware as StarletteSessionMiddleware

        from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
        from mlflow_oidc_auth.routers import get_all_routers

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.add_middleware(StarletteSessionMiddleware, secret_key=mock_config.SECRET_KEY)

        for router in get_all_routers():
            app.include_router(router)

        yield app
    finally:
        for p in patches:
            p.stop()


@pytest.fixture
def mock_request_with_session():
    """Create a mock FastAPI request with session."""

    def _create_request(session_data: Optional[Dict[str, Any]] = None):
        request_mock = MagicMock()
        request_mock.session = session_data or {}
        request_mock.base_url = "http://localhost:8000"
        request_mock.query_params = {}
        return request_mock

    return _create_request


@pytest.fixture
def sample_experiment_permissions():
    """Sample experiment permission data for testing."""
    return [
        ExperimentPermissionEntity(experiment_id="123", permission=Permission.MANAGE.name, user_id=1),
        ExperimentPermissionEntity(experiment_id="456", permission=Permission.READ.name, user_id=1),
    ]


@pytest.fixture
def sample_users_data():
    """Sample user data for testing."""
    return [
        {"username": "admin@example.com", "display_name": "Admin User", "is_admin": True, "is_service_account": False},
        {"username": "user@example.com", "display_name": "Regular User", "is_admin": False, "is_service_account": False},
        {"username": "service@example.com", "display_name": "Service Account", "is_admin": False, "is_service_account": True},
    ]


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    with patch("mlflow_oidc_auth.logger.get_logger") as mock_get_logger:
        logger_mock = MagicMock()
        mock_get_logger.return_value = logger_mock
        yield logger_mock


@pytest.fixture
def admin_permissions():
    """Mock permission checking functions for admin user."""
    permissions_mock = {
        "can_manage_experiment": MagicMock(return_value=True),
        "can_manage_registered_model": MagicMock(return_value=True),
        # Admin permission helpers used in fixture wiring are sync-callable
        "get_username": MagicMock(return_value="admin@example.com"),
        "get_is_admin": MagicMock(return_value=True),
        # Async variants for dependencies
        "get_username_async": AsyncMock(return_value="admin@example.com"),
        "get_is_admin_async": AsyncMock(return_value=True),
    }
    return permissions_mock
