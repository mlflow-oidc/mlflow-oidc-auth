import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, Response
from mlflow.protos.service_pb2 import CreateExperiment, SearchExperiments, SearchLoggedModels
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
    """Test _filter_search_experiments for non-admin user"""
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchExperiments]
    mock_response.json = {"experiments": [{"experiment_id": "123"}]}

    # Mock readable experiments
    mock_readable_experiments = [
        MagicMock(experiment_id="123", name="test_experiment"),
    ]
    mock_readable_experiments[0].to_proto.return_value = {"experiment_id": "123", "name": "test_experiment"}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.view_type = 1
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 1000

    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.fetch_readable_experiments", return_value=mock_readable_experiments
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ) as mock_parse, patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"experiments": [{"experiment_id": "123", "name": "test_experiment"}]}'
        ) as mock_to_json:
            # Mock response message
            mock_response_message = MagicMock()
            mock_response_message.ClearField = MagicMock()
            mock_response_message.experiments = MagicMock()
            mock_response_message.experiments.extend = MagicMock()
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response", return_value=mock_response_message):
                handler(mock_response)

                # Verify fetch_readable_experiments was called with correct parameters
                from mlflow_oidc_auth.hooks.after_request import fetch_readable_experiments

                fetch_readable_experiments.assert_called_once_with(view_type=1, order_by=[], filter_string=None, username="test_user")

                # Verify response was updated
                mock_response_message.ClearField.assert_called_once_with("experiments")
                mock_response_message.experiments.extend.assert_called_once()


def test_filter_search_registered_models(mock_response, mock_store, mock_utils):
    """Test _filter_search_registered_models for non-admin user"""
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchRegisteredModels]
    mock_response.json = {"registered_models": [{"name": "test_model"}]}

    # Mock readable models
    mock_readable_models = [
        MagicMock(name="test_model"),
    ]
    mock_readable_models[0].to_proto.return_value = {"name": "test_model"}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 1000

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.fetch_readable_registered_models", return_value=mock_readable_models
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ) as mock_parse, patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"registered_models": [{"name": "test_model"}]}'
        ) as mock_to_json:
            # Mock response message
            mock_response_message = MagicMock()
            mock_response_message.ClearField = MagicMock()
            mock_response_message.registered_models = MagicMock()
            mock_response_message.registered_models.extend = MagicMock()
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response", return_value=mock_response_message):
                handler(mock_response)

                # Verify fetch_readable_registered_models was called with correct parameters
                from mlflow_oidc_auth.hooks.after_request import fetch_readable_registered_models

                fetch_readable_registered_models.assert_called_once_with(filter_string=None, order_by=[], username="test_user")

                # Verify response was updated
                mock_response_message.ClearField.assert_called_once_with("registered_models")
                mock_response_message.registered_models.extend.assert_called_once()


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


def test_filter_search_logged_models_admin(mock_response, mock_utils):
    """Test _filter_search_logged_models when user is admin (should not filter)"""
    from mlflow.protos.service_pb2 import SearchLoggedModels

    handler = AFTER_REQUEST_PATH_HANDLERS[SearchLoggedModels]
    mock_response.json = {"models": [{"experiment_id": "123"}]}

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):
        # Mock admin user
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=True):
            original_json = mock_response.json.copy()
            handler(mock_response)
            # Should not modify response for admin
            assert mock_response.json == original_json


def test_filter_search_logged_models_non_admin(mock_response, mock_utils):
    """Test _filter_search_logged_models for non-admin user"""
    from mlflow.protos.service_pb2 import SearchLoggedModels

    handler = AFTER_REQUEST_PATH_HANDLERS[SearchLoggedModels]
    mock_response.json = {"models": [{"experiment_id": "123", "name": "model1"}, {"experiment_id": "456", "name": "model2"}]}

    # Mock readable models
    mock_readable_models = [
        MagicMock(experiment_id="123", name="model1"),
    ]
    mock_readable_models[0].to_proto.return_value = {"experiment_id": "123", "name": "model1"}

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.experiment_ids = ["123", "456"]
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 1000

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.fetch_readable_logged_models", return_value=mock_readable_models
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ) as mock_parse, patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"models": [{"experiment_id": "123", "name": "model1"}]}'
        ) as mock_to_json:
            # Mock response message
            mock_response_message = MagicMock()
            mock_response_message.ClearField = MagicMock()
            mock_response_message.models = MagicMock()
            mock_response_message.models.extend = MagicMock()
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response", return_value=mock_response_message):
                handler(mock_response)

                # Verify fetch_readable_logged_models was called with correct parameters
                from mlflow_oidc_auth.hooks.after_request import fetch_readable_logged_models

                fetch_readable_logged_models.assert_called_once_with(experiment_ids=["123", "456"], filter_string=None, order_by=None, username="test_user")

                # Verify response was updated
                mock_response_message.ClearField.assert_called_once_with("models")
                mock_response_message.models.extend.assert_called_once()


