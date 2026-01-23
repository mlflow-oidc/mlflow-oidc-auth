"""
Comprehensive tests for the dependencies module.

This module tests all dependency injection functions used with FastAPI,
including experiment permissions, admin permissions, and registered model permissions.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, Request

from mlflow_oidc_auth.dependencies import (
    check_admin_permission,
    check_experiment_manage_permission,
    check_registered_model_manage_permission,
)


class TestCheckAdminPermission:
    """Test the check_admin_permission dependency function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_admin_permission_success(self, mock_get_username, mock_get_is_admin):
        """Test successful admin permission check."""
        mock_request = MagicMock(spec=Request)
        mock_get_is_admin.return_value = True
        mock_get_username.return_value = "admin@example.com"

        result = await check_admin_permission(mock_request)

        assert result == "admin@example.com"
        mock_get_is_admin.assert_called_once_with(request=mock_request)
        mock_get_username.assert_called_once_with(request=mock_request)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_admin_permission_denied(self, mock_get_username, mock_get_is_admin):
        """Test admin permission check when user is not admin."""
        mock_request = MagicMock(spec=Request)
        mock_get_username.return_value = "user@example.com"
        mock_get_is_admin.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permission(mock_request)

        assert exc_info.value.status_code == 403
        assert "Administrator privileges required for this operation" in str(exc_info.value.detail)
        mock_get_is_admin.assert_called_once_with(request=mock_request)
        mock_get_username.assert_called_once_with(request=mock_request)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_admin_permission_none_result(self, mock_get_username, mock_get_is_admin):
        """Test admin permission check when get_is_admin returns None."""
        mock_request = MagicMock(spec=Request)
        mock_get_username.return_value = "user@example.com"
        mock_get_is_admin.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permission(mock_request)

        assert exc_info.value.status_code == 403
        mock_get_is_admin.assert_called_once_with(request=mock_request)
        mock_get_username.assert_called_once_with(request=mock_request)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_admin_permission_get_username_exception(self, mock_get_username, mock_get_is_admin):
        """Test admin permission check when get_username raises an exception."""
        mock_request = MagicMock(spec=Request)
        mock_get_is_admin.return_value = True
        mock_get_username.side_effect = Exception("Username retrieval failed")

        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permission(mock_request)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_admin_permission_get_is_admin_exception(self, mock_get_username, mock_get_is_admin):
        """Test admin permission check when get_is_admin raises an exception."""
        mock_request = MagicMock(spec=Request)
        mock_get_username.return_value = "user@example.com"
        mock_get_is_admin.side_effect = Exception("Admin check failed")

        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permission(mock_request)

        assert exc_info.value.status_code == 403


