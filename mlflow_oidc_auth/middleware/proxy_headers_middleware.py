"""
Proxy Headers Middleware for FastAPI.

This middleware handles X-Forwarded-* headers from reverse proxies (like nginx)
to ensure proper URL construction and request context when the application is
running behind a proxy.
"""

import ipaddress
from typing import List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def _parse_trusted_proxies(
    proxy_list: List[str],
) -> List[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse a list of CIDR strings into network objects.

    Parameters:
        proxy_list: List of CIDR notation strings (e.g., ["10.0.0.0/8", "172.16.0.0/12"]).
            Single IPs (e.g., "10.0.0.1") are treated as /32 (IPv4) or /128 (IPv6).

    Returns:
        List of parsed network objects.
    """
    networks = []
    for cidr in proxy_list:
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning(f"Invalid CIDR in TRUSTED_PROXIES, skipping: {cidr}")
    return networks


class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for handling proxy headers.

    This middleware:
    1. Validates the connecting client IP against TRUSTED_PROXIES (if configured)
    2. Processes X-Forwarded-* headers from reverse proxies
    3. Updates the request scope with correct protocol, host, and path information
    4. Enables proper URL construction for redirects and callbacks when behind a proxy

    When TRUSTED_PROXIES is empty (default), ALL proxy headers are trusted for
    backward compatibility. When TRUSTED_PROXIES is configured, only requests
    from IPs within the configured CIDR ranges will have their proxy headers
    processed.

    Common proxy headers handled:
    - X-Forwarded-Proto: Original protocol (http/https)
    - X-Forwarded-Host: Original host name
    - X-Forwarded-Port: Original port number
    - X-Forwarded-Prefix: Path prefix added by the proxy
    - X-Forwarded-For: Original client IP (for logging)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        from mlflow_oidc_auth.config import config

        self._trusted_networks = _parse_trusted_proxies(config.TRUSTED_PROXIES)

    def _is_trusted_proxy(self, request: Request) -> bool:
        """Check if the connecting client IP is from a trusted proxy.

        When TRUSTED_PROXIES is not configured (empty list), all sources are
        trusted for backward compatibility. When configured, only IPs within
        the specified CIDR ranges are trusted.

        Parameters:
            request: FastAPI request object.

        Returns:
            True if the request comes from a trusted proxy (or no restriction is configured).
        """
        if not self._trusted_networks:
            return True

        client = request.client
        if client is None:
            logger.warning("Cannot determine client IP — proxy headers will be ignored")
            return False

        client_ip_str = client.host
        try:
            client_ip = ipaddress.ip_address(client_ip_str)
        except ValueError:
            logger.warning(f"Cannot parse client IP '{client_ip_str}' — proxy headers will be ignored")
            return False

        for network in self._trusted_networks:
            if client_ip in network:
                return True

        logger.debug(f"Client IP {client_ip_str} is not in TRUSTED_PROXIES — proxy headers will be ignored")
        return False

    def _get_forwarded_proto(self, request: Request) -> Optional[str]:
        """
        Get the original protocol from proxy headers.

        Args:
            request: FastAPI request object

        Returns:
            Protocol string (http/https) or None if not forwarded
        """
        return request.headers.get("x-forwarded-proto")

    def _get_forwarded_host(self, request: Request) -> Optional[str]:
        """
        Get the original host from proxy headers.

        Args:
            request: FastAPI request object

        Returns:
            Host string or None if not forwarded
        """
        return request.headers.get("x-forwarded-host")

    def _get_forwarded_port(self, request: Request) -> Optional[int]:
        """
        Get the original port from proxy headers.

        Args:
            request: FastAPI request object

        Returns:
            Port number or None if not forwarded
        """
        port_header = request.headers.get("x-forwarded-port")
        if port_header:
            try:
                return int(port_header)
            except ValueError:
                logger.warning(f"Invalid X-Forwarded-Port header: {port_header}")
        return None

    def _get_forwarded_prefix(self, request: Request) -> str:
        """
        Get the path prefix added by the proxy.

        Args:
            request: FastAPI request object

        Returns:
            Path prefix string (empty if not forwarded)
        """
        prefix = request.headers.get("x-forwarded-prefix", "")
        # Ensure prefix starts with / if not empty, and remove trailing /
        if prefix and not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/")

    def _get_real_ip(self, request: Request) -> Optional[str]:
        """
        Get the real client IP from proxy headers.

        Args:
            request: FastAPI request object

        Returns:
            Client IP address or None if not forwarded
        """
        # Try X-Forwarded-For first (may contain multiple IPs)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

        # Fallback to X-Real-IP
        return request.headers.get("x-real-ip")

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Main middleware dispatch method.

        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in the chain

        Returns:
            Response from the application
        """
        # Only process proxy headers from trusted sources
        if not self._is_trusted_proxy(request):
            return await call_next(request)

        # Extract proxy headers
        forwarded_proto = self._get_forwarded_proto(request)
        forwarded_host = self._get_forwarded_host(request)
        forwarded_port = self._get_forwarded_port(request)
        forwarded_prefix = self._get_forwarded_prefix(request)
        real_ip = self._get_real_ip(request)

        # Store original values for debugging
        original_scheme = request.url.scheme
        original_host = request.headers.get("host", request.url.hostname)
        original_path = request.url.path

        # Update request scope with proxy information if headers are present
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto

        if forwarded_host:
            # Update the host header and server info
            if forwarded_port and forwarded_port not in (80, 443):
                # Include port if it's not standard
                request.scope["headers"] = [
                    (name, value) if name != b"host" else (b"host", f"{forwarded_host}:{forwarded_port}".encode())
                    for name, value in request.scope.get("headers", [])
                ]
                # Update server info in scope
                request.scope["server"] = (forwarded_host, forwarded_port)
            else:
                # Standard port, don't include in host header
                request.scope["headers"] = [
                    (name, value) if name != b"host" else (b"host", forwarded_host.encode()) for name, value in request.scope.get("headers", [])
                ]
                # Update server info in scope
                default_port = 443 if forwarded_proto == "https" else 80
                request.scope["server"] = (
                    forwarded_host,
                    forwarded_port or default_port,
                )

        # Set root_path for path prefix handling
        if forwarded_prefix:
            request.scope["root_path"] = forwarded_prefix

        # Store proxy information in request state for easier access
        request.state.proxy_info = {
            "forwarded_proto": forwarded_proto,
            "forwarded_host": forwarded_host,
            "forwarded_port": forwarded_port,
            "forwarded_prefix": forwarded_prefix,
            "real_ip": real_ip,
            "is_proxied": bool(forwarded_proto or forwarded_host or forwarded_prefix),
            "original_scheme": original_scheme,
            "original_host": original_host,
            "original_path": original_path,
        }

        # Log proxy information for debugging
        if hasattr(request.state, "proxy_info") and request.state.proxy_info["is_proxied"]:
            logger.debug(
                f"Proxy headers detected: proto={forwarded_proto}, host={forwarded_host}, "
                f"port={forwarded_port}, prefix={forwarded_prefix}, real_ip={real_ip}"
            )
            logger.debug(
                f"Request transformation: {original_scheme}://{original_host}{original_path} -> "
                f"{forwarded_proto or original_scheme}://{forwarded_host or original_host}"
                f"{forwarded_prefix}{original_path}"
            )

        # Proceed to the next middleware/handler
        return await call_next(request)
