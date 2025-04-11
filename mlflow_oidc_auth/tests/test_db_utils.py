import os
import sys
from tempfile import mkstemp
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mlflow_oidc_auth.db.utils import migrate, migrate_if_needed


class TestMigrate:
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate(self, mock_upgrade):
        engine = create_engine("sqlite:///:memory:")
        with sessionmaker(bind=engine)():
            migrate(engine, "head")

        mock_upgrade.assert_called_once()

    @patch("mlflow_oidc_auth.db.utils.MigrationContext")
    @patch("mlflow_oidc_auth.db.utils.ScriptDirectory")
    @patch("mlflow_oidc_auth.db.utils.upgrade")
    def test_migrate_if_needed_not_called_if_not_needed(self, mock_upgrade, mock_script_dir, mock_migration_context):
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
        script_dir_mock = MagicMock()
        script_dir_mock.get_current_head.return_value = "head"
        mock_script_dir.from_config.return_value = script_dir_mock
        mock_migration_context.configure.return_value.get_current_revision.return_value = "not_head"

        engine = create_engine("sqlite:///:memory:")
        with sessionmaker(bind=engine)():
            migrate_if_needed(engine, "head")

        mock_upgrade.assert_called_once()


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
