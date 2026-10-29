from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
from mlflow_oidc_auth.routers.users import users_router
from mlflow_oidc_auth.utils import get_is_admin, get_username


@pytest.mark.parametrize("is_admin", [False, True])
@pytest.mark.parametrize("paginated", [False, True])
def test_user_listing_limits_visibility_before_pagination(mock_store: MagicMock, is_admin: bool, paginated: bool) -> None:
    app = FastAPI()
    app.include_router(users_router)
    app.dependency_overrides[get_username] = lambda: "user@example.com"
    app.dependency_overrides[get_is_admin] = lambda: is_admin
    mock_store.list_usernames.return_value = ["admin@example.com", "user@example.com"]
    params = {"limit": 1} if paginated else {}

    with patch("mlflow_oidc_auth.store.store", mock_store), TestClient(app) as client:
        response = client.get("/api/2.0/mlflow/users", params=params)

    assert response.status_code == 200
    expected = ["admin@example.com", "user@example.com"] if is_admin else ["user@example.com"]
    assert response.json() == (expected[:1] if paginated else expected)
    if paginated:
        assert response.headers["X-Total-Count"] == str(len(expected))


@pytest.mark.parametrize("is_admin", [False, True])
@pytest.mark.parametrize("paginated", [False, True])
def test_group_listing_limits_visibility_before_pagination(mock_store: MagicMock, is_admin: bool, paginated: bool) -> None:
    app = FastAPI()
    app.include_router(group_permissions_router)
    app.dependency_overrides[get_username] = lambda: "user@example.com"
    app.dependency_overrides[get_is_admin] = lambda: is_admin
    mock_store.get_groups.return_value = ["admins", "developers"]
    mock_store.get_groups_for_user.return_value = ["developers"]
    params = {"limit": 1} if paginated else {}

    with patch("mlflow_oidc_auth.store.store", mock_store), TestClient(app) as client:
        response = client.get("/api/2.0/mlflow/permissions/groups", params=params)

    assert response.status_code == 200
    expected = ["admins", "developers"] if is_admin else ["developers"]
    assert response.json() == (expected[:1] if paginated else expected)
    if paginated:
        assert response.headers["X-Total-Count"] == str(len(expected))
