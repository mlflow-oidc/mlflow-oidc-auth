from unittest.mock import MagicMock, patch

from mlflow_oidc_auth.validators import registered_model


class DummyPermission:
    def __init__(self, can_read=False, can_update=False, can_delete=False, can_manage=False):
        self.can_read = can_read
        self.can_update = can_update
        self.can_delete = can_delete
        self.can_manage = can_manage


def _patch_permission(**kwargs):
    return patch(
        "mlflow_oidc_auth.validators.registered_model.effective_registered_model_permission",
        return_value=MagicMock(permission=DummyPermission(**kwargs)),
    )


def test__get_permission_from_registered_model_name():
    with patch("mlflow_oidc_auth.validators.registered_model.get_url_param", return_value="modelA"), patch(
        "mlflow_oidc_auth.validators.registered_model.get_username", return_value="alice"
    ), patch(
        "mlflow_oidc_auth.validators.registered_model.effective_registered_model_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        perm = registered_model._get_permission_from_registered_model_name()
        assert perm.can_read is True


def test_validate_can_read_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_url_param", return_value="modelA"):
        with patch("mlflow_oidc_auth.validators.registered_model.get_username", return_value="alice"):
            with _patch_permission(can_read=True):
                assert registered_model.validate_can_read_registered_model() is True


def test_validate_can_update_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_url_param", return_value="modelA"):
        with patch("mlflow_oidc_auth.validators.registered_model.get_username", return_value="alice"):
            with _patch_permission(can_update=True):
                assert registered_model.validate_can_update_registered_model() is True


def test_validate_can_delete_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_url_param", return_value="modelA"):
        with patch("mlflow_oidc_auth.validators.registered_model.get_username", return_value="alice"):
            with _patch_permission(can_delete=True):
                assert registered_model.validate_can_delete_registered_model() is True


def test_validate_can_manage_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_url_param", return_value="modelA"):
        with patch("mlflow_oidc_auth.validators.registered_model.get_username", return_value="alice"):
            with _patch_permission(can_manage=True):
                assert registered_model.validate_can_manage_registered_model() is True
