"""OIDC_WORKSPACE_CREATION_PERMISSION: the workspace permission needed for workspace-gated creates."""

import os
from unittest.mock import patch

import pytest

from mlflow_oidc_auth.config import AppConfig
from mlflow_oidc_auth.permissions import EDIT, MANAGE, NO_PERMISSIONS, READ, USE, meets_workspace_creation_threshold


class TestThreshold:
    @pytest.mark.parametrize("permission,allowed", [(MANAGE, True), (EDIT, False), (USE, False), (READ, False), (NO_PERMISSIONS, False), (None, False)])
    def test_manage_threshold_requires_manage(self, permission, allowed):
        assert meets_workspace_creation_threshold(permission, "MANAGE") is allowed

    @pytest.mark.parametrize("permission,allowed", [(MANAGE, True), (EDIT, True), (USE, False), (READ, False), (NO_PERMISSIONS, False), (None, False)])
    def test_edit_threshold_admits_edit_and_manage(self, permission, allowed):
        assert meets_workspace_creation_threshold(permission, "EDIT") is allowed

    @pytest.mark.parametrize("threshold", ["READ", "edit", "", None, object()])
    def test_anything_but_exactly_edit_requires_manage(self, threshold):
        assert meets_workspace_creation_threshold(EDIT, threshold) is False
        assert meets_workspace_creation_threshold(MANAGE, threshold) is True


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
