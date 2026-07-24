"""Tests for RESTRICT_RESOURCE_CREATION authorization on experiment/model creation (#247, #202)."""

from unittest.mock import patch

import pytest

from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import EDIT, MANAGE, NO_PERMISSIONS, READ


class TestCreateValidatorsAreNoOpWhenDisabled:
    """With RESTRICT_RESOURCE_CREATION off, creation validators must allow everyone (upstream default)."""

    def test_experiment_allowed_when_flag_off(self):
        from mlflow_oidc_auth.validators.experiment import validate_can_create_experiment

        with patch("mlflow_oidc_auth.validators.experiment.config") as cfg:
            cfg.RESTRICT_RESOURCE_CREATION = False
            with patch("mlflow_oidc_auth.validators.experiment.effective_new_experiment_permission") as resolver:
                assert validate_can_create_experiment("anyone") is True
                resolver.assert_not_called()

    def test_registered_model_allowed_when_flag_off(self):
        from mlflow_oidc_auth.validators.registered_model import validate_can_create_registered_model

        with patch("mlflow_oidc_auth.validators.registered_model.config") as cfg:
            cfg.RESTRICT_RESOURCE_CREATION = False
            with patch("mlflow_oidc_auth.validators.registered_model.effective_new_registered_model_permission") as resolver:
                assert validate_can_create_registered_model("anyone") is True
                resolver.assert_not_called()


class TestCreateValidatorsWhenEnabled:
    """With the flag on, creation requires EDIT+ on the new resource name."""

    @pytest.mark.parametrize("perm,expected", [(EDIT, True), (MANAGE, True), (READ, False), (NO_PERMISSIONS, False)])
    def test_experiment_requires_edit(self, perm, expected):
        from mlflow_oidc_auth.validators.experiment import validate_can_create_experiment

        with patch("mlflow_oidc_auth.validators.experiment.config") as cfg:
            cfg.RESTRICT_RESOURCE_CREATION = True
            with patch("mlflow_oidc_auth.validators.experiment.get_request_param", return_value="proj-exp"):
                with patch(
                    "mlflow_oidc_auth.validators.experiment.effective_new_experiment_permission",
                    return_value=PermissionResult(perm, "regex"),
                ) as resolver:
                    assert validate_can_create_experiment("alice") is expected
                    resolver.assert_called_once_with("proj-exp", "alice")

    @pytest.mark.parametrize("perm,expected", [(EDIT, True), (MANAGE, True), (READ, False), (NO_PERMISSIONS, False)])
    def test_registered_model_requires_edit(self, perm, expected):
        from mlflow_oidc_auth.validators.registered_model import validate_can_create_registered_model

        with patch("mlflow_oidc_auth.validators.registered_model.config") as cfg:
            cfg.RESTRICT_RESOURCE_CREATION = True
            with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="proj-model"):
                with patch(
                    "mlflow_oidc_auth.validators.registered_model.effective_new_registered_model_permission",
                    return_value=PermissionResult(perm, "regex"),
                ) as resolver:
                    assert validate_can_create_registered_model("alice") is expected
                    resolver.assert_called_once_with("proj-model", "alice")


class TestEffectiveNewPermissionWorkspaceFallback:
    """A regex miss falls back to workspace permission (on) or the global default (off)."""

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_workspaces_off_uses_default_fallback(self, mock_resolver):
        from mlflow_oidc_auth.utils.permissions import effective_new_experiment_permission

        # A "fallback" result means regex/group-regex found nothing; with workspaces off it stands.
        mock_resolver.return_value = PermissionResult(MANAGE, "fallback")
        with patch("mlflow_oidc_auth.utils.permissions.config") as cfg:
            cfg.MLFLOW_ENABLE_WORKSPACES = False
            result = effective_new_experiment_permission("new-exp", "user1")
        assert result.kind == "fallback"
        assert result.permission == MANAGE

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_regex_hit_is_not_overridden_by_workspace(self, mock_resolver):
        from mlflow_oidc_auth.utils.permissions import effective_new_experiment_permission

        # A concrete regex match (kind != "fallback") must survive even with workspaces on.
        mock_resolver.return_value = PermissionResult(EDIT, "regex")
        with patch("mlflow_oidc_auth.utils.permissions.config") as cfg:
            cfg.MLFLOW_ENABLE_WORKSPACES = True
            with patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value="team-ws"):
                result = effective_new_experiment_permission("new-exp", "user1")
        assert result.kind == "regex"
        assert result.permission == EDIT

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_regex_miss_uses_workspace_permission(self, mock_resolver):
        from mlflow_oidc_auth.utils.permissions import effective_new_registered_model_permission

        mock_resolver.return_value = PermissionResult(READ, "fallback")
        with patch("mlflow_oidc_auth.utils.permissions.config") as cfg:
            cfg.MLFLOW_ENABLE_WORKSPACES = True
            with patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value="team-ws"):
                with patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=EDIT):
                    result = effective_new_registered_model_permission("new-model", "user1")
        assert result.kind == "workspace"
        assert result.permission == EDIT

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_regex_miss_no_workspace_perm_denies(self, mock_resolver):
        from mlflow_oidc_auth.utils.permissions import effective_new_experiment_permission

        mock_resolver.return_value = PermissionResult(READ, "fallback")
        with patch("mlflow_oidc_auth.utils.permissions.config") as cfg:
            cfg.MLFLOW_ENABLE_WORKSPACES = True
            with patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value="team-ws"):
                with patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=None):
                    result = effective_new_experiment_permission("new-exp", "user1")
        assert result.kind == "workspace-deny"
        assert result.permission == NO_PERMISSIONS

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_header_less_request_keeps_default(self, mock_resolver):
        from mlflow_oidc_auth.utils.permissions import effective_new_experiment_permission

        # No workspace header: MLflow resolves to default; the global default fallback applies.
        mock_resolver.return_value = PermissionResult(MANAGE, "fallback")
        with patch("mlflow_oidc_auth.utils.permissions.config") as cfg:
            cfg.MLFLOW_ENABLE_WORKSPACES = True
            with patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value=None):
                result = effective_new_experiment_permission("new-exp", "user1")
        assert result.kind == "fallback"
        assert result.permission == MANAGE


class TestCreateHandlersBound:
    """CreateExperiment/CreateRegisteredModel must be wired into the before-request handlers (#202)."""

    def test_create_experiment_handler_bound(self):
        from mlflow.protos.service_pb2 import CreateExperiment

        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS
        from mlflow_oidc_auth.validators import validate_can_create_experiment

        assert BEFORE_REQUEST_HANDLERS.get(CreateExperiment) is validate_can_create_experiment

    def test_create_registered_model_handler_bound(self):
        from mlflow.protos.model_registry_pb2 import CreateRegisteredModel

        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS
        from mlflow_oidc_auth.validators import validate_can_create_registered_model

        assert BEFORE_REQUEST_HANDLERS.get(CreateRegisteredModel) is validate_can_create_registered_model
