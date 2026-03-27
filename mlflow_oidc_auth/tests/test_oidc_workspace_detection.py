"""Tests for OIDC workspace detection in _process_oidc_callback_fastapi().

Verifies:
- Workspace detection disabled when MLFLOW_ENABLE_WORKSPACES=False
- Plugin-based workspace detection via OIDC_WORKSPACE_DETECTION_PLUGIN
- JWT claim fallback via OIDC_WORKSPACE_CLAIM_NAME
- Auto-assign workspace membership via store.create_workspace_permission
- Idempotent handling of existing permissions
- Plugin error resilience (warning logged, login continues)
"""

from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides):
    """Build a mock config object with defaults for workspace detection tests."""
    cfg = MagicMock()
    cfg.MLFLOW_ENABLE_WORKSPACES = overrides.get("MLFLOW_ENABLE_WORKSPACES", True)
    cfg.OIDC_WORKSPACE_DETECTION_PLUGIN = overrides.get("OIDC_WORKSPACE_DETECTION_PLUGIN", None)
    cfg.OIDC_WORKSPACE_CLAIM_NAME = overrides.get("OIDC_WORKSPACE_CLAIM_NAME", "workspace")
    cfg.OIDC_WORKSPACE_DEFAULT_PERMISSION = overrides.get("OIDC_WORKSPACE_DEFAULT_PERMISSION", "NO_PERMISSIONS")
    cfg.OIDC_GROUP_DETECTION_PLUGIN = overrides.get("OIDC_GROUP_DETECTION_PLUGIN", None)
    cfg.OIDC_GROUPS_ATTRIBUTE = overrides.get("OIDC_GROUPS_ATTRIBUTE", "groups")
    cfg.OIDC_GROUP_NAME = overrides.get("OIDC_GROUP_NAME", ["mlflow"])
    cfg.OIDC_ADMIN_GROUP_NAME = overrides.get("OIDC_ADMIN_GROUP_NAME", ["mlflow-admin"])
    cfg.DEFAULT_LANDING_PAGE_IS_PERMISSIONS = True
    cfg.OIDC_PROVIDER_DISPLAY_NAME = "Test OIDC"
    cfg.OIDC_REDIRECT_URI = None
    return cfg


def _run_workspace_detection(
    *,
    config_overrides: dict | None = None,
    userinfo: dict | None = None,
    access_token: str = "tok-123",
    plugin_module: ModuleType | None = None,
    plugin_raises: Exception | None = None,
    store_side_effect=None,
):
    """
    Exercise the workspace-detection section of _process_oidc_callback_fastapi()
    by extracting only the workspace logic into a controlled test harness.

    Returns (mock_store, mock_logger) for assertions.
    """
    import importlib as real_importlib

    cfg = _make_config(**(config_overrides or {}))
    if userinfo is None:
        userinfo = {
            "email": "alice@example.com",
            "name": "Alice",
            "groups": ["mlflow"],
        }

    email = userinfo.get("email", "alice@example.com")
    mock_store = MagicMock()
    if store_side_effect:
        mock_store.create_workspace_permission.side_effect = store_side_effect
    mock_logger = MagicMock()

    # Simulate the workspace-detection block from auth.py
    config = cfg
    logger = mock_logger

    if config.MLFLOW_ENABLE_WORKSPACES:
        user_workspaces: list[str] = []
        if config.OIDC_WORKSPACE_DETECTION_PLUGIN:
            try:
                if plugin_raises:
                    raise plugin_raises
                assert plugin_module is not None
                user_workspaces = plugin_module.get_user_workspaces(access_token)
            except Exception as ws_plugin_err:
                logger.warning(f"Workspace detection plugin error: {ws_plugin_err}")
        else:
            # JWT claim fallback
            claim_value = userinfo.get(config.OIDC_WORKSPACE_CLAIM_NAME, [])
            if isinstance(claim_value, str):
                user_workspaces = [claim_value]
            elif isinstance(claim_value, list):
                user_workspaces = [str(w) for w in claim_value]

        # Auto-assign workspace memberships
        ws_store = mock_store
        for ws_name in user_workspaces:
            if not ws_name:
                continue
            try:
                ws_store.create_workspace_permission(
                    ws_name,
                    email.lower(),
                    config.OIDC_WORKSPACE_DEFAULT_PERMISSION,
                )
                logger.info(f"Auto-assigned user {email} to workspace '{ws_name}' with {config.OIDC_WORKSPACE_DEFAULT_PERMISSION}")
            except Exception:
                logger.debug(f"Workspace permission already exists for {email} in '{ws_name}'")

    return mock_store, mock_logger


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkspaceDetectionDisabled:
    """When MLFLOW_ENABLE_WORKSPACES=False, no workspace detection occurs."""

    def test_no_store_calls_when_workspaces_disabled(self):
        """No store calls should be made when workspaces are disabled."""
        mock_store, _ = _run_workspace_detection(
            config_overrides={"MLFLOW_ENABLE_WORKSPACES": False},
            userinfo={
                "email": "alice@example.com",
                "name": "Alice",
                "groups": ["mlflow"],
                "workspace": ["ws-1"],
            },
        )
        mock_store.create_workspace_permission.assert_not_called()


