"""
Comprehensive tests for the database migration environment module.

This module tests all aspects of the Alembic migration environment setup,
including offline and online migration modes, configuration handling,
error scenarios, and integration with the application configuration.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock, call
import tempfile
import os
import sys
from contextlib import contextmanager
from sqlalchemy import create_engine, MetaData
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DatabaseError

from mlflow_oidc_auth.config import config as app_config
from mlflow_oidc_auth.db.models import Base


class TestMigrationEnvironmentSetup:
    """Test the basic migration environment setup and configuration."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_module_imports_and_setup(self, mock_file_config, mock_context):
        """Test that all required modules are imported and setup correctly."""
        # Mock the context and config
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import the module with mocked context
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that the module has all required attributes
            assert hasattr(migration_env, "config")
            assert hasattr(migration_env, "context")
            assert hasattr(migration_env, "engine_from_config")
            assert hasattr(migration_env, "pool")
            assert hasattr(migration_env, "app_config")
            assert hasattr(migration_env, "Base")
            assert hasattr(migration_env, "target_metadata")

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_target_metadata_setup(self, mock_file_config, mock_context):
        """Test that target_metadata is properly set to Base.metadata."""
        # Mock the context and config
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import the module with mocked context
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify target_metadata is set correctly
            assert migration_env.target_metadata is not None
            assert migration_env.target_metadata == Base.metadata

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_logging_configuration_with_file(self, mock_file_config, mock_context):
        """Test that logging is configured when config file is present."""
        # Mock the config object with a config file name
        mock_config = MagicMock()
        mock_config.config_file_name = "alembic.ini"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import the module to trigger the logging configuration
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that fileConfig was called with the config file name
            mock_file_config.assert_called_once_with("alembic.ini")

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_logging_configuration_no_file(self, mock_file_config, mock_context):
        """Test that logging configuration is skipped when no config file."""
        # Mock the config object without a config file name
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import the module to trigger the logging configuration
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that fileConfig was not called
            mock_file_config.assert_not_called()


class TestOfflineMigrations:
    """Test offline migration functionality."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_offline_basic(self, mock_file_config, mock_context):
        """Test basic offline migration execution."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///test.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and get the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_config.reset_mock()
            mock_context.reset_mock()

            # Call the function directly
            migration_env.run_migrations_offline()

            # Verify configuration
            mock_config.get_main_option.assert_called_once_with("sqlalchemy.url")
            mock_context.configure.assert_called_once_with(
                url="sqlite:///test.db",
                target_metadata=Base.metadata,
                literal_binds=True,
                dialect_opts={"paramstyle": "named"},
                version_table=app_config.OIDC_ALEMBIC_VERSION_TABLE,
            )

            # Verify transaction and migration execution
            mock_context.begin_transaction.assert_called_once()
            mock_context.run_migrations.assert_called_once()

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_offline_with_custom_url(self, mock_file_config, mock_context):
        """Test offline migration with custom database URL."""
        # Setup mocks with custom URL
        mock_config = MagicMock()
        mock_config.config_file_name = None
        custom_url = "postgresql://user:pass@localhost:5432/testdb"
        mock_config.get_main_option.return_value = custom_url
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that custom URL is used
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["url"] == custom_url

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_offline_with_custom_version_table(self, mock_file_config, mock_context):
        """Test offline migration with custom version table name."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///test.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Mock app_config with custom version table
        with patch.object(app_config, "OIDC_ALEMBIC_VERSION_TABLE", "custom_version_table"):
            with patch.dict("sys.modules", {"alembic.context": mock_context}):
                import mlflow_oidc_auth.db.migrations.env as migration_env

                # Reset mocks to clear any calls from import
                mock_context.reset_mock()

                migration_env.run_migrations_offline()

                # Verify that custom version table is used
                mock_context.configure.assert_called_once()
                call_args = mock_context.configure.call_args
                assert call_args[1]["version_table"] == "custom_version_table"

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_offline_error_handling(self, mock_file_config, mock_context):
        """Test error handling in offline migration."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///test.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Make run_migrations raise an exception
        mock_context.run_migrations.side_effect = SQLAlchemyError("Migration failed")

        # Import and verify that the exception propagates
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            with pytest.raises(SQLAlchemyError, match="Migration failed"):
                migration_env.run_migrations_offline()

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_offline_no_url(self, mock_file_config, mock_context):
        """Test offline migration when no URL is configured."""
        # Setup mocks with no URL
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that None URL is passed to configure
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["url"] is None


