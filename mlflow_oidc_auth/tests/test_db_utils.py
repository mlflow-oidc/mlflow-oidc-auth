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
