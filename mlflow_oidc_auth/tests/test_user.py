import string
from unittest.mock import patch
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth import user


class DummyUser:
    def __init__(self, username, id):
        self.username = username
        self.id = id


class TestGenerateToken:
    """Test suite for generate_token function"""

    def test_generate_token_length_and_charset(self):
        """Test that generated token has correct length and character set"""
        token = user.generate_token()
        assert len(token) == 24
        assert all(c.isalnum() for c in token)

    def test_generate_token_uniqueness(self):
        """Test that generate_token produces unique tokens"""
        tokens = [user.generate_token() for _ in range(100)]
        # All tokens should be unique
        assert len(set(tokens)) == len(tokens)

    def test_generate_token_character_distribution(self):
        """Test that generated token uses expected character set"""
        expected_chars = set(string.ascii_letters + string.digits)
        token = user.generate_token()
        token_chars = set(token)
        # All characters in token should be from expected set
        assert token_chars.issubset(expected_chars)

    @patch("mlflow_oidc_auth.user.secrets.choice")
    def test_generate_token_uses_secrets_module(self, mock_choice):
        """Test that generate_token uses secrets module for cryptographic randomness"""
        mock_choice.side_effect = ["a"] * 24
        token = user.generate_token()
        assert token == "a" * 24
        assert mock_choice.call_count == 24


class TestCreateUser:
    """Test suite for create_user function"""

    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_already_exists_default_params(self, mock_store):
        """Test creating user that already exists with default parameters"""
        dummy = DummyUser("alice", 1)
        mock_store.get_user.return_value = dummy
        mock_store.update_user.return_value = None

        result = user.create_user("alice", "Alice")

        assert result == (False, "User alice (ID: 1) already exists")
        mock_store.get_user.assert_called_once_with("alice")
        mock_store.update_user.assert_called_once_with(username="alice", is_admin=False, is_service_account=False)

    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_already_exists_with_admin_flag(self, mock_store):
        """Test creating user that already exists with admin flag"""
        dummy = DummyUser("alice", 1)
        mock_store.get_user.return_value = dummy
        mock_store.update_user.return_value = None

        result = user.create_user("alice", "Alice", is_admin=True)

        assert result == (False, "User alice (ID: 1) already exists")
        mock_store.get_user.assert_called_once_with("alice")
        mock_store.update_user.assert_called_once_with(username="alice", is_admin=True, is_service_account=False)

    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_already_exists_with_service_account_flag(self, mock_store):
        """Test creating user that already exists with service account flag"""
        dummy = DummyUser("charlie", 3)
        mock_store.get_user.return_value = dummy
        mock_store.update_user.return_value = None

        result = user.create_user("charlie", "Charlie", is_service_account=True)

        assert result == (False, "User charlie (ID: 3) already exists")
        mock_store.get_user.assert_called_once_with("charlie")
        mock_store.update_user.assert_called_once_with(username="charlie", is_admin=False, is_service_account=True)

    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_already_exists_with_both_flags(self, mock_store):
        """Test creating user that already exists with both admin and service account flags"""
        dummy = DummyUser("dave", 4)
        mock_store.get_user.return_value = dummy
        mock_store.update_user.return_value = None

        result = user.create_user("dave", "Dave", is_admin=True, is_service_account=True)

        assert result == (False, "User dave (ID: 4) already exists")
        mock_store.get_user.assert_called_once_with("dave")
        mock_store.update_user.assert_called_once_with(username="dave", is_admin=True, is_service_account=True)

    @patch("mlflow_oidc_auth.user.generate_token", return_value="test_password_123")
    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_new_user_default_params(self, mock_store, mock_generate_token):
        """Test creating new user with default parameters"""
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy = DummyUser("bob", 2)
        mock_store.create_user.return_value = dummy

        result = user.create_user("bob", "Bob")

        assert result == (True, "User bob (ID: 2) successfully created")
        mock_store.get_user.assert_called_once_with("bob")
        mock_generate_token.assert_called_once()
        mock_store.create_user.assert_called_once_with(
            username="bob", password="test_password_123", display_name="Bob", is_admin=False, is_service_account=False
        )

    @patch("mlflow_oidc_auth.user.generate_token", return_value="admin_password_456")
    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_new_user_with_admin_flag(self, mock_store, mock_generate_token):
        """Test creating new user with admin flag"""
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy = DummyUser("admin_user", 5)
        mock_store.create_user.return_value = dummy

        result = user.create_user("admin_user", "Admin User", is_admin=True)

        assert result == (True, "User admin_user (ID: 5) successfully created")
        mock_store.get_user.assert_called_once_with("admin_user")
        mock_generate_token.assert_called_once()
        mock_store.create_user.assert_called_once_with(
            username="admin_user", password="admin_password_456", display_name="Admin User", is_admin=True, is_service_account=False
        )

    @patch("mlflow_oidc_auth.user.generate_token", return_value="service_password_789")
    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_new_user_with_service_account_flag(self, mock_store, mock_generate_token):
        """Test creating new user with service account flag"""
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy = DummyUser("service_user", 6)
        mock_store.create_user.return_value = dummy

        result = user.create_user("service_user", "Service User", is_service_account=True)

        assert result == (True, "User service_user (ID: 6) successfully created")
        mock_store.get_user.assert_called_once_with("service_user")
        mock_generate_token.assert_called_once()
        mock_store.create_user.assert_called_once_with(
            username="service_user", password="service_password_789", display_name="Service User", is_admin=False, is_service_account=True
        )

    @patch("mlflow_oidc_auth.user.generate_token", return_value="super_password_000")
    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_new_user_with_both_flags(self, mock_store, mock_generate_token):
        """Test creating new user with both admin and service account flags"""
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy = DummyUser("super_user", 7)
        mock_store.create_user.return_value = dummy

        result = user.create_user("super_user", "Super User", is_admin=True, is_service_account=True)

        assert result == (True, "User super_user (ID: 7) successfully created")
        mock_store.get_user.assert_called_once_with("super_user")
        mock_generate_token.assert_called_once()
        mock_store.create_user.assert_called_once_with(
            username="super_user", password="super_password_000", display_name="Super User", is_admin=True, is_service_account=True
        )

    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_edge_case_empty_username(self, mock_store):
        """Test creating user with empty username"""
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy = DummyUser("", 8)
        mock_store.create_user.return_value = dummy

        result = user.create_user("", "Empty Username")

        assert result == (True, "User  (ID: 8) successfully created")

    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_edge_case_empty_display_name(self, mock_store):
        """Test creating user with empty display name"""
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy = DummyUser("test_user", 9)
        mock_store.create_user.return_value = dummy

        result = user.create_user("test_user", "")

        assert result == (True, "User test_user (ID: 9) successfully created")

    @patch("mlflow_oidc_auth.user.store")
    def test_create_user_special_characters_in_username(self, mock_store):
        """Test creating user with special characters in username"""
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy = DummyUser("user@domain.com", 10)
        mock_store.create_user.return_value = dummy

        result = user.create_user("user@domain.com", "Email User")

        assert result == (True, "User user@domain.com (ID: 10) successfully created")


