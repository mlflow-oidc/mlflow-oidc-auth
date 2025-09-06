import importlib
from unittest.mock import MagicMock, patch

import pytest
from authlib.jose.errors import BadSignatureError

from mlflow_oidc_auth.auth import (
    _get_oidc_jwks,
    validate_token,
    handle_user_and_group_management,
)


class TestAuth:
    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_success(self, mock_config, mock_requests):
        """Test successful JWKS retrieval from OIDC provider"""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"

        # Mock discovery document response
        discovery_response = MagicMock()
        discovery_response.json.return_value = {"jwks_uri": "https://example.com/jwks"}

        # Mock JWKS response
        jwks_response = MagicMock()
        jwks_response.json.return_value = {"keys": [{"kty": "RSA", "kid": "test"}]}

        mock_requests.get.side_effect = [discovery_response, jwks_response]

        # Mock the cache import inside the function
        with patch("mlflow_oidc_auth.app.cache", mock_cache, create=True):
            result = _get_oidc_jwks()

            # Verify requests were made correctly
            assert mock_requests.get.call_count == 2
            mock_requests.get.assert_any_call("https://example.com/.well-known/openid_configuration")
            mock_requests.get.assert_any_call("https://example.com/jwks")

            # Verify cache was set
            mock_cache.set.assert_called_once_with("jwks", {"keys": [{"kty": "RSA", "kid": "test"}]}, timeout=3600)
            assert result == {"keys": [{"kty": "RSA", "kid": "test"}]}

    def test_get_oidc_jwks_cache_hit(self):
        """Test JWKS retrieval from cache"""
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"keys": "cached_keys"}

        with patch("mlflow_oidc_auth.app.cache", mock_cache, create=True):
            result = _get_oidc_jwks()
            assert result == {"keys": "cached_keys"}
            mock_cache.get.assert_called_once_with("jwks")

    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_no_discovery_url(self, mock_config):
        """Test JWKS retrieval fails when OIDC_DISCOVERY_URL is not set"""
        mock_config.OIDC_DISCOVERY_URL = None
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with patch("mlflow_oidc_auth.app.cache", mock_cache, create=True):
            with pytest.raises(ValueError, match="OIDC_DISCOVERY_URL is not set in the configuration"):
                _get_oidc_jwks()

    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_clear_cache(self, mock_config, mock_requests):
        """Test JWKS cache clearing functionality"""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"

        # Mock responses
        discovery_response = MagicMock()
        discovery_response.json.return_value = {"jwks_uri": "https://example.com/jwks"}
        jwks_response = MagicMock()
        jwks_response.json.return_value = {"keys": [{"kty": "RSA"}]}
        mock_requests.get.side_effect = [discovery_response, jwks_response]

        with patch("mlflow_oidc_auth.app.cache", mock_cache, create=True):
            _get_oidc_jwks(clear_cache=True)
            mock_cache.delete.assert_called_once_with("jwks")

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_success(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test successful token validation"""
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test"}]}
        mock_get_oidc_jwks.return_value = mock_jwks
        mock_payload = MagicMock()
        mock_jwt_decode.return_value = mock_payload

        result = validate_token("valid_token")

        mock_jwt_decode.assert_called_once_with("valid_token", mock_jwks)
        mock_payload.validate.assert_called_once()
        assert result == mock_payload

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_bad_signature_then_success(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test token validation with bad signature that succeeds after JWKS refresh"""
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_payload = MagicMock()
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), mock_payload]

        result = validate_token("token_with_new_key")

        assert result == mock_payload
        assert mock_get_oidc_jwks.call_count == 2
        # Verify JWKS was refreshed with clear_cache=True on second call
        mock_get_oidc_jwks.assert_any_call(clear_cache=True)

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_bad_signature_after_refresh(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test token validation that fails even after JWKS refresh"""
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), BadSignatureError("still bad")]

        with pytest.raises(BadSignatureError):
            validate_token("invalid_token")

        assert mock_get_oidc_jwks.call_count == 2

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_unexpected_error_after_refresh(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test token validation with unexpected error after JWKS refresh"""
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), ValueError("unexpected error")]

        with pytest.raises(ValueError, match="unexpected error"):
            validate_token("problematic_token")

        assert mock_get_oidc_jwks.call_count == 2

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth.create_user")
    @patch("mlflow_oidc_auth.auth.populate_groups")
    @patch("mlflow_oidc_auth.auth.update_user")
    def test_handle_user_and_group_management_success_admin(self, mock_update_user, mock_populate_groups, mock_create_user, mock_config):
        """Test successful user and group management for admin user"""
        token = {
            "userinfo": {"email": "admin@example.com", "name": "Admin User", "groups": ["admin", "users"]},
            "access_token": "access_token_123",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        errors = handle_user_and_group_management(token)

        assert errors == []
        mock_create_user.assert_called_once_with(username="admin@example.com", display_name="Admin User", is_admin=True)
        mock_populate_groups.assert_called_once_with(group_names=["admin", "users"])
        mock_update_user.assert_called_once_with(username="admin@example.com", group_names=["admin", "users"])

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth.create_user")
    @patch("mlflow_oidc_auth.auth.populate_groups")
    @patch("mlflow_oidc_auth.auth.update_user")
    def test_handle_user_and_group_management_success_regular_user(self, mock_update_user, mock_populate_groups, mock_create_user, mock_config):
        """Test successful user and group management for regular user"""
        token = {
            "userinfo": {"email": "User@Example.COM", "name": "Regular User", "groups": ["users"]},
            "access_token": "access_token_456",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        errors = handle_user_and_group_management(token)

        assert errors == []
        # Verify email is lowercased
        mock_create_user.assert_called_once_with(username="user@example.com", display_name="Regular User", is_admin=False)
        mock_populate_groups.assert_called_once_with(group_names=["users"])
        mock_update_user.assert_called_once_with(username="user@example.com", group_names=["users"])

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_missing_email(self, mock_config):
        """Test user management fails when email is missing"""
        token = {
            "userinfo": {"name": "User Without Email"},
            "access_token": "access_token_789",
        }

        errors = handle_user_and_group_management(token)

        assert len(errors) == 1
        assert "User profile error: No email provided in OIDC userinfo." in errors

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_missing_display_name(self, mock_config):
        """Test user management fails when display name is missing"""
        token = {
            "userinfo": {"email": "user@example.com"},
            "access_token": "access_token_abc",
        }

        errors = handle_user_and_group_management(token)

        assert len(errors) == 1
        assert "User profile error: No display name provided in OIDC userinfo." in errors

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_missing_both_email_and_name(self, mock_config):
        """Test user management fails when both email and display name are missing"""
        token = {
            "userinfo": {},
            "access_token": "access_token_def",
        }

        errors = handle_user_and_group_management(token)

        assert len(errors) == 2
        assert "User profile error: No email provided in OIDC userinfo." in errors
        assert "User profile error: No display name provided in OIDC userinfo." in errors

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth.create_user")
    @patch("mlflow_oidc_auth.auth.populate_groups")
    @patch("mlflow_oidc_auth.auth.update_user")
    def test_handle_user_and_group_management_preferred_username(self, mock_update_user, mock_populate_groups, mock_create_user, mock_config):
        """Test user management with preferred_username when email is missing"""
        token = {
            "userinfo": {"preferred_username": "techaccount@example.net", "name": "Tech Account", "groups": ["users"]},
            "access_token": "access_token_ghi",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        errors = handle_user_and_group_management(token)

        assert errors == []
        mock_create_user.assert_called_once_with(username="techaccount@example.net", display_name="Tech Account", is_admin=False)

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_unauthorized_user(self, mock_config):
        """Test user management fails for unauthorized user"""
        token = {
            "userinfo": {"email": "unauthorized@example.com", "name": "Unauthorized User", "groups": ["guests"]},
            "access_token": "access_token_jkl",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        errors = handle_user_and_group_management(token)

        assert len(errors) == 1
        assert "Authorization error: User is not allowed to login." in errors

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_plugin_success(self, mock_config):
        """Test user management with group detection plugin"""
        token = {
            "userinfo": {"email": "plugin_user@example.com", "name": "Plugin User"},
            "access_token": "access_token_mno",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = "custom.group.plugin"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        # Mock the plugin module
        mock_plugin = MagicMock()
        mock_plugin.get_user_groups.return_value = ["users", "developers"]

        with patch("mlflow_oidc_auth.auth.create_user") as mock_create_user, patch("mlflow_oidc_auth.auth.populate_groups") as mock_populate_groups, patch(
            "mlflow_oidc_auth.auth.update_user"
        ) as mock_update_user, patch("importlib.import_module", return_value=mock_plugin) as mock_import_module:
            errors = handle_user_and_group_management(token)

            assert errors == []
            mock_import_module.assert_called_once_with("custom.group.plugin")
            mock_plugin.get_user_groups.assert_called_once_with("access_token_mno")
            mock_create_user.assert_called_once_with(username="plugin_user@example.com", display_name="Plugin User", is_admin=False)
            mock_populate_groups.assert_called_once_with(group_names=["users", "developers"])
            mock_update_user.assert_called_once_with(username="plugin_user@example.com", group_names=["users", "developers"])

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_plugin_import_error(self, mock_config):
        """Test user management fails when group detection plugin import fails"""
        token = {
            "userinfo": {"email": "user@example.com", "name": "User"},
            "access_token": "access_token_pqr",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = "nonexistent.plugin"

        with patch("importlib.import_module", side_effect=ImportError("Module not found")):
            errors = handle_user_and_group_management(token)

            assert len(errors) == 1
            assert "Group detection error: Failed to get user groups" in errors

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_plugin_runtime_error(self, mock_config):
        """Test user management fails when group detection plugin raises runtime error"""
        token = {
            "userinfo": {"email": "user@example.com", "name": "User"},
            "access_token": "access_token_stu",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = "failing.plugin"
        mock_plugin = MagicMock()
        mock_plugin.get_user_groups.side_effect = RuntimeError("Plugin failed")

        with patch("importlib.import_module", return_value=mock_plugin):
            errors = handle_user_and_group_management(token)

            assert len(errors) == 1
            assert "Group detection error: Failed to get user groups" in errors

    @patch("mlflow_oidc_auth.auth.config")
    def test_handle_user_and_group_management_missing_groups_attribute(self, mock_config):
        """Test user management fails when groups attribute is missing from userinfo"""
        token = {
            "userinfo": {"email": "user@example.com", "name": "User"},
            "access_token": "access_token_vwx",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"

        errors = handle_user_and_group_management(token)

        assert len(errors) == 1
        assert "Group detection error: Failed to get user groups" in errors

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth.create_user")
    @patch("mlflow_oidc_auth.auth.populate_groups")
    @patch("mlflow_oidc_auth.auth.update_user")
    def test_handle_user_and_group_management_create_user_error(self, mock_update_user, mock_populate_groups, mock_create_user, mock_config):
        """Test user management handles create_user database error"""
        token = {
            "userinfo": {"email": "user@example.com", "name": "User", "groups": ["users"]},
            "access_token": "access_token_yz1",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        mock_create_user.side_effect = Exception("Database connection failed")

        errors = handle_user_and_group_management(token)

        assert len(errors) == 1
        assert "User/group DB error: Failed to update user/groups" in errors

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth.create_user")
    @patch("mlflow_oidc_auth.auth.populate_groups")
    @patch("mlflow_oidc_auth.auth.update_user")
    def test_handle_user_and_group_management_populate_groups_error(self, mock_update_user, mock_populate_groups, mock_create_user, mock_config):
        """Test user management handles populate_groups database error"""
        token = {
            "userinfo": {"email": "user@example.com", "name": "User", "groups": ["users"]},
            "access_token": "access_token_234",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        mock_populate_groups.side_effect = Exception("Failed to populate groups")

        errors = handle_user_and_group_management(token)

        assert len(errors) == 1
        assert "User/group DB error: Failed to update user/groups" in errors

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth.create_user")
    @patch("mlflow_oidc_auth.auth.populate_groups")
    @patch("mlflow_oidc_auth.auth.update_user")
    def test_handle_user_and_group_management_update_user_error(self, mock_update_user, mock_populate_groups, mock_create_user, mock_config):
        """Test user management handles update_user database error"""
        token = {
            "userinfo": {"email": "user@example.com", "name": "User", "groups": ["users"]},
            "access_token": "access_token_567",
        }

        mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
        mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
        mock_config.OIDC_ADMIN_GROUP_NAME = "admin"
        mock_config.OIDC_GROUP_NAME = ["users"]

        mock_update_user.side_effect = Exception("Failed to update user")

        errors = handle_user_and_group_management(token)

        assert len(errors) == 1
        assert "User/group DB error: Failed to update user/groups" in errors
