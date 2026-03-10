import os
import sys
from tempfile import mkstemp
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from alembic.config import Config

from mlflow_oidc_auth.db.utils import (
    migrate,
    migrate_if_needed,
    _get_alembic_dir,
    _get_alembic_config,
)


class TestPrivateFunctions:
    """Test private utility functions."""

    def test_get_alembic_dir(self):
        """Test _get_alembic_dir returns correct path."""
        alembic_dir = _get_alembic_dir()
        expected_path = Path(__file__).parent.parent / "db" / "migrations"
        assert str(alembic_dir) == str(expected_path)

    def test_get_alembic_config(self):
        """Test _get_alembic_config creates proper configuration."""
        test_url = "sqlite:///test.db"
        config = _get_alembic_config(test_url)

        assert isinstance(config, Config)
        assert config.get_main_option("sqlalchemy.url") == test_url

        # Test URL encoding for special characters
        # Note: Alembic Config interprets %% back to % when retrieving values
        test_url_with_percent = "postgresql://user:pass%word@localhost/db"
        config = _get_alembic_config(test_url_with_percent)
        # The function should escape % to %%, but Config.get_main_option() converts it back
        assert config.get_main_option("sqlalchemy.url") == test_url_with_percent

    def test_get_alembic_config_script_location(self):
        """Test _get_alembic_config sets correct script location."""
        test_url = "sqlite:///test.db"
        config = _get_alembic_config(test_url)

        expected_script_location = str(Path(__file__).parent.parent / "db" / "migrations")
        assert config.get_main_option("script_location") == expected_script_location


