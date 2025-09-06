import unittest
from datetime import datetime
from mlflow_oidc_auth.entities import (
    User,
    ExperimentPermission,
    RegisteredModelPermission,
    Group,
    UserGroup,
    RegisteredModelGroupRegexPermission,
    ExperimentGroupRegexPermission,
    RegisteredModelRegexPermission,
    ExperimentRegexPermission,
)


class TestUser(unittest.TestCase):
    def test_user_to_json(self):
        user = User(
            id_="123",
            username="test_user",
            password_hash="password",
            password_expiration=None,
            is_admin=True,
            is_service_account=False,
            display_name="Test User",
            experiment_permissions=[ExperimentPermission("exp1", "read")],
            registered_model_permissions=[RegisteredModelPermission("model1", "EDIT")],
            groups=[Group("group1", "Group 1")],
        )

        # expected_json updated to include "password_expiration"
        expected_json = {
            "id": "123",
            "username": "test_user",
            "is_admin": True,
            "is_service_account": False,
            "password_expiration": None,
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
            "registered_model_permissions": [{"name": "model1", "permission": "EDIT", "user_id": None, "group_id": None}],
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
        self.assertEqual(user.registered_model_permissions[0].permission, "EDIT")
        self.assertEqual(len(user.groups), 1)
        self.assertEqual(user.groups[0].id, "group1")
        self.assertEqual(user.groups[0].group_name, "Group 1")

    def test_user_to_json_with_none_fields(self):
        user = User(
            id_="123",
            username="test_user",
            password_hash="password",
            password_expiration=None,
            is_admin=True,
            is_service_account=False,
            display_name="Test User",
            experiment_permissions=None,
            registered_model_permissions=None,
            groups=None,
        )

        # expected_json updated to include "password_expiration"
        expected_json = {
            "id": "123",
            "username": "test_user",
            "is_admin": True,
            "is_service_account": False,
            "password_expiration": None,
            "display_name": "Test User",
            "groups": [],
        }
        self.assertEqual(user.to_json(), expected_json)

    def test_user_from_json_with_none_fields(self):
        json_data = {
            "id": "123",
            "username": "test_user",
            "is_admin": True,
            "display_name": "Test User",
            "experiment_permissions": [],
            "registered_model_permissions": [],
            "groups": [],
        }

        user = User.from_json(json_data)

        self.assertEqual(user.id, "123")
        self.assertEqual(user.username, "test_user")
        self.assertEqual(user.password_hash, "REDACTED")
        self.assertTrue(user.is_admin)
        self.assertEqual(user.display_name, "Test User")
        self.assertEqual(user.experiment_permissions, [])
        self.assertEqual(user.registered_model_permissions, [])
        self.assertEqual(user.groups, [])


class TestExperimentPermission(unittest.TestCase):
    def test_experiment_permission_properties_and_setters(self):
        perm = ExperimentPermission("exp1", "read", user_id="u1", group_id="g1")
        self.assertEqual(perm.experiment_id, "exp1")
        self.assertEqual(perm.user_id, "u1")
        self.assertEqual(perm.permission, "read")
        self.assertEqual(perm.group_id, "g1")
        perm.permission = "EDIT"
        perm.group_id = "g2"
        self.assertEqual(perm.permission, "EDIT")
        self.assertEqual(perm.group_id, "g2")

    def test_experiment_permission_to_json_and_from_json(self):
        perm = ExperimentPermission("exp1", "read", user_id="u1", group_id="g1")
        json_data = perm.to_json()
        self.assertEqual(json_data["experiment_id"], "exp1")
        self.assertEqual(json_data["permission"], "read")
        self.assertEqual(json_data["user_id"], "u1")
        self.assertEqual(json_data["group_id"], "g1")
        perm2 = ExperimentPermission.from_json(json_data)
        self.assertEqual(perm2.experiment_id, "exp1")
        self.assertEqual(perm2.permission, "read")
        self.assertEqual(perm2.user_id, "u1")
        self.assertEqual(perm2.group_id, "g1")


class TestRegisteredModelPermission(unittest.TestCase):
    def test_registered_model_permission_properties_and_setters(self):
        perm = RegisteredModelPermission("model1", "read", user_id="u1", group_id="g1", prompt=True)
        self.assertEqual(perm.name, "model1")
        self.assertEqual(perm.user_id, "u1")
        self.assertEqual(perm.permission, "read")
        self.assertEqual(perm.group_id, "g1")
        self.assertTrue(perm.prompt)
        perm.permission = "EDIT"
        perm.group_id = "g2"
        perm.prompt = False
        self.assertEqual(perm.permission, "EDIT")
        self.assertEqual(perm.group_id, "g2")
        self.assertFalse(perm.prompt)

    def test_registered_model_permission_to_json_and_from_json(self):
        perm = RegisteredModelPermission("model1", "read", user_id="u1", group_id="g1", prompt=True)
        json_data = perm.to_json()
        self.assertEqual(json_data["name"], "model1")
        self.assertEqual(json_data["permission"], "read")
        self.assertEqual(json_data["user_id"], "u1")
        self.assertEqual(json_data["group_id"], "g1")
        self.assertTrue(json_data["prompt"])
        perm2 = RegisteredModelPermission.from_json(json_data)
        self.assertEqual(perm2.name, "model1")
        self.assertEqual(perm2.permission, "read")
        self.assertEqual(perm2.user_id, "u1")
        self.assertEqual(perm2.group_id, "g1")
        self.assertTrue(perm2.prompt)


class TestGroup(unittest.TestCase):
    def test_group_properties(self):
        group = Group("g1", "Group 1")
        self.assertEqual(group.id, "g1")
        self.assertEqual(group.group_name, "Group 1")

    def test_group_to_json_and_from_json(self):
        group = Group("g1", "Group 1")
        json_data = group.to_json()
        self.assertEqual(json_data["id"], "g1")
        self.assertEqual(json_data["group_name"], "Group 1")
        group2 = Group.from_json(json_data)
        self.assertEqual(group2.id, "g1")
        self.assertEqual(group2.group_name, "Group 1")


class TestUserGroup(unittest.TestCase):
    def test_user_group_properties(self):
        ug = UserGroup("u1", "g1")
        self.assertEqual(ug.user_id, "u1")
        self.assertEqual(ug.group_id, "g1")

    def test_user_group_to_json_and_from_json(self):
        ug = UserGroup("u1", "g1")
        json_data = ug.to_json()
        self.assertEqual(json_data["user_id"], "u1")
        self.assertEqual(json_data["group_id"], "g1")
        ug2 = UserGroup.from_json(json_data)
        self.assertEqual(ug2.user_id, "u1")
        self.assertEqual(ug2.group_id, "g1")


class TestUserPropertiesSetters(unittest.TestCase):
    def test_user_property_setters(self):
        user = User(
            id_="1",
            username="u",
            password_hash="dummy_hash",
            password_expiration=None,
            is_admin=False,
            is_service_account=False,
            display_name="d",
            experiment_permissions=None,
            registered_model_permissions=None,
            groups=None,
        )
        user.is_admin = True
        user.is_service_account = True
        user.experiment_permissions = [ExperimentPermission("e", "p")]
        user.registered_model_permissions = [RegisteredModelPermission("m", "p")]
        user.display_name = "display"
        user.groups = [Group("g", "gn")]
        self.assertTrue(user.is_admin)
        self.assertTrue(user.is_service_account)
        self.assertEqual(user.experiment_permissions[0].experiment_id, "e")
        self.assertEqual(user.registered_model_permissions[0].name, "m")
        self.assertEqual(user.display_name, "display")
        self.assertEqual(user.groups[0].id, "g")

    def test_user_password_expiration_setter(self):
        user = User(id_="1", username="u", password_hash="dummy_hash", password_expiration=None, is_admin=False, is_service_account=False, display_name="d")
        expiration_date = datetime(2024, 12, 31, 23, 59, 59)
        user.password_expiration = expiration_date
        self.assertEqual(user.password_expiration, expiration_date)

    def test_user_to_json_with_password_expiration(self):
        expiration_date = datetime(2024, 12, 31, 23, 59, 59)
        user = User(
            id_="123",
            username="test_user",
            password_hash="password",
            password_expiration=expiration_date,
            is_admin=True,
            is_service_account=False,
            display_name="Test User",
        )

        json_data = user.to_json()
        self.assertEqual(json_data["password_expiration"], "2024-12-31T23:59:59")

    def test_user_from_json_with_is_service_account_default(self):
        json_data = {
            "id": "123",
            "username": "test_user",
            "is_admin": True,
            "display_name": "Test User",
            "experiment_permissions": [],
            "registered_model_permissions": [],
            "groups": [],
        }

        user = User.from_json(json_data)
        self.assertFalse(user.is_service_account)  # Should default to False


class TestRegisteredModelGroupRegexPermission(unittest.TestCase):
    def test_registered_model_group_regex_permission_properties(self):
        perm = RegisteredModelGroupRegexPermission(id_="1", regex="model-.*", priority=10, group_id="g1", permission="READ", prompt=True)

        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "model-.*")
        self.assertEqual(perm.priority, 10)
        self.assertEqual(perm.group_id, "g1")
        self.assertEqual(perm.permission, "READ")
        self.assertTrue(perm.prompt)

    def test_registered_model_group_regex_permission_setters(self):
        perm = RegisteredModelGroupRegexPermission(id_="1", regex="model-.*", priority=10, group_id="g1", permission="READ", prompt=False)

        perm.priority = 20
        perm.permission = "EDIT"

        self.assertEqual(perm.priority, 20)
        self.assertEqual(perm.permission, "EDIT")

    def test_registered_model_group_regex_permission_to_json(self):
        perm = RegisteredModelGroupRegexPermission(id_="1", regex="model-.*", priority=10, group_id="g1", permission="READ", prompt=True)

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "model-.*", "priority": 10, "group_id": "g1", "permission": "READ", "prompt": True}
        self.assertEqual(json_data, expected)

    def test_registered_model_group_regex_permission_from_json(self):
        json_data = {"id": "1", "regex": "model-.*", "priority": 10, "group_id": "g1", "permission": "READ", "prompt": True}

        perm = RegisteredModelGroupRegexPermission.from_json(json_data)
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "model-.*")
        self.assertEqual(perm.priority, 10)
        self.assertEqual(perm.group_id, "g1")
        self.assertEqual(perm.permission, "READ")
        self.assertTrue(perm.prompt)

    def test_registered_model_group_regex_permission_from_json_default_prompt(self):
        json_data = {"id": "1", "regex": "model-.*", "priority": 10, "group_id": "g1", "permission": "READ"}

        perm = RegisteredModelGroupRegexPermission.from_json(json_data)
        self.assertFalse(perm.prompt)  # Should default to False


