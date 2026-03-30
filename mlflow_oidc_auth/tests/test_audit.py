"""
Tests for the audit logging module.

Covers emit_audit_event, the enable/disable flag, log-level resolution,
and the singleton audit logger behaviour.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import mlflow_oidc_auth.audit as audit_module
from mlflow_oidc_auth.audit import (
    _get_audit_logger,
    _is_enabled,
    _resolve_level,
    emit_audit_event,
)


class TestEmitAuditEvent:
    """Test cases for the emit_audit_event function."""

    def setup_method(self):
        """Reset the audit logger singleton before each test."""
        audit_module._audit_logger = None

    def teardown_method(self):
        """Clean up the audit logger singleton after each test."""
        audit_module._audit_logger = None

    def test_emit_basic_event(self):
        """Test that a basic audit event is emitted with correct JSON structure."""
        with (
            patch.object(audit_module, "_is_enabled", return_value=True),
            patch.object(audit_module, "_get_audit_logger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            emit_audit_event(
                "permission.create",
                "admin_user",
                resource_type="experiment_permission",
                resource_id="123",
                detail={"username": "test_user", "permission": "READ"},
            )

            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            level = call_args[0][0]
            message = call_args[0][1]

            record = json.loads(message)
            assert record["event"] == "permission.create"
            assert record["actor"] == "admin_user"
            assert record["resource_type"] == "experiment_permission"
            assert record["resource_id"] == "123"
            assert record["detail"] == {"username": "test_user", "permission": "READ"}
            assert record["status"] == "success"
            assert "timestamp" in record

    def test_emit_event_with_denied_status(self):
        """Test that denied status is correctly included."""
        with (
            patch.object(audit_module, "_is_enabled", return_value=True),
            patch.object(audit_module, "_get_audit_logger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            emit_audit_event(
                "auth.login",
                "unknown_user",
                status="denied",
            )

            message = mock_logger.log.call_args[0][1]
            record = json.loads(message)
            assert record["status"] == "denied"
            assert record["detail"] == {}
            assert record["resource_type"] is None
            assert record["resource_id"] is None

    def test_emit_event_disabled(self):
        """Test that no event is emitted when audit logging is disabled."""
        with (
            patch.object(audit_module, "_is_enabled", return_value=False),
            patch.object(audit_module, "_get_audit_logger") as mock_get_logger,
        ):
            emit_audit_event("permission.create", "admin_user")
            mock_get_logger.assert_not_called()

    def test_emit_event_defaults_detail_to_empty_dict(self):
        """Test that detail defaults to an empty dict when not provided."""
        with (
            patch.object(audit_module, "_is_enabled", return_value=True),
            patch.object(audit_module, "_get_audit_logger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            emit_audit_event("test.event", "actor")

            message = mock_logger.log.call_args[0][1]
            record = json.loads(message)
            assert record["detail"] == {}


class TestIsEnabled:
    """Test cases for the _is_enabled function."""

    def test_enabled_by_default_when_config_unavailable(self):
        """Test that audit logging is enabled when config is not available."""
        with patch.object(audit_module, "_is_enabled", wraps=audit_module._is_enabled):
            # Force config import to fail
            with patch.dict("sys.modules", {"mlflow_oidc_auth.config": None}):
                result = _is_enabled()
                assert result is True

    def test_enabled_when_config_says_true(self):
        """Test that audit logging is enabled when config.AUDIT_LOG_ENABLED is True."""
        mock_config = MagicMock()
        mock_config.AUDIT_LOG_ENABLED = True

        with patch("mlflow_oidc_auth.audit.config", mock_config, create=True):
            # We need to call the real function, but it imports config internally
            # So let's patch at the point of import
            mock_module = MagicMock()
            mock_module.config = mock_config
            with patch.dict("sys.modules", {"mlflow_oidc_auth.config": mock_module}):
                result = _is_enabled()
                assert result is True

    def test_disabled_when_config_says_false(self):
        """Test that audit logging is disabled when config.AUDIT_LOG_ENABLED is False."""
        mock_config = MagicMock()
        mock_config.AUDIT_LOG_ENABLED = False

        mock_module = MagicMock()
        mock_module.config = mock_config
        with patch.dict("sys.modules", {"mlflow_oidc_auth.config": mock_module}):
            result = _is_enabled()
            assert result is False


class TestResolveLevel:
    """Test cases for the _resolve_level function."""

    def test_default_level_is_info(self):
        """Test that default level is INFO when config is unavailable."""
        with patch.dict("sys.modules", {"mlflow_oidc_auth.config": None}):
            result = _resolve_level()
            assert result == logging.INFO

    def test_level_warning(self):
        """Test WARNING level resolution."""
        mock_config = MagicMock()
        mock_config.AUDIT_LOG_LEVEL = "WARNING"

        mock_module = MagicMock()
        mock_module.config = mock_config
        with patch.dict("sys.modules", {"mlflow_oidc_auth.config": mock_module}):
            result = _resolve_level()
            assert result == logging.WARNING

    def test_level_info(self):
        """Test INFO level resolution."""
        mock_config = MagicMock()
        mock_config.AUDIT_LOG_LEVEL = "INFO"

        mock_module = MagicMock()
        mock_module.config = mock_config
        with patch.dict("sys.modules", {"mlflow_oidc_auth.config": mock_module}):
            result = _resolve_level()
            assert result == logging.INFO

    def test_invalid_level_defaults_to_info(self):
        """Test that an invalid level string defaults to INFO."""
        mock_config = MagicMock()
        mock_config.AUDIT_LOG_LEVEL = "INVALID_LEVEL"

        mock_module = MagicMock()
        mock_module.config = mock_config
        with patch.dict("sys.modules", {"mlflow_oidc_auth.config": mock_module}):
            result = _resolve_level()
            assert result == logging.INFO


class TestGetAuditLogger:
    """Test cases for the _get_audit_logger function."""

    def setup_method(self):
        """Reset the audit logger singleton before each test."""
        audit_module._audit_logger = None

    def teardown_method(self):
        """Clean up the audit logger singleton after each test."""
        audit_module._audit_logger = None

    def test_returns_logger_with_correct_name(self):
        """Test that the audit logger has the correct name."""
        logger = _get_audit_logger()
        assert logger.name == "mlflow_oidc_auth.audit"

    def test_singleton_behavior(self):
        """Test that the audit logger is a singleton."""
        logger1 = _get_audit_logger()
        logger2 = _get_audit_logger()
        assert logger1 is logger2

    def test_logger_has_handler(self):
        """Test that the audit logger has at least one handler."""
        logger = _get_audit_logger()
        assert len(logger.handlers) >= 1

    def test_logger_does_not_propagate(self):
        """Test that the audit logger does not propagate."""
        logger = _get_audit_logger()
        assert logger.propagate is False

    def test_logger_level_is_debug(self):
        """Test that the audit logger level is DEBUG (accepts all, handler decides)."""
        logger = _get_audit_logger()
        assert logger.level == logging.DEBUG

    def test_no_duplicate_handlers(self):
        """Test that calling _get_audit_logger multiple times doesn't duplicate handlers."""
        logger1 = _get_audit_logger()
        handler_count = len(logger1.handlers)
        # Reset singleton to force re-initialization
        audit_module._audit_logger = None
        logger2 = _get_audit_logger()
        # The logger object from logging.getLogger is the same, so handlers accumulate
        # unless we guard against it. The code checks `if not _audit_logger.handlers:`.
        # But since we're getting the same named logger, handlers from first call persist.
        # After reset, the code checks handlers and won't add a new one.
        assert len(logger2.handlers) == handler_count
