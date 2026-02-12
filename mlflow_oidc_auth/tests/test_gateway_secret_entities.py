"""Tests for GatewaySecretPermission, GatewaySecretRegexPermission, and GatewaySecretGroupRegexPermission entities."""

import unittest

from mlflow_oidc_auth.entities import (
    GatewaySecretGroupRegexPermission,
    GatewaySecretPermission,
    GatewaySecretRegexPermission,
)


class TestGatewaySecretPermission(unittest.TestCase):
    """Tests for GatewaySecretPermission entity."""

    def test_properties(self) -> None:
        """Should expose secret_id, permission, user_id, group_id properties."""
        perm = GatewaySecretPermission(secret_id="s1", permission="READ", user_id=1)
        self.assertEqual(perm.secret_id, "s1")
        self.assertEqual(perm.permission, "READ")
        self.assertEqual(perm.user_id, 1)
        self.assertIsNone(perm.group_id)

    def test_to_json(self) -> None:
        """Should serialize to JSON with 'secret_id' instead of 'instance'."""
        perm = GatewaySecretPermission(secret_id="s1", permission="MANAGE", user_id=1, group_id=2)
        data = perm.to_json()

        self.assertEqual(data["secret_id"], "s1")
        self.assertEqual(data["permission"], "MANAGE")
        self.assertEqual(data["user_id"], 1)
        self.assertEqual(data["group_id"], 2)
        self.assertNotIn("instance", data)

    def test_from_json(self) -> None:
        """Should deserialize from JSON dict."""
        data = {"secret_id": "s2", "permission": "EDIT", "user_id": 5, "group_id": 3}
        perm = GatewaySecretPermission.from_json(data)

        self.assertEqual(perm.secret_id, "s2")
        self.assertEqual(perm.permission, "EDIT")
        self.assertEqual(perm.user_id, 5)
        self.assertEqual(perm.group_id, 3)

    def test_to_json_and_from_json_roundtrip(self) -> None:
        """Should roundtrip through JSON correctly."""
        original = GatewaySecretPermission(secret_id="rt-1", permission="READ", user_id=10)
        data = original.to_json()
        restored = GatewaySecretPermission.from_json(data)

        self.assertEqual(restored.secret_id, original.secret_id)
        self.assertEqual(restored.permission, original.permission)
        self.assertEqual(restored.user_id, original.user_id)

    def test_from_json_with_none_ids(self) -> None:
        """Should handle None user_id and group_id."""
        data = {"secret_id": "s3", "permission": "READ"}
        perm = GatewaySecretPermission.from_json(data)

        self.assertIsNone(perm.user_id)
        self.assertIsNone(perm.group_id)

    def test_from_json_casts_string_ids(self) -> None:
        """Should cast string IDs to integers."""
        data = {
            "secret_id": "s4",
            "permission": "READ",
            "user_id": "42",
            "group_id": "7",
        }
        perm = GatewaySecretPermission.from_json(data)

        self.assertEqual(perm.user_id, 42)
        self.assertEqual(perm.group_id, 7)

    def test_from_json_invalid_user_id_raises(self) -> None:
        """Should raise ValueError for non-integer user_id."""
        data = {"secret_id": "s5", "permission": "READ", "user_id": "not-a-number"}
        with self.assertRaises(ValueError):
            GatewaySecretPermission.from_json(data)

    def test_from_json_invalid_group_id_raises(self) -> None:
        """Should raise ValueError for non-integer group_id."""
        data = {"secret_id": "s6", "permission": "READ", "group_id": "bad"}
        with self.assertRaises(ValueError):
            GatewaySecretPermission.from_json(data)


