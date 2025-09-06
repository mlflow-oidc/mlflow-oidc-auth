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
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        perm = experiment._get_permission_from_experiment_id("alice")
        assert perm.can_read is True


def test__get_permission_from_experiment_name_found():
    store_exp = MagicMock()
    store_exp.experiment_id = "456"
    with patch("mlflow_oidc_auth.validators.experiment.get_request_param", return_value="expname"), patch(
        "mlflow_oidc_auth.validators.experiment._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_update=True)),
    ):
        mock_store.return_value.get_experiment_by_name.return_value = store_exp
        perm = experiment._get_permission_from_experiment_name("alice")
        assert perm.can_update is True


def test__get_permission_from_experiment_name_not_found():
    with patch("mlflow_oidc_auth.validators.experiment.get_request_param", return_value="expname"), patch(
        "mlflow_oidc_auth.validators.experiment._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.experiment.get_permission") as mock_get_permission:
        mock_store.return_value.get_experiment_by_name.return_value = None
        mock_permission = DummyPermission(can_read=True, can_update=True, can_delete=True, can_manage=True)
        mock_get_permission.return_value = mock_permission
        perm = experiment._get_permission_from_experiment_name("alice")
        assert perm.can_read is True
        assert perm.can_update is True
        assert perm.can_delete is True
        assert perm.can_manage is True
        mock_get_permission.assert_called_once_with("MANAGE")


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
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_manage=True)),
    ):
        perm = experiment._get_permission_from_experiment_id_artifact_proxy("alice")
        assert perm.can_manage is True


def test__get_permission_from_experiment_id_artifact_proxy_no_id():
    dummy_perm = DummyPermission(can_read=True)
    with patch("mlflow_oidc_auth.validators.experiment._get_experiment_id_from_view_args", return_value=None), patch(
        "mlflow_oidc_auth.validators.experiment.config"
    ) as mock_config, patch("mlflow_oidc_auth.validators.experiment.get_permission", return_value=dummy_perm):
        mock_config.DEFAULT_MLFLOW_PERMISSION = "default"
        perm = experiment._get_permission_from_experiment_id_artifact_proxy("alice")
        assert perm.can_read is True


def test_validate_can_read_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_read=True):
            assert experiment.validate_can_read_experiment("alice") is True


def test_validate_can_read_experiment_by_name():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_name",
        return_value=DummyPermission(can_read=True),
    ):
        assert experiment.validate_can_read_experiment_by_name("alice") is True


def test_validate_can_update_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_update=True):
            assert experiment.validate_can_update_experiment("alice") is True


def test_validate_can_delete_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_delete=True):
            assert experiment.validate_can_delete_experiment("alice") is True


def test_validate_can_manage_experiment():
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_manage=True):
            assert experiment.validate_can_manage_experiment("alice") is True


def test_validate_can_read_experiment_artifact_proxy():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_read=True),
    ):
        assert experiment.validate_can_read_experiment_artifact_proxy("alice") is True


def test_validate_can_update_experiment_artifact_proxy():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_update=True),
    ):
        assert experiment.validate_can_update_experiment_artifact_proxy("alice") is True


def test_validate_can_delete_experiment_artifact_proxy():
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_delete=True),
    ):
        assert experiment.validate_can_delete_experiment_artifact_proxy("alice") is True


# Additional tests for missing coverage and edge cases


def test__get_permission_from_experiment_id_no_permission():
    """Test when user has no permissions"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"), patch(
        "mlflow_oidc_auth.validators.experiment.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission()),
    ):
        perm = experiment._get_permission_from_experiment_id("alice")
        assert perm.can_read is False
        assert perm.can_update is False
        assert perm.can_delete is False
        assert perm.can_manage is False


def test__get_permission_from_experiment_name_empty_name():
    """Test with empty experiment name"""
    with patch("mlflow_oidc_auth.validators.experiment.get_request_param", return_value=""), patch(
        "mlflow_oidc_auth.validators.experiment._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.experiment.get_permission") as mock_get_permission:
        mock_store.return_value.get_experiment_by_name.return_value = None
        mock_permission = DummyPermission(can_read=True, can_update=True, can_delete=True, can_manage=True)
        mock_get_permission.return_value = mock_permission
        perm = experiment._get_permission_from_experiment_name("alice")
        assert perm.can_manage is True


def test__get_permission_from_experiment_name_store_exception():
    """Test when store raises an exception"""
    with patch("mlflow_oidc_auth.validators.experiment.get_request_param", return_value="expname"), patch(
        "mlflow_oidc_auth.validators.experiment._get_tracking_store"
    ) as mock_store, patch("mlflow_oidc_auth.validators.experiment.get_permission") as mock_get_permission:
        mock_store.return_value.get_experiment_by_name.side_effect = Exception("Store error")
        mock_permission = DummyPermission(can_read=True, can_update=True, can_delete=True, can_manage=True)
        mock_get_permission.return_value = mock_permission

        with pytest.raises(Exception, match="Store error"):
            experiment._get_permission_from_experiment_name("alice")


def test__get_experiment_id_from_view_args_no_view_args():
    """Test when request has no view_args"""
    mock_request = MagicMock()
    mock_request.view_args = {}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() is None


def test__get_experiment_id_from_view_args_no_artifact_path():
    """Test when view_args has no artifact_path"""
    mock_request = MagicMock()
    mock_request.view_args = {"other_param": "value"}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() is None


def test__get_experiment_id_from_view_args_invalid_pattern():
    """Test with artifact path that doesn't match pattern"""
    mock_request = MagicMock()
    mock_request.view_args = {"artifact_path": "invalid/path/format"}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() is None