class TestExperimentGroupRegexPermission(unittest.TestCase):
    def test_experiment_group_regex_permission_properties(self):
        perm = ExperimentGroupRegexPermission(id_="1", regex="exp-.*", priority=5, group_id="g1", permission="READ")

        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "exp-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.group_id, "g1")
        self.assertEqual(perm.permission, "READ")

    def test_experiment_group_regex_permission_setters(self):
        perm = ExperimentGroupRegexPermission(id_="1", regex="exp-.*", priority=5, group_id="g1", permission="READ")

        perm.priority = 15
        perm.permission = "EDIT"

        self.assertEqual(perm.priority, 15)
        self.assertEqual(perm.permission, "EDIT")

    def test_experiment_group_regex_permission_to_json(self):
        perm = ExperimentGroupRegexPermission(id_="1", regex="exp-.*", priority=5, group_id="g1", permission="READ")

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "exp-.*", "priority": 5, "group_id": "g1", "permission": "READ"}
        self.assertEqual(json_data, expected)

    def test_experiment_group_regex_permission_from_json(self):
        json_data = {"id": "1", "regex": "exp-.*", "priority": 5, "group_id": "g1", "permission": "READ"}

        perm = ExperimentGroupRegexPermission.from_json(json_data)
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "exp-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.group_id, "g1")
        self.assertEqual(perm.permission, "READ")


