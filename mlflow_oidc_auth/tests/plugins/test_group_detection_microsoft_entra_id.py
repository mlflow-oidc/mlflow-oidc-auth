import unittest
from unittest.mock import Mock, patch
from mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id import get_user_groups


class TestGetUserGroups(unittest.TestCase):
    """Comprehensive tests for Microsoft Entra ID group detection plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.access_token = "test_access_token_12345"
        self.base_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        self.graph_url = "https://graph.microsoft.com/v1.0/me/memberOf"

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_success_single_page(self, mock_get):
        """Test successful group retrieval with single page response."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "value": [
                {"displayName": "Group 1"},
                {"displayName": "Group 2"},
                {"displayName": "Group 3"},
                {"displayName": "Group 3"},  # Duplicate to test deduplication
                {"displayName": None},  # None value to test filtering
            ]
        }
        mock_get.return_value = mock_response

        groups = get_user_groups(self.access_token)

        mock_get.assert_called_once_with(self.graph_url, headers=self.base_headers)
        expected_groups = ["Group 1", "Group 2", "Group 3"]
        self.assertEqual(groups, expected_groups)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_success_multiple_pages(self, mock_get):
        """Test successful group retrieval with pagination."""
        # First page response
        first_response = Mock()
        first_response.ok = True
        first_response.json.return_value = {
            "value": [
                {"displayName": "Group 1"},
                {"displayName": "Group 2"},
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/memberOf?$skiptoken=abc123",
        }

        # Second page response
        second_response = Mock()
        second_response.ok = True
        second_response.json.return_value = {
            "value": [
                {"displayName": "Group 3"},
                {"displayName": "Group 4"},
            ]
        }

        mock_get.side_effect = [first_response, second_response]

        groups = get_user_groups(self.access_token)

        # Verify both API calls were made
        self.assertEqual(mock_get.call_count, 2)
        mock_get.assert_any_call(self.graph_url, headers=self.base_headers)
        mock_get.assert_any_call(
            "https://graph.microsoft.com/v1.0/me/memberOf?$skiptoken=abc123",
            headers=self.base_headers,
        )

        expected_groups = ["Group 1", "Group 2", "Group 3", "Group 4"]
        self.assertEqual(groups, expected_groups)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_empty_response(self, mock_get):
        """Test handling of empty group response."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"value": []}
        mock_get.return_value = mock_response

        groups = get_user_groups(self.access_token)

        mock_get.assert_called_once_with(self.graph_url, headers=self.base_headers)
        self.assertEqual(groups, [])

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_all_none_display_names(self, mock_get):
        """Test handling when all groups have None displayName."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "value": [
                {"displayName": None},
                {"displayName": None},
                {"id": "group-id-1"},  # Group without displayName
            ]
        }
        mock_get.return_value = mock_response

        groups = get_user_groups(self.access_token)

        mock_get.assert_called_once_with(self.graph_url, headers=self.base_headers)
        self.assertEqual(groups, [])

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_http_error_401(self, mock_get):
        """Test handling of HTTP 401 Unauthorized error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized: Invalid token"
        mock_get.return_value = mock_response

        with self.assertRaises(Exception) as context:
            get_user_groups(self.access_token)

        self.assertIn(
            "Error retrieving user groups: 401-Unauthorized: Invalid token",
            str(context.exception),
        )
        mock_get.assert_called_once_with(self.graph_url, headers=self.base_headers)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_http_error_403(self, mock_get):
        """Test handling of HTTP 403 Forbidden error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Forbidden: Insufficient permissions"
        mock_get.return_value = mock_response

        with self.assertRaises(Exception) as context:
            get_user_groups(self.access_token)

        self.assertIn(
            "Error retrieving user groups: 403-Forbidden: Insufficient permissions",
            str(context.exception),
        )

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_http_error_500(self, mock_get):
        """Test handling of HTTP 500 Internal Server Error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        with self.assertRaises(Exception) as context:
            get_user_groups(self.access_token)

        self.assertIn(
            "Error retrieving user groups: 500-Internal Server Error",
            str(context.exception),
        )

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_network_error(self, mock_get):
        """Test handling of network connectivity errors."""
        import requests

        mock_get.side_effect = requests.ConnectionError("Network unreachable")

        with self.assertRaises(requests.ConnectionError):
            get_user_groups(self.access_token)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_timeout_error(self, mock_get):
        """Test handling of request timeout errors."""
        import requests

        mock_get.side_effect = requests.Timeout("Request timed out")

        with self.assertRaises(requests.Timeout):
            get_user_groups(self.access_token)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_json_decode_error(self, mock_get):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        with self.assertRaises(ValueError):
            get_user_groups(self.access_token)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_malformed_response_no_value(self, mock_get):
        """Test handling of malformed response without 'value' key."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"error": "malformed response"}
        mock_get.return_value = mock_response

        with self.assertRaises(KeyError):
            get_user_groups(self.access_token)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_pagination_error_on_second_page(self, mock_get):
        """Test error handling when second page request fails."""
        # First page response succeeds
        first_response = Mock()
        first_response.ok = True
        first_response.json.return_value = {
            "value": [{"displayName": "Group 1"}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/memberOf?$skiptoken=abc123",
        }

        # Second page response fails
        second_response = Mock()
        second_response.ok = False
        second_response.status_code = 429
        second_response.text = "Too Many Requests"

        mock_get.side_effect = [first_response, second_response]

        with self.assertRaises(Exception) as context:
            get_user_groups(self.access_token)

        self.assertIn(
            "Error retrieving user groups: 429-Too Many Requests",
            str(context.exception),
        )
        self.assertEqual(mock_get.call_count, 2)

    @patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get")
    def test_get_user_groups_complex_pagination_scenario(self, mock_get):
        """Test complex pagination scenario with multiple pages and mixed data."""
        # Page 1
        page1_response = Mock()
        page1_response.ok = True
        page1_response.json.return_value = {
            "value": [
                {"displayName": "Admin Group"},
                {"displayName": "User Group"},
                {"displayName": None},  # Should be filtered out
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/memberOf?$skiptoken=page2",
        }

        # Page 2
        page2_response = Mock()
        page2_response.ok = True
        page2_response.json.return_value = {
            "value": [
                {"displayName": "Developer Group"},
                {"displayName": "Admin Group"},  # Duplicate from page 1
                {"displayName": "Test Group"},
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/memberOf?$skiptoken=page3",
        }

        # Page 3 (final page)
        page3_response = Mock()
        page3_response.ok = True
        page3_response.json.return_value = {
            "value": [
                {"displayName": "Final Group"},
                {"displayName": None},  # Should be filtered out
            ]
        }

        mock_get.side_effect = [page1_response, page2_response, page3_response]

        groups = get_user_groups(self.access_token)

        # Verify all three API calls were made
        self.assertEqual(mock_get.call_count, 3)

        # Verify deduplication and filtering worked correctly
        expected_groups = [
            "Admin Group",
            "User Group",
            "Developer Group",
            "Test Group",
            "Final Group",
        ]
        self.assertEqual(groups, expected_groups)

    def test_get_user_groups_parameter_validation(self):
        """Test that the function accepts various token formats."""
        # Test with different token formats - this tests the function signature
        # and parameter handling without making actual HTTP requests
        with patch("mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {"value": []}
            mock_get.return_value = mock_response

            # Test with various token formats
            test_tokens = [
                "simple_token",
                "Bearer_token_format",
                "very_long_token_" + "x" * 100,
                "token.with.dots",
                "token-with-dashes",
                "token_with_underscores",
            ]

            for token in test_tokens:
                groups = get_user_groups(token)
                self.assertEqual(groups, [])

                # Verify correct headers were used
                expected_headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                mock_get.assert_called_with(self.graph_url, headers=expected_headers)
