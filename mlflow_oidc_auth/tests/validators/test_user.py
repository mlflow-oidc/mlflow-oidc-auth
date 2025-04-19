import pytest
from unittest.mock import patch
from mlflow_oidc_auth.validators import user

# Patch in the correct namespace: mlflow_oidc_auth.validators.user


def test__username_is_sender_true():
    with patch("mlflow_oidc_auth.validators.user.get_request_param", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.user.get_username", return_value="alice"
    ):
        assert user._username_is_sender() is True


def test__username_is_sender_false():
    with patch("mlflow_oidc_auth.validators.user.get_request_param", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.user.get_username", return_value="bob"
    ):
        assert user._username_is_sender() is False


def test_validate_can_get_user_token():
    assert user.validate_can_get_user_token() is False


def test_validate_can_create_user():
    assert user.validate_can_create_user() is False


def test_validate_can_update_user_admin():
    assert user.validate_can_update_user_admin() is False


def test_validate_can_delete_user():
    assert user.validate_can_delete_user() is False


def test_validate_can_read_user_true():
    with patch("mlflow_oidc_auth.validators.user.get_request_param", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.user.get_username", return_value="alice"
    ):
        assert user.validate_can_read_user() is True


def test_validate_can_read_user_false():
    with patch("mlflow_oidc_auth.validators.user.get_request_param", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.user.get_username", return_value="bob"
    ):
        assert user.validate_can_read_user() is False


def test_validate_can_update_user_password_true():
    with patch("mlflow_oidc_auth.validators.user.get_request_param", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.user.get_username", return_value="alice"
    ):
        assert user.validate_can_update_user_password() is True


def test_validate_can_update_user_password_false():
    with patch("mlflow_oidc_auth.validators.user.get_request_param", return_value="alice"), patch(
        "mlflow_oidc_auth.validators.user.get_username", return_value="bob"
    ):
        assert user.validate_can_update_user_password() is False
