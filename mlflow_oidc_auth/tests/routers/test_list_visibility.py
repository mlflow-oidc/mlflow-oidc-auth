from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
from mlflow_oidc_auth.routers.users import users_router
from mlflow_oidc_auth.utils import get_is_admin, get_username

CALLER = "user@example.com"


def _client(router, is_admin: bool) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_username] = lambda: CALLER
    app.dependency_overrides[get_is_admin] = lambda: is_admin
    return TestClient(app)


def _assert_page(response, expected: list[str], paginated: bool) -> None:
    assert response.status_code == 200
    assert response.json() == (expected[:1] if paginated else expected)
    if paginated:
        assert response.headers["X-Total-Count"] == str(len(expected))


@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize("is_admin", [False, True])
@pytest.mark.parametrize("paginated", [False, True])
def test_user_listing_visibility(mock_store: MagicMock, monkeypatch, restricted: bool, is_admin: bool, paginated: bool) -> None:
    monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", restricted)
    everyone = ["admin@example.com", CALLER, "other@example.com"]
    mock_store.list_usernames.return_value = everyone
    params = {"limit": 1} if paginated else {}

    with patch("mlflow_oidc_auth.store.store", mock_store), _client(users_router, is_admin) as client:
        response = client.get("/api/2.0/mlflow/users", params=params)

    _assert_page(response, [CALLER] if restricted and not is_admin else everyone, paginated)


@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize("is_admin", [False, True])
def test_service_account_listing_visibility(mock_store: MagicMock, monkeypatch, restricted: bool, is_admin: bool) -> None:
    monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", restricted)
    accounts = ["svc-a", "svc-b"]
    mock_store.list_usernames.return_value = accounts

    with patch("mlflow_oidc_auth.store.store", mock_store), _client(users_router, is_admin) as client:
        response = client.get("/api/2.0/mlflow/users", params={"service": "true"})

    mock_store.list_usernames.assert_called_once_with(is_service_account=True)
    _assert_page(response, [] if restricted and not is_admin else accounts, paginated=False)


@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize("is_admin", [False, True])
@pytest.mark.parametrize("paginated", [False, True])
def test_group_listing_visibility(mock_store: MagicMock, monkeypatch, restricted: bool, is_admin: bool, paginated: bool) -> None:
    monkeypatch.setattr(config, "RESTRICT_USER_AND_GROUP_LISTING", restricted)
    mock_store.get_groups.return_value = ["admins", "developers", "other-tenant"]
    mock_store.get_groups_for_user.return_value = ["developers"]
    params = {"limit": 1} if paginated else {}

    with patch("mlflow_oidc_auth.store.store", mock_store), _client(group_permissions_router, is_admin) as client:
        response = client.get("/api/2.0/mlflow/permissions/groups", params=params)

    if restricted and not is_admin:
        mock_store.get_groups_for_user.assert_called_once_with(CALLER)
        mock_store.get_groups.assert_not_called()
        _assert_page(response, ["developers"], paginated)
    else:
        mock_store.get_groups_for_user.assert_not_called()
        _assert_page(response, ["admins", "developers", "other-tenant"], paginated)