class TestPopulateGroups:
    """Test suite for populate_groups function"""

    @patch("mlflow_oidc_auth.user.store")
    def test_populate_groups_single_group(self, mock_store):
        """Test populating a single group"""
        user.populate_groups(["admin"])
        mock_store.populate_groups.assert_called_once_with(group_names=["admin"])

    @patch("mlflow_oidc_auth.user.store")
    def test_populate_groups_multiple_groups(self, mock_store):
        """Test populating multiple groups"""
        groups = ["admin", "users", "developers"]
        user.populate_groups(groups)
        mock_store.populate_groups.assert_called_once_with(group_names=groups)

    @patch("mlflow_oidc_auth.user.store")
    def test_populate_groups_empty_list(self, mock_store):
        """Test populating with empty group list"""
        user.populate_groups([])
        mock_store.populate_groups.assert_called_once_with(group_names=[])

    @patch("mlflow_oidc_auth.user.store")
    def test_populate_groups_with_special_characters(self, mock_store):
        """Test populating groups with special characters"""
        groups = ["group-1", "group_2", "group@domain.com"]
        user.populate_groups(groups)
        mock_store.populate_groups.assert_called_once_with(group_names=groups)

    @patch("mlflow_oidc_auth.user.store")
    def test_populate_groups_with_duplicates(self, mock_store):
        """Test populating groups with duplicate names"""
        groups = ["admin", "admin", "users"]
        user.populate_groups(groups)
        mock_store.populate_groups.assert_called_once_with(group_names=groups)


