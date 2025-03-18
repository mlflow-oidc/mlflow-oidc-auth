import pytest
from unittest.mock import patch
from mlflow.exceptions import RestException
from mlflow_oidc_auth.client import AuthServiceClient
from mlflow_oidc_auth.routes import (
    CREATE_EXPERIMENT_PERMISSION,
    CREATE_REGISTERED_MODEL_PERMISSION,
    CREATE_USER,
    DELETE_EXPERIMENT_PERMISSION,
    DELETE_REGISTERED_MODEL_PERMISSION,
    DELETE_USER,
    GET_EXPERIMENT_PERMISSION,
    GET_REGISTERED_MODEL_PERMISSION,
    GET_USER,
    UPDATE_EXPERIMENT_PERMISSION,
    UPDATE_REGISTERED_MODEL_PERMISSION,
    UPDATE_USER_ADMIN,
    UPDATE_USER_PASSWORD,
)


@pytest.fixture
def client():
    return AuthServiceClient(tracking_uri="https://test")


class TestClientExceptions:
    def test_create_user_no_password(self, client):
        with pytest.raises(ValueError):
            client.create_user("test_user", None)

    def test_create_user_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.create_user(None, "password")

    def test_get_user_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.get_user(None)

    def test_update_user_password_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.update_user_password(None, "password")

    def test_update_user_password_with_no_password(self, client):
        with pytest.raises(ValueError):
            client.update_user_password("test_user", None)

    def test_update_user_admin_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.update_user_admin(None, True)

    def test_update_user_admin_with_no_boolean(self, client):
        # TODO: probably, use mypy to check typing
        with pytest.raises(ValueError):
            client.update_user_admin("test_user", "this is not boolean value")

    def test_delete_user_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.delete_user(None)

    def test_create_experiment_permission_with_no_experiment_id(self, client):
        with pytest.raises(ValueError):
            client.create_experiment_permission(None, "test_user", "READ")

    def test_create_experiment_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.create_experiment_permission("1", None, "READ")

    def test_create_experiment_permission_with_invalid_permission(self, client):
        with pytest.raises(ValueError):
            client.create_experiment_permission("1", "test_user", "THIS_PERMISSION_DOES_NOT_EXIST")

    def test_get_experiment_permission_with_no_experiment_id(self, client):
        with pytest.raises(ValueError):
            client.get_experiment_permission(None, "test_user")

    def test_get_experiment_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.get_experiment_permission("1", None)

    def test_update_experiment_permission_with_no_experiment_id(self, client):
        with pytest.raises(ValueError):
            client.update_experiment_permission(None, "test_user", "READ")

    def test_update_experiment_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.update_experiment_permission("1", None, "READ")

    def test_update_experiment_permission_with_invalid_permission(self, client):
        with pytest.raises(ValueError):
            client.update_experiment_permission("1", "test_user", "THIS_PERMISSION_DOES_NOT_EXIST")

    def test_delete_experiment_permission_with_no_experiment_id(self, client):
        with pytest.raises(ValueError):
            client.delete_experiment_permission(None, "test_user")

    def test_delete_experiment_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.delete_experiment_permission("1", None)

    def test_create_registered_model_permission_with_no_name(self, client):
        with pytest.raises(ValueError):
            client.create_registered_model_permission(None, "test_user", "READ")

    def test_create_registered_model_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.create_registered_model_permission("model", None, "READ")

    def test_create_registered_model_permission_with_invalid_permission(self, client):
        with pytest.raises(ValueError):
            client.create_registered_model_permission("model", "test_user", "THIS_PERMISSION_DOES_NOT_EXIST")

    def test_get_registered_model_permission_with_no_name(self, client):
        with pytest.raises(ValueError):
            client.get_registered_model_permission(None, "test_user")

    def test_get_registered_model_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.get_registered_model_permission("model", None)

    def test_update_registered_model_permission_with_no_name(self, client):
        with pytest.raises(ValueError):
            client.update_registered_model_permission(None, "test_user", "READ")

    def test_update_registered_model_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.update_registered_model_permission("model", None, "READ")

    def test_update_registered_model_permission_with_invalid_permission(self, client):
        with pytest.raises(ValueError):
            client.update_registered_model_permission("model", "test_user", "THIS_PERMISSION_DOES_NOT_EXIST")

    def test_delete_registered_model_permission_with_no_name(self, client):
        with pytest.raises(ValueError):
            client.delete_registered_model_permission(None, "test_user")

    def test_delete_registered_model_permission_with_no_username(self, client):
        with pytest.raises(ValueError):
            client.delete_registered_model_permission("model", None)


