"""Tests for workspace-scoped search filtering in after_request hooks.

Tests _can_access_workspace helper and workspace filtering in:
- _filter_search_experiments (WSSEC-01)
- _filter_search_registered_models (WSSEC-02)
- _filter_search_logged_models (WSSEC-03)
"""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

app = Flask(__name__)
app.config["TESTING"] = True


class _FakePagedList(list):
    """Lightweight stand-in for MLflow's PagedList in unit tests."""

    def __init__(self, items, token=None):
        super().__init__(items)
        self.token = token


# ---------------------------------------------------------------------------
# _can_access_workspace helper tests
# ---------------------------------------------------------------------------


class TestCanAccessWorkspace:
    """Tests for _can_access_workspace helper function."""

    def test_returns_true_when_workspaces_disabled(self):
        """_can_access_workspace returns True when MLFLOW_ENABLE_WORKSPACES is False."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = False
            assert _can_access_workspace("user1", "some-ws") is True

    def test_returns_true_when_workspace_is_none(self):
        """_can_access_workspace returns True for None workspace (pre-workspace-era, WSSEC-05)."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            assert _can_access_workspace("user1", None) is True

    def test_returns_true_when_workspace_is_empty_string(self):
        """_can_access_workspace returns True for empty string workspace (pre-workspace-era, WSSEC-05)."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            assert _can_access_workspace("user1", "") is True

    def test_returns_true_when_user_has_read_permission(self):
        """_can_access_workspace returns True when user has at least READ permission."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace
        from mlflow_oidc_auth.permissions import READ

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_workspace_permission_cached",
                return_value=READ,
            ):
                assert _can_access_workspace("user1", "team-alpha") is True

    def test_returns_false_when_user_has_no_permission(self):
        """_can_access_workspace returns False when user has no workspace permission."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_workspace_permission_cached",
                return_value=None,
            ):
                assert _can_access_workspace("user1", "restricted-ws") is False

    def test_returns_false_when_permission_is_no_permissions(self):
        """_can_access_workspace returns False when user has NO_PERMISSIONS (can_read=False)."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_workspace_permission_cached",
                return_value=NO_PERMISSIONS,
            ):
                assert _can_access_workspace("user1", "some-ws") is False

    def test_default_workspace_treated_like_any_other(self):
        """_can_access_workspace treats 'default' workspace the same as any other — no implicit grant."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_workspace_permission_cached",
                return_value=None,
            ):
                assert _can_access_workspace("user1", "default") is False


# ---------------------------------------------------------------------------
# _filter_search_experiments workspace filtering tests
# ---------------------------------------------------------------------------


class TestFilterSearchExperimentsWorkspace:
    """Tests for workspace filtering in _filter_search_experiments (WSSEC-01)."""

    def test_removes_experiments_from_inaccessible_workspaces(self):
        """Experiments from inaccessible workspaces are removed on initial page."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_experiments

        mock_response = MagicMock()
        mock_response.json = {"experiments": []}

        mock_request_message = MagicMock()
        mock_request_message.view_type = 1
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        tracking_store = MagicMock()

        # Two experiments: one in accessible ws, one in inaccessible ws
        exp_accessible = MagicMock()
        exp_accessible.experiment_id = "exp_1"
        exp_accessible.workspace = "allowed-ws"

        exp_inaccessible = MagicMock()
        exp_inaccessible.experiment_id = "exp_2"
        exp_inaccessible.workspace = "denied-ws"

        tracking_store.get_experiment.side_effect = lambda eid: (
            exp_accessible if eid == "exp_1" else exp_inaccessible
        )

        with app.test_request_context():
            # Proto experiments (from initial page)
            proto_exp1 = MagicMock()
            proto_exp1.experiment_id = "exp_1"
            proto_exp2 = MagicMock()
            proto_exp2.experiment_id = "exp_2"

            mock_response_message = MagicMock()
            mock_response_message.experiments = [proto_exp1, proto_exp2]
            mock_response_message.next_page_token = ""

            def can_access_ws(username, workspace):
                return workspace in ("allowed-ws", None, "")

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=tracking_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    side_effect=can_access_ws,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_experiments(mock_response)

                # Only exp_1 should remain
                assert len(mock_response_message.experiments) == 1
                assert mock_response_message.experiments[0].experiment_id == "exp_1"

    def test_keeps_experiments_from_accessible_workspaces(self):
        """Experiments from accessible workspaces are kept on initial page."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_experiments

        mock_response = MagicMock()
        mock_response.json = {"experiments": []}

        mock_request_message = MagicMock()
        mock_request_message.view_type = 1
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        tracking_store = MagicMock()

        exp1 = MagicMock()
        exp1.experiment_id = "exp_1"
        exp1.workspace = "allowed-ws"
        exp2 = MagicMock()
        exp2.experiment_id = "exp_2"
        exp2.workspace = "allowed-ws"

        tracking_store.get_experiment.side_effect = lambda eid: (
            exp1 if eid == "exp_1" else exp2
        )

        with app.test_request_context():
            proto_exp1 = MagicMock()
            proto_exp1.experiment_id = "exp_1"
            proto_exp2 = MagicMock()
            proto_exp2.experiment_id = "exp_2"

            mock_response_message = MagicMock()
            mock_response_message.experiments = [proto_exp1, proto_exp2]
            mock_response_message.next_page_token = ""

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=tracking_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    return_value=True,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_experiments(mock_response)

                # Both should remain
                assert len(mock_response_message.experiments) == 2

    def test_refetch_path_applies_workspace_filtering(self):
        """Refetch path filters out entities from inaccessible workspaces."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_experiments

        mock_response = MagicMock()
        mock_response.json = {"experiments": []}

        mock_request_message = MagicMock()
        mock_request_message.view_type = 1
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 10

        # Build refetched entities — 5 in allowed-ws, 5 in denied-ws
        refetched_entities = []
        for i in range(10):
            e = MagicMock()
            e.experiment_id = f"exp_{i}"
            e.workspace = "allowed-ws" if i % 2 == 0 else "denied-ws"
            e.to_proto.return_value = MagicMock(experiment_id=f"exp_{i}")
            refetched_entities.append(e)

        tracking_store = MagicMock()
        # First call returns the entities, second call returns empty to break the loop
        tracking_store.search_experiments.side_effect = [
            _FakePagedList(refetched_entities, token=None),
            _FakePagedList([], token=None),
        ]

        with app.test_request_context():
            # Use a real list for experiments to properly test extend/len
            experiments_list = []
            mock_response_message = MagicMock()
            mock_response_message.experiments = experiments_list
            mock_response_message.next_page_token = "page_token_0"

            def can_access_ws(username, workspace):
                return workspace in ("allowed-ws", None, "")

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=tracking_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    side_effect=can_access_ws,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchUtils.parse_start_offset_from_page_token",
                    return_value=0,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchUtils.create_page_token",
                    return_value="page_token_10",
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_experiments(mock_response)

                # Only 5 of 10 should pass (even-indexed with allowed-ws)
                assert len(experiments_list) == 5

    def test_admin_bypasses_workspace_filtering(self):
        """Admin users see all experiments regardless of workspace (WSSEC-06)."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_experiments

        mock_response = MagicMock()
        mock_response.json = {"experiments": [{"experiment_id": "123"}]}

        with app.test_request_context():
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                return_value=True,
            ):
                original_json = mock_response.json.copy()
                _filter_search_experiments(mock_response)
                assert mock_response.json == original_json

    def test_no_workspace_filtering_when_disabled(self):
        """Workspace filtering is a no-op when MLFLOW_ENABLE_WORKSPACES is False."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_experiments

        mock_response = MagicMock()
        mock_response.json = {"experiments": []}

        mock_request_message = MagicMock()
        mock_request_message.view_type = 1
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        with app.test_request_context():
            proto_exp = MagicMock()
            proto_exp.experiment_id = "exp_1"

            mock_response_message = MagicMock()
            mock_response_message.experiments = [proto_exp]
            mock_response_message.next_page_token = ""

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=MagicMock(),
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchExperiments.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = False
                _filter_search_experiments(mock_response)

                # Experiment should remain since workspace filtering is disabled
                assert len(mock_response_message.experiments) == 1


