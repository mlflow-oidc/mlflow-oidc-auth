import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, Response
from mlflow.protos.service_pb2 import CreateExperiment
from mlflow_oidc_auth.hooks.after_request import (
    after_request_hook,
    _set_can_manage_experiment_permission,
    _set_can_manage_registered_model_permission,
    _delete_can_manage_registered_model_permission,
    _filter_search_experiments,
    _filter_search_registered_models,
    _filter_search_logged_models,
    _rename_registered_model_permission,
    _get_after_request_handler,
)

app = Flask(__name__)


class _FakePagedList(list):
    """Lightweight stand-in for MLflow's PagedList in unit tests."""

    def __init__(self, items, token=None):
        super().__init__(items)
        self.token = token


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
def mock_bridge():
    with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_username", return_value="test_user") as mock_username, patch(
        "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False
    ) as mock_is_admin:
        yield mock_username, mock_is_admin


def test_after_request_hook_no_handler(mock_response):
    with app.test_request_context(path="/unknown/path", method="GET", headers={"Content-Type": "application/json"}):
        result = after_request_hook(mock_response)
        assert result == mock_response


def test_after_request_hook_error_response(mock_response):
    """Test after_request_hook with error response codes"""
    mock_response.status_code = 404

    with app.test_request_context(path="/unknown/path", method="GET", headers={"Content-Type": "application/json"}):
        result = after_request_hook(mock_response)
        assert result == mock_response


def test_after_request_hook_server_error(mock_response):
    """Test after_request_hook with server error response codes"""
    mock_response.status_code = 500

    with app.test_request_context(path="/unknown/path", method="GET", headers={"Content-Type": "application/json"}):
        result = after_request_hook(mock_response)
        assert result == mock_response


def test_get_after_request_handler():
    """Test _get_after_request_handler function"""
    # Test with valid request class
    handler = _get_after_request_handler(CreateExperiment)
    assert handler == _set_can_manage_experiment_permission

    # Test with invalid request class
    handler = _get_after_request_handler(type("UnknownRequest", (), {}))
    assert handler is None


def test_set_can_manage_experiment_permission(mock_response, mock_store, mock_bridge):
    """Test _set_can_manage_experiment_permission handler"""
    mock_response.json = {"experiment_id": "test_exp_123"}

    with app.test_request_context(path="/api/2.0/mlflow/experiments/create", method="POST", headers={"Content-Type": "application/json"}), patch(
        "mlflow_oidc_auth.hooks.after_request.parse_dict"
    ):
        # Mock the response message
        mock_response_message = MagicMock()
        mock_response_message.experiment_id = "test_exp_123"

        with patch("mlflow_oidc_auth.hooks.after_request.CreateExperiment.Response", return_value=mock_response_message):
            _set_can_manage_experiment_permission(mock_response)
            mock_store.create_experiment_permission.assert_called_once_with("test_exp_123", "test_user", "MANAGE")


def test_set_can_manage_registered_model_permission(mock_response, mock_store, mock_bridge):
    """Test _set_can_manage_registered_model_permission handler"""
    mock_response.json = {"registered_model": {"name": "test_model_123"}}

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/create", method="POST", headers={"Content-Type": "application/json"}), patch(
        "mlflow_oidc_auth.hooks.after_request.parse_dict"
    ):
        # Mock the response message
        mock_response_message = MagicMock()
        mock_response_message.registered_model.name = "test_model_123"

        with patch("mlflow_oidc_auth.hooks.after_request.CreateRegisteredModel.Response", return_value=mock_response_message):
            _set_can_manage_registered_model_permission(mock_response)
            mock_store.create_registered_model_permission.assert_called_once_with("test_model_123", "test_user", "MANAGE")


def test_delete_can_manage_registered_model_permission(mock_response, mock_store):
    """Test _delete_can_manage_registered_model_permission handler"""
    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/delete",
        method="DELETE",
        json={"name": "test_model"},
        headers={"Content-Type": "application/json"},
    ), patch("mlflow_oidc_auth.hooks.after_request.get_model_name", return_value="test_model"):
        _delete_can_manage_registered_model_permission(mock_response)
        mock_store.wipe_group_model_permissions.assert_called_once_with("test_model")
        mock_store.wipe_registered_model_permissions.assert_called_once_with("test_model")


def test_filter_search_experiments_admin(mock_response, mock_bridge):
    """Test _filter_search_experiments when user is admin (should not filter)"""
    mock_response.json = {"experiments": [{"experiment_id": "123"}]}

    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        # Mock admin user
        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=True):
            original_json = mock_response.json.copy()
            _filter_search_experiments(mock_response)
            # Should not modify response for admin
            assert mock_response.json == original_json