def test_filter_search_logged_models_with_pagination(mock_response, mock_utils):
    """Test _filter_search_logged_models with pagination needed"""
    from mlflow.protos.service_pb2 import SearchLoggedModels

    handler = AFTER_REQUEST_PATH_HANDLERS[SearchLoggedModels]
    mock_response.json = {"models": []}

    # Create more models than max_results to test pagination
    mock_readable_models = []
    for i in range(15):  # More than max_results (10)
        model = MagicMock()
        model.experiment_id = f"exp_{i}"
        model.name = f"model_{i}"
        model.to_proto.return_value = {"experiment_id": f"exp_{i}", "name": f"model_{i}"}
        mock_readable_models.append(model)

    # Mock request message with small max_results
    mock_request_message = MagicMock()
    mock_request_message.experiment_ids = ["exp_1", "exp_2"]
    mock_request_message.filter = "filter_string"
    mock_request_message.order_by = [MagicMock(field_name="name", ascending=True, dataset_name="", dataset_digest="")]
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.fetch_readable_logged_models", return_value=mock_readable_models
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ) as mock_parse, patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"models": [], "next_page_token": "token123"}'
        ) as mock_to_json:
            # Mock response message
            mock_response_message = MagicMock()
            mock_response_message.ClearField = MagicMock()
            mock_response_message.models = MagicMock()
            mock_response_message.models.extend = MagicMock()

            # Mock Token for pagination
            mock_token = MagicMock()
            mock_token.encode.return_value = "encoded_token"

            with patch("mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response", return_value=mock_response_message), patch(
                "mlflow.utils.search_utils.SearchLoggedModelsPaginationToken", return_value=mock_token
            ) as mock_token_class:
                handler(mock_response)

                # Verify fetch_readable_logged_models was called with order_by
                from mlflow_oidc_auth.hooks.after_request import fetch_readable_logged_models

                fetch_readable_logged_models.assert_called_once_with(
                    experiment_ids=["exp_1", "exp_2"],
                    filter_string="filter_string",
                    order_by=[{"field_name": "name", "ascending": True, "dataset_name": "", "dataset_digest": ""}],
                    username="test_user",
                )

                # Verify pagination token was set
                mock_token_class.assert_called_once()


def test_filter_search_logged_models_no_pagination_needed(mock_response, mock_utils):
    """Test _filter_search_logged_models when no pagination is needed"""
    from mlflow.protos.service_pb2 import SearchLoggedModels

    handler = AFTER_REQUEST_PATH_HANDLERS[SearchLoggedModels]
    mock_response.json = {"models": []}

    # Create fewer models than max_results
    mock_readable_models = []
    for i in range(5):  # Less than max_results (10)
        model = MagicMock()
        model.experiment_id = f"exp_{i}"
        model.name = f"model_{i}"
        model.to_proto.return_value = {"experiment_id": f"exp_{i}", "name": f"model_{i}"}
        mock_readable_models.append(model)

    # Mock request message
    mock_request_message = MagicMock()
    mock_request_message.experiment_ids = ["exp_1"]
    mock_request_message.filter = None
    mock_request_message.order_by = None
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/logged-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.fetch_readable_logged_models", return_value=mock_readable_models
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ) as mock_parse, patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"models": []}'
        ) as mock_to_json:
            # Mock response message
            mock_response_message = MagicMock()
            mock_response_message.ClearField = MagicMock()
            mock_response_message.models = MagicMock()
            mock_response_message.models.extend = MagicMock()
            mock_response_message.next_page_token = ""

            with patch("mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response", return_value=mock_response_message):
                handler(mock_response)

                # Verify no pagination token was set (next_page_token should be empty)
                assert mock_response_message.next_page_token == ""


def test_filter_search_experiments_admin(mock_response, mock_utils):
    """Test _filter_search_experiments when user is admin (should not filter)"""
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchExperiments]
    mock_response.json = {"experiments": [{"experiment_id": "123"}]}

    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        # Mock admin user
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=True):
            original_json = mock_response.json.copy()
            handler(mock_response)
            # Should not modify response for admin
            assert mock_response.json == original_json


def test_filter_search_registered_models_admin(mock_response, mock_utils):
    """Test _filter_search_registered_models when user is admin (should not filter)"""
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchRegisteredModels]
    mock_response.json = {"registered_models": [{"name": "test_model"}]}

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/search", method="POST", headers={"Content-Type": "application/json"}):
        # Mock admin user
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=True):
            original_json = mock_response.json.copy()
            handler(mock_response)
            # Should not modify response for admin
            assert mock_response.json == original_json


def test_after_request_hook_error_response(mock_response):
    """Test after_request_hook with error response codes"""
    mock_response.status_code = 404

    with app.test_request_context(path="/unknown/path", method="GET", headers={"Content-Type": "application/json"}):
        result = after_request_hook(mock_response)
        assert result == mock_response


