from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.validators import run


class DummyPermission:
    def __init__(
        self,
        can_read=False,
        can_use=False,
        can_update=False,
        can_delete=False,
        can_manage=False,
    ):
        self.can_read = can_read
        self.can_use = can_use
        self.can_update = can_update
        self.can_delete = can_delete
        self.can_manage = can_manage


def _patch_permission(**kwargs):
    return patch(
        "mlflow_oidc_auth.validators.run.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(**kwargs)),
    )


def test__get_permission_from_run_id():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
        patch(
            "mlflow_oidc_auth.validators.run.effective_experiment_permission",
            return_value=MagicMock(permission=DummyPermission(can_read=True)),
        ),
    ):
        mock_store.return_value.get_run.return_value = mock_run
        perm = run._get_permission_from_run_id("alice")
        assert perm.can_read is True


def test_validate_can_read_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True


def test_validate_can_update_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_update=True):
            assert run.validate_can_update_run("alice") is True


def test_validate_can_delete_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_delete=True):
            assert run.validate_can_delete_run("alice") is True


def test_validate_can_manage_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_manage=True):
            assert run.validate_can_manage_run("alice") is True


# Additional tests for missing coverage and edge cases


def test__get_permission_from_run_id_no_permission():
    """Test when user has no permissions for run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
        patch(
            "mlflow_oidc_auth.validators.run.effective_experiment_permission",
            return_value=MagicMock(permission=DummyPermission()),
        ),
    ):
        mock_store.return_value.get_run.return_value = mock_run
        perm = run._get_permission_from_run_id("alice")
        assert perm.can_read is False
        assert perm.can_update is False
        assert perm.can_delete is False
        assert perm.can_manage is False


def test_validate_can_read_run_false():
    """Test when user cannot read run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=False):
            assert run.validate_can_read_run("alice") is False


def test_validate_can_update_run_false():
    """Test when user cannot update run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_update=False):
            assert run.validate_can_update_run("alice") is False


def test_validate_can_delete_run_false():
    """Test when user cannot delete run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_delete=False):
            assert run.validate_can_delete_run("alice") is False


def test_validate_can_manage_run_false():
    """Test when user cannot manage run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_manage=False):
            assert run.validate_can_manage_run("alice") is False


# Security and edge case tests


def test_validate_with_none_username_run():
    """Test validation functions with None username"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run(None) is True


def test_validate_with_empty_username_run():
    """Test validation functions with empty username"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("") is True


def test_validate_with_special_characters_username_run():
    """Test validation functions with special characters in username"""
    username = "user@domain.com"
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run(username) is True


def test_validate_with_malformed_run_id():
    """Test with malformed run ID"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=[""]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True


def test_validate_with_very_long_run_id():
    """Test with very long run ID"""
    long_run_id = "run_" + "a" * 1000
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch(
            "mlflow_oidc_auth.validators.run.get_request_param_values",
            return_value=[long_run_id],
        ),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True


def test_get_run_store_exception():
    """Test when store raises an exception for run"""
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.side_effect = Exception("Store error")

        with pytest.raises(Exception, match="Store error"):
            run._get_permission_from_run_id("alice")