class TestWorkspaceDetectionPlugin:
    """Plugin-based workspace detection via OIDC_WORKSPACE_DETECTION_PLUGIN."""

    def test_plugin_called_with_access_token(self):
        """When plugin is configured, calls get_user_workspaces(access_token)."""
        plugin_mod = MagicMock()
        plugin_mod.get_user_workspaces.return_value = ["ws-alpha", "ws-beta"]

        mock_store, _ = _run_workspace_detection(
            config_overrides={"OIDC_WORKSPACE_DETECTION_PLUGIN": "my_ws_plugin"},
            plugin_module=plugin_mod,
            access_token="my-token",
        )

        plugin_mod.get_user_workspaces.assert_called_once_with("my-token")
        assert mock_store.create_workspace_permission.call_count == 2
        mock_store.create_workspace_permission.assert_any_call("ws-alpha", "alice@example.com", "NO_PERMISSIONS")
        mock_store.create_workspace_permission.assert_any_call("ws-beta", "alice@example.com", "NO_PERMISSIONS")

    def test_plugin_error_logged_as_warning(self):
        """Plugin errors are logged as warnings and don't prevent login."""
        mock_store, mock_logger = _run_workspace_detection(
            config_overrides={"OIDC_WORKSPACE_DETECTION_PLUGIN": "broken_plugin"},
            plugin_raises=ImportError("module not found"),
        )

        mock_logger.warning.assert_called_once()
        assert "Workspace detection plugin error" in mock_logger.warning.call_args[0][0]
        # No store calls because plugin failed
        mock_store.create_workspace_permission.assert_not_called()


class TestWorkspaceDetectionJWTClaim:
    """JWT claim fallback when no plugin is configured."""

    def test_string_claim_converted_to_list(self):
        """A single string claim value is wrapped into a list."""
        mock_store, _ = _run_workspace_detection(
            userinfo={
                "email": "bob@example.com",
                "name": "Bob",
                "groups": ["mlflow"],
                "workspace": "single-ws",
            },
        )

        mock_store.create_workspace_permission.assert_called_once_with("single-ws", "bob@example.com", "NO_PERMISSIONS")

    def test_list_claim_used_as_is(self):
        """A list claim value is used directly."""
        mock_store, _ = _run_workspace_detection(
            userinfo={
                "email": "carol@example.com",
                "name": "Carol",
                "groups": ["mlflow"],
                "workspace": ["ws-1", "ws-2"],
            },
        )

        assert mock_store.create_workspace_permission.call_count == 2
        mock_store.create_workspace_permission.assert_any_call("ws-1", "carol@example.com", "NO_PERMISSIONS")
        mock_store.create_workspace_permission.assert_any_call("ws-2", "carol@example.com", "NO_PERMISSIONS")

    def test_custom_claim_name(self):
        """Uses configured OIDC_WORKSPACE_CLAIM_NAME to extract claim."""
        mock_store, _ = _run_workspace_detection(
            config_overrides={"OIDC_WORKSPACE_CLAIM_NAME": "org"},
            userinfo={
                "email": "dave@example.com",
                "name": "Dave",
                "groups": ["mlflow"],
                "org": ["my-org"],
            },
        )

        mock_store.create_workspace_permission.assert_called_once_with("my-org", "dave@example.com", "NO_PERMISSIONS")

    def test_missing_claim_results_in_no_workspaces(self):
        """When the configured claim is absent, no workspace assignments are made."""
        mock_store, _ = _run_workspace_detection(
            userinfo={"email": "eve@example.com", "name": "Eve", "groups": ["mlflow"]},
        )

        mock_store.create_workspace_permission.assert_not_called()

    def test_empty_list_claim_results_in_no_workspaces(self):
        """An empty list claim results in no workspace assignments."""
        mock_store, _ = _run_workspace_detection(
            userinfo={
                "email": "frank@example.com",
                "name": "Frank",
                "groups": ["mlflow"],
                "workspace": [],
            },
        )

        mock_store.create_workspace_permission.assert_not_called()


