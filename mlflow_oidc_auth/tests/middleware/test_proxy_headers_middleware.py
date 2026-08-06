"""
Tests for ProxyHeadersMiddleware trusted proxy CIDR validation.
"""

import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mlflow_oidc_auth.middleware.proxy_headers_middleware import (
    ProxyHeadersMiddleware,
    _parse_trusted_proxies,
)

# ---------------------------------------------------------------------------
# _parse_trusted_proxies unit tests
# ---------------------------------------------------------------------------


class TestParseTrustedProxies:
    """Tests for the CIDR parsing helper."""

    def test_empty_list(self):
        assert _parse_trusted_proxies([]) == []

    def test_single_ipv4_cidr(self):
        result = _parse_trusted_proxies(["10.0.0.0/8"])
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("10.0.0.0/8")

    def test_single_ipv4_host(self):
        """A bare IP should be treated as /32."""
        result = _parse_trusted_proxies(["192.168.1.1"])
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("192.168.1.1/32")

    def test_multiple_cidrs(self):
        result = _parse_trusted_proxies(["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])
        assert len(result) == 3

    def test_ipv6_cidr(self):
        result = _parse_trusted_proxies(["::1/128"])
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("::1/128")

    def test_invalid_cidr_skipped(self):
        """Invalid entries should be silently skipped with a warning."""
        result = _parse_trusted_proxies(["10.0.0.0/8", "not-a-cidr", "172.16.0.0/12"])
        assert len(result) == 2

    def test_whitespace_trimmed(self):
        result = _parse_trusted_proxies(["  10.0.0.0/8  ", " 172.16.0.0/12 "])
        assert len(result) == 2

    def test_empty_strings_skipped(self):
        result = _parse_trusted_proxies(["", "10.0.0.0/8", ""])
        assert len(result) == 1

    def test_strict_false_allows_host_bits(self):
        """10.0.0.1/8 should parse as 10.0.0.0/8 with strict=False."""
        result = _parse_trusted_proxies(["10.0.0.1/8"])
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("10.0.0.0/8")


# ---------------------------------------------------------------------------
# _is_trusted_proxy tests
# ---------------------------------------------------------------------------


class TestIsTrustedProxy:
    """Tests for the proxy trust check method."""

    def _make_middleware(self, trusted_proxies: list):
        """Create a ProxyHeadersMiddleware with mocked config."""
        with patch("mlflow_oidc_auth.config.config") as mock_config:
            mock_config.TRUSTED_PROXIES = trusted_proxies
            app = MagicMock()
            middleware = ProxyHeadersMiddleware(app)
        return middleware

    def _make_request(self, client_host: str):
        """Create a mock request with the given client IP."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = client_host
        return request

    def test_no_trusted_proxies_trusts_all(self):
        """When TRUSTED_PROXIES is empty, all requests are trusted."""
        middleware = self._make_middleware([])
        request = self._make_request("1.2.3.4")
        assert middleware._is_trusted_proxy(request) is True

    def test_trusted_ip_in_cidr(self):
        """Request from an IP within a trusted CIDR is trusted."""
        middleware = self._make_middleware(["10.0.0.0/8"])
        request = self._make_request("10.1.2.3")
        assert middleware._is_trusted_proxy(request) is True

    def test_untrusted_ip_outside_cidr(self):
        """Request from an IP outside trusted CIDRs is not trusted."""
        middleware = self._make_middleware(["10.0.0.0/8"])
        request = self._make_request("192.168.1.1")
        assert middleware._is_trusted_proxy(request) is False

    def test_exact_ip_match(self):
        """Single-host CIDR (/32) should match exactly."""
        middleware = self._make_middleware(["10.0.0.5"])
        request_match = self._make_request("10.0.0.5")
        request_no_match = self._make_request("10.0.0.6")
        assert middleware._is_trusted_proxy(request_match) is True
        assert middleware._is_trusted_proxy(request_no_match) is False

    def test_multiple_cidrs(self):
        """Request matching any of multiple CIDRs is trusted."""
        middleware = self._make_middleware(["10.0.0.0/8", "172.16.0.0/12"])
        assert middleware._is_trusted_proxy(self._make_request("10.1.2.3")) is True
        assert middleware._is_trusted_proxy(self._make_request("172.20.1.1")) is True
        assert middleware._is_trusted_proxy(self._make_request("192.168.1.1")) is False

    def test_ipv6_trusted(self):
        """IPv6 loopback should match ::1/128."""
        middleware = self._make_middleware(["::1/128"])
        assert middleware._is_trusted_proxy(self._make_request("::1")) is True
        assert middleware._is_trusted_proxy(self._make_request("::2")) is False

    def test_no_client_returns_false(self):
        """When client is None (e.g., unit test), proxy is not trusted."""
        middleware = self._make_middleware(["10.0.0.0/8"])
        request = MagicMock()
        request.client = None
        assert middleware._is_trusted_proxy(request) is False

    def test_unparseable_client_ip_returns_false(self):
        """When client IP can't be parsed, proxy is not trusted."""
        middleware = self._make_middleware(["10.0.0.0/8"])
        request = self._make_request("not-an-ip")
        assert middleware._is_trusted_proxy(request) is False


# ---------------------------------------------------------------------------
# dispatch integration tests
# ---------------------------------------------------------------------------


class TestProxyHeadersDispatch:
    """Tests for the full dispatch method with trust checking."""

    def _make_middleware(self, trusted_proxies: list):
        with patch("mlflow_oidc_auth.config.config") as mock_config:
            mock_config.TRUSTED_PROXIES = trusted_proxies
            app = MagicMock()
            middleware = ProxyHeadersMiddleware(app)
        return middleware

    @pytest.mark.asyncio
    async def test_untrusted_ip_skips_proxy_headers(self):
        """When client IP is not trusted, proxy headers are ignored and request passes through."""
        middleware = self._make_middleware(["10.0.0.0/8"])

        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.scope = {"scheme": "http", "headers": [], "server": ("localhost", 8000)}
        request.url.scheme = "http"
        request.url.path = "/test"
        request.headers = {
            "x-forwarded-proto": "https",
            "x-forwarded-host": "external.com",
        }

        response = MagicMock()
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        # Should have called next handler
        call_next.assert_called_once_with(request)
        assert result == response
        # Scheme should NOT have been modified (proxy headers ignored)
        assert request.scope["scheme"] == "http"

    @pytest.mark.asyncio
    async def test_trusted_ip_processes_proxy_headers(self):
        """When client IP is trusted, proxy headers are processed normally."""
        middleware = self._make_middleware(["10.0.0.0/8"])

        # Build a more realistic request mock
        scope = {
            "scheme": "http",
            "headers": [(b"host", b"localhost:8000"), (b"x-forwarded-proto", b"https")],
            "server": ("localhost", 8000),
        }
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        request.scope = scope
        request.url.scheme = "http"
        request.url.path = "/test"
        request.url.hostname = "localhost"
        request.headers = MagicMock()
        request.headers.get = lambda key, default=None: {
            "host": "localhost:8000",
            "x-forwarded-proto": "https",
            "x-forwarded-host": None,
            "x-forwarded-port": None,
            "x-forwarded-prefix": "",
            "x-forwarded-for": None,
            "x-real-ip": None,
        }.get(key, default)

        response = MagicMock()
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert result == response
        # Scheme SHOULD have been updated
        assert request.scope["scheme"] == "https"

    @pytest.mark.asyncio
    async def test_empty_trusted_proxies_processes_all(self):
        """When TRUSTED_PROXIES is empty, all proxy headers are processed (backward compat)."""
        middleware = self._make_middleware([])

        scope = {
            "scheme": "http",
            "headers": [(b"host", b"localhost:8000")],
            "server": ("localhost", 8000),
        }
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "1.2.3.4"  # Any IP
        request.scope = scope
        request.url.scheme = "http"
        request.url.path = "/test"
        request.url.hostname = "localhost"
        request.headers = MagicMock()
        request.headers.get = lambda key, default=None: {
            "host": "localhost:8000",
            "x-forwarded-proto": "https",
            "x-forwarded-host": None,
            "x-forwarded-port": None,
            "x-forwarded-prefix": "",
            "x-forwarded-for": None,
            "x-real-ip": None,
        }.get(key, default)

        response = MagicMock()
        call_next = AsyncMock(return_value=response)

        await middleware.dispatch(request, call_next)

        # Scheme should have been updated (all proxies trusted)
        assert request.scope["scheme"] == "https"
