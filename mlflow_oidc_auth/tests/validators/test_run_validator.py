from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.validators.run import (
    validate_can_read_run_artifact,
    validate_can_update_run_artifact,
)


def test_validate_can_read_run_artifact_supports_run_uuid_alias() -> None:
    """Ensure run validator accepts `run_uuid` when `run_id` is absent.

    MLflow clients may send `run_uuid` instead of `run_id`. The project-wide
    `get_request_param("run_id")` helper already supports this alias; this test
    verifies the run permission validator follows that behavior.
    """

    app = Flask(__name__)

    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp-123"

    with (
        app.test_request_context("/?run_uuid=uuid123", method="GET"),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as mock_effective_exp_perm,
    ):
        mock_tracking_store.return_value.get_run.return_value = mock_run
        mock_effective_exp_perm.return_value = SimpleNamespace(permission=get_permission("READ"))

        assert validate_can_read_run_artifact("alice") is True

        mock_tracking_store.return_value.get_run.assert_called_once_with("uuid123")
        mock_effective_exp_perm.assert_called_once_with("exp-123", "alice")


def test_validate_can_update_run_artifact_works_with_run_id() -> None:
    """Ensure run artifact UPDATE permission works with a normal run_id param."""

    app = Flask(__name__)

    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp-999"

    with (
        app.test_request_context("/?run_id=run-999", method="GET"),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as mock_effective_exp_perm,
    ):
        mock_tracking_store.return_value.get_run.return_value = mock_run
        mock_effective_exp_perm.return_value = SimpleNamespace(permission=get_permission("EDIT"))

        assert validate_can_update_run_artifact("bob") is True

        mock_tracking_store.return_value.get_run.assert_called_once_with("run-999")
        mock_effective_exp_perm.assert_called_once_with("exp-999", "bob")
