from unittest.mock import MagicMock, patch

import pytest

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
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"), patch(
        "mlflow_oidc_auth.validators.registered_model.effective_registered_model_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        perm = registered_model._get_permission_from_registered_model_name("alice")
        assert perm.can_read is True


def test_validate_can_read_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_read=True):
            assert registered_model.validate_can_read_registered_model("alice") is True


def test_validate_can_update_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_update=True):
            assert registered_model.validate_can_update_registered_model("alice") is True


def test_validate_can_delete_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_delete=True):
            assert registered_model.validate_can_delete_registered_model("alice") is True


def test_validate_can_manage_registered_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_manage=True):
            assert registered_model.validate_can_manage_registered_model("alice") is True


def test__get_permission_from_model_id():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        # Mock the logged model object
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        perm = registered_model._get_permission_from_model_id("alice")
        assert perm.can_read is True
        mock_store.return_value.get_logged_model.assert_called_once_with("model123")


def test_validate_can_read_logged_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_read_logged_model("alice") is True


def test_validate_can_update_logged_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_update=True)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_update_logged_model("alice") is True


def test_validate_can_delete_logged_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_delete=True)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_delete_logged_model("alice") is True


def test_validate_can_manage_logged_model():
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_manage=True)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_manage_logged_model("alice") is True


# Additional tests for missing coverage and edge cases


def test__get_permission_from_registered_model_name_no_permission():
    """Test when user has no permissions for registered model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"), patch(
        "mlflow_oidc_auth.validators.registered_model.effective_registered_model_permission",
        return_value=MagicMock(permission=DummyPermission()),
    ):
        perm = registered_model._get_permission_from_registered_model_name("alice")
        assert perm.can_read is False
        assert perm.can_update is False
        assert perm.can_delete is False
        assert perm.can_manage is False


def test__get_permission_from_model_id_no_permission():
    """Test when user has no permissions for logged model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission()),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        perm = registered_model._get_permission_from_model_id("alice")
        assert perm.can_read is False
        assert perm.can_update is False
        assert perm.can_delete is False
        assert perm.can_manage is False


def test_validate_can_read_registered_model_false():
    """Test when user cannot read registered model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_read=False):
            assert registered_model.validate_can_read_registered_model("alice") is False


def test_validate_can_update_registered_model_false():
    """Test when user cannot update registered model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_update=False):
            assert registered_model.validate_can_update_registered_model("alice") is False


def test_validate_can_delete_registered_model_false():
    """Test when user cannot delete registered model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_delete=False):
            assert registered_model.validate_can_delete_registered_model("alice") is False


def test_validate_can_manage_registered_model_false():
    """Test when user cannot manage registered model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_manage=False):
            assert registered_model.validate_can_manage_registered_model("alice") is False


def test_validate_can_read_logged_model_false():
    """Test when user cannot read logged model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=False)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_read_logged_model("alice") is False


def test_validate_can_update_logged_model_false():
    """Test when user cannot update logged model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_update=False)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_update_logged_model("alice") is False


def test_validate_can_delete_logged_model_false():
    """Test when user cannot delete logged model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_delete=False)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_delete_logged_model("alice") is False


def test_validate_can_manage_logged_model_false():
    """Test when user cannot manage logged model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.registered_model.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_manage=False)),
    ):
        mock_model = MagicMock()
        mock_model.experiment_id = "exp123"
        mock_store.return_value.get_logged_model.return_value = mock_model

        assert registered_model.validate_can_manage_logged_model("alice") is False


# Security and edge case tests


def test_validate_with_none_username_registered_model():
    """Test validation functions with None username"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_read=True):
            assert registered_model.validate_can_read_registered_model(None) is True


def test_validate_with_empty_username_registered_model():
    """Test validation functions with empty username"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_read=True):
            assert registered_model.validate_can_read_registered_model("") is True


def test_validate_with_special_characters_username_registered_model():
    """Test validation functions with special characters in username"""
    username = "user@domain.com"
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_read=True):
            assert registered_model.validate_can_read_registered_model(username) is True


def test_validate_with_malformed_model_name():
    """Test with malformed model name"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value=""):
        with _patch_permission(can_read=True):
            assert registered_model.validate_can_read_registered_model("alice") is True


def test_validate_with_very_long_model_name():
    """Test with very long model name"""
    long_model_name = "model_" + "a" * 1000
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value=long_model_name):
        with _patch_permission(can_read=True):
            assert registered_model.validate_can_read_registered_model("alice") is True


def test_get_logged_model_store_exception():
    """Test when store raises an exception for logged model"""
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_id", return_value="model123"), patch(
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_logged_model.side_effect = Exception("Store error")

        with pytest.raises(Exception, match="Store error"):
            registered_model._get_permission_from_model_id("alice")


def test_permission_inheritance_scenarios_registered_model():
    """Test various permission inheritance scenarios for registered models"""
    # Test partial permissions
    with patch("mlflow_oidc_auth.validators.registered_model.get_model_name", return_value="modelA"):
        with _patch_permission(can_read=True, can_update=False, can_delete=False, can_manage=False):
            assert registered_model.validate_can_read_registered_model("alice") is True
            assert registered_model.validate_can_update_registered_model("alice") is False
            assert registered_model.validate_can_delete_registered_model("alice") is False
            assert registered_model.validate_can_manage_registered_model("alice") is False
