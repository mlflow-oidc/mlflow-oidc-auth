"""
Pytest configuration and fixtures for router tests.

This module provides comprehensive fixtures for testing FastAPI routers including
authentication mocking, database setup, and test client configuration.
"""

import pytest

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mlflow_oidc_auth.routers import get_all_routers
from mlflow_oidc_auth.db.models import Base
from mlflow_oidc_auth.entities import User, Group, ExperimentPermission as ExperimentPermissionEntity
from mlflow_oidc_auth.permissions import Permission


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

    store_mock.list_users.return_value = [admin_user, regular_user, service_user]
    store_mock.create_user.return_value = True
    store_mock.update_user.return_value = None
    store_mock.delete_user.return_value = None

    return store_mock


@pytest.fixture
def mock_oauth():
    """Mock OAuth client for OIDC authentication."""
    oauth_mock = MagicMock()
    oidc_mock = MagicMock()

    # Mock successful authorization redirect
    async def mock_authorize_redirect(request, redirect_uri, state):
        return MagicMock(status_code=302, headers={"Location": f"https://provider.com/auth?redirect_uri={redirect_uri}&state={state}"})

    # Mock successful token exchange
    async def mock_authorize_access_token(request):
        return {
            "access_token": "mock_access_token",
            "id_token": "mock_id_token",
            "userinfo": {"email": "test@example.com", "name": "Test User", "groups": ["test-group"]},
        }

    oidc_mock.authorize_redirect = mock_authorize_redirect
    oidc_mock.authorize_access_token = mock_authorize_access_token
    oidc_mock.server_metadata = {"end_session_endpoint": "https://provider.com/logout"}

    oauth_mock.oidc = oidc_mock
    return oauth_mock


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
    return tracking_store_mock


@pytest.fixture
def mock_permissions():
    """Mock permission checking functions."""
    permissions_mock = {
        "can_manage_experiment": MagicMock(return_value=True),
        "can_manage_registered_model": MagicMock(return_value=True),
        "get_username": AsyncMock(return_value="test@example.com"),
        "get_is_admin": AsyncMock(return_value=False),
    }
    return permissions_mock


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
    app = FastAPI(title="Test MLflow OIDC Auth")

    # Add all routers
    for router in get_all_routers():
        app.include_router(router)

    # Mock dependencies
    with patch("mlflow_oidc_auth.store.store", mock_store), patch("mlflow_oidc_auth.oauth.oauth", mock_oauth), patch(
        "mlflow_oidc_auth.config.config", mock_config
    ), patch("mlflow.server.handlers._get_tracking_store", return_value=mock_tracking_store), patch(
        "mlflow_oidc_auth.utils.can_manage_experiment", mock_permissions["can_manage_experiment"]
    ), patch(
        "mlflow_oidc_auth.utils.can_manage_registered_model", mock_permissions["can_manage_registered_model"]
    ), patch(
        "mlflow_oidc_auth.utils.get_username", mock_permissions["get_username"]
    ), patch(
        "mlflow_oidc_auth.utils.get_is_admin", mock_permissions["get_is_admin"]
    ):
        yield app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI application."""
    return TestClient(test_app)


@pytest.fixture
def authenticated_client(test_app, authenticated_session):
    """Create a test client with authenticated session."""
    client = TestClient(test_app)

    # Mock session middleware
    with patch.object(client, "session", authenticated_session):
        yield client


@pytest.fixture
def admin_client(test_app, admin_session):
    """Create a test client with admin session."""
    client = TestClient(test_app)

    # Mock session middleware
    with patch.object(client, "session", admin_session):
        yield client


@pytest.fixture
def mock_user_management():
    """Mock user management functions."""
    with patch("mlflow_oidc_auth.user.create_user") as mock_create, patch("mlflow_oidc_auth.user.populate_groups") as mock_populate, patch(
        "mlflow_oidc_auth.user.update_user"
    ) as mock_update, patch("mlflow_oidc_auth.user.generate_token") as mock_generate:
        mock_create.return_value = (True, "User created successfully")
        mock_populate.return_value = None
        mock_update.return_value = None
        mock_generate.return_value = "generated_token_123"

        yield {"create_user": mock_create, "populate_groups": mock_populate, "update_user": mock_update, "generate_token": mock_generate}


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
        ExperimentPermissionEntity(experiment_id="123", permission=Permission.MANAGE, username="user@example.com"),
        ExperimentPermissionEntity(experiment_id="456", permission=Permission.READ, username="user@example.com"),
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