def test_filter_search_experiments_non_admin(mock_response, mock_bridge):
    """Test _filter_search_experiments for non-admin user"""
    mock_response.json = {"experiments": [{"experiment_id": "123"}]}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.view_type = 1
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 1000

    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_experiment", return_value=True
        ) as mock_can_read, patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"experiments": [{"experiment_id": "123"}]}'
        ):
            exp = MagicMock()
            exp.experiment_id = "123"
            mock_response_message = MagicMock()
            mock_response_message.experiments = [exp]
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response", return_value=mock_response_message):
                _filter_search_experiments(mock_response)

                mock_can_read.assert_called_once_with("123", "test_user")
                assert len(mock_response_message.experiments) == 1


def test_filter_search_experiments_with_pagination(mock_response, mock_bridge):
    """Test _filter_search_experiments with pagination needed"""
    mock_response.json = {"experiments": []}

    # Mock request message with small max_results
    mock_request_message = MagicMock()
    mock_request_message.view_type = 1
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        exp_entities = []
        for i in range(10):
            e = MagicMock()
            e.experiment_id = f"exp_{i}"
            e.to_proto.return_value = {"experiment_id": f"exp_{i}"}
            exp_entities.append(e)

        tracking_store = MagicMock()
        tracking_store.search_experiments.return_value = _FakePagedList(exp_entities, token=None)

        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_experiment", return_value=True
        ), patch("mlflow_oidc_auth.hooks.after_request._get_tracking_store", return_value=tracking_store), patch(
            "mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"experiments": []}'
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.SearchUtils.parse_start_offset_from_page_token", return_value=0
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.SearchUtils.create_page_token", return_value="page_token_123"
        ) as mock_page_token:
            mock_response_message = MagicMock()
            mock_response_message.experiments = []
            mock_response_message.next_page_token = "page_token_0"

            with patch("mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response", return_value=mock_response_message):
                _filter_search_experiments(mock_response)

                mock_page_token.assert_called_once_with(10)
                assert mock_response_message.next_page_token == "page_token_123"


def test_filter_search_experiments_no_pagination(mock_response, mock_bridge):
    """Test _filter_search_experiments when no pagination is needed"""
    mock_response.json = {"experiments": []}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.view_type = 1
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_experiment", return_value=True
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"experiments": []}'
        ):
            mock_response_message = MagicMock()
            mock_response_message.experiments = []
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response", return_value=mock_response_message):
                _filter_search_experiments(mock_response)

                assert mock_response_message.next_page_token == ""


def test_filter_search_registered_models_admin(mock_response, mock_bridge):
    """Test _filter_search_registered_models when user is admin (should not filter)"""
    mock_response.json = {"registered_models": [{"name": "test_model"}]}

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/search", method="POST", headers={"Content-Type": "application/json"}):
        # Mock admin user
        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=True):
            original_json = mock_response.json.copy()
            _filter_search_registered_models(mock_response)
            # Should not modify response for admin
            assert mock_response.json == original_json


def test_filter_search_registered_models_non_admin(mock_response, mock_bridge):
    """Test _filter_search_registered_models for non-admin user"""
    mock_response.json = {"registered_models": [{"name": "test_model"}]}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 1000

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_registered_model", return_value=True
        ) as mock_can_read, patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"registered_models": [{"name": "test_model"}]}'
        ):
            rm = MagicMock()
            rm.name = "test_model"
            mock_response_message = MagicMock()
            mock_response_message.registered_models = [rm]
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response", return_value=mock_response_message):
                _filter_search_registered_models(mock_response)

                mock_can_read.assert_called_once_with("test_model", "test_user")
                assert len(mock_response_message.registered_models) == 1


def test_filter_search_registered_models_with_pagination(mock_response, mock_bridge):
    """Test _filter_search_registered_models with pagination needed"""
    mock_response.json = {"registered_models": []}

    # Mock request message with small max_results
    mock_request_message = MagicMock()
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/search", method="POST", headers={"Content-Type": "application/json"}):
        rm_entities = []
        for i in range(10):
            rm = MagicMock()
            rm.name = f"model_{i}"
            rm.to_proto.return_value = {"name": f"model_{i}"}
            rm_entities.append(rm)

        model_registry_store = MagicMock()
        model_registry_store.search_registered_models.return_value = _FakePagedList(rm_entities, token=None)

        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_registered_model", return_value=True
        ), patch("mlflow_oidc_auth.hooks.after_request._get_model_registry_store", return_value=model_registry_store), patch(
            "mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"registered_models": []}'
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.SearchUtils.parse_start_offset_from_page_token", return_value=0
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.SearchUtils.create_page_token", return_value="page_token_456"
        ) as mock_page_token:
            mock_response_message = MagicMock()
            mock_response_message.registered_models = []
            mock_response_message.next_page_token = "page_token_0"

            with patch("mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response", return_value=mock_response_message):
                _filter_search_registered_models(mock_response)

                mock_page_token.assert_called_once_with(10)
                assert mock_response_message.next_page_token == "page_token_456"


