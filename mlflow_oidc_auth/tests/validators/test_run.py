from unittest.mock import MagicMock, patch

from mlflow_oidc_auth.validators import run


class DummyPermission:
    def __init__(self, can_read=False, can_update=False, can_delete=False, can_manage=False):
        self.can_read = can_read
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
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.run.get_username", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.run.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        mock_store.return_value.get_run.return_value = mock_run
        perm = run._get_permission_from_run_id()
        assert perm.can_read is True


def test_validate_can_read_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.run.get_username", return_value="alice"):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run() is True


def test_validate_can_update_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.run.get_username", return_value="alice"):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_update=True):
            assert run.validate_can_update_run() is True


def test_validate_can_delete_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.run.get_username", return_value="alice"):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_delete=True):
            assert run.validate_can_delete_run() is True


def test_validate_can_manage_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.run.get_username", return_value="alice"):
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_manage=True):
            assert run.validate_can_manage_run() is True