@pytest.fixture(
    scope="function",
    autouse=True,
)
def mock_request():
    with patch("mlflow_oidc_auth.client.AuthServiceClient._request") as mock:
        yield mock


class TestClient:
    def test_create_user(self, mock_request, client):
        mock_request.return_value = {
            "user": {
                "id": 123,
                "username": "test_user",
                "display_name": "Test User",
                "is_admin": False,
                "experiment_permissions": [],
                "registered_model_permissions": [],
                "groups": [],
            }
        }
        user = client.create_user("test_user", "password")
        assert user.username == "test_user"
        mock_request.assert_called_once_with(CREATE_USER, "POST", json={"username": "test_user", "password": "password"})

    def test_get_user(self, mock_request, client):
        mock_request.return_value = {
            "user": {
                "id": 123,
                "username": "test_user",
                "display_name": "Test User",
                "is_admin": False,
                "experiment_permissions": [],
                "registered_model_permissions": [],
                "groups": [],
            }
        }
        user = client.get_user("test_user")
        assert user.username == "test_user"
        mock_request.assert_called_once_with(GET_USER, "GET", params={"username": "test_user"})

    def test_update_user_password(self, mock_request, client):
        client.update_user_password("test_user", "new_password")
        mock_request.assert_called_once_with(
            UPDATE_USER_PASSWORD, "PATCH", json={"username": "test_user", "password": "new_password"}
        )

    def test_update_user_admin(self, mock_request, client):
        mock_request.return_value = {
            "user": {
                "id": 123,
                "username": "test_user",
                "display_name": "Test User",
                "is_admin": True,
                "experiment_permissions": [],
                "registered_model_permissions": [],
                "groups": [],
            }
        }
        client.update_user_admin("test_user", True)
        mock_request.assert_called_once_with(UPDATE_USER_ADMIN, "PATCH", json={"username": "test_user", "is_admin": True})

    def test_delete_user(self, mock_request, client):
        client.delete_user("test_user")
        mock_request.assert_called_once_with(DELETE_USER, "DELETE", json={"username": "test_user"})

    def test_create_experiment_permission(self, mock_request, client):
        mock_request.return_value = {"experiment_permission": {"experiment_id": 1, "permission": "READ", "user_id": 123}}
        permission = client.create_experiment_permission("1", "test_user", "READ")
        assert permission.permission == "READ"
        assert permission.experiment_id == 1
        assert permission.user_id == 123
        mock_request.assert_called_once_with(
            CREATE_EXPERIMENT_PERMISSION, "POST", json={"experiment_id": "1", "username": "test_user", "permission": "READ"}
        )

    def test_get_experiment_permission(self, mock_request, client):
        mock_request.return_value = {"experiment_permission": {"experiment_id": 1, "permission": "READ", "user_id": 123}}
        permission = client.get_experiment_permission("1", "test_user")
        assert permission.permission == "READ"
        assert permission.experiment_id == 1
        assert permission.user_id == 123
        mock_request.assert_called_once_with(
            GET_EXPERIMENT_PERMISSION, "GET", params={"experiment_id": "1", "username": "test_user"}
        )

    def test_update_experiment_permission(self, mock_request, client):
        mock_request.return_value = {"experiment_permission": {"experiment_id": 1, "permission": "READ", "user_id": 123}}
        client.update_experiment_permission("1", "test_user", "READ")
        mock_request.assert_called_once_with(
            UPDATE_EXPERIMENT_PERMISSION, "PATCH", json={"experiment_id": "1", "username": "test_user", "permission": "READ"}
        )

    def test_delete_experiment_permission(self, mock_request, client):
        client.delete_experiment_permission("1", "test_user")
        mock_request.assert_called_once_with(
            DELETE_EXPERIMENT_PERMISSION, "DELETE", json={"experiment_id": "1", "username": "test_user"}
        )

    def test_create_registered_model_permission(self, mock_request, client):
        mock_request.return_value = {"registered_model_permission": {"name": "model", "permission": "READ", "user_id": 123}}
        permission = client.create_registered_model_permission("model", "test_user", "READ")
        assert permission.permission == "READ"
        assert permission.name == "model"
        assert permission.user_id == 123
        mock_request.assert_called_once_with(
            CREATE_REGISTERED_MODEL_PERMISSION, "POST", json={"name": "model", "username": "test_user", "permission": "READ"}
        )

    def test_get_registered_model_permission(self, mock_request, client):
        mock_request.return_value = {"registered_model_permission": {"name": "model", "permission": "READ", "user_id": 123}}
        permission = client.get_registered_model_permission("model", "test_user")
        assert permission.permission == "READ"
        assert permission.name == "model"
        assert permission.user_id == 123
        mock_request.assert_called_once_with(
            GET_REGISTERED_MODEL_PERMISSION, "GET", params={"name": "model", "username": "test_user"}
        )

    def test_update_registered_model_permission(self, mock_request, client):
        mock_request.return_value = {"registered_model_permission": {"name": "model", "permission": "READ", "user_id": 123}}
        client.update_registered_model_permission("model", "test_user", "READ")
        mock_request.assert_called_once_with(
            UPDATE_REGISTERED_MODEL_PERMISSION, "PATCH", json={"name": "model", "username": "test_user", "permission": "READ"}
        )

    def test_delete_registered_model_permission(self, mock_request, client):
        client.delete_registered_model_permission("model", "test_user")
        mock_request.assert_called_once_with(
            DELETE_REGISTERED_MODEL_PERMISSION, "DELETE", json={"name": "model", "username": "test_user"}
        )

    def test_request(self, mock_request, client):
        mock_request.return_value = {"key": "value"}
        response = client._request("endpoint", "GET")
        assert response == {"key": "value"}
        mock_request.assert_called_once()

    def test_request_with_kwargs(self, mock_request, client):
        mock_request.return_value = {"key": "value"}
        response = client._request("endpoint", "POST", json={"data": "value"})
        assert response == {"key": "value"}
        mock_request.assert_called_once_with("endpoint", "POST", json={"data": "value"})

    def test_create_user_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.create_user("test_user", "password")

    def test_get_user_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.get_user("test_user")

    def test_update_user_password_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.update_user_password("test_user", "new_password")

    def test_update_user_admin_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.update_user_admin("test_user", True)

    def test_delete_user_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.delete_user("test_user")

    def test_create_experiment_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.create_experiment_permission("1", "test_user", "READ")

    def test_get_experiment_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.get_experiment_permission("1", "test_user")

    def test_update_experiment_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.update_experiment_permission("1", "test_user", "READ")

    def test_delete_experiment_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.delete_experiment_permission("1", "test_user")

    def test_create_registered_model_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.create_registered_model_permission("model", "test_user", "READ")

    def test_get_registered_model_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.get_registered_model_permission("model", "test_user")

    def test_update_registered_model_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.update_registered_model_permission("model", "test_user", "READ")

    def test_delete_registered_model_permission_rest_exception(self, mock_request, client):
        mock_request.side_effect = RestException({"error_code": "INTERNAL_ERROR", "message": "Error"})
        with pytest.raises(RestException):
            client.delete_registered_model_permission("model", "test_user")