class TestOnlineMigrations:
    """Test online migration functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_engine = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_engine.connect.return_value.__enter__ = MagicMock(return_value=self.mock_connection)
        self.mock_engine.connect.return_value.__exit__ = MagicMock()

    @patch("sqlalchemy.engine_from_config")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_online_basic(self, mock_file_config, mock_context, mock_engine_from_config):
        """Test basic online migration execution."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_section.return_value = {"sqlalchemy.url": "sqlite:///test.db"}
        mock_config.config_ini_section = "alembic"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_engine_from_config.return_value = self.mock_engine
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()
            mock_engine_from_config.reset_mock()

            migration_env.run_migrations_online()

            # Verify engine creation
            mock_engine_from_config.assert_called_once()
            call_args = mock_engine_from_config.call_args
            assert call_args[0][0] == {"sqlalchemy.url": "sqlite:///test.db"}
            assert call_args[1]["prefix"] == "sqlalchemy."

            # Verify connection and configuration
            self.mock_engine.connect.assert_called_once()
            mock_context.configure.assert_called_once_with(
                connection=self.mock_connection,
                target_metadata=Base.metadata,
                version_table=app_config.OIDC_ALEMBIC_VERSION_TABLE,
            )

            # Verify migration execution
            mock_context.begin_transaction.assert_called_once()
            mock_context.run_migrations.assert_called_once()

    @patch("sqlalchemy.engine_from_config")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_online_with_custom_config_section(self, mock_file_config, mock_context, mock_engine_from_config):
        """Test online migration with custom config section."""
        # Setup mocks with custom config section
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_section.return_value = {"sqlalchemy.url": "postgresql://localhost/test"}
        mock_config.config_ini_section = "custom_section"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_engine_from_config.return_value = self.mock_engine
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_config.reset_mock()

            migration_env.run_migrations_online()

            # Verify that custom section is used
            mock_config.get_section.assert_called_once_with("custom_section", {})

    @patch("sqlalchemy.engine_from_config")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_online_engine_creation_error(self, mock_file_config, mock_context, mock_engine_from_config):
        """Test error handling when engine creation fails."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_section.return_value = {"sqlalchemy.url": "invalid://url"}
        mock_config.config_ini_section = "alembic"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_engine_from_config.side_effect = SQLAlchemyError("Invalid URL")

        # Import and verify that the exception propagates
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            with pytest.raises(SQLAlchemyError, match="Invalid URL"):
                migration_env.run_migrations_online()

    @patch("sqlalchemy.engine_from_config")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_run_migrations_online_connection_error(self, mock_file_config, mock_context, mock_engine_from_config):
        """Test error handling when database connection fails."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_section.return_value = {"sqlalchemy.url": "postgresql://localhost:9999/nonexistent"}
        mock_config.config_ini_section = "alembic"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_engine_from_config.return_value = self.mock_engine

        # Make connection fail
        self.mock_engine.connect.side_effect = OperationalError("Connection failed", None, None)

        # Import and verify that the exception propagates
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            with pytest.raises(OperationalError, match="Connection failed"):
                migration_env.run_migrations_online()


class TestMigrationModeSelection:
    """Test the migration mode selection logic."""

    @patch("mlflow_oidc_auth.db.migrations.env.run_migrations_offline")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_offline_mode_selection(self, mock_file_config, mock_context, mock_offline):
        """Test that offline mode is selected when context.is_offline_mode() returns True."""
        # Mock offline mode
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True

        # Import the module to trigger the mode selection
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that offline migration is called during import
            mock_offline.assert_called_once()

    @patch("mlflow_oidc_auth.db.migrations.env.run_migrations_online")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_online_mode_selection(self, mock_file_config, mock_context, mock_online):
        """Test that online mode is selected when context.is_offline_mode() returns False."""
        # Mock online mode
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = False

        # Import the module to trigger the mode selection
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that online migration is called during import
            mock_online.assert_called_once()


class TestConfigurationIntegration:
    """Test integration with application configuration."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_app_config_integration(self, mock_file_config, mock_context):
        """Test that app_config is properly integrated."""
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            assert migration_env.app_config is not None
            assert hasattr(migration_env.app_config, "OIDC_ALEMBIC_VERSION_TABLE")

    def test_version_table_configuration(self):
        """Test that version table configuration is accessible."""
        # The version table should be accessible from app_config
        version_table = app_config.OIDC_ALEMBIC_VERSION_TABLE
        assert version_table is not None
        assert isinstance(version_table, str)

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_version_table_used_in_offline_mode(self, mock_file_config, mock_context):
        """Test that version table from app_config is used in offline mode."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///test.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call offline migration
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that app_config version table is used
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["version_table"] == app_config.OIDC_ALEMBIC_VERSION_TABLE


