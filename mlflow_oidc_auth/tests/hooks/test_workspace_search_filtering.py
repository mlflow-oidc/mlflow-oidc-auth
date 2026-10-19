"""Tests for workspace-scoped search filtering in after_request hooks.

Tests _can_access_workspace helper and workspace filtering in:
- _filter_search_experiments (WSSEC-01)
- _filter_search_registered_models (WSSEC-02)
- _filter_search_logged_models (WSSEC-03)
"""

from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock, patch

from flask import Flask

app = Flask(__name__)
app.config["TESTING"] = True


class _FakePagedList(list):
    """Lightweight stand-in for MLflow's PagedList in unit tests."""

    def __init__(self, items, token=None):
        super().__init__(items)
        self.token = token

    def __eq__(self, other):
        if isinstance(other, _FakePagedList):
            return list.__eq__(self, other) and self.token == other.token
        return list.__eq__(self, other)


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
                "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                return_value=READ,
            ):
                assert _can_access_workspace("user1", "team-alpha") is True

    def test_returns_false_when_user_has_no_permission(self):
        """_can_access_workspace returns False when user has no workspace permission."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            with patch(
                "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
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
                "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                return_value=NO_PERMISSIONS,
            ):
                assert _can_access_workspace("user1", "some-ws") is False

    def test_default_workspace_treated_like_any_other(self):
        """_can_access_workspace treats 'default' workspace the same as any other — no implicit grant."""
        from mlflow_oidc_auth.hooks.after_request import _can_access_workspace

        with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
            mock_config.MLFLOW_ENABLE_WORKSPACES = True
            with patch(
                "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                return_value=None,
            ):
                assert _can_access_workspace("user1", "default") is False


# ---------------------------------------------------------------------------
# _filter_search_experiments workspace filtering tests
# ---------------------------------------------------------------------------


class TestFilterSearchExperimentsWorkspace:
    """Tests for workspace filtering in _filter_search_experiments (WSSEC-01)."""

    def test_removes_experiments_from_inaccessible_workspaces(self):
        """An experiment search in an inaccessible workspace returns nothing (issue #456).

        MLflow scopes the search to the request's workspace, so one check on that workspace
        covers every row; no per-row ``get_experiment`` and no per-row workspace field.
        """
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

        tracking_store.get_experiment.side_effect = lambda eid: (exp_accessible if eid == "exp_1" else exp_inaccessible)

        with app.test_request_context():
            # Proto experiments (from initial page)
            # Initial-page protos carry their own workspace (issue #456: no per-row get_experiment).
            proto_exp1 = MagicMock()
            proto_exp1.experiment_id = "exp_1"
            proto_exp1.HasField.return_value = True
            proto_exp1.workspace = "allowed-ws"
            proto_exp2 = MagicMock()
            proto_exp2.experiment_id = "exp_2"
            proto_exp2.HasField.return_value = True
            proto_exp2.workspace = "denied-ws"

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
                ) as mock_access,
                patch(
                    "mlflow_oidc_auth.hooks.after_request.resolve_entity_workspace_name",
                    return_value="denied-ws",
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_experiments(mock_response)

                assert len(mock_response_message.experiments) == 0
                assert mock_response_message.next_page_token == ""
                mock_access.assert_called_once_with("user1", "denied-ws")
                tracking_store.get_experiment.assert_not_called()
                tracking_store.search_experiments.assert_not_called()

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

        tracking_store.get_experiment.side_effect = lambda eid: (exp1 if eid == "exp_1" else exp2)

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
        """The top-up path is covered by the one search-scope check (issue #456).

        Every refetched row lives in the workspace the search was scoped to; no row's own
        ``workspace`` attribute is consulted.
        """
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
            e.workspace = "allowed-ws"
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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
                ) as mock_access,
                patch(
                    "mlflow_oidc_auth.hooks.after_request.resolve_entity_workspace_name",
                    return_value="allowed-ws",
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

                assert len(experiments_list) == 10
                assert {c.args for c in mock_access.call_args_list} == {("user1", "allowed-ws")}

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
        """Models from an inaccessible workspace are removed on the initial page.

        MLflow scopes a registry search to the request's workspace and the registered-model
        proto has no ``workspace`` field, so the page's workspace is the search scope
        (issue #456) rather than a per-row ``get_registered_model`` lookup.
        """
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
                    "mlflow_oidc_auth.hooks.after_request._can_read_registered_model",
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
                ) as mock_access,
                patch(
                    "mlflow_oidc_auth.hooks.after_request.resolve_entity_workspace_name",
                    return_value="denied-ws",
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_registered_models(mock_response)

                assert len(mock_response_message.registered_models) == 0
                mock_access.assert_called_with("user1", "denied-ws")
                model_registry_store.get_registered_model.assert_not_called()

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_registered_model",
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
        """The top-up path is covered by the one search-scope check (issue #456).

        MLflow scopes the registry search to the request's workspace, so every refetched row
        lives there; no row's own ``workspace`` attribute is consulted.
        """
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
            rm.workspace = "allowed-ws"
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
                    "mlflow_oidc_auth.hooks.after_request._can_read_registered_model",
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
                ) as mock_access,
                patch(
                    "mlflow_oidc_auth.hooks.after_request.resolve_entity_workspace_name",
                    return_value="allowed-ws",
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

                assert len(mock_response_message.registered_models) == 10
                assert {c.args for c in mock_access.call_args_list} == {("user1", "allowed-ws")}

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_registered_model",
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
        """A logged-model search in an inaccessible workspace returns nothing (issue #456).

        MLflow scopes the search to the experiments of the request's workspace, so one check
        on that workspace covers every row; no per-experiment ``get_experiment`` lookup.
        """
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": [{"info": {"experiment_id": "exp_1"}}, {"info": {"experiment_id": "exp_2"}}]}

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
        tracking_store.get_experiment.side_effect = lambda eid: (exp_allowed if eid == "exp_1" else exp_denied)
        tracking_store.search_logged_models.return_value = _FakePagedList([], token=None)

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
                    "mlflow_oidc_auth.hooks.after_request.resolve_entity_workspace_name",
                    return_value="denied-ws",
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_logged_models(mock_response)

                assert len(mock_response_message.models) == 0
                assert mock_response_message.next_page_token == ""
                tracking_store.get_experiment.assert_not_called()
                tracking_store.search_logged_models.assert_not_called()

    def test_keeps_logged_models_from_accessible_workspaces(self):
        """Logged models whose experiment is in accessible workspace are kept."""
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": [{"info": {"experiment_id": "exp_1"}}], "next_page_token": "token123"}

        mock_request_message = MagicMock()
        mock_request_message.experiment_ids = ["exp_1"]
        mock_request_message.filter = None
        mock_request_message.order_by = []
        mock_request_message.max_results = 1000

        exp_entity = MagicMock()
        exp_entity.workspace = "allowed-ws"
        tracking_store = MagicMock()
        tracking_store.get_experiment.return_value = exp_entity
        tracking_store.search_logged_models.return_value = _FakePagedList([], token=None)

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
        """The top-up path needs no per-experiment workspace lookup (issue #456).

        With the search's workspace readable, every refetched row is kept on its read
        permission alone; ``get_experiment`` is never called.
        """
        from mlflow_oidc_auth.hooks.after_request import _filter_search_logged_models

        mock_response = MagicMock()
        mock_response.json = {"models": [], "next_page_token": "token123"}

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
        tracking_store.get_experiment.side_effect = lambda eid: (exp_allowed if eid == "exp_1" else exp_denied)
        tracking_store.search_logged_models.return_value = _FakePagedList(batch_models, token=None)

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
                    "mlflow_oidc_auth.hooks.after_request.resolve_entity_workspace_name",
                    return_value="allowed-ws",
                ),
                patch(
                    "mlflow.utils.search_utils.SearchLoggedModelsPaginationToken",
                    mock_token_class,
                ),
            ):
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_search_logged_models(mock_response)

                assert len(mock_response_message.models) == 10
                tracking_store.get_experiment.assert_not_called()

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
        tracking_store.search_logged_models.return_value = _FakePagedList([], token=None)

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
                    "mlflow_oidc_auth.hooks.after_request._can_read_experiment",
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
                "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                return_value=READ,
            ):
                assert _can_access_workspace("user1", "default") is True


class TestWorkspaceMemoLifetime:
    """The workspace memo's safety argument is that its lifetime is ONE request.

    Nothing else in the suite executes the memoizing branch, so without these a refactor
    that moved the memo to module scope — turning it into an uninvalidated cross-request
    authorization cache — would keep CI green.
    """

    def _app(self):
        from flask import Flask

        app = Flask(__name__)
        app.secret_key = "test"
        return app

    def test_repeat_checks_in_one_request_hit_the_memo(self, monkeypatch):
        """A DENY is memoized: get_workspace_permission_cached never caches denials."""
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks import after_request as ar

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        calls = []
        monkeypatch.setattr("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", lambda u, w: calls.append((u, w)))

        with self._app().test_request_context("/"):
            assert ar._can_access_workspace("bob", "ws1") is False
            assert ar._can_access_workspace("bob", "ws1") is False

        assert len(calls) == 1, f"deny not memoized within one request: {calls}"

    def test_memo_does_not_survive_into_the_next_request(self, monkeypatch):
        """The bounded lifetime is the whole safety argument — pin it."""
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks import after_request as ar

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        calls = []
        monkeypatch.setattr("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", lambda u, w: calls.append((u, w)))

        app = self._app()
        for _ in range(2):
            with app.test_request_context("/"):
                ar._can_access_workspace("bob", "ws1")

        assert len(calls) == 2, "memo leaked across requests — it must not outlive one request"

    def test_distinct_users_are_not_conflated(self, monkeypatch):
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks import after_request as ar

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        seen = []

        def _perm(username, workspace):
            seen.append(username)
            return SimpleNamespace(can_read=(username == "allowed"))

        monkeypatch.setattr("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", _perm)

        with self._app().test_request_context("/"):
            assert ar._can_access_workspace("allowed", "ws1") is True
            assert ar._can_access_workspace("denied", "ws1") is False

        assert seen == ["allowed", "denied"], "memo key must include the username"


# ---------------------------------------------------------------------------
# First-page workspace source (issue #456): the row's own workspace, no per-row lookup
# ---------------------------------------------------------------------------


class TestFirstPageWorkspaceWithoutLookups:
    """Real protos, real MLflow workspace context, a store with no get_experiment/get_registered_model.

    Any per-row lookup would raise AttributeError on this store; the filter must not need one.
    The request's workspace is the one the search was scoped to, so a denial on it must empty
    the page — including model versions, whose proto carries no workspace field.
    """

    @staticmethod
    def _rows(kind):
        from mlflow_oidc_auth.tests.search_paging_helpers import make_experiments, make_model_versions, make_registered_models

        return {"experiments": make_experiments, "registered_models": make_registered_models, "model_versions": make_model_versions}[kind](30)

    @pytest.mark.parametrize("kind", ["experiments", "registered_models", "model_versions"])
    def test_denied_workspace_empties_the_page(self, kind):
        from mlflow.utils.workspace_context import WorkspaceContext

        from mlflow_oidc_auth.tests.search_paging_helpers import FakeSearchStore, run_filtered_page

        checked = []

        def can_access(username, workspace):
            checked.append(workspace)
            return workspace != "ws-a"

        with WorkspaceContext("ws-a"):
            store = FakeSearchStore(self._rows(kind))
            ids, token = run_filtered_page(kind, store, lambda rid: True, max_results=10, page_token=None, can_access_workspace=can_access)

        assert ids == [], "rows from a denied workspace were returned"
        assert token == ""
        assert checked and set(checked) == {"ws-a"}
        # One scope check covers the top-up half too: nothing more is fetched (issue #456).
        assert store.calls == 1, "top-up pages were fetched for a denied workspace"

    def test_model_version_rows_without_workspace_are_not_waved_through(self):
        """A top-up row missing ``workspace`` is judged by the search scope, never treated as pre-workspace."""
        from mlflow.utils.workspace_context import WorkspaceContext

        from mlflow_oidc_auth.tests.search_paging_helpers import FakeSearchStore, run_filtered_page

        class _NoWorkspaceVersion:
            def __init__(self, i):
                self.name = f"model-{i}"

            def to_proto(self):
                from mlflow.protos.model_registry_pb2 import ModelVersion as ModelVersionProto

                return ModelVersionProto(name=self.name, version="1")

        rows = [_NoWorkspaceVersion(i) for i in range(30)]
        # The first page is all unreadable, so every visible row would have to come from top-up.
        readable = {f"model-{i}" for i in range(10, 30)}

        with WorkspaceContext("ws-a"):
            denied_store = FakeSearchStore(rows)
            ids, token = run_filtered_page(
                "model_versions", denied_store, lambda rid: rid in readable, max_results=10, page_token=None, can_access_workspace=lambda u, w: False
            )
            assert ids == [] and token == ""

            allowed_store = FakeSearchStore(rows)
            ids, _ = run_filtered_page(
                "model_versions", allowed_store, lambda rid: rid in readable, max_results=10, page_token=None, can_access_workspace=lambda u, w: w == "ws-a"
            )
            assert ids == [f"model-{i}" for i in range(10, 20)]

    @pytest.mark.parametrize("kind", ["experiments", "registered_models", "model_versions"])
    def test_allowed_workspace_keeps_the_page(self, kind):
        from mlflow.utils.workspace_context import WorkspaceContext

        from mlflow_oidc_auth.tests.search_paging_helpers import FakeSearchStore, row_id, run_filtered_page

        with WorkspaceContext("ws-a"):
            rows = self._rows(kind)
            store = FakeSearchStore(rows)
            ids, token = run_filtered_page(kind, store, lambda rid: True, max_results=10, page_token=None, can_access_workspace=lambda u, w: w == "ws-a")

        assert ids == [row_id(kind, r) for r in rows[:10]]
        assert token != ""