def test_after_request_hook_with_handler(mock_response, mock_store):
    """Test after_request_hook with a valid handler"""
    mock_response.status_code = 200
    mock_response.json = {"experiment_id": "test_exp_123"}

    with app.test_request_context(path="/api/2.0/mlflow/experiments/create", method="POST", headers={"Content-Type": "application/json"}), patch(
        "mlflow_oidc_auth.hooks.after_request.get_username", return_value="test_user"
    ), patch("mlflow_oidc_auth.hooks.after_request.parse_dict") as mock_parse:
        # Mock the response message
        mock_response_message = MagicMock()
        mock_response_message.experiment_id = "test_exp_123"

        with patch("mlflow_oidc_auth.hooks.after_request.CreateExperiment.Response", return_value=mock_response_message):
            result = after_request_hook(mock_response)
            assert result == mock_response
            mock_store.create_experiment_permission.assert_called_once_with("test_exp_123", "test_user", "MANAGE")


def test_set_can_manage_registered_model_permission(mock_response, mock_store):
    """Test _set_can_manage_registered_model_permission handler"""
    handler = AFTER_REQUEST_PATH_HANDLERS[CreateRegisteredModel]
    mock_response.json = {"registered_model": {"name": "test_model_123"}}

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/create", method="POST", headers={"Content-Type": "application/json"}), patch(
        "mlflow_oidc_auth.hooks.after_request.get_username", return_value="test_user"
    ), patch("mlflow_oidc_auth.hooks.after_request.parse_dict") as mock_parse:
        # Mock the response message
        mock_response_message = MagicMock()
        mock_response_message.registered_model.name = "test_model_123"

        with patch("mlflow_oidc_auth.hooks.after_request.CreateRegisteredModel.Response", return_value=mock_response_message):
            handler(mock_response)
            mock_store.create_registered_model_permission.assert_called_once_with("test_model_123", "test_user", "MANAGE")


def test_filter_search_experiments_with_pagination(mock_response, mock_utils):
    """Test _filter_search_experiments with pagination needed"""
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchExperiments]
    mock_response.json = {"experiments": []}

    # Create more experiments than max_results to test pagination
    mock_readable_experiments = []
    for i in range(15):  # More than max_results (10)
        experiment = MagicMock()
        experiment.experiment_id = f"exp_{i}"
        experiment.name = f"experiment_{i}"
        experiment.to_proto.return_value = {"experiment_id": f"exp_{i}", "name": f"experiment_{i}"}
        mock_readable_experiments.append(experiment)

    # Mock request message with small max_results
    mock_request_message = MagicMock()
    mock_request_message.view_type = 1
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/experiments/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.fetch_readable_experiments", return_value=mock_readable_experiments
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ) as mock_parse, patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"experiments": []}'
        ) as mock_to_json, patch(
            "mlflow_oidc_auth.hooks.after_request.SearchUtils.create_page_token", return_value="page_token_123"
        ) as mock_page_token:
            # Mock response message
            mock_response_message = MagicMock()
            mock_response_message.ClearField = MagicMock()
            mock_response_message.experiments = MagicMock()
            mock_response_message.experiments.extend = MagicMock()

            with patch("mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response", return_value=mock_response_message):
                handler(mock_response)

                # Verify pagination token was set
                mock_page_token.assert_called_once_with(10)
                assert mock_response_message.next_page_token == "page_token_123"


def test_filter_search_registered_models_with_pagination(mock_response, mock_utils):
    """Test _filter_search_registered_models with pagination needed"""
    handler = AFTER_REQUEST_PATH_HANDLERS[SearchRegisteredModels]
    mock_response.json = {"registered_models": []}

    # Create more models than max_results to test pagination
    mock_readable_models = []
    for i in range(15):  # More than max_results (10)
        model = MagicMock()
        model.name = f"model_{i}"
        model.to_proto.return_value = {"name": f"model_{i}"}
        mock_readable_models.append(model)

    # Mock request message with small max_results
    mock_request_message = MagicMock()
    mock_request_message.filter = None
    mock_request_message.order_by = []
    mock_request_message.max_results = 10

    with app.test_request_context(path="/api/2.0/mlflow/registered-models/search", method="POST", headers={"Content-Type": "application/json"}):
        with patch("mlflow_oidc_auth.hooks.after_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.after_request.fetch_readable_registered_models", return_value=mock_readable_models
        ), patch("mlflow_oidc_auth.hooks.after_request._get_request_message", return_value=mock_request_message), patch(
            "mlflow_oidc_auth.hooks.after_request.parse_dict"
        ) as mock_parse, patch(
            "mlflow_oidc_auth.hooks.after_request.message_to_json", return_value='{"registered_models": []}'
        ) as mock_to_json, patch(
            "mlflow_oidc_auth.hooks.after_request.SearchUtils.create_page_token", return_value="page_token_456"
        ) as mock_page_token:
            # Mock response message
            mock_response_message = MagicMock()
            mock_response_message.ClearField = MagicMock()
            mock_response_message.registered_models = MagicMock()
            mock_response_message.registered_models.extend = MagicMock()

            with patch("mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response", return_value=mock_response_message):
                handler(mock_response)

                # Verify pagination token was set
                mock_page_token.assert_called_once_with(10)
                assert mock_response_message.next_page_token == "page_token_456"
