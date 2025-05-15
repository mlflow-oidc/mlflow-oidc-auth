from mlflow_oidc_auth.utils import get_request_param, get_username


def _username_is_sender():
    """Validate if the request username is the sender"""
    username = get_request_param("username")
    sender = get_username()
    return username == sender


def validate_can_get_user_token():
    # only admins can get user token, but admins won't reach this validator
    return False


def validate_can_read_user():
    return _username_is_sender()


def validate_can_create_user():
    # only admins can create user, but admins won't reach this validator
    return False


def validate_can_update_user_password():
    return _username_is_sender()


def validate_can_update_user_admin():
    # only admins can update, but admins won't reach this validator
    return False


def validate_can_delete_user():
    # only admins can delete, but admins won't reach this validator
    return False
