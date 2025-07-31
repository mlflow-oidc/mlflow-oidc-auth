"""
Tests for dynamic OIDC redirect URI calculation.

These tests verify that the redirect URI is correctly calculated
from request headers in various proxy scenarios using ProxyFix middleware.
"""

import unittest
from unittest.mock import Mock, patch
from flask import Flask
from mlflow_oidc_auth.utils.uri_helpers import _get_dynamic_redirect_uri, get_configured_or_dynamic_redirect_uri, _get_base_url_from_request, normalize_url_port


class TestDynamicRedirectUri(unittest.TestCase):
    """Test cases for dynamic redirect URI calculation."""

    def setUp(self):
        """Set up test fixtures."""
        from werkzeug.middleware.proxy_fix import ProxyFix

        self.app = Flask(__name__)
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        """Clean up test fixtures."""
        self.app_context.pop()

    def test_script_root_base(self):
        """Test redirect URI calculation using only request.script_root for base path."""
        cases = [
            # (base_url, script_root, expected_redirect)
            ("http://localhost:5000/", "", "http://localhost:5000/callback"),
            ("https://example.com/mlflow/", "/mlflow", "https://example.com/callback"),
            ("https://corp.example.com/apps/ml-platform/", "/apps/ml-platform", "https://corp.example.com/callback"),
            ("http://localhost:5000/myapp/", "/myapp", "http://localhost:5000/callback"),
            ("https://k8s-cluster.example.com/v1/ml-platform/", "/v1/ml-platform", "https://k8s-cluster.example.com/callback"),
            ("https://example.com:8443/my-app/", "/my-app", "https://example.com:8443/callback"),
            ("http://localhost:8080/", "", "http://localhost:8080/callback"),
            ("http://localhost:5000/", "", "http://localhost:5000/callback"),
            ("https://example.com:443/my-app/", "/my-app", "https://example.com/callback"),
            ("http://example.com:80/my-app/", "/my-app", "http://example.com/callback"),
        ]
        for url, script_root, expected in cases:
            # Ensure the URL path matches SCRIPT_NAME for correct script_root
            if script_root:
                # Ensure the path in the URL starts with script_root
                url = url.rstrip("/") + script_root + "/"
            environ_base = {"SCRIPT_NAME": script_root} if script_root else {}
            with self.app.test_request_context(url, environ_base=environ_base):
                result = get_configured_or_dynamic_redirect_uri(None)
                self.assertEqual(result, expected)

    def test_http_standard_port_omitted(self):
        """Test redirect URI calculation where HTTP standard port 80 is omitted."""
        url = "http://example.com:80/my-app/"
        with self.app.test_request_context(url, environ_base={"SCRIPT_NAME": "/my-app"}):
            result = _get_dynamic_redirect_uri()
            expected = "http://example.com/callback"
            self.assertEqual(result, expected)

    def test_get_base_url_from_request(self):
        """Test getting base URL from request context."""
        url = "https://example.com/my-app/"
        with self.app.test_request_context(url, environ_base={"SCRIPT_NAME": "/my-app"}):
            result = _get_base_url_from_request()
            expected = "https://example.com"
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


class TestRequestContextRequirement(unittest.TestCase):
    """Test cases for functions that require Flask request context."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

    def test_get_base_url_from_request_no_context(self):
        """Test that _get_base_url_from_request raises RuntimeError without request context."""
        with self.assertRaises(RuntimeError) as context:
            _get_base_url_from_request()
        self.assertIn("requires an active Flask request context", str(context.exception))

    def test_get_dynamic_redirect_uri_no_context(self):
        """Test that _get_dynamic_redirect_uri raises RuntimeError without request context."""
        with self.assertRaises(RuntimeError) as context:
            _get_dynamic_redirect_uri()
        self.assertIn("requires an active Flask request context", str(context.exception))

    def test_get_dynamic_redirect_uri_empty_callback_path(self):
        """Test redirect URI calculation with empty callback path."""
        with self.app.test_request_context("http://localhost:5000/"):
            result = _get_dynamic_redirect_uri("")
            expected = "http://localhost:5000/"
            self.assertEqual(result, expected)

    def test_configured_or_dynamic_redirect_uri_whitespace_config(self):
        """Test that whitespace-only configured URI falls back to dynamic calculation."""
        with self.app.test_request_context("http://localhost:5000/"):
            result = get_configured_or_dynamic_redirect_uri("   ")
            expected = "http://localhost:5000/callback"
            self.assertEqual(result, expected)

    def test_configured_or_dynamic_redirect_uri_empty_string_config(self):
        """Test that empty string configured URI falls back to dynamic calculation."""
        with self.app.test_request_context("http://localhost:5000/"):
            result = get_configured_or_dynamic_redirect_uri("")
            expected = "http://localhost:5000/callback"
            self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
