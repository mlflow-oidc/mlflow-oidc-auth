"""
Tests for bridge.user module - Flask/FastAPI compatibility layer
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from mlflow_oidc_auth.bridge.user import get_fastapi_username, get_fastapi_admin_status


class TestGetFastAPIUsername:
    """Test cases for get_fastapi_username function"""

    def test_get_fastapi_username_success(self):
        """Test successful retrieval of username from Flask environ"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": "test_user@example.com"}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_username()
            assert result == "test_user@example.com"

    def test_get_fastapi_username_no_username_in_environ(self):
        """Test when username is not present in environ"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_none_username(self):
        """Test when username is None in environ"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": None}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_empty_username(self):
        """Test when username is empty string in environ"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": ""}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_no_environ_attribute(self):
        """Test when request has no environ attribute"""
        # Mock the Flask request import without environ attribute
        mock_request = Mock(spec=[])  # Empty spec means no attributes

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_flask_import_error(self):
        """Test when Flask import fails"""
        with patch.dict("sys.modules", {"flask": None}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_attribute_error(self):
        """Test when accessing environ raises AttributeError"""
        # Mock the Flask request that raises AttributeError when environ.get is called
        mock_request = Mock()
        mock_request.environ.get.side_effect = AttributeError("No environ")

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_generic_exception(self):
        """Test when a generic exception occurs during username retrieval"""
        # Mock the Flask request that raises a generic exception
        mock_request = Mock()
        mock_request.environ.get = Mock(side_effect=RuntimeError("Generic error"))

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()


class TestGetFastAPIAdminStatus:
    """Test cases for get_fastapi_admin_status function"""

    def test_get_fastapi_admin_status_true(self):
        """Test successful retrieval of admin status when user is admin"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.is_admin": True}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is True

    def test_get_fastapi_admin_status_false(self):
        """Test successful retrieval of admin status when user is not admin"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.is_admin": False}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_default_false(self):
        """Test default admin status when not present in environ"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_no_environ_attribute(self):
        """Test when request has no environ attribute"""
        # Mock the Flask request import without environ attribute
        mock_request = Mock(spec=[])  # Empty spec means no attributes

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_flask_import_error(self):
        """Test when Flask import fails"""
        with patch.dict("sys.modules", {"flask": None}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_attribute_error(self):
        """Test when accessing environ raises AttributeError"""
        # Mock the Flask request that raises AttributeError when environ.get is called
        mock_request = Mock()
        mock_request.environ.get.side_effect = AttributeError("No environ")

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_generic_exception(self):
        """Test when a generic exception occurs during admin status retrieval"""
        # Mock the Flask request that raises a generic exception
        mock_request = Mock()
        mock_request.environ.get = Mock(side_effect=RuntimeError("Generic error"))

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_string_true(self):
        """Test admin status with string 'true' value"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.is_admin": "true"}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result == "true"  # Should return the actual value, not convert to boolean

    def test_get_fastapi_admin_status_integer_one(self):
        """Test admin status with integer 1 value"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.is_admin": 1}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result == 1  # Should return the actual value


class TestBridgeIntegration:
    """Integration tests for bridge functionality"""

    def test_bridge_data_transformation_complete_user_data(self):
        """Test complete user data transformation through bridge"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": "admin@example.com", "mlflow_oidc_auth.is_admin": True}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            is_admin = get_fastapi_admin_status()

            assert username == "admin@example.com"
            assert is_admin is True

    def test_bridge_data_transformation_partial_user_data(self):
        """Test partial user data transformation through bridge"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": "user@example.com"}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            is_admin = get_fastapi_admin_status()

            assert username == "user@example.com"
            assert is_admin is False  # Default value

    def test_bridge_error_handling_consistency(self):
        """Test error handling consistency between functions"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Username function should raise exception
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

            # Admin status function should return False (graceful degradation)
            result = get_fastapi_admin_status()
            assert result is False

    def test_bridge_performance_with_multiple_calls(self):
        """Test bridge performance with multiple rapid calls"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": "perf_user@example.com", "mlflow_oidc_auth.is_admin": True}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Make multiple calls to test performance
            usernames = []
            admin_statuses = []

            for _ in range(100):
                usernames.append(get_fastapi_username())
                admin_statuses.append(get_fastapi_admin_status())

            # Verify all calls returned consistent results
            assert all(username == "perf_user@example.com" for username in usernames)
            assert all(status is True for status in admin_statuses)

    def test_bridge_reliability_with_environ_changes(self):
        """Test bridge reliability when environ changes between calls"""
        # Mock the Flask request import
        mock_request1 = Mock()
        mock_request1.environ = {"mlflow_oidc_auth.username": "user1@example.com"}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request1)}):
            username1 = get_fastapi_username()
            assert username1 == "user1@example.com"

        # Change environ
        mock_request2 = Mock()
        mock_request2.environ = {"mlflow_oidc_auth.username": "user2@example.com"}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request2)}):
            username2 = get_fastapi_username()
            assert username2 == "user2@example.com"

        # Verify functions adapt to changes
        assert username1 != username2


