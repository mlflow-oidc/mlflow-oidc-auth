import unittest
from unittest.mock import Mock, patch
from mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id import get_user_groups


class TestGetUserGroups(unittest.TestCase):
    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "value": [
                {"displayName": "Group 1"},
                {"displayName": "Group 2"},
                {"displayName": "Group 3"},
                {"displayName": "Group 3"},
                {"displayName": None},
            ]
        }
        mock_get.return_value = mock_response

        access_token = "D34DB33F"
        groups = get_user_groups(access_token)

        mock_get.assert_called_once_with(
            "https://graph.microsoft.com/v1.0/me/memberOf",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

        expected_groups = ["Group 1", "Group 2", "Group 3"]
        self.assertEqual(groups, expected_groups)
