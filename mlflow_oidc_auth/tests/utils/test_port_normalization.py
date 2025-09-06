#!/usr/bin/env python3
"""
Comprehensive tests for URL port normalization functionality.

This test module validates that the normalize_url_port function correctly
handles various URL formats, port combinations, and edge cases.
"""

import unittest
from mlflow_oidc_auth.utils.uri import normalize_url_port


class TestPortNormalization(unittest.TestCase):
    """Test cases for URL port normalization functionality."""

    def test_normalize_https_standard_port(self):
        """Test that HTTPS port 443 is omitted from URLs."""
        url = "https://example.com:443/path"
        result = normalize_url_port(url)
        expected = "https://example.com/path"
        self.assertEqual(result, expected)

    def test_normalize_http_standard_port(self):
        """Test that HTTP port 80 is omitted from URLs."""
        url = "http://example.com:80/path"
        result = normalize_url_port(url)
        expected = "http://example.com/path"
        self.assertEqual(result, expected)

    def test_preserve_custom_https_port(self):
        """Test that custom HTTPS ports are preserved in URLs."""
        url = "https://example.com:8443/path"
        result = normalize_url_port(url)
        expected = "https://example.com:8443/path"
        self.assertEqual(result, expected)

    def test_preserve_custom_http_port(self):
        """Test that custom HTTP ports are preserved in URLs."""
        url = "http://example.com:8080/path"
        result = normalize_url_port(url)
        expected = "http://example.com:8080/path"
        self.assertEqual(result, expected)

    def test_no_port_in_url(self):
        """Test that URLs without explicit ports remain unchanged."""
        url = "https://example.com/path"
        result = normalize_url_port(url)
        expected = "https://example.com/path"
        self.assertEqual(result, expected)

    def test_localhost_custom_port(self):
        """Test that localhost custom ports are preserved."""
        url = "http://localhost:5000/path"
        result = normalize_url_port(url)
        expected = "http://localhost:5000/path"
        self.assertEqual(result, expected)

    def test_https_standard_port_with_mlflow_callback(self):
        """Test HTTPS standard port normalization with MLflow callback path."""
        url = "https://example.com:443/apps/mlflow/oidc/callback"
        result = normalize_url_port(url)
        expected = "https://example.com/apps/mlflow/oidc/callback"
        self.assertEqual(result, expected)

    def test_http_standard_port_with_mlflow_callback(self):
        """Test HTTP standard port normalization with MLflow callback path."""
        url = "http://example.com:80/apps/mlflow/oidc/callback"
        result = normalize_url_port(url)
        expected = "http://example.com/apps/mlflow/oidc/callback"
        self.assertEqual(result, expected)

    def test_malformed_url_handling(self):
        """Test that malformed URLs are returned unchanged without errors."""
        url = "not-a-valid-url"
        result = normalize_url_port(url)
        expected = "not-a-valid-url"
        self.assertEqual(result, expected)

    def test_url_with_userinfo_and_standard_port(self):
        """Test that URLs with userinfo and standard ports are handled correctly."""
        url = "https://user:pass@example.com:443/path"
        result = normalize_url_port(url)
        expected = "https://user:pass@example.com/path"
        self.assertEqual(result, expected)

    def test_url_with_userinfo_and_custom_port(self):
        """Test that URLs with userinfo and custom ports preserve the port."""
        url = "https://user:pass@example.com:8443/path"
        result = normalize_url_port(url)
        expected = "https://user:pass@example.com:8443/path"
        self.assertEqual(result, expected)

    def test_url_with_query_parameters(self):
        """Test that URLs with query parameters are handled correctly."""
        url = "https://example.com:443/path?param=value"
        result = normalize_url_port(url)
        expected = "https://example.com/path?param=value"
        self.assertEqual(result, expected)

    def test_url_with_fragment(self):
        """Test that URLs with fragments are handled correctly."""
        url = "https://example.com:443/path#section"
        result = normalize_url_port(url)
        expected = "https://example.com/path#section"
        self.assertEqual(result, expected)

    def test_edge_case_empty_string(self):
        """Test handling of empty string input."""
        url = ""
        result = normalize_url_port(url)
        expected = ""
        self.assertEqual(result, expected)

    def test_edge_case_none_input(self):
        """Test handling of None input (should handle gracefully)."""
        with self.assertRaises((TypeError, AttributeError)):
            normalize_url_port(None)


if __name__ == "__main__":
    unittest.main()