class TestUpdateUser:
    """Test suite for update_user function"""

    @patch("mlflow_oidc_auth.user.store")
    def test_update_user_single_group(self, mock_store):
        """Test updating user with single group"""
        user.update_user("alice", ["admin"])
        mock_store.set_user_groups.assert_called_once_with("alice", ["admin"])

    @patch("mlflow_oidc_auth.user.store")
    def test_update_user_multiple_groups(self, mock_store):
        """Test updating user with multiple groups"""
        groups = ["admin", "developers", "testers"]
        user.update_user("bob", groups)
        mock_store.set_user_groups.assert_called_once_with("bob", groups)

    @patch("mlflow_oidc_auth.user.store")
    def test_update_user_empty_groups(self, mock_store):
        """Test updating user with empty group list (removing all groups)"""
        user.update_user("charlie", [])
        mock_store.set_user_groups.assert_called_once_with("charlie", [])

    @patch("mlflow_oidc_auth.user.store")
    def test_update_user_special_characters_in_username(self, mock_store):
        """Test updating user with special characters in username"""
        user.update_user("user@domain.com", ["group1"])
        mock_store.set_user_groups.assert_called_once_with("user@domain.com", ["group1"])

    @patch("mlflow_oidc_auth.user.store")
    def test_update_user_special_characters_in_groups(self, mock_store):
        """Test updating user with special characters in group names"""
        groups = ["group-1", "group_2", "group@domain.com"]
        user.update_user("dave", groups)
        mock_store.set_user_groups.assert_called_once_with("dave", groups)

    @patch("mlflow_oidc_auth.user.store")
    def test_update_user_duplicate_groups(self, mock_store):
        """Test updating user with duplicate group names"""
        groups = ["admin", "admin", "users"]
        user.update_user("eve", groups)
        mock_store.set_user_groups.assert_called_once_with("eve", groups)


class TestUserModuleIntegration:
    """Integration tests for user module functions"""

    @patch("mlflow_oidc_auth.user.store")
    def test_user_creation_and_group_assignment_workflow(self, mock_store):
        """Test complete workflow of creating user and assigning groups"""
        # Setup mocks for user creation
        mock_store.get_user.side_effect = MlflowException("User not found")
        dummy_user = DummyUser("workflow_user", 100)
        mock_store.create_user.return_value = dummy_user

        # Create user
        create_result = user.create_user("workflow_user", "Workflow User", is_admin=True)
        assert create_result[0] is True
        assert "successfully created" in create_result[1]

        # Populate groups
        groups = ["admin", "developers"]
        user.populate_groups(groups)

        # Assign groups to user
        user.update_user("workflow_user", groups)

        # Verify all calls were made
        mock_store.get_user.assert_called_with("workflow_user")
        mock_store.create_user.assert_called_once()
        mock_store.populate_groups.assert_called_once_with(group_names=groups)
        mock_store.set_user_groups.assert_called_once_with("workflow_user", groups)


# Legacy tests for backward compatibility
def test_generate_token_length_and_charset():
    """Legacy test for backward compatibility"""
    token = user.generate_token()
    assert len(token) == 24
    assert all(c.isalnum() for c in token)


@patch("mlflow_oidc_auth.user.store")
def test_create_user_already_exists(mock_store):
    """Legacy test for backward compatibility"""
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
    """Legacy test for backward compatibility"""
    mock_store.get_user.side_effect = Exception
    dummy = DummyUser("bob", 2)
    mock_store.create_user.return_value = dummy
    result = user.create_user("bob", "Bob", is_admin=False, is_service_account=True)
    assert result == (True, f"User bob (ID: 2) successfully created")
    mock_store.create_user.assert_called_once_with(username="bob", password="dummy_password", display_name="Bob", is_admin=False, is_service_account=True)


@patch("mlflow_oidc_auth.user.store")
def test_populate_groups(mock_store):
    """Legacy test for backward compatibility"""
    user.populate_groups(["g1", "g2"])
    mock_store.populate_groups.assert_called_once_with(group_names=["g1", "g2"])


@patch("mlflow_oidc_auth.user.store")
def test_update_user(mock_store):
    """Legacy test for backward compatibility"""
    user.update_user("alice", ["g1", "g2"])
    mock_store.set_user_groups.assert_called_once_with("alice", ["g1", "g2"])