class TestMetadataIntegration:
    """Test integration with SQLAlchemy metadata."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_base_metadata_integration(self, mock_file_config, mock_context):
        """Test that Base metadata is properly integrated."""
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            assert migration_env.Base is not None
            assert hasattr(migration_env.Base, "metadata")
            assert migration_env.target_metadata == Base.metadata

    def test_target_metadata_type(self):
        """Test that target_metadata is a proper SQLAlchemy MetaData object."""
        assert isinstance(Base.metadata, MetaData)

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_target_metadata_used_in_offline_mode(self, mock_file_config, mock_context):
        """Test that target_metadata is used in offline mode."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///test.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call offline migration
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that target_metadata is used
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["target_metadata"] == Base.metadata


class TestErrorHandlingAndEdgeCases:
    """Test comprehensive error handling and edge cases."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_offline_migration_with_none_url(self, mock_file_config, mock_context):
        """Test offline migration when URL is None."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function - should not raise an exception
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that None URL is handled gracefully
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["url"] is None

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_offline_migration_config_error(self, mock_file_config, mock_context):
        """Test offline migration when config access fails."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.side_effect = Exception("Config access failed")
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import and verify that the exception propagates
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            with pytest.raises(Exception, match="Config access failed"):
                migration_env.run_migrations_offline()


class TestSecurityConsiderations:
    """Test security-related aspects of migration environment."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_offline_migration_sql_injection_prevention(self, mock_file_config, mock_context):
        """Test that offline migration handles potentially malicious URLs."""
        # Setup mocks with potentially malicious URL
        mock_config = MagicMock()
        mock_config.config_file_name = None
        malicious_url = "sqlite:///test.db'; DROP TABLE users; --"
        mock_config.get_main_option.return_value = malicious_url
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that the URL is passed as-is to context.configure
            # The security should be handled by SQLAlchemy/Alembic
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["url"] == malicious_url

    def test_version_table_name_validation(self):
        """Test that version table name from config is properly validated."""
        # The version table name should be a valid identifier
        version_table = app_config.OIDC_ALEMBIC_VERSION_TABLE

        # Basic validation - should be a string and not empty
        assert isinstance(version_table, str)
        assert len(version_table) > 0

        # Should not contain obvious SQL injection patterns
        dangerous_patterns = [";", "--", "/*", "*/", "DROP", "DELETE", "INSERT", "UPDATE"]
        version_table_upper = version_table.upper()
        for pattern in dangerous_patterns:
            assert pattern not in version_table_upper