def test_permission_inheritance_scenarios_run():
    """Test various permission inheritance scenarios for runs"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run
        # Test partial permissions
        with _patch_permission(can_read=True, can_update=False, can_delete=False, can_manage=False):
            assert run.validate_can_read_run("alice") is True
            assert run.validate_can_update_run("alice") is False
            assert run.validate_can_delete_run("alice") is False
            assert run.validate_can_manage_run("alice") is False


def test_run_with_different_experiment_ids():
    """Test runs with different experiment IDs"""
    # Test with numeric experiment ID
    mock_run1 = MagicMock()
    mock_run1.info.experiment_id = "123"

    # Test with string experiment ID
    mock_run2 = MagicMock()
    mock_run2.info.experiment_id = "default"

    with (
        patch("mlflow_oidc_auth.validators.run.get_request_param_values", return_value=["run123"]),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_store,
    ):
        mock_store.return_value.get_run.return_value = mock_run1
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True

        mock_store.return_value.get_run.return_value = mock_run2
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True


# ---------------------------------------------------------------------------
# validate_can_log_metrics and the referenced-resource helpers
# ---------------------------------------------------------------------------

from flask import Flask  # noqa: E402
from mlflow.exceptions import MlflowException  # noqa: E402
from mlflow.protos.databricks_pb2 import INTERNAL_ERROR, RESOURCE_DOES_NOT_EXIST  # noqa: E402

from mlflow_oidc_auth.permissions import EDIT, NO_PERMISSIONS, READ  # noqa: E402
from mlflow_oidc_auth.validators import _referenced  # noqa: E402

_log_app = Flask(__name__)


def _log_metrics(body, *, run_ok=True, model_perm=EDIT):
    with (
        _log_app.test_request_context("/api/2.0/mlflow/runs/log-batch", method="POST", json=body),
        patch.object(run, "validate_can_update_run", return_value=run_ok),
        patch.object(run, "referenced_logged_model_permission", return_value=model_perm) as model_check,
    ):
        return run.validate_can_log_metrics("alice"), model_check


def test_log_metrics_without_model_ids_checks_only_the_run():
    result, model_check = _log_metrics({"run_id": "r1", "metrics": [{"key": "k", "value": 1, "timestamp": 1}]})
    assert result is True
    model_check.assert_not_called()


def test_log_metrics_denied_without_update_on_run():
    result, model_check = _log_metrics({"run_id": "r1", "model_id": "m-1"}, run_ok=False)
    assert result is False
    model_check.assert_not_called()


def test_log_metrics_checks_top_level_and_nested_model_ids():
    body = {"run_id": "r1", "model_id": "m-1", "metrics": [{"model_id": "m-2"}, {"modelId": "m-3"}, {"model_id": "m-2"}]}
    result, model_check = _log_metrics(body)
    assert result is True
    assert [c.args[0] for c in model_check.call_args_list] == ["m-1", "m-2", "m-3"]


@pytest.mark.parametrize("perm", [READ, NO_PERMISSIONS])
def test_log_metrics_denied_without_update_on_logged_model(perm):
    result, _ = _log_metrics({"run_id": "r1", "metrics": [{"model_id": "m-1"}]}, model_perm=perm)
    assert result is False


def test_referenced_permission_of_missing_resource_is_no_permissions():
    missing = MlflowException("gone", RESOURCE_DOES_NOT_EXIST)
    with patch.object(_referenced, "_get_tracking_store") as store:
        store.return_value.get_run.side_effect = missing
        store.return_value.get_logged_model.side_effect = missing
        assert _referenced.referenced_run_permission("r1", "alice") is NO_PERMISSIONS
        assert _referenced.referenced_logged_model_permission("m-1", "alice") is NO_PERMISSIONS


def test_referenced_permission_reraises_other_store_errors():
    with patch.object(_referenced, "_get_tracking_store") as store:
        store.return_value.get_run.side_effect = MlflowException("boom", INTERNAL_ERROR)
        with pytest.raises(MlflowException):
            _referenced.referenced_run_permission("r1", "alice")


def test_referenced_permission_uses_the_experiment():
    with (
        patch.object(_referenced, "_get_tracking_store") as store,
        patch.object(_referenced, "effective_experiment_permission", return_value=MagicMock(permission=READ)) as perm,
    ):
        store.return_value.get_logged_model.return_value = MagicMock(experiment_id="7")
        assert _referenced.referenced_logged_model_permission("m-1", "alice") is READ
        perm.assert_called_once_with("7", "alice")


def _presigned(body, *, run_perm=EDIT, model_perm=EDIT):
    with (
        _log_app.test_request_context("/api/2.0/mlflow/artifacts/presigned-upload-url", method="POST", json=body),
        patch.object(run, "referenced_run_permission", return_value=run_perm) as run_check,
        patch.object(run, "referenced_logged_model_permission", return_value=model_perm) as model_check,
    ):
        return run.validate_can_update_run_or_logged_model("alice"), run_check, model_check


def test_presigned_upload_by_run_checks_the_run():
    result, run_check, model_check = _presigned({"run_id": "r1", "path": "x"})
    assert result is True
    run_check.assert_called_once_with("r1", "alice")
    model_check.assert_not_called()


def test_presigned_upload_by_logged_model_checks_the_logged_model():
    result, run_check, model_check = _presigned({"model_id": "m-1", "path": "x"})
    assert result is True
    run_check.assert_not_called()
    model_check.assert_called_once_with("m-1", "alice")


def test_presigned_upload_without_a_target_is_denied():
    result, run_check, model_check = _presigned({"path": "x"})
    assert result is False
    run_check.assert_not_called()
    model_check.assert_not_called()


@pytest.mark.parametrize("perm", [READ, NO_PERMISSIONS])
def test_presigned_upload_denied_without_update_on_logged_model(perm):
    result, _, _ = _presigned({"model_id": "m-1", "path": "x"}, model_perm=perm)
    assert result is False


def test_presigned_upload_denied_without_update_on_run():
    result, _, _ = _presigned({"run_id": "r1", "path": "x"}, run_perm=READ)
    assert result is False