class TestRegisteredModelRegexPermission(unittest.TestCase):
    def test_registered_model_regex_permission_properties(self):
        perm = RegisteredModelRegexPermission(id_="1", regex="model-.*", priority=10, user_id="u1", permission="READ", prompt=True)

        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "model-.*")
        self.assertEqual(perm.priority, 10)
        self.assertEqual(perm.user_id, "u1")
        self.assertEqual(perm.permission, "READ")
        self.assertTrue(perm.prompt)

    def test_registered_model_regex_permission_setters(self):
        perm = RegisteredModelRegexPermission(id_="1", regex="model-.*", priority=10, user_id="u1", permission="READ", prompt=False)

        perm.priority = 20
        perm.permission = "EDIT"
        perm.prompt = True

        self.assertEqual(perm.priority, 20)
        self.assertEqual(perm.permission, "EDIT")
        self.assertTrue(perm.prompt)

    def test_registered_model_regex_permission_to_json(self):
        perm = RegisteredModelRegexPermission(id_="1", regex="model-.*", priority=10, user_id="u1", permission="READ", prompt=True)

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "model-.*", "priority": 10, "user_id": "u1", "permission": "READ", "prompt": True}
        self.assertEqual(json_data, expected)

    def test_registered_model_regex_permission_from_json(self):
        json_data = {"id": "1", "regex": "model-.*", "priority": 10, "user_id": "u1", "permission": "READ", "prompt": True}

        perm = RegisteredModelRegexPermission.from_json(json_data)
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "model-.*")
        self.assertEqual(perm.priority, 10)
        self.assertEqual(perm.user_id, "u1")
        self.assertEqual(perm.permission, "READ")
        self.assertTrue(perm.prompt)

    def test_registered_model_regex_permission_from_json_default_prompt(self):
        json_data = {"id": "1", "regex": "model-.*", "priority": 10, "user_id": "u1", "permission": "READ"}

        perm = RegisteredModelRegexPermission.from_json(json_data)
        self.assertFalse(perm.prompt)  # Should default to False