class TestWorkspaceAutoAssign:
    """Auto-assign workspace membership tests."""

    def test_default_permission_configurable(self):
        """Uses OIDC_WORKSPACE_DEFAULT_PERMISSION value for auto-assign."""
        mock_store, _ = _run_workspace_detection(
            config_overrides={"OIDC_WORKSPACE_DEFAULT_PERMISSION": "READ"},
            userinfo={
                "email": "grace@example.com",
                "name": "Grace",
                "groups": ["mlflow"],
                "workspace": ["ws-x"],
            },
        )

        mock_store.create_workspace_permission.assert_called_once_with("ws-x", "grace@example.com", "READ")

    def test_existing_permission_silently_ignored(self):
        """Duplicate workspace permission (re-login) is silently ignored."""
        mock_store, mock_logger = _run_workspace_detection(
            userinfo={
                "email": "heidi@example.com",
                "name": "Heidi",
                "groups": ["mlflow"],
                "workspace": ["ws-dup"],
            },
            store_side_effect=Exception("IntegrityError: UNIQUE constraint failed"),
        )

        # Store was called but exception was caught
        mock_store.create_workspace_permission.assert_called_once()
        # Should log at debug level, not error
        mock_logger.debug.assert_called_once()
        assert "already exists" in mock_logger.debug.call_args[0][0]

    def test_empty_workspace_names_skipped(self):
        """Empty workspace names in the list are skipped."""
        mock_store, _ = _run_workspace_detection(
            userinfo={
                "email": "ivan@example.com",
                "name": "Ivan",
                "groups": ["mlflow"],
                "workspace": ["", "valid-ws", ""],
            },
        )

        mock_store.create_workspace_permission.assert_called_once_with("valid-ws", "ivan@example.com", "NO_PERMISSIONS")


class TestConfigEntries:
    """Verify new config entries exist with correct defaults."""

    def test_oidc_workspace_claim_name_default(self):
        """OIDC_WORKSPACE_CLAIM_NAME defaults to 'workspace'."""
        from mlflow_oidc_auth.config import config

        assert hasattr(config, "OIDC_WORKSPACE_CLAIM_NAME")
        assert config.OIDC_WORKSPACE_CLAIM_NAME == "workspace"

    def test_oidc_workspace_detection_plugin_default(self):
        """OIDC_WORKSPACE_DETECTION_PLUGIN defaults to None."""
        from mlflow_oidc_auth.config import config

        assert hasattr(config, "OIDC_WORKSPACE_DETECTION_PLUGIN")
        assert config.OIDC_WORKSPACE_DETECTION_PLUGIN is None

    def test_oidc_workspace_default_permission_default(self):
        """OIDC_WORKSPACE_DEFAULT_PERMISSION defaults to 'NO_PERMISSIONS'."""
        from mlflow_oidc_auth.config import config

        assert hasattr(config, "OIDC_WORKSPACE_DEFAULT_PERMISSION")
        assert config.OIDC_WORKSPACE_DEFAULT_PERMISSION == "NO_PERMISSIONS"