def test__get_experiment_id_from_view_args_complex_path():
    """Test with complex artifact path"""
    mock_request = MagicMock()
    mock_request.view_args = {"artifact_path": "456/models/model_name/artifacts/file.txt"}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() == "456"


def test_validate_can_read_experiment_false():
    """Test when user cannot read experiment"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_read=False):
            assert experiment.validate_can_read_experiment("alice") is False


def test_validate_can_read_experiment_by_name_false():
    """Test when user cannot read experiment by name"""
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_name",
        return_value=DummyPermission(can_read=False),
    ):
        assert experiment.validate_can_read_experiment_by_name("alice") is False


def test_validate_can_update_experiment_false():
    """Test when user cannot update experiment"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_update=False):
            assert experiment.validate_can_update_experiment("alice") is False


def test_validate_can_delete_experiment_false():
    """Test when user cannot delete experiment"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_delete=False):
            assert experiment.validate_can_delete_experiment("alice") is False


def test_validate_can_manage_experiment_false():
    """Test when user cannot manage experiment"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_manage=False):
            assert experiment.validate_can_manage_experiment("alice") is False


def test_validate_can_read_experiment_artifact_proxy_false():
    """Test when user cannot read experiment artifact proxy"""
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_read=False),
    ):
        assert experiment.validate_can_read_experiment_artifact_proxy("alice") is False


def test_validate_can_update_experiment_artifact_proxy_false():
    """Test when user cannot update experiment artifact proxy"""
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_update=False),
    ):
        assert experiment.validate_can_update_experiment_artifact_proxy("alice") is False


def test_validate_can_delete_experiment_artifact_proxy_false():
    """Test when user cannot delete experiment artifact proxy"""
    with patch(
        "mlflow_oidc_auth.validators.experiment._get_permission_from_experiment_id_artifact_proxy",
        return_value=DummyPermission(can_delete=False),
    ):
        assert experiment.validate_can_delete_experiment_artifact_proxy("alice") is False


# Security and edge case tests


def test_validate_with_none_username():
    """Test validation functions with None username"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_read=True):
            assert experiment.validate_can_read_experiment(None) is True


def test_validate_with_empty_username():
    """Test validation functions with empty username"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_read=True):
            assert experiment.validate_can_read_experiment("") is True


def test_validate_with_special_characters_username():
    """Test validation functions with special characters in username"""
    username = "user@domain.com"
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_read=True):
            assert experiment.validate_can_read_experiment(username) is True


def test_validate_with_malformed_experiment_id():
    """Test with malformed experiment ID"""
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="invalid_id"):
        with _patch_permission(can_read=True):
            assert experiment.validate_can_read_experiment("alice") is True


def test_validate_with_very_long_username():
    """Test with very long username"""
    long_username = "a" * 1000
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_read=True):
            assert experiment.validate_can_read_experiment(long_username) is True


def test_get_experiment_id_from_view_args_edge_cases():
    """Test edge cases for experiment ID extraction"""
    # Test with leading zeros
    mock_request = MagicMock()
    mock_request.view_args = {"artifact_path": "0123/path"}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() == "0123"

    # Test with very large number
    mock_request.view_args = {"artifact_path": "999999999999999999/path"}
    with patch("mlflow_oidc_auth.validators.experiment.request", mock_request):
        assert experiment._get_experiment_id_from_view_args() == "999999999999999999"


def test_permission_inheritance_scenarios():
    """Test various permission inheritance scenarios"""
    # Test partial permissions
    with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
        with _patch_permission(can_read=True, can_update=False, can_delete=False, can_manage=False):
            assert experiment.validate_can_read_experiment("alice") is True
            assert experiment.validate_can_update_experiment("alice") is False
            assert experiment.validate_can_delete_experiment("alice") is False
            assert experiment.validate_can_manage_experiment("alice") is False