class TestExperimentRegexPermission(unittest.TestCase):
    def test_experiment_regex_permission_properties(self):
        perm = ExperimentRegexPermission(id_="1", regex="exp-.*", priority=5, user_id="u1", permission="READ")

        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "exp-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.user_id, "u1")
        self.assertEqual(perm.permission, "READ")

    def test_experiment_regex_permission_setters(self):
        perm = ExperimentRegexPermission(id_="1", regex="exp-.*", priority=5, user_id="u1", permission="READ")

        perm.priority = 15
        perm.permission = "EDIT"

        self.assertEqual(perm.priority, 15)
        self.assertEqual(perm.permission, "EDIT")

    def test_experiment_regex_permission_to_json(self):
        perm = ExperimentRegexPermission(id_="1", regex="exp-.*", priority=5, user_id="u1", permission="READ")

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "exp-.*", "priority": 5, "user_id": "u1", "permission": "READ"}
        self.assertEqual(json_data, expected)

    def test_experiment_regex_permission_from_json(self):
        json_data = {"id": "1", "regex": "exp-.*", "priority": 5, "user_id": "u1", "permission": "READ"}

        perm = ExperimentRegexPermission.from_json(json_data)
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "exp-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.user_id, "u1")
        self.assertEqual(perm.permission, "READ")


class TestExperimentPermissionEdgeCases(unittest.TestCase):
    def test_experiment_permission_from_json_without_group_id(self):
        json_data = {"experiment_id": "exp1", "permission": "read", "user_id": "u1"}

        perm = ExperimentPermission.from_json(json_data)
        self.assertEqual(perm.experiment_id, "exp1")
        self.assertEqual(perm.permission, "read")
        self.assertEqual(perm.user_id, "u1")
        self.assertIsNone(perm.group_id)


class TestRegisteredModelPermissionEdgeCases(unittest.TestCase):
    def test_registered_model_permission_from_json_without_group_id(self):
        json_data = {"name": "model1", "permission": "read", "user_id": "u1"}

        perm = RegisteredModelPermission.from_json(json_data)
        self.assertEqual(perm.name, "model1")
        self.assertEqual(perm.permission, "read")
        self.assertEqual(perm.user_id, "u1")
        self.assertIsNone(perm.group_id)

    def test_registered_model_permission_from_json_prompt_conversion(self):
        # Test various prompt values that should convert to boolean
        test_cases = [
            (True, True),
            (False, False),
            (1, True),
            (0, False),
            ("true", True),
            ("false", True),  # Non-empty string is truthy
            ("", False),
            (None, False),
        ]

        for prompt_value, expected in test_cases:
            json_data = {"name": "model1", "permission": "read", "user_id": "u1", "prompt": prompt_value}

            perm = RegisteredModelPermission.from_json(json_data)
            self.assertEqual(perm.prompt, expected, f"Failed for prompt value: {prompt_value}")