class TestCheckExperimentManagePermission:
    """Test the check_experiment_manage_permission dependency function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_admin_success(self, mock_can_manage):
        """Test successful experiment manage permission check for admin user."""

        result = await check_experiment_manage_permission("123", "admin@example.com", True)

        assert result is None
        # Admin should not need to check can_manage_experiment
        mock_can_manage.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_non_admin_success(self, mock_can_manage):
        """Test successful experiment manage permission check for non-admin user with permissions."""
        mock_can_manage.return_value = True

        result = await check_experiment_manage_permission("123", "user@example.com", False)

        assert result is None
        mock_can_manage.assert_called_once_with("123", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_non_admin_denied(self, mock_can_manage):
        """Test experiment manage permission check when non-admin user lacks permissions."""
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_experiment_manage_permission("123", "user@example.com", False)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions to manage experiment 123" in str(exc_info.value.detail)
        mock_can_manage.assert_called_once_with("123", "user@example.com")

    @pytest.mark.asyncio
    async def test_check_manage_permission_admin_various_experiments(self):
        """Test admin user can manage various experiment IDs."""
        # Test with different experiment ID formats
        experiment_ids = ["123", "exp-456", "experiment_789", ""]

        for exp_id in experiment_ids:
            result = await check_experiment_manage_permission(exp_id, "admin@example.com", True)
            assert result is None

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_can_manage_exception(self, mock_can_manage):
        """Test experiment manage permission check when can_manage_experiment raises exception."""
        mock_can_manage.side_effect = Exception("Permission check failed")

        with pytest.raises(Exception, match="Permission check failed"):
            await check_experiment_manage_permission("123", "user@example.com", False)


class TestCheckRegisteredModelPermission:
    """Test the check_registered_model_manage_permission dependency function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_admin_success(self, mock_can_manage):
        """Test successful registered model permission check for admin user."""
        result = await check_registered_model_manage_permission("my-model", "admin@example.com", True)

        assert result is None
        # Admin should not need to check can_manage_registered_model
        mock_can_manage.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_non_admin_success(self, mock_can_manage):
        """Test successful registered model permission check for non-admin user with permissions."""
        mock_can_manage.return_value = True

        result = await check_registered_model_manage_permission("my-model", "user@example.com", False)

        assert result is None
        mock_can_manage.assert_called_once_with("my-model", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_non_admin_denied(self, mock_can_manage):
        """Test registered model permission check when non-admin user lacks permissions."""
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_registered_model_manage_permission("my-model", "user@example.com", False)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions to manage my-model" in str(exc_info.value.detail)
        mock_can_manage.assert_called_once_with("my-model", "user@example.com")

    @pytest.mark.asyncio
    async def test_check_model_permission_admin_various_models(self):
        """Test admin user can manage various model names."""
        # Test with different model name formats
        model_names = ["simple-model", "model_with_underscores", "model-123", "Model.Name", ""]

        for model_name in model_names:
            result = await check_registered_model_manage_permission(model_name, "admin@example.com", True)
            assert result is None

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_special_characters(self, mock_can_manage):
        """Test registered model permission check with special characters in model name."""
        mock_can_manage.return_value = True

        result = await check_registered_model_manage_permission("model-with-special_chars.123", "user@example.com", False)

        assert result is None
        mock_can_manage.assert_called_once_with("model-with-special_chars.123", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_can_manage_exception(self, mock_can_manage):
        """Test registered model permission check when can_manage_registered_model raises exception."""
        mock_can_manage.side_effect = Exception("Model permission check failed")

        with pytest.raises(Exception, match="Model permission check failed"):
            await check_registered_model_manage_permission("my-model", "user@example.com", False)


class TestDependencyIntegration:
    """Test integration scenarios and edge cases across all dependency functions."""

    @pytest.mark.asyncio
    async def test_all_dependencies_return_none_on_success(self):
        """Test that all permission dependencies return None on successful authorization."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_experiment", return_value=True), patch(
            "mlflow_oidc_auth.dependencies.can_manage_registered_model", return_value=True
        ), patch("mlflow_oidc_auth.dependencies.get_is_admin", return_value=True), patch(
            "mlflow_oidc_auth.dependencies.get_username", return_value="admin@example.com"
        ):
            mock_request = MagicMock(spec=Request)

            # Test all dependency functions return None on success
            result3 = await check_experiment_manage_permission("123", "admin@example.com", True)
            result4 = await check_registered_model_manage_permission("model", "admin@example.com", True)

            assert result3 is None
            assert result4 is None

            # Only check_admin_permission returns username
            result5 = await check_admin_permission(mock_request)
            assert result5 == "admin@example.com"

    @pytest.mark.asyncio
    async def test_all_dependencies_raise_403_on_failure(self):
        """Test that all permission dependencies raise HTTPException with 403 status on failure."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_experiment", return_value=False), patch(
            "mlflow_oidc_auth.dependencies.can_manage_registered_model", return_value=False
        ), patch("mlflow_oidc_auth.dependencies.get_is_admin", return_value=False):
            mock_request = MagicMock(spec=Request)

            with pytest.raises(HTTPException) as exc3:
                await check_experiment_manage_permission("123", "user@example.com", False)
            assert exc3.value.status_code == 403

            with pytest.raises(HTTPException) as exc4:
                await check_registered_model_manage_permission("model", "user@example.com", False)
            assert exc4.value.status_code == 403

            with pytest.raises(HTTPException) as exc5:
                await check_admin_permission(mock_request)
            assert exc5.value.status_code == 403

    def test_dependency_function_signatures(self):
        """Test that all dependency functions have correct async signatures."""
        import inspect

        # All dependency functions should be async
        assert inspect.iscoroutinefunction(check_admin_permission)
        assert inspect.iscoroutinefunction(check_experiment_manage_permission)
        assert inspect.iscoroutinefunction(check_registered_model_manage_permission)


class TestDependencyErrorHandling:
    """Test error handling and edge cases in dependency functions."""

    @pytest.mark.asyncio
    async def test_admin_permission_with_none_request(self):
        """Test admin permission handling with None request."""
        with patch("mlflow_oidc_auth.dependencies.get_is_admin") as mock_get_is_admin:
            mock_get_is_admin.return_value = True

            with patch("mlflow_oidc_auth.dependencies.get_username") as mock_get_username:
                mock_get_username.return_value = "admin@example.com"

                result = await check_admin_permission(None)
                assert result == "admin@example.com"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_model_permission_with_empty_strings(self, mock_can_manage):
        """Test registered model permission handling with empty strings."""
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_registered_model_manage_permission("", "", False)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions to manage " in str(exc_info.value.detail)
