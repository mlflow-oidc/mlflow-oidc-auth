"""RESTRICT_RESOURCE_CREATION must not silently do nothing (#293).

The creation validators require EDIT+ on the resource NAME, resolved from regex rules with
a workspace fallback. With workspaces off and no regex match, that lands on
DEFAULT_MLFLOW_PERMISSION — which ships as MANAGE, and MANAGE grants create rights. So the
flag denies nothing on a default install while reading as though it locked things down.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth import config as config_module


def _warn_for(default_permission, restrict, workspaces):
    """Run the check in isolation against a stub config, returning the warning or None."""
    stub = MagicMock()
    stub.RESTRICT_RESOURCE_CREATION = restrict
    stub.MLFLOW_ENABLE_WORKSPACES = workspaces
    stub.DEFAULT_MLFLOW_PERMISSION = default_permission

    with patch.object(config_module, "logger") as logger:
        config_module.AppConfig._warn_if_resource_creation_restriction_is_inert(stub)

    return logger.warning.call_args.args[0] if logger.warning.called else None


class TestInertCombinationWarns:
    @pytest.mark.parametrize("default_permission", ["MANAGE", "EDIT"])
    def test_permissive_default_without_workspaces_warns(self, default_permission):
        """These grant can_update, so a name matching no regex is still creatable."""
        warning = _warn_for(default_permission, restrict=True, workspaces=False)

        assert warning is not None, f"{default_permission} grants create rights; the flag is inert"
        assert "RESTRICT_RESOURCE_CREATION is enabled but has no effect" in warning
        assert default_permission in warning

    def test_the_shipped_default_is_the_case_that_warns(self):
        """Guards the premise: if MANAGE ever stops granting create, this test should fail."""
        from mlflow_oidc_auth.permissions import get_permission

        assert get_permission("MANAGE").can_update is True


class TestEffectiveCombinationsAreSilent:
    @pytest.mark.parametrize("default_permission", ["NO_PERMISSIONS", "READ"])
    def test_a_default_below_edit_is_effective(self, default_permission):
        """Only regex or group-regex matches can create, which is the intended setup."""
        assert _warn_for(default_permission, restrict=True, workspaces=False) is None

    def test_workspaces_enabled_is_effective(self):
        """The workspace creation gate does the enforcing; the global default is bypassed."""
        assert _warn_for("MANAGE", restrict=True, workspaces=True) is None

    def test_the_flag_being_off_is_not_worth_warning_about(self):
        assert _warn_for("MANAGE", restrict=False, workspaces=False) is None

    def test_an_unparseable_default_is_reported_elsewhere(self):
        assert _warn_for("NOT_A_PERMISSION", restrict=True, workspaces=False) is None


def test_the_check_runs_during_config_construction():
    """Wiring: the warning is useless if nothing calls it."""
    with patch.object(config_module.AppConfig, "_warn_if_resource_creation_restriction_is_inert") as check:
        config_module.AppConfig()

    check.assert_called_once()


class TestPermissiveDefaultAnnouncement:
    """An open-by-default deployment must be told the default is changing (#293)."""

    @staticmethod
    def _warn_for(default_permission, workspaces):
        stub = MagicMock()
        stub.MLFLOW_ENABLE_WORKSPACES = workspaces
        stub.DEFAULT_MLFLOW_PERMISSION = default_permission

        with patch.object(config_module, "logger") as logger:
            config_module.AppConfig._warn_if_default_permission_is_permissive(stub)

        return logger.warning.call_args.args[0] if logger.warning.called else None

    @pytest.mark.parametrize("default_permission", ["MANAGE", "EDIT", "READ"])
    def test_a_granting_default_is_announced(self, default_permission):
        warning = self._warn_for(default_permission, workspaces=False)

        assert warning is not None
        assert "becomes NO_PERMISSIONS in the next major version" in warning
        assert "docs/permissions.md" in warning, "the warning must point at the migration"

    def test_a_denying_default_is_already_migrated(self):
        assert self._warn_for("NO_PERMISSIONS", workspaces=False) is None

    def test_workspace_deployments_are_unaffected(self):
        """With workspaces, workspace permissions take the fallback role entirely."""
        assert self._warn_for("MANAGE", workspaces=True) is None

    def test_an_unparseable_default_is_reported_elsewhere(self):
        assert self._warn_for("NOT_A_PERMISSION", workspaces=False) is None

    def test_the_announcement_runs_during_config_construction(self):
        with patch.object(config_module.AppConfig, "_warn_if_default_permission_is_permissive") as check:
            config_module.AppConfig()

        check.assert_called_once()
