from unittest.mock import MagicMock, patch

import pytest

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
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.run.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission(can_read=True)),
    ):
        mock_store.return_value.get_run.return_value = mock_run
        perm = run._get_permission_from_run_id("alice")
        assert perm.can_read is True


def test_validate_can_read_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True


def test_validate_can_update_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_update=True):
            assert run.validate_can_update_run("alice") is True


def test_validate_can_delete_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_delete=True):
            assert run.validate_can_delete_run("alice") is True


def test_validate_can_manage_run():
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_manage=True):
            assert run.validate_can_manage_run("alice") is True


# Additional tests for missing coverage and edge cases


def test__get_permission_from_run_id_no_permission():
    """Test when user has no permissions for run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store, patch(
        "mlflow_oidc_auth.validators.run.effective_experiment_permission",
        return_value=MagicMock(permission=DummyPermission()),
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
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=False):
            assert run.validate_can_read_run("alice") is False


def test_validate_can_update_run_false():
    """Test when user cannot update run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_update=False):
            assert run.validate_can_update_run("alice") is False


def test_validate_can_delete_run_false():
    """Test when user cannot delete run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_delete=False):
            assert run.validate_can_delete_run("alice") is False


def test_validate_can_manage_run_false():
    """Test when user cannot manage run"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_manage=False):
            assert run.validate_can_manage_run("alice") is False


# Security and edge case tests


def test_validate_with_none_username_run():
    """Test validation functions with None username"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run(None) is True


def test_validate_with_empty_username_run():
    """Test validation functions with empty username"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("") is True


def test_validate_with_special_characters_username_run():
    """Test validation functions with special characters in username"""
    username = "user@domain.com"
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run(username) is True


def test_validate_with_malformed_run_id():
    """Test with malformed run ID"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value=""), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True


def test_validate_with_very_long_run_id():
    """Test with very long run ID"""
    long_run_id = "run_" + "a" * 1000
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value=long_run_id), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True


def test_get_run_store_exception():
    """Test when store raises an exception for run"""
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.side_effect = Exception("Store error")

        with pytest.raises(Exception, match="Store error"):
            run._get_permission_from_run_id("alice")


def test_permission_inheritance_scenarios_run():
    """Test various permission inheritance scenarios for runs"""
    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp1"
    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
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

    with patch("mlflow_oidc_auth.validators.run.get_request_param", return_value="run123"), patch(
        "mlflow_oidc_auth.validators.run._get_tracking_store"
    ) as mock_store:
        mock_store.return_value.get_run.return_value = mock_run1
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True

        mock_store.return_value.get_run.return_value = mock_run2
        with _patch_permission(can_read=True):
            assert run.validate_can_read_run("alice") is True
