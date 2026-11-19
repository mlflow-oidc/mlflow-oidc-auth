"""OIDC_WORKSPACE_CREATION_PERMISSION: the workspace permission needed for workspace-gated creates."""

import os
from unittest.mock import patch

import pytest

from mlflow_oidc_auth.config import AppConfig
from mlflow_oidc_auth.permissions import EDIT, MANAGE, NO_PERMISSIONS, READ, USE, meets_workspace_creation_threshold, workspace_creation_requirement


class TestThreshold:
    @pytest.mark.parametrize("permission,allowed", [(MANAGE, True), (EDIT, False), (USE, False), (READ, False), (NO_PERMISSIONS, False), (None, False)])
    def test_manage_threshold_requires_manage(self, permission, allowed):
        assert meets_workspace_creation_threshold(permission, "MANAGE") is allowed

    @pytest.mark.parametrize("permission,allowed", [(MANAGE, True), (EDIT, True), (USE, False), (READ, False), (NO_PERMISSIONS, False), (None, False)])
    def test_edit_threshold_admits_edit_and_manage(self, permission, allowed):
        assert meets_workspace_creation_threshold(permission, "EDIT") is allowed

    @pytest.mark.parametrize("threshold", ["READ", "USE", "NO_PERMISSIONS", "EDITOR", "", None, object()])
    def test_anything_but_edit_requires_manage(self, threshold):
        assert workspace_creation_requirement(threshold) is MANAGE
        assert meets_workspace_creation_threshold(EDIT, threshold) is False
        assert meets_workspace_creation_threshold(NO_PERMISSIONS, threshold) is False
        assert meets_workspace_creation_threshold(MANAGE, threshold) is True

    @pytest.mark.parametrize("threshold", ["EDIT", "edit", " Edit "])
    def test_edit_in_any_spelling_is_the_same_rule_as_the_config(self, threshold):
        """The helper and the config agree: what the config normalises to EDIT, the helper reads as EDIT."""
        assert workspace_creation_requirement(threshold) is EDIT
        assert meets_workspace_creation_threshold(EDIT, threshold) is True
        assert meets_workspace_creation_threshold(USE, threshold) is False

    def test_no_permissions_never_meets_a_threshold_despite_its_priority(self):
        assert NO_PERMISSIONS.priority > MANAGE.priority
        for threshold in ("EDIT", "MANAGE"):
            assert meets_workspace_creation_threshold(NO_PERMISSIONS, threshold) is False


class TestConfig:
    def test_default_is_manage(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OIDC_WORKSPACE_CREATION_PERMISSION", None)
            assert AppConfig().OIDC_WORKSPACE_CREATION_PERMISSION == "MANAGE"

    @pytest.mark.parametrize("value,expected", [("EDIT", "EDIT"), (" edit ", "EDIT"), ("MANAGE", "MANAGE"), ("manage", "MANAGE")])
    def test_recognised_values_are_normalised(self, value, expected):
        with patch.dict(os.environ, {"OIDC_WORKSPACE_CREATION_PERMISSION": value}):
            assert AppConfig().OIDC_WORKSPACE_CREATION_PERMISSION == expected

    @pytest.mark.parametrize("value", ["READ", "USE", "NO_PERMISSIONS", "EDITOR", ""])
    def test_unrecognised_values_fail_closed_to_manage(self, value):
        with patch.dict(os.environ, {"OIDC_WORKSPACE_CREATION_PERMISSION": value}):
            assert AppConfig().OIDC_WORKSPACE_CREATION_PERMISSION == "MANAGE"

    def test_the_warning_never_echoes_the_rejected_value(self):
        """Configuration can come from a secret provider: a mistaken value is never logged."""
        with patch.dict(os.environ, {"OIDC_WORKSPACE_CREATION_PERMISSION": "edtt"}), patch("mlflow_oidc_auth.config.logger") as logger:
            AppConfig()
        calls = [call for call in logger.warning.call_args_list if "OIDC_WORKSPACE_CREATION_PERMISSION" in str(call.args[0])]
        assert calls
        assert not any("edtt" in str(call) for call in calls)


class TestStartupWarning:
    def test_edit_warns_that_every_edit_grant_creates(self):
        env = {"OIDC_WORKSPACE_CREATION_PERMISSION": "EDIT", "MLFLOW_ENABLE_WORKSPACES": "true"}
        with patch.dict(os.environ, env), patch("mlflow_oidc_auth.config.logger") as logger:
            AppConfig()
        messages = " ".join(str(call.args[0]) for call in logger.warning.call_args_list)
        assert "OIDC_WORKSPACE_CREATION_PERMISSION=EDIT" in messages
        assert "WORKSPACE_RULES_MAX_PERMISSION" in messages

    def test_manage_does_not_warn(self):
        with patch.dict(os.environ, {"OIDC_WORKSPACE_CREATION_PERMISSION": "MANAGE"}), patch("mlflow_oidc_auth.config.logger") as logger:
            AppConfig()
        assert not any("OIDC_WORKSPACE_CREATION_PERMISSION" in str(call.args[0]) for call in logger.warning.call_args_list)

    def test_edit_does_not_warn_without_workspaces(self):
        """The setting is inert with workspaces off, so there is nothing to warn about."""
        env = {"OIDC_WORKSPACE_CREATION_PERMISSION": "EDIT", "MLFLOW_ENABLE_WORKSPACES": "false"}
        with patch.dict(os.environ, env), patch("mlflow_oidc_auth.config.logger") as logger:
            AppConfig()
        assert not any("OIDC_WORKSPACE_CREATION_PERMISSION=EDIT" in str(call.args[0]) for call in logger.warning.call_args_list)


class TestGateUsesTheNormalisedValue:
    @pytest.mark.parametrize("raw,edit_allowed", [("EDIT", True), (" edit ", True), ("READ", False), ("EDITOR", False), ("", False)])
    def test_a_configured_value_reaches_the_registry_gate_normalised(self, raw, edit_allowed):
        """The real config feeds the real gate: only EDIT, however spelled, admits an EDIT grant."""
        from mlflow_oidc_auth.middleware import registry_support

        with patch.dict(os.environ, {"OIDC_WORKSPACE_CREATION_PERMISSION": raw}):
            real = AppConfig()
        with (
            patch.object(registry_support, "config", real),
            patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value="team-ws"),
            patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=EDIT),
        ):
            real.OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT = False
            real.OIDC_WORKSPACE_DENY_DEFAULT_CREATION = False
            assert registry_support.can_create_in_request_workspace("bob") is edit_allowed