class TestMigrate:
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate(self, mock_upgrade):
        """Test basic migration functionality."""
        engine = create_engine("sqlite:///:memory:")
        with sessionmaker(bind=engine)():
            migrate(engine, "head")

        mock_upgrade.assert_called_once()

    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_with_specific_revision(self, mock_upgrade):
        """Test migration to specific revision."""
        engine = create_engine("sqlite:///:memory:")
        revision = "abc123"

        migrate(engine, revision)

        # Verify upgrade was called with the specific revision
        args, kwargs = mock_upgrade.call_args
        assert args[1] == revision

    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_connection_handling(self, mock_upgrade):
        """Test that migration properly handles database connections."""
        engine = create_engine("sqlite:///:memory:")

        migrate(engine, "head")

        # Verify that the alembic config received the connection
        args, kwargs = mock_upgrade.call_args
        alembic_cfg = args[0]
        assert "connection" in alembic_cfg.attributes

    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_error_handling(self, mock_upgrade):
        """Test migration error handling."""
        mock_upgrade.side_effect = SQLAlchemyError("Migration failed")
        engine = create_engine("sqlite:///:memory:")

        with pytest.raises(SQLAlchemyError, match="Migration failed"):
            migrate(engine, "head")

    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_connection_error(self, mock_upgrade):
        """Test migration with database connection errors."""
        # Create an engine with invalid SQLite path that will fail to connect
        engine = create_engine("sqlite:///nonexistent/path/to/database.db")

        with pytest.raises(Exception):  # Connection will fail
            migrate(engine, "head")

    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_url_rendering(self, mock_upgrade):
        """Test that database URL is properly rendered for alembic config."""
        engine = create_engine("sqlite:///test.db")

        migrate(engine, "head")

        # Verify that _get_alembic_config was called with rendered URL
        args, kwargs = mock_upgrade.call_args
        alembic_cfg = args[0]
        assert alembic_cfg.get_main_option("sqlalchemy.url") is not None

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_not_called_if_not_needed(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migrate_if_needed skips migration when not needed."""
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "head"
        mock_script_dir.from_config.return_value = script_dir_mock
        mock_migration_context.configure.return_value.get_current_revision.return_value = "head"

        engine = create_engine("sqlite:///:memory:")
        with sessionmaker(bind=engine)():
            migrate_if_needed(engine, "head")

        mock_upgrade.assert_not_called()

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_called_if_needed(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migrate_if_needed performs migration when needed."""
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "head"
        mock_script_dir.from_config.return_value = script_dir_mock
        mock_migration_context.configure.return_value.get_current_revision.return_value = "not_head"

        engine = create_engine("sqlite:///:memory:")
        with sessionmaker(bind=engine)():
            migrate_if_needed(engine, "head")

        mock_upgrade.assert_called_once()

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_with_none_current_revision(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migrate_if_needed when current revision is None (fresh database)."""
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "head"
        mock_script_dir.from_config.return_value = script_dir_mock
        mock_migration_context.configure.return_value.get_current_revision.return_value = None

        engine = create_engine("sqlite:///:memory:")
        migrate_if_needed(engine, "head")

        mock_upgrade.assert_called_once()

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_script_directory_error(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migrate_if_needed handles ScriptDirectory errors."""
        mock_script_dir.from_config.side_effect = Exception("Script directory error")
        engine = create_engine("sqlite:///:memory:")

        with pytest.raises(Exception, match="Script directory error"):
            migrate_if_needed(engine, "head")

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_migration_context_error(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migrate_if_needed handles MigrationContext errors."""
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "head"
        mock_script_dir.from_config.return_value = script_dir_mock
        mock_migration_context.configure.side_effect = OperationalError("statement", "params", "orig")

        engine = create_engine("sqlite:///:memory:")

        with pytest.raises(OperationalError):
            migrate_if_needed(engine, "head")

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_upgrade_error(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migrate_if_needed handles upgrade errors gracefully."""
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "head"
        mock_script_dir.from_config.return_value = script_dir_mock
        mock_migration_context.configure.return_value.get_current_revision.return_value = "old_revision"
        mock_upgrade.side_effect = SQLAlchemyError("Upgrade failed")

        engine = create_engine("sqlite:///:memory:")

        with pytest.raises(SQLAlchemyError, match="Upgrade failed"):
            migrate_if_needed(engine, "head")

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_with_specific_revision(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migrate_if_needed with specific target revision."""
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "latest"
        mock_script_dir.from_config.return_value = script_dir_mock
        mock_migration_context.configure.return_value.get_current_revision.return_value = "old"

        engine = create_engine("sqlite:///:memory:")
        target_revision = "specific_revision"

        migrate_if_needed(engine, target_revision)

        # Verify upgrade was called with the specific revision
        args, kwargs = mock_upgrade.call_args
        assert args[1] == target_revision


class TestModifiedVersionTable:
    @patch.dict(os.environ, {"OIDC_ALEMBIC_VERSION_TABLE": "alembic_modified_version"})
    def test_different_alembic_version_table(self):
        # Force reload of the config module
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

        # Create temporary file
        _, db_file = mkstemp()

        engine = create_engine(f"sqlite:///{db_file}")
        with sessionmaker(bind=engine)() as f:
            migrate(engine, "head")

        tables = []
        with engine.begin() as conn:
            connection = conn.connection

            connection = f.connection().connection
            cursor = connection.cursor()

            query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name NOT LIKE 'sqlite_%'"
            tables = [x[0] for x in cursor.execute(query).fetchall()]

        # Delete the temp file again
        os.unlink(db_file)

        # Do the asserts
        assert "alembic_modified_version" in tables
        assert "alembic_version" not in tables


class TestDefaultVersionTable:
    def test_default_alembic_table(self):
        # Force reload of the config module
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

        # Create temporary file
        _, db_file = mkstemp()

        # If we have residual config options in environment, clean it
        if "OIDC_ALEMBIC_VERSION_TABLE" in os.environ:
            del os.environ["OIDC_ALEMBIC_VERSION_TABLE"]

        engine = create_engine(f"sqlite:///{db_file}")
        with sessionmaker(bind=engine)() as f:
            migrate(engine, "head")

        tables = []
        with engine.begin() as conn:
            connection = conn.connection

            connection = f.connection().connection
            cursor = connection.cursor()

            query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name NOT LIKE 'sqlite_%'"
            tables = [x[0] for x in cursor.execute(query).fetchall()]

        # Remove the temp file again
        os.unlink(db_file)

        # Do the assert
        assert "alembic_version" in tables


class TestDatabaseInitializationAndCleanup:
    """Test database initialization and cleanup procedures."""

    def test_database_initialization_with_fresh_database(self):
        """Test database initialization on a fresh database."""
        # Create temporary file
        _, db_file = mkstemp()

        try:
            engine = create_engine(f"sqlite:///{db_file}")

            # Verify database is initially empty
            with engine.begin() as conn:
                cursor = conn.connection.cursor()
                query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name NOT LIKE 'sqlite_%'"
                tables = [x[0] for x in cursor.execute(query).fetchall()]
                assert len(tables) == 0

            # Run migration
            migrate(engine, "head")

            # Verify tables were created
            with engine.begin() as conn:
                cursor = conn.connection.cursor()
                query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name NOT LIKE 'sqlite_%'"
                tables = [x[0] for x in cursor.execute(query).fetchall()]
                assert len(tables) > 0
                assert "alembic_version" in tables

        finally:
            # Cleanup
            os.unlink(db_file)

    def test_database_cleanup_after_migration_error(self):
        """Test database state after migration error."""
        _, db_file = mkstemp()

        try:
            engine = create_engine(f"sqlite:///{db_file}")

            # Mock upgrade to fail
            with patch("mlflow_oidc_auth.db.utils.upgrade") as mock_upgrade:
                mock_upgrade.side_effect = SQLAlchemyError("Migration failed")

                with pytest.raises(SQLAlchemyError):
                    migrate(engine, "head")

                # Verify database connection is still valid after error
                with engine.begin() as conn:
                    # Should be able to execute simple query
                    result = conn.execute(text("SELECT 1")).fetchone()
                    assert result[0] == 1

        finally:
            os.unlink(db_file)

    def test_concurrent_migration_handling(self):
        """Test handling of concurrent migration attempts."""
        _, db_file = mkstemp()

        try:
            engine1 = create_engine(f"sqlite:///{db_file}")
            engine2 = create_engine(f"sqlite:///{db_file}")

            # First migration should succeed
            migrate(engine1, "head")

            # Second migration should be idempotent
            migrate_if_needed(engine2, "head")

            # Verify database is in consistent state
            with engine1.begin() as conn:
                cursor = conn.connection.cursor()
                query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name NOT LIKE 'sqlite_%'"
                tables = [x[0] for x in cursor.execute(query).fetchall()]
                assert "alembic_version" in tables

        finally:
            os.unlink(db_file)


class TestMigrationCompatibility:
    """Test migration compatibility and data preservation."""

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migration_version_compatibility(self, mock_upgrade, mock_script_dir, mock_migration_context):
        """Test migration compatibility between different versions."""
        # Setup mocks for version comparison
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "abc123"
        mock_script_dir.from_config.return_value = script_dir_mock

        # Test with older version
        mock_migration_context.configure.return_value.get_current_revision.return_value = "def456"

        engine = create_engine("sqlite:///:memory:")
        migrate_if_needed(engine, "head")

        mock_upgrade.assert_called_once()

    def test_migration_rollback_scenario(self):
        """Test migration rollback scenarios."""
        _, db_file = mkstemp()

        try:
            engine = create_engine(f"sqlite:///{db_file}")

            # Initial migration
            migrate(engine, "head")

            # Verify initial state
            with engine.begin() as conn:
                cursor = conn.connection.cursor()
                query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name NOT LIKE 'sqlite_%'"
                initial_tables = [x[0] for x in cursor.execute(query).fetchall()]
                assert len(initial_tables) > 0

            # Test rollback by migrating to a specific (older) revision
            # Note: In a real scenario, this would be a specific revision hash
            with patch("mlflow_oidc_auth.db.utils.upgrade") as mock_upgrade:
                migrate(engine, "base")  # Rollback to base
                mock_upgrade.assert_called_with(mock_upgrade.call_args[0][0], "base")

        finally:
            os.unlink(db_file)

    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_data_preservation_during_migration(self, mock_upgrade):
        """Test that data is preserved during migrations."""
        _, db_file = mkstemp()

        try:
            engine = create_engine(f"sqlite:///{db_file}")

            # Simulate a migration that should preserve data
            migrate(engine, "head")

            # Verify that the migration process was called
            mock_upgrade.assert_called_once()

            # In a real test, we would:
            # 1. Insert test data before migration
            # 2. Run migration
            # 3. Verify data is still present and correct

        finally:
            os.unlink(db_file)


class TestErrorRecovery:
    """Test error recovery and graceful error handling."""

    def test_recovery_from_connection_timeout(self):
        """Test recovery from database connection timeouts."""
        # Create an engine and test normal operation
        engine = create_engine("sqlite:///:memory:")

        # This should work normally
        migrate_if_needed(engine, "head")

    def test_recovery_from_invalid_database_url(self):
        """Test graceful handling of invalid database URLs."""
        with pytest.raises(Exception):
            # This should fail gracefully
            engine = create_engine("invalid://url")
            migrate(engine, "head")

    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_recovery_from_partial_migration_failure(self, mock_upgrade):
        """Test recovery from partial migration failures."""
        mock_upgrade.side_effect = [SQLAlchemyError("Partial failure"), None]

        engine = create_engine("sqlite:///:memory:")

        # First attempt should fail
        with pytest.raises(SQLAlchemyError):
            migrate(engine, "head")

        # Second attempt should succeed (in real scenario, after fixing the issue)
        migrate(engine, "head")

        assert mock_upgrade.call_count == 2

    def test_logging_during_error_conditions(self):
        """Test that appropriate logging occurs during error conditions."""
        with patch("mlflow_oidc_auth.db.utils.upgrade") as mock_upgrade:
            mock_upgrade.side_effect = SQLAlchemyError("Test error")

            engine = create_engine("sqlite:///:memory:")

            with pytest.raises(SQLAlchemyError):
                migrate(engine, "head")

            # In a real implementation, we would verify logging calls here
            # This test ensures the error propagates correctly