class TestGatewaySecretRegexPermission(unittest.TestCase):
    """Tests for GatewaySecretRegexPermission entity."""

    def test_properties(self) -> None:
        """Should expose id, regex, priority, user_id, permission."""
        perm = GatewaySecretRegexPermission(id_="10", regex="secret-.*", priority=5, user_id=1, permission="READ")

        self.assertEqual(perm.id, "10")
        self.assertEqual(perm.regex, "secret-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.user_id, 1)
        self.assertEqual(perm.permission, "READ")

    def test_to_json(self) -> None:
        """Should serialize to JSON dict."""
        perm = GatewaySecretRegexPermission(id_="20", regex="^api-.*", priority=1, user_id=2, permission="MANAGE")
        data = perm.to_json()

        self.assertEqual(data["id"], "20")
        self.assertEqual(data["regex"], "^api-.*")
        self.assertEqual(data["priority"], 1)
        self.assertEqual(data["user_id"], 2)
        self.assertEqual(data["permission"], "MANAGE")

    def test_from_json(self) -> None:
        """Should deserialize from JSON dict."""
        data = {
            "id": "30",
            "regex": "test-.*",
            "priority": 3,
            "user_id": 5,
            "permission": "EDIT",
        }
        perm = GatewaySecretRegexPermission.from_json(data)

        self.assertEqual(perm.id, "30")
        self.assertEqual(perm.regex, "test-.*")
        self.assertEqual(perm.priority, 3)
        self.assertEqual(perm.user_id, 5)
        self.assertEqual(perm.permission, "EDIT")

    def test_from_json_casts_string_user_id(self) -> None:
        """Should cast string user_id to int."""
        data = {
            "id": "1",
            "regex": ".*",
            "priority": 0,
            "user_id": "99",
            "permission": "READ",
        }
        perm = GatewaySecretRegexPermission.from_json(data)

        self.assertEqual(perm.user_id, 99)

    def test_from_json_invalid_user_id_raises(self) -> None:
        """Should raise ValueError for non-integer user_id."""
        data = {
            "id": "1",
            "regex": ".*",
            "priority": 0,
            "user_id": "bad",
            "permission": "READ",
        }
        with self.assertRaises(ValueError):
            GatewaySecretRegexPermission.from_json(data)


class TestGatewaySecretGroupRegexPermission(unittest.TestCase):
    """Tests for GatewaySecretGroupRegexPermission entity."""

    def test_properties(self) -> None:
        """Should expose id, regex, priority, group_id, permission."""
        perm = GatewaySecretGroupRegexPermission(id_="1", regex="grp-.*", priority=10, group_id=5, permission="READ")

        self.assertEqual(perm.id, "1")
        self.assertEqual(perm.regex, "grp-.*")
        self.assertEqual(perm.priority, 10)
        self.assertEqual(perm.group_id, 5)
        self.assertEqual(perm.permission, "READ")

    def test_to_json(self) -> None:
        """Should serialize to JSON dict."""
        perm = GatewaySecretGroupRegexPermission(id_="2", regex="^team-.*", priority=2, group_id=3, permission="MANAGE")
        data = perm.to_json()

        self.assertEqual(data["id"], "2")
        self.assertEqual(data["regex"], "^team-.*")
        self.assertEqual(data["priority"], 2)
        self.assertEqual(data["group_id"], 3)
        self.assertEqual(data["permission"], "MANAGE")

    def test_from_json(self) -> None:
        """Should deserialize from JSON dict."""
        data = {
            "id": "5",
            "regex": "prod-.*",
            "priority": 7,
            "group_id": 8,
            "permission": "EDIT",
        }
        perm = GatewaySecretGroupRegexPermission.from_json(data)

        self.assertEqual(perm.id, "5")
        self.assertEqual(perm.regex, "prod-.*")
        self.assertEqual(perm.group_id, 8)

    def test_from_json_casts_string_group_id(self) -> None:
        """Should cast string group_id to int."""
        data = {
            "id": "1",
            "regex": ".*",
            "priority": 0,
            "group_id": "42",
            "permission": "READ",
        }
        perm = GatewaySecretGroupRegexPermission.from_json(data)

        self.assertEqual(perm.group_id, 42)

    def test_from_json_invalid_group_id_raises(self) -> None:
        """Should raise ValueError for non-integer group_id."""
        data = {
            "id": "1",
            "regex": ".*",
            "priority": 0,
            "group_id": "nope",
            "permission": "READ",
        }
        with self.assertRaises(ValueError):
            GatewaySecretGroupRegexPermission.from_json(data)

    def test_to_json_omits_none_values(self) -> None:
        """Should omit user_id from JSON when it's None."""
        perm = GatewaySecretGroupRegexPermission(id_="3", regex=".*", priority=0, group_id=1, permission="READ")
        data = perm.to_json()

        self.assertNotIn("user_id", data)
        self.assertIn("group_id", data)