class TestBridgeErrorHandling:
    """Test error handling and edge cases in bridge functionality"""

    def test_bridge_with_malformed_environ_data(self):
        """Test bridge behavior with malformed environ data"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": {"invalid": "object"}, "mlflow_oidc_auth.is_admin": ["invalid", "list"]}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Username should still be retrieved (even if it's an object)
            username = get_fastapi_username()
            assert username == {"invalid": "object"}

            # Admin status should be retrieved (even if it's a list)
            admin_status = get_fastapi_admin_status()
            assert admin_status == ["invalid", "list"]

    def test_bridge_with_unicode_username(self):
        """Test bridge behavior with unicode characters in username"""
        # Mock the Flask request import
        unicode_username = "üser@éxample.com"
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": unicode_username}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            assert username == unicode_username

    def test_bridge_with_very_long_username(self):
        """Test bridge behavior with very long username"""
        # Mock the Flask request import
        long_username = "a" * 1000 + "@example.com"
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": long_username}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            assert username == long_username
            assert len(username) == 1012  # 1000 + '@example.com'

    def test_bridge_external_system_integration_simulation(self):
        """Test bridge integration with external systems (simulated)"""
        # Mock the Flask request import
        external_auth_data = {
            "mlflow_oidc_auth.username": "external_user@corp.com",
            "mlflow_oidc_auth.is_admin": True,
            "external_system_id": "ext_12345",
            "external_roles": ["admin", "user"],
        }

        mock_request = Mock()
        mock_request.environ = external_auth_data

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Bridge should extract only the relevant data
            username = get_fastapi_username()
            is_admin = get_fastapi_admin_status()

            assert username == "external_user@corp.com"
            assert is_admin is True

    @patch("mlflow_oidc_auth.bridge.user.logger")
    def test_bridge_logging_behavior(self, mock_logger):
        """Test that bridge functions log appropriately"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": "log_user@example.com", "mlflow_oidc_auth.is_admin": True}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Call functions
            get_fastapi_username()
            get_fastapi_admin_status()

            # Verify debug logging was called
            assert mock_logger.debug.call_count >= 2

            # Verify log messages contain expected content
            log_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
            assert any("Retrieved FastAPI username" in msg for msg in log_calls)
            assert any("Retrieved FastAPI admin status" in msg for msg in log_calls)


class TestBridgeDataValidation:
    """Test data validation and transformation in bridge functionality"""

    def test_bridge_username_whitespace_handling(self):
        """Test bridge behavior with whitespace in username"""
        # Mock the Flask request import
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth.username": "  user@example.com  "}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            assert username == "  user@example.com  "  # Should preserve whitespace

    def test_bridge_admin_status_various_falsy_values(self):
        """Test admin status with various falsy values"""
        falsy_values = [False, 0, "", None, [], {}]

        for falsy_value in falsy_values:
            mock_request = Mock()
            mock_request.environ = {"mlflow_oidc_auth.is_admin": falsy_value}

            with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
                result = get_fastapi_admin_status()
                assert result == falsy_value  # Should return the actual falsy value

    def test_bridge_admin_status_various_truthy_values(self):
        """Test admin status with various truthy values"""
        truthy_values = [True, 1, "true", "admin", [1], {"admin": True}]

        for truthy_value in truthy_values:
            mock_request = Mock()
            mock_request.environ = {"mlflow_oidc_auth.is_admin": truthy_value}

            with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
                result = get_fastapi_admin_status()
                assert result == truthy_value  # Should return the actual truthy value

    def test_bridge_environ_key_case_sensitivity(self):
        """Test that bridge is case-sensitive for environ keys"""
        # Mock the Flask request import with wrong case
        mock_request = Mock()
        mock_request.environ = {"MLFLOW_OIDC_AUTH.USERNAME": "user@example.com", "mlflow_oidc_auth.IS_ADMIN": True}  # Wrong case  # Wrong case

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Should not find the username with wrong case
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

            # Should return default False for admin status
            result = get_fastapi_admin_status()
            assert result is False

    def test_bridge_concurrent_access_simulation(self):
        """Test bridge behavior under simulated concurrent access"""
        import threading
        import time

        results = []
        errors = []

        def worker(user_id):
            try:
                mock_request = Mock()
                mock_request.environ = {
                    "mlflow_oidc_auth.username": f"user{user_id}@example.com",
                    "mlflow_oidc_auth.is_admin": user_id % 2 == 0,  # Even users are admin
                }

                with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
                    username = get_fastapi_username()
                    is_admin = get_fastapi_admin_status()
                    results.append((user_id, username, is_admin))
            except Exception as e:
                errors.append((user_id, str(e)))

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 10

        # Verify each result is correct
        for user_id, username, is_admin in results:
            assert username == f"user{user_id}@example.com"
            assert is_admin == (user_id % 2 == 0)
