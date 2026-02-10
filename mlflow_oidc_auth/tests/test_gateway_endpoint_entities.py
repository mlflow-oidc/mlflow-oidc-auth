import unittest

from mlflow_oidc_auth.entities import (
    GatewayEndpointPermission,
    GatewayEndpointRegexPermission,
    GatewayEndpointGroupRegexPermission,
)


class TestGatewayEndpointEntities(unittest.TestCase):
    def test_gateway_endpoint_permission_properties(self):
        perm = GatewayEndpointPermission(endpoint_id="ep1", permission="USE", user_id=1)
        self.assertEqual(perm.endpoint_id, "ep1")
        self.assertEqual(perm.permission, "USE")
        self.assertEqual(perm.user_id, 1)

    def test_gateway_endpoint_permission_to_json_and_from_json(self):
        perm = GatewayEndpointPermission(endpoint_id="ep1", permission="READ", user_id=1, group_id=2)
        json_data = perm.to_json()
        self.assertEqual(json_data["endpoint_id"], "ep1")
        self.assertEqual(json_data["permission"], "READ")
        self.assertEqual(json_data["user_id"], 1)
        self.assertEqual(json_data["group_id"], 2)

        p2 = GatewayEndpointPermission.from_json(json_data)
        self.assertEqual(p2.endpoint_id, "ep1")
        self.assertEqual(p2.permission, "READ")
        self.assertEqual(p2.user_id, 1)
        self.assertEqual(p2.group_id, 2)

    def test_endpoint_regex_permission(self):
        perm = GatewayEndpointRegexPermission(id_="1", regex="ep-.*", priority=5, user_id=1, permission="USE")
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "ep-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.user_id, 1)
        self.assertEqual(perm.permission, "USE")

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "ep-.*", "priority": 5, "user_id": 1, "permission": "USE"}
        self.assertEqual(json_data, expected)

        p2 = GatewayEndpointRegexPermission.from_json(json_data)
        self.assertEqual(p2.id, "1")
        self.assertEqual(p2.user_id, 1)
        self.assertEqual(p2.permission, "USE")

    def test_endpoint_group_regex_permission(self):
        perm = GatewayEndpointGroupRegexPermission(id_="1", regex="ep-.*", priority=5, group_id=1, permission="READ")
        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "ep-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.group_id, 1)
        self.assertEqual(perm.permission, "READ")

        json_data = perm.to_json()
        expected = {"id": "1", "regex": "ep-.*", "priority": 5, "group_id": 1, "permission": "READ"}
        self.assertEqual(json_data, expected)

        p2 = GatewayEndpointGroupRegexPermission.from_json(json_data)
        self.assertEqual(p2.id, "1")
        self.assertEqual(p2.group_id, 1)
        self.assertEqual(p2.permission, "READ")
