import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, Response
from mlflow.protos.service_pb2 import CreateExperiment, SearchExperiments
from mlflow.protos.model_registry_pb2 import CreateRegisteredModel, DeleteRegisteredModel, SearchRegisteredModels
from mlflow_oidc_auth.hooks.after_request import after_request_hook, AFTER_REQUEST_PATH_HANDLERS

app = Flask(__name__)


@pytest.fixture
def mock_response():
    response = MagicMock(spec=Response)
    response.status_code = 200
    response.json = {}
    response.data = b"{}"
    return response


@pytest.fixture
def mock_store():
    with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
        yield mock_store


@pytest.fixture
def mock_utils():
    with patch("mlflow_oidc_auth.hooks.after_request.get_username", return_value="test_user") as mock_username, patch(
        "mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False
    ) as mock_is_admin:
        yield mock_username, mock_is_admin


def test_after_request_hook_no_handler(mock_response):
    with app.test_request_context(path="/unknown/path", method="GET", headers={"Content-Type": "application/json"}):
        result = after_request_hook(mock_response)
        assert result == mock_response


def test_delete_can_manage_registered_model_permission(mock_response, mock_store):
    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/delete",
        method="DELETE",
        json={"name": "test_model"},  # Send parameters in the body as JSON
        headers={"Content-Type": "application/json"},
    ):
        handler = AFTER_REQUEST_PATH_HANDLERS[DeleteRegisteredModel]
        with patch("mlflow_oidc_auth.utils.get_request_param", return_value="test_model"):
            handler(mock_response)
            mock_store.wipe_group_model_permissions.assert_called_once_with("test_model")
            mock_store.wipe_registered_model_permissions.assert_called_once_with("test_model")


def test_filter_search_experiments(mock_response, mock_store, mock_utils):
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchExperiments]
    mock_response.json = {"experiments": [{"experiment_id": "123"}]}
    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.can_read_experiment", side_effect=lambda exp_id, _: exp_id != "123"):
            handler(mock_response)
            assert len(mock_response.json["experiments"]) == 1


def test_filter_search_registered_models(mock_response, mock_store, mock_utils):
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchRegisteredModels]
    mock_response.json = {"registered_models": [{"name": "test_model"}]}
    with app.test_request_context(path="/api/2.0/mlflow/registered-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.can_read_registered_model", side_effect=lambda name, _: name != "test_model"):
            handler(mock_response)
            assert len(mock_response.json["registered_models"]) == 1


def test_rename_registered_model_permission(mock_response, mock_store):
    """Test _rename_registered_model_permission handler"""
    from mlflow.protos.model_registry_pb2 import RenameRegisteredModel

    handler = AFTER_REQUEST_PATH_HANDLERS[RenameRegisteredModel]

    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        json={"name": "old_model", "new_name": "new_model"},
        headers={"Content-Type": "application/json"},
    ):
        handler(mock_response)
        mock_store.rename_registered_model_permissions.assert_called_once_with("old_model", "new_model")
        mock_store.rename_group_model_permissions.assert_called_once_with("old_model", "new_model")


def test_rename_registered_model_permission_missing_name(mock_response, mock_store):
    """Test _rename_registered_model_permission handler with missing name"""
    from mlflow.protos.model_registry_pb2 import RenameRegisteredModel

    handler = AFTER_REQUEST_PATH_HANDLERS[RenameRegisteredModel]

    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        json={"new_name": "new_model"},  # Missing 'name'
        headers={"Content-Type": "application/json"},
    ):
        with pytest.raises(ValueError, match="Both 'name' and 'new_name' must be provided"):
            handler(mock_response)


def test_rename_registered_model_permission_missing_new_name(mock_response, mock_store):
    """Test _rename_registered_model_permission handler with missing new_name"""
    from mlflow.protos.model_registry_pb2 import RenameRegisteredModel

    handler = AFTER_REQUEST_PATH_HANDLERS[RenameRegisteredModel]

    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        json={"name": "old_model"},  # Missing 'new_name'
        headers={"Content-Type": "application/json"},
    ):
        with pytest.raises(ValueError, match="Both 'name' and 'new_name' must be provided"):
            handler(mock_response)


def test_rename_registered_model_permission_no_json(mock_response, mock_store):
    """Test _rename_registered_model_permission handler with no JSON data"""
    from mlflow.protos.model_registry_pb2 import RenameRegisteredModel

    handler = AFTER_REQUEST_PATH_HANDLERS[RenameRegisteredModel]

    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        headers={"Content-Type": "application/json"},
    ):
        with pytest.raises(ValueError, match="Both 'name' and 'new_name' must be provided"):
            handler(mock_response)