# ---------------------------------------------------------------------------
# _filter_search_registered_models workspace filtering tests
# ---------------------------------------------------------------------------


class TestFilterSearchRegisteredModelsWorkspace:
    """Tests for workspace filtering in _filter_search_registered_models (WSSEC-02)."""

    def test_removes_models_from_inaccessible_workspaces(self):
        """Models from inaccessible workspaces are removed on initial page."""
        from mlflow_oidc_auth.hooks.after_request import (
            _filter_search_registered_models,
        )

        mock_response = MagicMock()
        mock_response.json = {"registered_models": []}

        mock_request_message = MagicMock()
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        model_registry_store = MagicMock()
        model_allowed = MagicMock()
        model_allowed.workspace = "allowed-ws"
        model_denied = MagicMock()
        model_denied.workspace = "denied-ws"

        model_registry_store.get_registered_model.side_effect = lambda name: (
            model_allowed if name == "model-ok" else model_denied
        )

        with app.test_request_context():
            rm1 = MagicMock()
            rm1.name = "model-ok"
            rm2 = MagicMock()
            rm2.name = "model-bad"

            mock_response_message = MagicMock()
            mock_response_message.registered_models = [rm1, rm2]
            mock_response_message.next_page_token = ""

            def can_access_ws(username, workspace):
                return workspace in ("allowed-ws", None, "")

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_registered_model",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_model_registry_store",
                    return_value=model_registry_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    side_effect=can_access_ws,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_registered_models(mock_response)

                assert len(mock_response_message.registered_models) == 1
                assert mock_response_message.registered_models[0].name == "model-ok"

    def test_keeps_models_from_accessible_workspaces(self):
        """Models from accessible workspaces are kept."""
        from mlflow_oidc_auth.hooks.after_request import (
            _filter_search_registered_models,
        )

        mock_response = MagicMock()
        mock_response.json = {"registered_models": []}

        mock_request_message = MagicMock()
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        model_registry_store = MagicMock()
        model_entity = MagicMock()
        model_entity.workspace = "allowed-ws"
        model_registry_store.get_registered_model.return_value = model_entity

        with app.test_request_context():
            rm1 = MagicMock()
            rm1.name = "model-1"
            rm2 = MagicMock()
            rm2.name = "model-2"

            mock_response_message = MagicMock()
            mock_response_message.registered_models = [rm1, rm2]
            mock_response_message.next_page_token = ""

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_registered_model",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_model_registry_store",
                    return_value=model_registry_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    return_value=True,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_registered_models(mock_response)

                assert len(mock_response_message.registered_models) == 2

    def test_refetch_path_applies_workspace_filtering(self):
        """Refetch path filters out models from inaccessible workspaces."""
        from mlflow_oidc_auth.hooks.after_request import (
            _filter_search_registered_models,
        )

        mock_response = MagicMock()
        mock_response.json = {"registered_models": []}

        mock_request_message = MagicMock()
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 10

        refetched_entities = []
        for i in range(10):
            rm = MagicMock()
            rm.name = f"model_{i}"
            rm.workspace = "allowed-ws" if i % 2 == 0 else "denied-ws"
            rm.to_proto.return_value = MagicMock(name=f"model_{i}")
            refetched_entities.append(rm)

        model_registry_store = MagicMock()
        model_registry_store.search_registered_models.side_effect = [
            _FakePagedList(refetched_entities, token=None),
            _FakePagedList([], token=None),
        ]

        with app.test_request_context():
            mock_response_message = MagicMock()
            mock_response_message.registered_models = []
            mock_response_message.next_page_token = "page_token_0"

            def can_access_ws(username, workspace):
                return workspace in ("allowed-ws", None, "")

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_registered_model",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_model_registry_store",
                    return_value=model_registry_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    side_effect=can_access_ws,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchUtils.parse_start_offset_from_page_token",
                    return_value=0,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchUtils.create_page_token",
                    return_value="page_token_10",
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_registered_models(mock_response)

                # Only 5 of 10 should pass
                assert len(mock_response_message.registered_models) == 5

    def test_admin_bypasses_workspace_filtering(self):
        """Admin users see all models regardless of workspace (WSSEC-06)."""
        from mlflow_oidc_auth.hooks.after_request import (
            _filter_search_registered_models,
        )

        mock_response = MagicMock()
        mock_response.json = {"registered_models": [{"name": "model-1"}]}

        with app.test_request_context():
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                return_value=True,
            ):
                original_json = mock_response.json.copy()
                _filter_search_registered_models(mock_response)
                assert mock_response.json == original_json

    def test_no_workspace_filtering_when_disabled(self):
        """Workspace filtering is a no-op when MLFLOW_ENABLE_WORKSPACES is False."""
        from mlflow_oidc_auth.hooks.after_request import (
            _filter_search_registered_models,
        )

        mock_response = MagicMock()
        mock_response.json = {"registered_models": []}

        mock_request_message = MagicMock()
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        with app.test_request_context():
            rm = MagicMock()
            rm.name = "model-1"

            mock_response_message = MagicMock()
            mock_response_message.registered_models = [rm]
            mock_response_message.next_page_token = ""

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_registered_model",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchRegisteredModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = False
                _filter_search_registered_models(mock_response)

                assert len(mock_response_message.registered_models) == 1


