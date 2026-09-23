"""
Tests for bridge.user module - Flask/FastAPI compatibility layer

Updated to use AuthContext pattern instead of individual environ keys.
"""

import pytest
from unittest.mock import Mock, patch
from mlflow_oidc_auth.bridge.user import (
    set_auth_context,
    clear_auth_context,
    get_auth_context,
    get_fastapi_username,
    get_fastapi_admin_status,
    get_request_workspace,
)
from mlflow_oidc_auth.entities.auth_context import AuthContext


class TestGetAuthContext:
    """Test cases for get_auth_context function"""

    def test_get_auth_context_success(self):
        """Test successful retrieval of AuthContext from Flask environ"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="test_user@example.com", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_auth_context()
            assert isinstance(result, AuthContext)
            assert result.username == "test_user@example.com"
            assert result.is_admin is False
            assert result.workspace is None

    def test_get_auth_context_with_workspace(self):
        """Test retrieval of AuthContext with workspace set"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="test@example.com", is_admin=True, workspace="my-ws")}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_auth_context()
            assert result.workspace == "my-ws"

    def test_get_auth_context_missing_environ(self):
        """Test when mlflow_oidc_auth is not in environ"""
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve AuthContext"):
                get_auth_context()

    def test_get_auth_context_not_auth_context_type(self):
        """Test when environ has wrong type (e.g. dict instead of AuthContext)"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": {"username": "user", "is_admin": False}}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve AuthContext"):
                get_auth_context()

    def test_get_auth_context_no_environ_attribute(self):
        """Test when request has no environ attribute"""
        mock_request = Mock(spec=[])

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve AuthContext"):
                get_auth_context()

    def test_get_auth_context_flask_import_error(self):
        """Test when Flask import fails"""
        with patch.dict("sys.modules", {"flask": None}):
            with pytest.raises(Exception, match="Could not retrieve AuthContext"):
                get_auth_context()


class TestGetFastAPIUsername:
    """Test cases for get_fastapi_username function"""

    def test_get_fastapi_username_success(self):
        """Test successful retrieval of username from Flask environ"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="test_user@example.com", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_username()
            assert result == "test_user@example.com"

    def test_get_fastapi_username_no_auth_context_in_environ(self):
        """Test when AuthContext is not present in environ"""
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_empty_username(self):
        """Test when username is empty string in AuthContext"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_no_environ_attribute(self):
        """Test when request has no environ attribute"""
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
        mock_request = Mock()
        mock_request.environ.get.side_effect = AttributeError("No environ")

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

    def test_get_fastapi_username_generic_exception(self):
        """Test when a generic exception occurs during username retrieval"""
        mock_request = Mock()
        mock_request.environ.get = Mock(side_effect=RuntimeError("Generic error"))

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()


class TestGetFastAPIAdminStatus:
    """Test cases for get_fastapi_admin_status function"""

    def test_get_fastapi_admin_status_true(self):
        """Test successful retrieval of admin status when user is admin"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="admin@example.com", is_admin=True)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is True

    def test_get_fastapi_admin_status_false(self):
        """Test successful retrieval of admin status when user is not admin"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="user@example.com", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_default_false(self):
        """Test default admin status when AuthContext not present in environ"""
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_no_environ_attribute(self):
        """Test when request has no environ attribute"""
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
        mock_request = Mock()
        mock_request.environ.get.side_effect = AttributeError("No environ")

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False

    def test_get_fastapi_admin_status_generic_exception(self):
        """Test when a generic exception occurs during admin status retrieval"""
        mock_request = Mock()
        mock_request.environ.get = Mock(side_effect=RuntimeError("Generic error"))

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_fastapi_admin_status()
            assert result is False


class TestGetRequestWorkspace:
    """Test cases for get_request_workspace function"""

    def test_get_request_workspace_present(self):
        """Test workspace retrieval when workspace is set in AuthContext"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="user@example.com", is_admin=False, workspace="my-workspace")}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_request_workspace()
            assert result == "my-workspace"

    def test_get_request_workspace_none(self):
        """Test workspace retrieval when workspace is None in AuthContext"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="user@example.com", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_request_workspace()
            assert result is None

    def test_get_request_workspace_no_auth_context(self):
        """Test workspace retrieval when no AuthContext in environ"""
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_request_workspace()
            assert result is None

    def test_get_request_workspace_flask_import_error(self):
        """Test workspace retrieval when Flask import fails"""
        with patch.dict("sys.modules", {"flask": None}):
            result = get_request_workspace()
            assert result is None


class TestBridgeIntegration:
    """Integration tests for bridge functionality"""

    def test_bridge_data_transformation_complete_user_data(self):
        """Test complete user data transformation through bridge"""
        mock_request = Mock()
        mock_request.environ = {
            "mlflow_oidc_auth": AuthContext(username="admin@example.com", is_admin=True),
        }

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            is_admin = get_fastapi_admin_status()

            assert username == "admin@example.com"
            assert is_admin is True

    def test_bridge_data_transformation_with_workspace(self):
        """Test complete user data transformation including workspace"""
        mock_request = Mock()
        mock_request.environ = {
            "mlflow_oidc_auth": AuthContext(username="user@example.com", is_admin=False, workspace="prod-ws"),
        }

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            is_admin = get_fastapi_admin_status()
            workspace = get_request_workspace()

            assert username == "user@example.com"
            assert is_admin is False
            assert workspace == "prod-ws"

    def test_bridge_error_handling_consistency(self):
        """Test error handling consistency between functions"""
        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Username function should raise exception
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

            # Admin status function should return False (graceful degradation)
            result = get_fastapi_admin_status()
            assert result is False

            # Workspace function should return None (graceful degradation)
            workspace = get_request_workspace()
            assert workspace is None

    def test_bridge_performance_with_multiple_calls(self):
        """Test bridge performance with multiple rapid calls"""
        mock_request = Mock()
        mock_request.environ = {
            "mlflow_oidc_auth": AuthContext(username="perf_user@example.com", is_admin=True),
        }

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
        mock_request1 = Mock()
        mock_request1.environ = {"mlflow_oidc_auth": AuthContext(username="user1@example.com", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request1)}):
            username1 = get_fastapi_username()
            assert username1 == "user1@example.com"

        # Change environ
        mock_request2 = Mock()
        mock_request2.environ = {"mlflow_oidc_auth": AuthContext(username="user2@example.com", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request2)}):
            username2 = get_fastapi_username()
            assert username2 == "user2@example.com"

        # Verify functions adapt to changes
        assert username1 != username2


class TestBridgeErrorHandling:
    """Test error handling and edge cases in bridge functionality"""

    def test_bridge_with_unicode_username(self):
        """Test bridge behavior with unicode characters in username"""
        unicode_username = "üser@éxample.com"
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username=unicode_username, is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            assert username == unicode_username

    def test_bridge_with_very_long_username(self):
        """Test bridge behavior with very long username"""
        long_username = "a" * 1000 + "@example.com"
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username=long_username, is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            assert username == long_username
            assert len(username) == 1012  # 1000 + '@example.com'

    def test_bridge_external_system_integration_simulation(self):
        """Test bridge integration with external systems (simulated)"""
        mock_request = Mock()
        mock_request.environ = {
            "mlflow_oidc_auth": AuthContext(username="external_user@corp.com", is_admin=True),
            "external_system_id": "ext_12345",
            "external_roles": ["admin", "user"],
        }

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Bridge should extract only the relevant data
            username = get_fastapi_username()
            is_admin = get_fastapi_admin_status()

            assert username == "external_user@corp.com"
            assert is_admin is True

    @patch("mlflow_oidc_auth.bridge.user.logger")
    def test_bridge_logging_behavior(self, mock_logger):
        """Test that bridge functions log appropriately"""
        mock_request = Mock()
        mock_request.environ = {
            "mlflow_oidc_auth": AuthContext(username="log_user@example.com", is_admin=True),
        }

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Call functions
            get_fastapi_username()
            get_fastapi_admin_status()

            # Verify debug logging was called (get_auth_context logs on retrieval)
            assert mock_logger.debug.call_count >= 2

            # Verify log messages contain expected content
            log_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
            assert any("Retrieved AuthContext from Flask environ" in msg for msg in log_calls)


class TestContextVarFallback:
    """Test ContextVar fallback for FastAPI-native routes (no Flask context)."""

    def setup_method(self):
        clear_auth_context()

    def teardown_method(self):
        clear_auth_context()

    def test_get_auth_context_from_contextvar(self):
        """When Flask is unavailable, get_auth_context falls back to the ContextVar."""
        ctx = AuthContext(username="fastapi@example.com", is_admin=False, workspace="team-ws")
        set_auth_context(ctx)

        with patch.dict("sys.modules", {"flask": None}):
            result = get_auth_context()
            assert result is ctx
            assert result.username == "fastapi@example.com"
            assert result.workspace == "team-ws"

    def test_get_request_workspace_from_contextvar(self):
        """get_request_workspace returns workspace from ContextVar when Flask is unavailable"""
        set_auth_context(AuthContext(username="user@example.com", is_admin=False, workspace="my-ws"))

        with patch.dict("sys.modules", {"flask": None}):
            assert get_request_workspace() == "my-ws"

    def test_get_request_workspace_none_from_contextvar(self):
        """get_request_workspace returns None when ContextVar has no workspace."""
        set_auth_context(AuthContext(username="user@example.com", is_admin=False))

        with patch.dict("sys.modules", {"flask": None}):
            assert get_request_workspace() is None

    def test_contextvar_cleared(self):
        """After clear_auth_context, get_auth_context raises."""
        set_auth_context(AuthContext(username="user@example.com", is_admin=False))
        clear_auth_context()

        with patch.dict("sys.modules", {"flask": None}):
            with pytest.raises(Exception, match="Could not retrieve AuthContext"):
                get_auth_context()

    def test_flask_environ_takes_precedence(self):
        """Flask env is preferred over ContextVar when both are available."""
        flask_ctx = AuthContext(username="flask@example.com", is_admin=False, workspace="flask-ws")
        cv_ctx = AuthContext(username="cv@example.com", is_admin=False, workspace="cv-ws")
        set_auth_context(cv_ctx)

        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": flask_ctx}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_auth_context()
            assert result.username == "flask@example.com"
            assert result.workspace == "flask-ws"

    def test_contextvar_used_when_flask_environ_empty(self):
        """ContextVar is used when Flask environ exists but has no AuthContext."""
        cv_ctx = AuthContext(username="cv@example.com", is_admin=False, workspace="cv-ws")
        set_auth_context(cv_ctx)

        mock_request = Mock()
        mock_request.environ = {}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            result = get_auth_context()
            assert result.username == "cv@example.com"

    def test_get_fastapi_username_from_context_var(self):
        """get_fastapi_username works via ContextVar fallback."""
        set_auth_context(AuthContext(username="fastapi@example.com", is_admin=False))

        with patch.dict("sys.modules", {"flask": None}):
            assert get_fastapi_username() == "fastapi@example.com"

    def test_get_fastapi_admin_status_from_context_var(self):
        """get_fastapi_admin_status works via ContextVar fallback."""
        set_auth_context(AuthContext(username="fastapi@example.com", is_admin=True))

        with patch.dict("sys.modules", {"flask": None}):
            assert get_fastapi_admin_status() is True


class TestBridgeDataValidation:
    """Test data validation and transformation in bridge functionality"""

    def test_bridge_username_whitespace_handling(self):
        """Test bridge behavior with whitespace in username"""
        mock_request = Mock()
        mock_request.environ = {"mlflow_oidc_auth": AuthContext(username="  user@example.com  ", is_admin=False)}

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            username = get_fastapi_username()
            assert username == "  user@example.com  "  # Should preserve whitespace

    def test_bridge_environ_key_case_sensitivity(self):
        """Test that bridge is case-sensitive for environ keys"""
        # Wrong key in environ — AuthContext not found
        mock_request = Mock()
        mock_request.environ = {
            "MLFLOW_OIDC_AUTH": AuthContext(username="user@example.com", is_admin=True),
        }

        with patch.dict("sys.modules", {"flask": Mock(request=mock_request)}):
            # Should not find the AuthContext with wrong case
            with pytest.raises(Exception, match="Could not retrieve FastAPI username"):
                get_fastapi_username()

            # Should return default False for admin status
            result = get_fastapi_admin_status()
            assert result is False

    def test_bridge_concurrent_access_simulation(self):
        """Test bridge behavior under simulated concurrent access"""
        import threading

        results = []
        errors = []

        def worker(user_id):
            try:
                mock_request = Mock()
                mock_request.environ = {
                    "mlflow_oidc_auth": AuthContext(
                        username=f"user{user_id}@example.com",
                        is_admin=user_id % 2 == 0,
                    ),
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