def test_rename_registered_model_permission(mock_response, mock_store):
    """Test _rename_registered_model_permission handler"""
    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        json={"name": "old_model", "new_name": "new_model"},
        headers={"Content-Type": "application/json"},
    ):
        _rename_registered_model_permission(mock_response)
        mock_store.rename_registered_model_permissions.assert_called_once_with("old_model", "new_model")
        mock_store.rename_group_model_permissions.assert_called_once_with("old_model", "new_model")


def test_rename_registered_model_permission_missing_name(mock_response, mock_store):
    """Test _rename_registered_model_permission handler with missing name"""
    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        json={"new_name": "new_model"},  # Missing 'name'
        headers={"Content-Type": "application/json"},
    ):
        _rename_registered_model_permission(mock_response)
        mock_store.rename_registered_model_permissions.assert_not_called()
        mock_store.rename_group_model_permissions.assert_not_called()


def test_rename_registered_model_permission_missing_new_name(mock_response, mock_store):
    """Test _rename_registered_model_permission handler with missing new_name"""
    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        json={"name": "old_model"},  # Missing 'new_name'
        headers={"Content-Type": "application/json"},
    ):
        _rename_registered_model_permission(mock_response)
        mock_store.rename_registered_model_permissions.assert_not_called()
        mock_store.rename_group_model_permissions.assert_not_called()


def test_rename_registered_model_permission_no_json(mock_response, mock_store):
    """Test _rename_registered_model_permission handler with no JSON data"""
    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        headers={"Content-Type": "application/json"},
    ):
        _rename_registered_model_permission(mock_response)
        mock_store.rename_registered_model_permissions.assert_not_called()
        mock_store.rename_group_model_permissions.assert_not_called()


def test_filter_search_logged_models_admin(mock_response, mock_bridge):
    """Test _filter_search_logged_models when user is admin (should not filter)"""
    mock_response.json = {"models": [{"experiment_id": "123"}]}

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):
        # Mock admin user
        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=True):
            original_json = mock_response.json.copy()
            _filter_search_logged_models(mock_response)
            # Should not modify response for admin
            assert mock_response.json == original_json


def test_filter_search_logged_models_non_admin(mock_response, mock_bridge):
    """Test _filter_search_logged_models for non-admin user"""
    mock_response.json = {"models": [{"experiment_id": "123", "name": "model1"}, {"experiment_id": "456", "name": "model2"}]}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.experiment_ids = ["123", "456"]
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 1000

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):

        def fake_can_read(exp_id: str, _user: str) -> bool:
            return exp_id == "123"

        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_experiment", side_effect=fake_can_read
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"models": []}'
        ):
            m1 = MagicMock()
            m1.info.experiment_id = "123"
            m2 = MagicMock()
            m2.info.experiment_id = "456"

            mock_response_message = MagicMock()
            mock_response_message.models = [m1, m2]
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response", return_value=mock_response_message):
                _filter_search_logged_models(mock_response)

                assert len(mock_response_message.models) == 1
                assert mock_response_message.models[0].info.experiment_id == "123"