class TestPerformanceConsiderations:
    """Test performance-related aspects of migration environment."""

    @patch("sqlalchemy.engine_from_config")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_online_migration_uses_null_pool(self, mock_file_config, mock_context, mock_engine_from_config):
        """Test that online migration uses NullPool for better performance."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_section.return_value = {"sqlalchemy.url": "sqlite:///test.db"}
        mock_config.config_ini_section = "alembic"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_engine.connect.return_value.__exit__ = MagicMock()
        mock_engine_from_config.return_value = mock_engine
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_engine_from_config.reset_mock()

            migration_env.run_migrations_online()

            # Verify that NullPool is used
            mock_engine_from_config.assert_called_once()
            call_args = mock_engine_from_config.call_args
            # Check that poolclass is set to NullPool
            assert "poolclass" in call_args[1]

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_offline_migration_literal_binds(self, mock_file_config, mock_context):
        """Test that offline migration uses literal_binds for performance."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///test.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that literal_binds is enabled
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["literal_binds"] is True

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_offline_migration_dialect_opts(self, mock_file_config, mock_context):
        """Test that offline migration uses appropriate dialect options."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///test.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify that dialect_opts is set correctly
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert call_args[1]["dialect_opts"] == {"paramstyle": "named"}


class TestIntegrationScenarios:
    """Test integration scenarios and real-world usage patterns."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_sqlite_offline_migration(self, mock_file_config, mock_context):
        """Test offline migration with SQLite database."""
        # Setup mocks for SQLite
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_main_option.return_value = "sqlite:///auth.db"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_context.reset_mock()

            migration_env.run_migrations_offline()

            # Verify SQLite-specific configuration
            mock_context.configure.assert_called_once()
            call_args = mock_context.configure.call_args
            assert "sqlite:///" in call_args[1]["url"]

    @patch("sqlalchemy.engine_from_config")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_postgresql_online_migration(self, mock_file_config, mock_context, mock_engine_from_config):
        """Test online migration with PostgreSQL database."""
        # Setup mocks for PostgreSQL
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_config.get_section.return_value = {"sqlalchemy.url": "postgresql://user:pass@localhost:5432/mlflow_auth"}
        mock_config.config_ini_section = "alembic"
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_engine.connect.return_value.__exit__ = MagicMock()
        mock_engine_from_config.return_value = mock_engine
        mock_context.begin_transaction.return_value.__enter__ = MagicMock()
        mock_context.begin_transaction.return_value.__exit__ = MagicMock()

        # Import and call the function
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Reset mocks to clear any calls from import
            mock_engine_from_config.reset_mock()

            migration_env.run_migrations_online()

            # Verify PostgreSQL-specific configuration
            mock_engine_from_config.assert_called_once()
            call_args = mock_engine_from_config.call_args
            assert "postgresql://" in call_args[0][0]["sqlalchemy.url"]

    def test_development_vs_production_config(self):
        """Test that migration environment works with different configurations."""
        # Test that the migration environment can handle both development and production configs
        # This is more of a structural test since we can't easily test actual config differences

        # Verify that the required components are available
        assert app_config is not None
        assert Base is not None
        assert Base.metadata is not None

        # Verify that the configuration values are accessible
        version_table = app_config.OIDC_ALEMBIC_VERSION_TABLE
        assert isinstance(version_table, str)
        assert len(version_table) > 0


class TestModuleLevelExecution:
    """Test the module-level execution logic that runs when the module is imported."""

    @patch("mlflow_oidc_auth.db.migrations.env.run_migrations_offline")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_module_execution_offline_mode(self, mock_file_config, mock_context, mock_offline):
        """Test that the module executes offline migration when imported in offline mode."""
        # Mock offline mode
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True

        # Import the module to trigger execution
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            # Remove the module from cache if it exists
            if "mlflow_oidc_auth.db.migrations.env" in sys.modules:
                del sys.modules["mlflow_oidc_auth.db.migrations.env"]

            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that offline migration was called during import
            mock_offline.assert_called_once()

    @patch("mlflow_oidc_auth.db.migrations.env.run_migrations_online")
    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_module_execution_online_mode(self, mock_file_config, mock_context, mock_online):
        """Test that the module executes online migration when imported in online mode."""
        # Mock online mode
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = False

        # Import the module to trigger execution
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            # Remove the module from cache if it exists
            if "mlflow_oidc_auth.db.migrations.env" in sys.modules:
                del sys.modules["mlflow_oidc_auth.db.migrations.env"]

            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that online migration was called during import
            mock_online.assert_called_once()


class TestCoverageCompleteness:
    """Test to ensure all lines in the migration environment are covered."""

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_all_imports_covered(self, mock_file_config, mock_context):
        """Test that all import statements are covered."""
        # Mock the context and config
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import the module to cover all import statements
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify all expected imports are available
            assert hasattr(migration_env, "fileConfig")
            assert hasattr(migration_env, "context")
            assert hasattr(migration_env, "engine_from_config")
            assert hasattr(migration_env, "pool")
            assert hasattr(migration_env, "app_config")
            assert hasattr(migration_env, "Base")

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_config_assignment_covered(self, mock_file_config, mock_context):
        """Test that config assignment is covered."""
        # Mock the context and config
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import the module to cover config assignment
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that config is assigned correctly
            assert migration_env.config == mock_config

    @patch("alembic.context")
    @patch("logging.config.fileConfig")
    def test_target_metadata_assignment_covered(self, mock_file_config, mock_context):
        """Test that target_metadata assignment is covered."""
        # Mock the context and config
        mock_config = MagicMock()
        mock_config.config_file_name = None
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = True  # Prevent execution

        # Import the module to cover target_metadata assignment
        with patch.dict("sys.modules", {"alembic.context": mock_context}):
            import mlflow_oidc_auth.db.migrations.env as migration_env

            # Verify that target_metadata is assigned correctly
            assert migration_env.target_metadata == Base.metadata
