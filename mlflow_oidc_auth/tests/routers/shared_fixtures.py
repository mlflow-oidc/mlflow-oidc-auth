"""
Shared fixtures for router tests extracted from conftest.py.
Keep this file minimal: common mocks and helpers used across router test modules.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from mlflow_oidc_auth.entities import User


# Delegator helpers: ensure dependencies.can_manage_* call the utils implementation at runtime
def _deleg_can_manage_experiment(experiment_id, username):
    from mlflow_oidc_auth import utils as _utils

    return _utils.can_manage_experiment(experiment_id, username)


def _deleg_can_manage_registered_model(model_name, username):
    from mlflow_oidc_auth import utils as _utils

    return _utils.can_manage_registered_model(model_name, username)


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

    Also maps allow_redirects -> follow_redirects to be compatible with tests.
    """

    def __init__(self, client: TestClient):
        self._client = client

    def __getattr__(self, name):
        return getattr(self._client, name)

    def delete(self, url, **kwargs):
        data = kwargs.pop("data", None)
        json_body = kwargs.pop("json", None)

        if data is not None:
            if isinstance(data, str):
                return self._client.request("DELETE", url, data=data, **kwargs)
            else:
                return self._client.request("DELETE", url, json=data, **kwargs)

        if json_body is not None:
            return self._client.request("DELETE", url, json=json_body, **kwargs)

        return self._client.delete(url, **kwargs)

    def _map_allow_redirects(self, kwargs):
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")

    def get(self, url, **kwargs):
        self._map_allow_redirects(kwargs)
        resp = self._client.request("GET", url, **kwargs)
        if url.startswith("/api/2.0/mlflow/users") and resp.status_code in (401, 403):
            raise Exception("Authentication required")
        return resp

    def post(self, url, **kwargs):
        self._map_allow_redirects(kwargs)
        return self._client.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        self._map_allow_redirects(kwargs)
        return self._client.request("PUT", url, **kwargs)

    def patch(self, url, **kwargs):
        self._map_allow_redirects(kwargs)
        return self._client.request("PATCH", url, **kwargs)

    def head(self, url, **kwargs):
        self._map_allow_redirects(kwargs)
        return self._client.request("HEAD", url, **kwargs)

    def options(self, url, **kwargs):
        self._map_allow_redirects(kwargs)
        return self._client.request("OPTIONS", url, **kwargs)


@pytest.fixture
def mock_oauth():
    oauth_mock = MagicMock()
    oidc_mock = MagicMock()
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
def mock_tracking_store():
    tracking_store_mock = MagicMock()

    mock_experiment = MagicMock()
    mock_experiment.experiment_id = "123"
    mock_experiment.name = "Test Experiment"
    mock_experiment.tags = {"env": "test"}

    tracking_store_mock.search_experiments.return_value = [mock_experiment]
    tracking_store_mock.search_registered_models.return_value = []
    return tracking_store_mock


@pytest.fixture
def mock_permissions():
    permissions_mock = {
        "can_manage_experiment": MagicMock(return_value=True),
        "can_manage_registered_model": MagicMock(return_value=True),
        "get_username": AsyncMock(return_value="test@example.com"),
        "get_is_admin": AsyncMock(return_value=False),
    }
    return permissions_mock


@pytest.fixture(autouse=True)
def _patch_router_stores(mock_store):
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
            pass

    yield

    for p in patches:
        try:
            p.stop()
        except Exception:
            pass
