import unittest
from mlflow_oidc_auth.entities import User, ExperimentPermission, RegisteredModelPermission, Group


class TestUser(unittest.TestCase):
    def test_user_to_json(self):
        user = User(
            id_="123",
            username="test_user",
            password_hash="password",
            is_admin=True,
            is_service_account=False,
            display_name="Test User",
            experiment_permissions=[ExperimentPermission("exp1", "read")],
            registered_model_permissions=[RegisteredModelPermission("model1", "write")],
            groups=[Group("group1", "Group 1")],
        )

        # expected_json does not contain "experiment_permissions" and "registered_model_permissions",
        # this is expected
        expected_json = {
            "id": "123",
            "username": "test_user",
            "is_admin": True,
            "is_service_account": False,
            "display_name": "Test User",
            "groups": [{"id": "group1", "group_name": "Group 1"}],
        }
        self.assertEqual(user.to_json(), expected_json)

    def test_user_from_json(self):
        json_data = {
            "id": "123",
            "username": "test_user",
            "is_admin": True,
            "display_name": "Test User",
            "experiment_permissions": [{"experiment_id": "exp1", "permission": "read", "user_id": None, "group_id": None}],
            "registered_model_permissions": [{"name": "model1", "permission": "write", "user_id": None, "group_id": None}],
            "groups": [{"id": "group1", "group_name": "Group 1"}],
        }

        user = User.from_json(json_data)

        self.assertEqual(user.id, "123")
        self.assertEqual(user.username, "test_user")
        self.assertEqual(user.password_hash, "REDACTED")
        self.assertTrue(user.is_admin)
        self.assertEqual(user.display_name, "Test User")
        self.assertEqual(len(user.experiment_permissions or []), 1)
        self.assertEqual(user.experiment_permissions[0].experiment_id, "exp1")
        self.assertEqual(user.experiment_permissions[0].permission, "read")
        self.assertEqual(len(user.registered_model_permissions), 1)
        self.assertEqual(user.registered_model_permissions[0].name, "model1")
        self.assertEqual(user.registered_model_permissions[0].permission, "write")
        self.assertEqual(len(user.groups), 1)
        self.assertEqual(user.groups[0].id, "group1")
        self.assertEqual(user.groups[0].group_name, "Group 1")