def test_filter_search_logged_models_with_pagination(mock_response, mock_bridge):
    """Test _filter_search_logged_models with pagination needed"""
    mock_response.json = {"models": []}

    # Mock request message with small max_results
    mock_request_message = MagicMock()
    mock_request_message.experiment_ids = ["exp_1", "exp_2"]
    mock_request_message.filter = "filter_string"
    mock_request_message.order_by = [MagicMock(field_name="name", ascending=True, dataset_name="", dataset_digest="")]
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):
        batch_models = []
        for i in range(10):
            model = MagicMock()
            model.experiment_id = f"exp_{i}"
            model.to_proto.return_value = {"experiment_id": f"exp_{i}"}
            batch_models.append(model)

        tracking_store = MagicMock()
        tracking_store.search_logged_models.return_value = _FakePagedList(batch_models, token=None)

        mock_token_class = MagicMock()
        mock_token_class.decode.return_value = MagicMock(offset=0)
        mock_token_class.return_value.encode.return_value = "encoded_token"

        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_experiment", return_value=True
        ), patch("mlflow_oidc_auth.hooks.after_request._get_tracking_store", return_value=tracking_store), patch(
            "mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"models": [], "next_page_token": "token123"}'
        ), patch(
            "mlflow.utils.search_utils.SearchLoggedModelsPaginationToken", mock_token_class
        ):
            mock_response_message = MagicMock()
            mock_response_message.models = []
            mock_response_message.next_page_token = "token123"

            with patch("mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response", return_value=mock_response_message):
                _filter_search_logged_models(mock_response)

                tracking_store.search_logged_models.assert_called_once()
                assert len(mock_response_message.models) == 10
                assert mock_response_message.next_page_token == ""


def test_filter_search_logged_models_no_pagination_needed(mock_response, mock_bridge):
    """Test _filter_search_logged_models when no pagination is needed"""
    mock_response.json = {"models": []}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.experiment_ids = ["exp_1"]
    mock_request_message.filter = None
    mock_request_message.order_by = None
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.can_read_experiment", return_value=True
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ), patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"models": []}'
        ):
            m = MagicMock()
            m.info.experiment_id = "exp_1"
            mock_response_message = MagicMock()
            mock_response_message.models = [m]
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response", return_value=mock_response_message):
                _filter_search_logged_models(mock_response)
                assert mock_response_message.next_page_token == ""


def test_after_request_hook_with_handler(mock_response, mock_store, mock_bridge):
    """Test after_request_hook with a valid handler"""
    mock_response.status_code = 200
    mock_response.json = {"experiment_id": "test_exp_123"}

    with app.test_request_context(path="/api/2.0/mlflow/experiments/create", method="POST", headers={"Content-Type": "application/json"}), patch(
        "mlflow_oidc_auth.hooks.after_request.parse_dict"
    ):
        # Mock the response message
        mock_response_message = MagicMock()
        mock_response_message.experiment_id = "test_exp_123"

        with patch("mlflow_oidc_auth.hooks.after_request.CreateExperiment.Response", return_value=mock_response_message):
            result = after_request_hook(mock_response)
            assert result == mock_response
            mock_store.create_experiment_permission.assert_called_once_with("test_exp_123", "test_user", "MANAGE")


def test_after_request_hook_graphql_excluded():
    """Test that GraphQL paths are excluded from after request handlers"""
    from mlflow_oidc_auth.hooks.after_request import AFTER_REQUEST_HANDLERS

    # Verify that no GraphQL paths are in the handlers
    graphql_handlers = [path for (path, method) in AFTER_REQUEST_HANDLERS.keys() if "/graphql" in path]
    assert len(graphql_handlers) == 0


def test_after_request_hook_exception_handling(mock_response, mock_store, mock_bridge):
    """Test that after_request_hook properly handles exceptions with @catch_mlflow_exception"""
    mock_response.status_code = 200
    mock_response.json = {"experiment_id": "test_exp_123"}

    with app.test_request_context(path="/api/2.0/mlflow/experiments/create", method="POST", headers={"Content-Type": "application/json"}):
        # Mock store to raise an exception
        mock_store.create_experiment_permission.side_effect = Exception("Database error")

        with patch("mlflow_oidc_auth.hooks.after_request.parse_dict"):
            # Mock the response message
            mock_response_message = MagicMock()
            mock_response_message.experiment_id = "test_exp_123"

            with patch("mlflow_oidc_auth.hooks.after_request.CreateExperiment.Response", return_value=mock_response_message):
                # The @catch_mlflow_exception decorator should handle the exception
                # The function should raise the exception since that's how the decorator works
                try:
                    result = after_request_hook(mock_response)
                    # If no exception is raised, the decorator handled it and returned the response
                    assert result == mock_response
                except Exception as e:
                    # If exception is raised, that's also expected behavior
                    assert str(e) == "Database error"


def test_rename_registered_model_permission_invalid_json(mock_response, mock_store):
    """Test _rename_registered_model_permission handler with invalid JSON"""
    with app.test_request_context(
        path="/api/2.0/mlflow/registered-models/rename",
        method="PATCH",
        data="invalid json",
        headers={"Content-Type": "application/json"},
    ):
        _rename_registered_model_permission(mock_response)
        mock_store.rename_registered_model_permissions.assert_not_called()
        mock_store.rename_group_model_permissions.assert_not_called()
