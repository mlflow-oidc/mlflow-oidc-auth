from unittest.mock import MagicMock, patch

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.validators import experiment


class DummyPermission:
    def __init__(self, can_read=False, can_update=False, can_delete=False, can_manage=False):
        self.can_read = can_read
        self.can_update = can_update
        self.can_delete = can_delete
        self.can_manage = can_manage


def _patch_permission(**kwargs):
    return patch(
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(**kwargs)),
    )


def test__get_permission_from_experiment_id():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"), patch(
        "mlflow_oidc_auth.validators.experiment.get_username", return_value="alice"
    ), patch(
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        perm = experiment._get_permission_from_experiment_id()
        assert perm.can_read is True


def test__get_permission_from_experiment_name_found():
    store_exp = MagicMock()
    store_exp.experiment_id = "456"
    with patch("mlflow_oidc_auth.validators.experiment.get_request_param", return_value="expname"), patch(
        "mlflow_oidc_auth.validators.experiment._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.experiment.get_username", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_update=True)),
    ):
        mock_store.return_value.get_experiment_by_name.return_value = store_exp
        perm = experiment._get_permission_from_experiment_name()
        assert perm.can_update is True


def test__get_permission_from_experiment_name_not_found():
    with patch("mlflow_oidc_auth.validators.experiment.get_request_param", return_value="expname"), patch(
        "mlflow_oidc_auth.validators.experiment._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_experiment_by_name.return_value = None
        with pytest.raises(MlflowException):
            experiment._get_permission_from_experiment_name()


def test__get_experiment_id_from_view_args_match():
    mock_request = MagicMock()
    mock_request.view_args = {"artifact_path": "123/some/path"}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() == "123"


def test__get_experiment_id_from_view_args_no_match():
    mock_request = MagicMock()
    mock_request.view_args = {"artifact_path": "notanid/path"}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() is None


def test__get_experiment_id_from_view_args_none():
    mock_request = MagicMock()
    mock_request.view_args = None
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() is None


def test__get_permission_from_experiment_id_artifact_proxy_with_id():
    with patch("mlflow_oidc_auth.validators.experiment._get_experiment_id_from_view_args", return_value="123"), patch(
        "mlflow_oidc_auth.validators.experiment.get_username", return_value="alice"
    ), patch(
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_manage=True)),
    ):
        perm = experiment._get_permission_from_experiment_id_artifact_proxy()
        assert perm.can_manage is True


def test__get_permission_from_experiment_id_artifact_proxy_no_id():
    dummy_perm = DummyPermission(can_read=True)
    with patch("mlflow_oidc_auth.validators.experiment._get_experiment_id_from_view_args", return_value=None), patch(
        "mlflow_oidc_auth.validators.experiment.config"
    ) as mock_config, patch("mlflow_oidc_auth.validators.experiment.get_permission", return_value=dummy_perm):
        mock_config.DEFAULT_MLFLOW_PERMISSION = "default"
        perm = experiment._get_permission_from_experiment_id_artifact_proxy()
        assert perm.can_read is True


def test_validate_can_read_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with patch("mlflow_oidc_auth.validators.experiment.get_username", return_value="alice"):
            with _patch_permission(can_read=True):
                assert experiment.validate_can_read_experiment() is True


def test_validate_can_read_experiment_by_name():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_name",
        return_value=DummyPermission(can_read=True),
    ):
        assert experiment.validate_can_read_experiment_by_name() is True


def test_validate_can_update_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with patch("mlflow_oidc_auth.validators.experiment.get_username", return_value="alice"):
            with _patch_permission(can_update=True):
                assert experiment.validate_can_update_experiment() is True


def test_validate_can_delete_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with patch("mlflow_oidc_auth.validators.experiment.get_username", return_value="alice"):
            with _patch_permission(can_delete=True):
                assert experiment.validate_can_delete_experiment() is True


def test_validate_can_manage_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with patch("mlflow_oidc_auth.validators.experiment.get_username", return_value="alice"):
            with _patch_permission(can_manage=True):
                assert experiment.validate_can_manage_experiment() is True


def test_validate_can_read_experiment_artifact_proxy():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_read=True),
    ):
        assert experiment.validate_can_read_experiment_artifact_proxy() is True


def test_validate_can_update_experiment_artifact_proxy():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_update=True),
    ):
        assert experiment.validate_can_update_experiment_artifact_proxy() is True


def test_validate_can_delete_experiment_artifact_proxy():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_manage=True),
    ):
        assert experiment.validate_can_delete_experiment_artifact_proxy() is True
