from unittest.mock import patch
from mlflow_oidc_auth import user


class DummyUser:
    def __init__(self, username, id):
        self.username = username
        self.id = id


def test_generate_token_length_and_charset():
    token = user.generate_token()
    assert len(token) == 24
    assert all(c.isalnum() for c in token)


@patch("mlflow_oidc_auth.user.store")
def test_create_user_already_exists(mock_store):
    dummy = DummyUser("alice", 1)
    mock_store.get_user.return_value = dummy
    mock_store.update_user.return_value = None
    result = user.create_user("alice", "Alice", is_admin=True)
    assert result == (False, f"User alice (ID: 1) already exists")
    mock_store.get_user.assert_called_once_with("alice")
    mock_store.update_user.assert_called_once_with(username="alice", is_admin=True, is_service_account=False)


@patch("mlflow_oidc_auth.user.MlflowException", Exception)
@patch("mlflow_oidc_auth.user.generate_token", return_value="dummy_password")
@patch("mlflow_oidc_auth.user.store")
def test_create_user_new_user(mock_store, mock_generate_token):
    mock_store.get_user.side_effect = Exception
    dummy = DummyUser("bob", 2)
    mock_store.create_user.return_value = dummy
    result = user.create_user("bob", "Bob", is_admin=False, is_service_account=True)
    assert result == (True, f"User bob (ID: 2) successfully created")
    mock_store.create_user.assert_called_once_with(username="bob", password="dummy_password", display_name="Bob", is_admin=False, is_service_account=True)


@patch("mlflow_oidc_auth.user.store")
def test_populate_groups(mock_store):
    user.populate_groups(["g1", "g2"])
    mock_store.populate_groups.assert_called_once_with(group_names=["g1", "g2"])


@patch("mlflow_oidc_auth.user.store")
def test_update_user(mock_store):
    user.update_user("alice", ["g1", "g2"])
    mock_store.set_user_groups.assert_called_once_with("alice", ["g1", "g2"])