# ---------------------------------------------------------------------------
# _filter_search_logged_models workspace filtering tests
# ---------------------------------------------------------------------------


class TestFilterSearchLoggedModelsWorkspace:
    """Tests for workspace filtering in _filter_search_logged_models (WSSEC-03)."""

    def test_removes_logged_models_from_inaccessible_workspaces(self):
        """Logged models whose experiment is in inaccessible workspace are removed."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": []}

        mock_request_message = MagicMock()
        mock_request_message.experiment_ids = ["exp_1", "exp_2"]
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        exp_allowed = MagicMock()
        exp_allowed.workspace = "allowed-ws"
        exp_denied = MagicMock()
        exp_denied.workspace = "denied-ws"

        tracking_store = MagicMock()
        tracking_store.get_experiment.side_effect = lambda eid: (
            exp_allowed if eid == "exp_1" else exp_denied
        )
        tracking_store.search_logged_models.return_value = _FakePagedList(
            [], token=None
        )

        with app.test_request_context():
            m1 = MagicMock()
            m1.info.experiment_id = "exp_1"
            m2 = MagicMock()
            m2.info.experiment_id = "exp_2"

            mock_response_message = MagicMock()
            mock_response_message.models = [m1, m2]
            mock_response_message.next_page_token = ""

            def can_access_ws(username, workspace):
                return workspace in ("allowed-ws", None, "")

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=tracking_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    side_effect=can_access_ws,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_logged_models(mock_response)

                assert len(mock_response_message.models) == 1
                assert mock_response_message.models[0].info.experiment_id == "exp_1"

    def test_keeps_logged_models_from_accessible_workspaces(self):
        """Logged models whose experiment is in accessible workspace are kept."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": []}

        mock_request_message = MagicMock()
        mock_request_message.experiment_ids = ["exp_1"]
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        exp_entity = MagicMock()
        exp_entity.workspace = "allowed-ws"
        tracking_store = MagicMock()
        tracking_store.get_experiment.return_value = exp_entity
        tracking_store.search_logged_models.return_value = _FakePagedList(
            [], token=None
        )

        with app.test_request_context():
            m1 = MagicMock()
            m1.info.experiment_id = "exp_1"

            mock_response_message = MagicMock()
            mock_response_message.models = [m1]
            mock_response_message.next_page_token = ""

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=tracking_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    return_value=True,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_logged_models(mock_response)

                assert len(mock_response_message.models) == 1

    def test_refetch_path_applies_workspace_filtering(self):
        """Refetch path filters logged models by experiment workspace."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": []}

        mock_request_message = MagicMock()
        mock_request_message.experiment_ids = ["exp_1", "exp_2"]
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 10

        # Build refetched batch
        batch_models = []
        for i in range(10):
            model = MagicMock()
            model.experiment_id = "exp_1" if i % 2 == 0 else "exp_2"
            model.to_proto.return_value = MagicMock()
            batch_models.append(model)

        exp_allowed = MagicMock()
        exp_allowed.workspace = "allowed-ws"
        exp_denied = MagicMock()
        exp_denied.workspace = "denied-ws"

        tracking_store = MagicMock()
        tracking_store.get_experiment.side_effect = lambda eid: (
            exp_allowed if eid == "exp_1" else exp_denied
        )
        tracking_store.search_logged_models.return_value = _FakePagedList(
            batch_models, token=None
        )

        mock_token_class = MagicMock()
        mock_token_class.decode.return_value = MagicMock(offset=0)
        mock_token_class.return_value.encode.return_value = "encoded_token"

        with app.test_request_context():
            mock_response_message = MagicMock()
            mock_response_message.models = []
            mock_response_message.next_page_token = "token123"

            def can_access_ws(username, workspace):
                return workspace in ("allowed-ws", None, "")

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=tracking_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
                patch(
                    "mlflow_oidc_auth.hooks.after_request._can_access_workspace",
                    side_effect=can_access_ws,
                ),
                patch(
                    "mlflow.utils.search_utils.SearchLoggedModelsPaginationToken",
                    mock_token_class,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_logged_models(mock_response)

                # Only 5 of 10 should pass (even-indexed with exp_1/allowed-ws)
                assert len(mock_response_message.models) == 5

    def test_admin_bypasses_workspace_filtering(self):
        """Admin users see all logged models regardless of workspace (WSSEC-06)."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": [{"experiment_id": "123"}]}

        with app.test_request_context():
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                return_value=True,
            ):
                original_json = mock_response.json.copy()
                _filter_search_logged_models(mock_response)
                assert mock_response.json == original_json

    def test_no_workspace_filtering_when_disabled(self):
        """Workspace filtering is a no-op when MLFLOW_ENABLE_WORKSPACES is False."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": []}

        mock_request_message = MagicMock()
        mock_request_message.experiment_ids = ["exp_1"]
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        tracking_store = MagicMock()
        tracking_store.search_logged_models.return_value = _FakePagedList(
            [], token=None
        )

        with app.test_request_context():
            m = MagicMock()
            m.info.experiment_id = "exp_1"

            mock_response_message = MagicMock()
            mock_response_message.models = [m]
            mock_response_message.next_page_token = ""

            with (
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status",
                    return_value=False,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.get_fastapi_username",
                    return_value="user1",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.can_read_experiment",
                    return_value=True,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_request_message",
                    return_value=mock_request_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.parse_dict"),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.message_to_json",
                    return_value="{}",
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request._get_tracking_store",
                    return_value=tracking_store,
                ),
                patch(
                    "mlflow_oidc_auth.hooks.after_request.SearchLoggedModels.Response",
                    return_value=mock_response_message,
                ),
                patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config,
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = False
                _filter_search_logged_models(mock_response)

                assert len(mock_response_message.models) == 1


# ---------------------------------------------------------------------------
# Cross-cutting workspace filtering tests
# ---------------------------------------------------------------------------


class TestWorkspaceFilteringCrossCutting:
    """Cross-cutting tests for workspace filtering across all three search handlers."""

    def test_pre_workspace_resources_visible_in_experiments(self):
        """Pre-workspace-era experiments (workspace=None) visible to authorized users (WSSEC-05)."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            assert _can_access_workspace("user1", None) is True
            assert _can_access_workspace("user1", "") is True

    def test_default_workspace_resources_visible_when_user_has_read_permission(self):
        """Default workspace resources visible when user has readable permission — no special-casing (WSSEC-04)."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace
        from mlflow_oidc_auth.permissions import READ

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            with patch(
                "mlflow_oidc_auth.hooks.after_request.get_workspace_permission_cached",
                return_value=READ,
            ):
                assert _can_access_workspace("user1", "default") is True
