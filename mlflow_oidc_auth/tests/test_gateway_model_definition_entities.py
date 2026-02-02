import unittest

from mlflow_oidc_auth.entities import (
    GatewayModelDefinitionPermission,
    GatewayModelDefinitionRegexPermission,
    GatewayModelDefinitionGroupRegexPermission,
)


class TestGatewayModelDefinitionEntities(unittest.TestCase):
    def test_model_definition_permission_properties(self):
        perm = GatewayModelDefinitionPermission(model_definition_id="md1", permission="USE", user_id=1)
        self.assertEqual(perm.model_definition_id, "md1")
        self.assertEqual(perm.permission, "USE")
        self.assertEqual(perm.user_id, 1)

    def test_model_definition_permission_to_json_and_from_json(self):
        perm = GatewayModelDefinitionPermission(model_definition_id="md1", permission="READ", user_id=1, group_id=2)
        json_data = perm.to_json()
        self.assertEqual(json_data["model_definition_id"], "md1")
        self.assertEqual(json_data["permission"], "READ")
        self.assertEqual(json_data["user_id"], 1)
        self.assertEqual(json_data["group_id"], 2)

        p2 = GatewayModelDefinitionPermission.from_json(json_data)
        self.assertEqual(p2.model_definition_id, "md1")
        self.assertEqual(p2.permission, "READ")
        self.assertEqual(p2.user_id, 1)
        self.assertEqual(p2.group_id, 2)

    def test_model_definition_regex_permission(self):
        perm = GatewayModelDefinitionRegexPermission(id_="1", regex="md-.*", priority=5, user_id=1, permission="USE")
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "md-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.user_id, 1)
        self.assertEqual(perm.permission, "USE")

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "md-.*", "priority": 5, "user_id": 1, "permission": "USE"}
        self.assertEqual(json_data, expected)

        p2 = GatewayModelDefinitionRegexPermission.from_json(json_data)
        self.assertEqual(p2.id, "1")
        self.assertEqual(p2.user_id, 1)
        self.assertEqual(p2.permission, "USE")

    def test_model_definition_group_regex_permission(self):
        perm = GatewayModelDefinitionGroupRegexPermission(id_="1", regex="md-.*", priority=5, group_id=1, permission="READ")
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "md-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.group_id, 1)
        self.assertEqual(perm.permission, "READ")

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "md-.*", "priority": 5, "group_id": 1, "permission": "READ"}
        self.assertEqual(json_data, expected)

        p2 = GatewayModelDefinitionGroupRegexPermission.from_json(json_data)
        self.assertEqual(p2.id, "1")
        self.assertEqual(p2.group_id, 1)
        self.assertEqual(p2.permission, "READ" )