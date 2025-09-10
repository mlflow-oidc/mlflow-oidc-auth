"""
Comprehensive tests for the dependencies module.

This module tests all dependency injection functions used with FastAPI,
including experiment permissions, admin permissions, and registered model permissions.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, Request

from mlflow_oidc_auth.dependencies import (
    check_experiment_permission,
    create_experiment_permission_dependency,
    check_current_user_experiment_permission,
    check_admin_permission,
    check_experiment_manage_permission,
    check_registered_model_permission,
)


class TestCheckExperimentPermission:
    """Test the check_experiment_permission dependency function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_experiment_permission_success(self, mock_can_manage):
        """Test successful experiment permission check."""
        mock_can_manage.return_value = True

        result = await check_experiment_permission("123", "user@example.com")

        assert result is None
        mock_can_manage.assert_called_once_with("123", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_experiment_permission_denied(self, mock_can_manage):
        """Test experiment permission check when access is denied."""
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_experiment_permission("123", "user@example.com")

        assert exc_info.value.status_code == 403
        assert "User does not have sufficient permissions to access experiment 123" in str(exc_info.value.detail)
        mock_can_manage.assert_called_once_with("123", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_experiment_permission_with_special_characters(self, mock_can_manage):
        """Test experiment permission check with special characters in experiment ID."""
        mock_can_manage.return_value = True

        result = await check_experiment_permission("exp-123_test", "user+test@example.com")

        assert result is None
        mock_can_manage.assert_called_once_with("exp-123_test", "user+test@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_experiment_permission_empty_strings(self, mock_can_manage):
        """Test experiment permission check with empty strings."""
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_experiment_permission("", "")

        assert exc_info.value.status_code == 403
        mock_can_manage.assert_called_once_with("", "")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_experiment_permission_exception_handling(self, mock_can_manage):
        """Test experiment permission check when can_manage_experiment raises an exception."""
        mock_can_manage.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            await check_experiment_permission("123", "user@example.com")


class TestCreateExperimentPermissionDependency:
    """Test the create_experiment_permission_dependency factory function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_create_dependency_default_params(self, mock_can_manage):
        """Test creating dependency with default parameter names."""
        mock_can_manage.return_value = True

        dependency = create_experiment_permission_dependency()
        result = await dependency("123", "user@example.com")

        assert result is None
        mock_can_manage.assert_called_once_with("123", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_create_dependency_custom_params(self, mock_can_manage):
        """Test creating dependency with custom parameter names."""
        mock_can_manage.return_value = True

        dependency = create_experiment_permission_dependency("exp_id", "user_name")
        result = await dependency("456", "admin@example.com")

        assert result is None
        mock_can_manage.assert_called_once_with("456", "admin@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_create_dependency_permission_denied(self, mock_can_manage):
        """Test created dependency when permission is denied."""
        mock_can_manage.return_value = False

        dependency = create_experiment_permission_dependency()

        with pytest.raises(HTTPException) as exc_info:
            await dependency("123", "user@example.com")

        assert exc_info.value.status_code == 403
        assert "User does not have sufficient permissions to access experiment 123" in str(exc_info.value.detail)

    def test_create_dependency_function_signature(self):
        """Test that the created dependency function has the correct signature."""
        dependency = create_experiment_permission_dependency("custom_exp", "custom_user")

        # Check that the function is callable
        assert callable(dependency)

        # Check that it's an async function
        import inspect

        assert inspect.iscoroutinefunction(dependency)


class TestCheckCurrentUserExperimentPermission:
    """Test the check_current_user_experiment_permission dependency function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_current_user_permission_success(self, mock_get_username, mock_can_manage):
        """Test successful current user experiment permission check."""
        mock_get_username.return_value = "current@example.com"
        mock_can_manage.return_value = True

        result = await check_current_user_experiment_permission("123", "current@example.com")

        assert result is None
        mock_can_manage.assert_called_once_with("123", "current@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_current_user_permission_denied(self, mock_get_username, mock_can_manage):
        """Test current user experiment permission check when access is denied."""
        mock_get_username.return_value = "current@example.com"
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_current_user_experiment_permission("123", "current@example.com")

        assert exc_info.value.status_code == 403
        assert "User does not have sufficient permissions to access experiment 123" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_current_user_permission_with_different_usernames(self, mock_can_manage):
        """Test current user permission check with different username formats."""
        mock_can_manage.return_value = True

        # Test with email format
        result = await check_current_user_experiment_permission("123", "user@domain.com")
        assert result is None

        # Test with username format
        result = await check_current_user_experiment_permission("456", "username")
        assert result is None

        assert mock_can_manage.call_count == 2


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
    async def test_check_admin_permission_denied(self, mock_get_is_admin):
        """Test admin permission check when user is not admin."""
        mock_request = MagicMock(spec=Request)
        mock_get_is_admin.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permission(mock_request)

        assert exc_info.value.status_code == 403
        assert "Administrator privileges required for this operation" in str(exc_info.value.detail)
        mock_get_is_admin.assert_called_once_with(request=mock_request)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    async def test_check_admin_permission_none_result(self, mock_get_is_admin):
        """Test admin permission check when get_is_admin returns None."""
        mock_request = MagicMock(spec=Request)
        mock_get_is_admin.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await check_admin_permission(mock_request)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    @patch("mlflow_oidc_auth.dependencies.get_username")
    async def test_check_admin_permission_get_username_exception(self, mock_get_username, mock_get_is_admin):
        """Test admin permission check when get_username raises an exception."""
        mock_request = MagicMock(spec=Request)
        mock_get_is_admin.return_value = True
        mock_get_username.side_effect = Exception("Username retrieval failed")

        with pytest.raises(Exception, match="Username retrieval failed"):
            await check_admin_permission(mock_request)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.get_is_admin")
    async def test_check_admin_permission_get_is_admin_exception(self, mock_get_is_admin):
        """Test admin permission check when get_is_admin raises an exception."""
        mock_request = MagicMock(spec=Request)
        mock_get_is_admin.side_effect = Exception("Admin check failed")

        with pytest.raises(Exception, match="Admin check failed"):
            await check_admin_permission(mock_request)


class TestCheckExperimentManagePermission:
    """Test the check_experiment_manage_permission dependency function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_admin_success(self, mock_can_manage):
        """Test successful experiment manage permission check for admin user."""
        mock_request = MagicMock(spec=Request)

        result = await check_experiment_manage_permission(mock_request, "123", "admin@example.com", True)

        assert result is None
        # Admin should not need to check can_manage_experiment
        mock_can_manage.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_non_admin_success(self, mock_can_manage):
        """Test successful experiment manage permission check for non-admin user with permissions."""
        mock_request = MagicMock(spec=Request)
        mock_can_manage.return_value = True

        result = await check_experiment_manage_permission(mock_request, "123", "user@example.com", False)

        assert result is None
        mock_can_manage.assert_called_once_with("123", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_non_admin_denied(self, mock_can_manage):
        """Test experiment manage permission check when non-admin user lacks permissions."""
        mock_request = MagicMock(spec=Request)
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_experiment_manage_permission(mock_request, "123", "user@example.com", False)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions to manage experiment 123" in str(exc_info.value.detail)
        mock_can_manage.assert_called_once_with("123", "user@example.com")

    @pytest.mark.asyncio
    async def test_check_manage_permission_admin_various_experiments(self):
        """Test admin user can manage various experiment IDs."""
        mock_request = MagicMock(spec=Request)

        # Test with different experiment ID formats
        experiment_ids = ["123", "exp-456", "experiment_789", ""]

        for exp_id in experiment_ids:
            result = await check_experiment_manage_permission(mock_request, exp_id, "admin@example.com", True)
            assert result is None

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_check_manage_permission_can_manage_exception(self, mock_can_manage):
        """Test experiment manage permission check when can_manage_experiment raises exception."""
        mock_request = MagicMock(spec=Request)
        mock_can_manage.side_effect = Exception("Permission check failed")

        with pytest.raises(Exception, match="Permission check failed"):
            await check_experiment_manage_permission(mock_request, "123", "user@example.com", False)


class TestCheckRegisteredModelPermission:
    """Test the check_registered_model_permission dependency function."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_admin_success(self, mock_can_manage):
        """Test successful registered model permission check for admin user."""
        result = await check_registered_model_permission("my-model", "admin@example.com", True)

        assert result is None
        # Admin should not need to check can_manage_registered_model
        mock_can_manage.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_non_admin_success(self, mock_can_manage):
        """Test successful registered model permission check for non-admin user with permissions."""
        mock_can_manage.return_value = True

        result = await check_registered_model_permission("my-model", "user@example.com", False)

        assert result is None
        mock_can_manage.assert_called_once_with("my-model", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_non_admin_denied(self, mock_can_manage):
        """Test registered model permission check when non-admin user lacks permissions."""
        mock_can_manage.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await check_registered_model_permission("my-model", "user@example.com", False)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions to manage registered model my-model" in str(exc_info.value.detail)
        mock_can_manage.assert_called_once_with("my-model", "user@example.com")

    @pytest.mark.asyncio
    async def test_check_model_permission_admin_various_models(self):
        """Test admin user can manage various model names."""
        # Test with different model name formats
        model_names = ["simple-model", "model_with_underscores", "model-123", "Model.Name", ""]

        for model_name in model_names:
            result = await check_registered_model_permission(model_name, "admin@example.com", True)
            assert result is None

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_special_characters(self, mock_can_manage):
        """Test registered model permission check with special characters in model name."""
        mock_can_manage.return_value = True

        result = await check_registered_model_permission("model-with-special_chars.123", "user@example.com", False)

        assert result is None
        mock_can_manage.assert_called_once_with("model-with-special_chars.123", "user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_registered_model")
    async def test_check_model_permission_can_manage_exception(self, mock_can_manage):
        """Test registered model permission check when can_manage_registered_model raises exception."""
        mock_can_manage.side_effect = Exception("Model permission check failed")

        with pytest.raises(Exception, match="Model permission check failed"):
            await check_registered_model_permission("my-model", "user@example.com", False)


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
            result1 = await check_experiment_permission("123", "user@example.com")
            result2 = await check_current_user_experiment_permission("123", "user@example.com")
            result3 = await check_experiment_manage_permission(mock_request, "123", "admin@example.com", True)
            result4 = await check_registered_model_permission("model", "admin@example.com", True)

            assert result1 is None
            assert result2 is None
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

            # Test all dependency functions raise 403 HTTPException on failure
            with pytest.raises(HTTPException) as exc1:
                await check_experiment_permission("123", "user@example.com")
            assert exc1.value.status_code == 403

            with pytest.raises(HTTPException) as exc2:
                await check_current_user_experiment_permission("123", "user@example.com")
            assert exc2.value.status_code == 403

            with pytest.raises(HTTPException) as exc3:
                await check_experiment_manage_permission(mock_request, "123", "user@example.com", False)
            assert exc3.value.status_code == 403

            with pytest.raises(HTTPException) as exc4:
                await check_registered_model_permission("model", "user@example.com", False)
            assert exc4.value.status_code == 403

            with pytest.raises(HTTPException) as exc5:
                await check_admin_permission(mock_request)
            assert exc5.value.status_code == 403

    @pytest.mark.asyncio
    async def test_dependency_isolation(self):
        """Test that dependencies don't interfere with each other."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_experiment") as mock_exp, patch(
            "mlflow_oidc_auth.dependencies.can_manage_registered_model"
        ) as mock_model:
            mock_exp.return_value = True
            mock_model.return_value = False

            # Experiment permission should succeed
            result1 = await check_experiment_permission("123", "user@example.com")
            assert result1 is None

            # Model permission should fail
            with pytest.raises(HTTPException):
                await check_registered_model_permission("model", "user@example.com", False)

            # Verify each function was called with correct parameters
            mock_exp.assert_called_once_with("123", "user@example.com")
            mock_model.assert_called_once_with("model", "user@example.com")

    def test_dependency_function_signatures(self):
        """Test that all dependency functions have correct async signatures."""
        import inspect

        # All dependency functions should be async
        assert inspect.iscoroutinefunction(check_experiment_permission)
        assert inspect.iscoroutinefunction(check_current_user_experiment_permission)
        assert inspect.iscoroutinefunction(check_admin_permission)
        assert inspect.iscoroutinefunction(check_experiment_manage_permission)
        assert inspect.iscoroutinefunction(check_registered_model_permission)

        # Factory function should not be async
        assert not inspect.iscoroutinefunction(create_experiment_permission_dependency)

        # But the function it creates should be async
        dependency = create_experiment_permission_dependency()
        assert inspect.iscoroutinefunction(dependency)


class TestDependencyErrorHandling:
    """Test error handling and edge cases in dependency functions."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.dependencies.can_manage_experiment")
    async def test_experiment_permission_with_none_values(self, mock_can_manage):
        """Test experiment permission handling with None values."""
        mock_can_manage.return_value = True

        # Test with None experiment_id (should still work if can_manage_experiment handles it)
        result = await check_experiment_permission(None, "user@example.com")
        assert result is None
        mock_can_manage.assert_called_once_with(None, "user@example.com")

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
            await check_registered_model_permission("", "", False)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions to manage registered model " in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_dependency_with_unicode_characters(self):
        """Test dependencies with unicode characters in parameters."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_experiment", return_value=True) as mock_can_manage:
            result = await check_experiment_permission("实验-123", "用户@example.com")
            assert result is None
            mock_can_manage.assert_called_once_with("实验-123", "用户@example.com")

    @pytest.mark.asyncio
    async def test_dependency_concurrent_calls(self):
        """Test that dependencies work correctly with concurrent calls."""
        import asyncio

        with patch("mlflow_oidc_auth.dependencies.can_manage_experiment", return_value=True):
            # Create multiple concurrent calls
            tasks = [check_experiment_permission(f"exp-{i}", f"user{i}@example.com") for i in range(10)]

            results = await asyncio.gather(*tasks)

            # All should return None
            assert all(result is None for result in results)
