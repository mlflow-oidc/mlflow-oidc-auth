"""
Tests for dynamic OIDC redirect URI calculation.

These tests verify that the redirect URI is correctly calculated
from request headers in various proxy scenarios.
"""

import unittest
from unittest.mock import MagicMock
from fastapi import Request
from mlflow_oidc_auth.utils.uri import (
    _get_dynamic_redirect_uri,
    get_configured_or_dynamic_redirect_uri,
    _get_base_url_from_request,
    normalize_url_port,
)


class TestDynamicRedirectUri(unittest.TestCase):
    """Test cases for dynamic redirect URI calculation."""

    def setUp(self):
        """Set up test fixtures."""

    def tearDown(self):
        """Clean up test fixtures."""

    def test_get_base_url_from_request(self):
        """Test base URL extraction from FastAPI request."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "https://example.com/my-app/endpoint"
        mock_request.scope = {"root_path": "/my-app"}

        result = _get_base_url_from_request(mock_request)
        expected = "https://example.com/my-app"
        self.assertEqual(result, expected)

    def test_get_base_url_from_request_no_root_path(self):
        """Test base URL extraction without root path."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "https://example.com/endpoint"
        mock_request.scope = {}

        result = _get_base_url_from_request(mock_request)
        expected = "https://example.com"
        self.assertEqual(result, expected)

    def test_get_base_url_from_request_none_request(self):
        """Test base URL extraction with None request."""
        with self.assertRaises(RuntimeError) as cm:
            _get_base_url_from_request(None)
        self.assertIn("requires an active FastAPI request context", str(cm.exception))

    def test_get_dynamic_redirect_uri(self):
        """Test dynamic redirect URI calculation."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "https://example.com/my-app/endpoint"
        mock_request.scope = {"root_path": "/my-app"}

        result = _get_dynamic_redirect_uri(mock_request, "/callback")
        expected = "https://example.com/my-app/callback"
        self.assertEqual(result, expected)

    def test_get_dynamic_redirect_uri_empty_callback(self):
        """Test dynamic redirect URI with empty callback path."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "https://example.com/endpoint"
        mock_request.scope = {}

        result = _get_dynamic_redirect_uri(mock_request, "")
        expected = "https://example.com/"
        self.assertEqual(result, expected)

    def test_get_dynamic_redirect_uri_callback_without_slash(self):
        """Test dynamic redirect URI with callback path without leading slash."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "https://example.com/endpoint"
        mock_request.scope = {}

        result = _get_dynamic_redirect_uri(mock_request, "callback")
        expected = "https://example.com/callback"
        self.assertEqual(result, expected)


class TestPortNormalization(unittest.TestCase):
    """Test cases for URL port normalization."""

    def test_normalize_https_standard_port(self):
        """Test that HTTPS port 443 is omitted."""
        url = "https://example.com:443/path"
        result = normalize_url_port(url)
        expected = "https://example.com/path"
        self.assertEqual(result, expected)

    def test_normalize_http_standard_port(self):
        """Test that HTTP port 80 is omitted."""
        url = "http://example.com:80/path"
        result = normalize_url_port(url)
        expected = "http://example.com/path"
        self.assertEqual(result, expected)

    def test_preserve_custom_https_port(self):
        """Test that custom HTTPS ports are preserved."""
        url = "https://example.com:8443/path"
        result = normalize_url_port(url)
        expected = "https://example.com:8443/path"
        self.assertEqual(result, expected)

    def test_preserve_custom_http_port(self):
        """Test that custom HTTP ports are preserved."""
        url = "http://example.com:8080/path"
        result = normalize_url_port(url)
        expected = "http://example.com:8080/path"
        self.assertEqual(result, expected)

    def test_no_port_in_url(self):
        """Test that URLs without explicit ports are unchanged."""
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

    def test_malformed_url_handling(self):
        """Test that malformed URLs are returned unchanged."""
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


class TestConfiguredOrDynamicRedirectUri(unittest.TestCase):
    """Test cases for configured or dynamic redirect URI calculation."""

    def test_configured_or_dynamic_redirect_uri_with_configured(self):
        """Test that configured URI is used when provided."""
        mock_request = MagicMock(spec=Request)
        result = get_configured_or_dynamic_redirect_uri(mock_request, "/callback", "https://configured.example.com/callback")
        expected = "https://configured.example.com/callback"
        self.assertEqual(result, expected)

    def test_configured_or_dynamic_redirect_uri_whitespace_config(self):
        """Test that whitespace-only configured URI falls back to dynamic calculation."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "http://localhost:5000/endpoint"
        mock_request.scope = {}

        result = get_configured_or_dynamic_redirect_uri(mock_request, "/callback", "   ")
        expected = "http://localhost:5000/callback"
        self.assertEqual(result, expected)

    def test_configured_or_dynamic_redirect_uri_empty_string_config(self):
        """Test that empty string configured URI falls back to dynamic calculation."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "http://localhost:5000/endpoint"
        mock_request.scope = {}

        result = get_configured_or_dynamic_redirect_uri(mock_request, "/callback", "")
        expected = "http://localhost:5000/callback"
        self.assertEqual(result, expected)

    def test_configured_or_dynamic_redirect_uri_none_config(self):
        """Test that None configured URI falls back to dynamic calculation."""
        mock_request = MagicMock(spec=Request)
        mock_request.url = "http://localhost:5000/endpoint"
        mock_request.scope = {}

        result = get_configured_or_dynamic_redirect_uri(mock_request, "/callback", None)
        expected = "http://localhost:5000/callback"
        self.assertEqual(result, expected)

    def test_normalize_url_port_none_input(self):
        """Test normalize_url_port with None input."""
        with self.assertRaises(TypeError):
            normalize_url_port(None)

    def test_normalize_url_port_empty_string(self):
        """Test normalize_url_port with empty string."""
        result = normalize_url_port("")
        self.assertEqual(result, "")

    def test_normalize_url_port_with_userinfo_standard_port(self):
        """Test normalize_url_port with userinfo and standard port."""
        url = "http://user:pass@example.com:80/path"
        result = normalize_url_port(url)
        expected = "http://user:pass@example.com/path"
        self.assertEqual(result, expected)

    def test_normalize_url_port_with_userinfo_custom_port(self):
        """Test normalize_url_port with userinfo and custom port."""
        url = "https://user:pass@example.com:8443/path"
        result = normalize_url_port(url)
        expected = "https://user:pass@example.com:8443/path"
        self.assertEqual(result, expected)

    def test_normalize_url_port_malformed_url_with_logging(self):
        """Test normalize_url_port with malformed URL and logging."""
        from flask import Flask

        app = Flask(__name__)
        with app.app_context():
            # Test that malformed URL is handled gracefully
            url = "not-a-valid-url"
            result = normalize_url_port(url)
            self.assertEqual(result, url)  # Should return original URL unchanged

    def test_normalize_url_port_malformed_url_no_flask_context(self):
        """Test normalize_url_port with malformed URL and no Flask context."""
        url = "not-a-valid-url"
        result = normalize_url_port(url)
        self.assertEqual(result, url)  # Should return original URL unchanged


if __name__ == "__main__":
    unittest.main()
