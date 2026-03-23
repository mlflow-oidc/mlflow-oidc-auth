"""Tests for workspace permission cache module."""

import pytest
from unittest.mock import MagicMock, patch

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.permissions import MANAGE, READ, get_permission


class TestGetWorkspacePermissionCached:
    """Test get_workspace_permission_cached() function."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset module-level cache between tests."""
        import mlflow_oidc_auth.utils.workspace_cache as wc

        wc._cache = None
        yield
        wc._cache = None

    def test_returns_none_when_workspaces_disabled(self):
        """get_workspace_permission_cached() returns None when MLFLOW_ENABLE_WORKSPACES is False."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = False

        with patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config):
            result = get_workspace_permission_cached("user1", "ws1")
            assert result is None

    def test_returns_manage_for_default_workspace_with_grant_enabled(self):
        """get_workspace_permission_cached('user1', 'default') returns MANAGE when GRANT_DEFAULT_WORKSPACE_ACCESS is True."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.GRANT_DEFAULT_WORKSPACE_ACCESS = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300

        with patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config):
            result = get_workspace_permission_cached("user1", "default")
            assert result == MANAGE

    def test_default_workspace_no_implicit_manage_when_grant_disabled(self):
        """get_workspace_permission_cached('user1', 'default') does NOT return implicit MANAGE when GRANT_DEFAULT_WORKSPACE_ACCESS is False."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.GRANT_DEFAULT_WORKSPACE_ACCESS = False
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300

        mock_store = MagicMock()
        mock_perm = MagicMock()
        mock_perm.permission = "READ"
        mock_store.get_workspace_permission.return_value = mock_perm

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch(
                "mlflow_oidc_auth.utils.workspace_cache._lookup_workspace_permission"
            ) as mock_lookup,
        ):
            mock_lookup.return_value = READ
            result = get_workspace_permission_cached("user1", "default")
            assert result == READ
            mock_lookup.assert_called_once_with("user1", "default")

    def test_calls_lookup_on_cache_miss(self):
        """get_workspace_permission_cached() calls _lookup_workspace_permission on cache miss."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch(
                "mlflow_oidc_auth.utils.workspace_cache._lookup_workspace_permission"
            ) as mock_lookup,
        ):
            mock_lookup.return_value = READ
            result = get_workspace_permission_cached("user1", "ws1")
            mock_lookup.assert_called_once_with("user1", "ws1")
            assert result == READ

    def test_returns_cached_value_on_hit(self):
        """get_workspace_permission_cached() returns cached value on cache hit without DB query."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch(
                "mlflow_oidc_auth.utils.workspace_cache._lookup_workspace_permission"
            ) as mock_lookup,
        ):
            mock_lookup.return_value = MANAGE
            # First call — cache miss
            get_workspace_permission_cached("user1", "ws1")
            # Second call — cache hit
            result = get_workspace_permission_cached("user1", "ws1")
            assert result == MANAGE
            # lookup should only be called once (not twice)
            assert mock_lookup.call_count == 1

    def test_does_not_cache_none_results(self):
        """get_workspace_permission_cached() does NOT cache None results."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch(
                "mlflow_oidc_auth.utils.workspace_cache._lookup_workspace_permission"
            ) as mock_lookup,
        ):
            mock_lookup.return_value = None
            # First call — returns None, should not cache
            result1 = get_workspace_permission_cached("user1", "ws1")
            assert result1 is None
            # Second call — should call lookup again because None was not cached
            result2 = get_workspace_permission_cached("user1", "ws1")
            assert result2 is None
            assert mock_lookup.call_count == 2


class TestLookupWorkspacePermission:
    """Test _lookup_workspace_permission() function."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset module-level cache between tests."""
        import mlflow_oidc_auth.utils.workspace_cache as wc

        wc._cache = None
        yield
        wc._cache = None

    def test_tries_user_permission_first(self):
        """_lookup_workspace_permission() tries user-level permission first."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()
        mock_config.GRANT_DEFAULT_WORKSPACE_ACCESS = False

        mock_store = MagicMock()
        mock_perm = MagicMock()
        mock_perm.permission = "MANAGE"
        mock_store.get_workspace_permission.return_value = mock_perm

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "ws1")
            assert result == MANAGE
            mock_store.get_workspace_permission.assert_called_once_with("ws1", "user1")

    def test_falls_through_to_group_permission(self):
        """_lookup_workspace_permission() tries group-level when user-level fails."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()
        mock_config.GRANT_DEFAULT_WORKSPACE_ACCESS = False

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = MlflowException(
            "Not found", RESOURCE_DOES_NOT_EXIST
        )
        mock_group_perm = MagicMock()
        mock_group_perm.permission = "READ"
        mock_store.get_user_groups_workspace_permission.return_value = mock_group_perm

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "ws1")
            assert result == READ
            mock_store.get_user_groups_workspace_permission.assert_called_once_with(
                "ws1", "user1"
            )

    def test_returns_none_when_no_permission(self):
        """_lookup_workspace_permission() returns None when no user or group permission exists."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()
        mock_config.GRANT_DEFAULT_WORKSPACE_ACCESS = False

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = MlflowException(
            "Not found", RESOURCE_DOES_NOT_EXIST
        )
        mock_store.get_user_groups_workspace_permission.side_effect = MlflowException(
            "Not found", RESOURCE_DOES_NOT_EXIST
        )

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "ws1")
            assert result is None

    def test_implicit_manage_for_default_workspace(self):
        """_lookup_workspace_permission() returns MANAGE for default workspace when GRANT_DEFAULT_WORKSPACE_ACCESS is True."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()
        mock_config.GRANT_DEFAULT_WORKSPACE_ACCESS = True

        with patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config):
            result = _lookup_workspace_permission("user1", "default")
            assert result == MANAGE
