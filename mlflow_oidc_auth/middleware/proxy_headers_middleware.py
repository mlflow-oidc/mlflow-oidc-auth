"""
Proxy Headers Middleware for FastAPI.

This middleware handles X-Forwarded-* headers from reverse proxies (like nginx)
to ensure proper URL construction and request context when the application is
running behind a proxy.
"""

import ipaddress
from typing import Any, List, Mapping, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: Scope key under which the original client address from a trusted proxy is recorded.
#: ``scope["client"]`` is deliberately left as the direct connection: MLflow and the ASGI server
#: make their own decisions on it (MLflow's assistant API treats a loopback peer as local).
FORWARDED_CLIENT_SCOPE_KEY = "mlflow_oidc_auth.forwarded_client"

_Address = ipaddress.IPv4Address | ipaddress.IPv6Address


def _parse_address(value: str) -> Optional[_Address]:
    """Parse one forwarded address: a bare IP, ``IPv4:port``, or ``[IPv6]`` / ``[IPv6]:port``.

    IPv4-mapped IPv6 addresses are returned as their IPv4 form so they compare equal to it.

    Parameters:
        value: The address as it appears in a header.

    Returns:
        The address, or None when ``value`` is not one.
    """
    value = value.strip()
    if value.startswith("["):
        host, sep, rest = value[1:].partition("]")
        if not sep or (rest and not (rest.startswith(":") and rest[1:].isdigit())):
            return None
        value = host
    elif value.count(":") == 1:
        host, _, port = value.partition(":")
        if not port.isdigit():
            return None
        value = host
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def client_address(scope: Mapping[str, Any]) -> Optional[str]:
    """The original client address of a request, for rate limiting and audit records.

    The address a trusted proxy forwarded (see :class:`ProxyHeadersMiddleware`), otherwise the
    direct connection's. Not for authorization decisions.

    Parameters:
        scope: ASGI connection scope.

    Returns:
        The client address, or None when the connection has none.
    """
    forwarded = scope.get(FORWARDED_CLIENT_SCOPE_KEY)
    if forwarded:
        return forwarded
    client = scope.get("client")
    return client[0] if client else None


def _parse_trusted_proxies(
    proxy_list: List[str],
) -> List[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse a list of CIDR strings into network objects.

    Parameters:
        proxy_list: List of CIDR notation strings (e.g., ["10.0.0.0/8", "172.16.0.0/12"]).
            Single IPs (e.g., "10.0.0.1") are treated as /32 (IPv4) or /128 (IPv6).

    Returns:
        List of parsed network objects. An IPv4-mapped IPv6 entry (``::ffff:10.0.0.5`` or
        ``::ffff:10.0.0.0/104``, prefix length 96 or more) is converted to its IPv4 form, since
        connection and forwarded addresses are compared in IPv4 form (see ``_parse_address``).
    """
    networks = []
    for cidr in proxy_list:
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            logger.warning("Invalid CIDR in TRUSTED_PROXIES, skipping entry")
            continue
        mapped = _ipv4_form_of_mapped_network(network)
        if mapped is not None:
            logger.info("A TRUSTED_PROXIES entry is IPv4-mapped IPv6; it is matched in its IPv4 form")
            network = mapped
        networks.append(network)
    return networks


_IPV4_MAPPED = ipaddress.IPv6Network("::ffff:0:0/96")


def _ipv4_form_of_mapped_network(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> Optional[ipaddress.IPv4Network]:
    """Return the IPv4 network an IPv4-mapped IPv6 network covers, or None if it is not one.

    Parameters:
        network: A parsed TRUSTED_PROXIES entry.

    Returns:
        The IPv4 network with prefix length ``prefixlen - 96`` when ``network`` lies within
        ``::ffff:0:0/96``; None otherwise.
    """
    if not isinstance(network, ipaddress.IPv6Network) or network.prefixlen < 96 or not network.subnet_of(_IPV4_MAPPED):
        return None
    mapped = network.network_address.ipv4_mapped
    if mapped is None:  # pragma: no cover - guaranteed by subnet_of above
        return None
    return ipaddress.IPv4Network((mapped, network.prefixlen - 96))


class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for handling proxy headers.

    This middleware:
    1. Validates the connecting client IP against TRUSTED_PROXIES
    2. Processes X-Forwarded-* headers from a trusted reverse proxy
    3. Updates the request scope with correct protocol, host, path prefix and client address
    4. Enables proper URL construction for redirects and callbacks when behind a proxy

    Forwarded headers are honoured only from a connecting client whose address is inside one of
    the TRUSTED_PROXIES networks. When TRUSTED_PROXIES is unset or empty (the default), no client
    is trusted and every forwarded header is ignored: the scheme, host, path and client address
    of the direct connection are used. This middleware is the only place in the package that
    reads these headers; everything else reads the scope it leaves behind.

    Headers handled (from a trusted proxy only):
    - X-Forwarded-Proto: Original protocol (http/https) -> ``scope["scheme"]``
    - X-Forwarded-Host / X-Forwarded-Port: Original host and port -> ``Host`` header, ``scope["server"]``
    - X-Forwarded-Prefix: Path prefix added by the proxy -> ``scope["root_path"]``
    - X-Forwarded-For / X-Real-IP: Original client IP -> ``scope[FORWARDED_CLIENT_SCOPE_KEY]``
      (read through :func:`client_address`; ``scope["client"]`` stays the direct connection)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        from mlflow_oidc_auth.config import config

        configured = [entry for entry in (config.TRUSTED_PROXIES or []) if entry and entry.strip()]
        self._trusted_networks = _parse_trusted_proxies(configured)
        # An unset setting and a setting whose entries are all invalid both trust no source.
        if not configured:
            logger.info(
                "TRUSTED_PROXIES is not set: X-Forwarded-* headers are ignored from every client. "
                "A deployment behind a reverse proxy must set TRUSTED_PROXIES to the proxy's address or CIDR range."
            )
        elif not self._trusted_networks:
            logger.warning("TRUSTED_PROXIES contains no valid entry: X-Forwarded-* headers will be ignored from every client")

    def _is_trusted_proxy(self, request: Request) -> bool:
        """Check if the connecting client IP is from a trusted proxy.

        Only IPs within the configured valid CIDR ranges are trusted. When TRUSTED_PROXIES is
        not configured, or has no valid entry, no source is trusted.

        Parameters:
            request: FastAPI request object.

        Returns:
            True if the request comes from a trusted proxy.
        """
        if not self._trusted_networks:
            return False

        client = request.client
        if client is None:
            logger.warning("Cannot determine client IP — proxy headers will be ignored")
            return False

        client_ip_str = client.host
        client_ip = _parse_address(client_ip_str) if client_ip_str else None
        if client_ip is None:
            logger.warning(f"Cannot parse client IP '{client_ip_str}' — proxy headers will be ignored")
            return False

        if self._is_trusted_address(client_ip):
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

    def _is_trusted_address(self, address: _Address) -> bool:
        """Whether ``address`` is inside one of the TRUSTED_PROXIES networks.

        Addresses arrive in IPv4 form when they were IPv4-mapped (see ``_parse_address``), so an
        IPv4 address is also checked in its mapped IPv6 form: a wide IPv6 entry such as ``::/0``
        covers the mapped range and must keep matching a dual-stack peer.
        """
        candidates: List[_Address] = [address]
        if isinstance(address, ipaddress.IPv4Address):
            candidates.append(ipaddress.IPv6Address(f"::ffff:{address}"))
        return any(candidate in network for candidate in candidates for network in self._trusted_networks if candidate.version == network.version)

    def _get_real_ip(self, request: Request) -> Optional[str]:
        """
        Get the original client IP from proxy headers.

        ``X-Forwarded-For`` is read from the right: each proxy appends the address it received
        the request from, so the right-most entries were written by trusted proxies and anything
        to their left came from further out. Repeated header lines are read as one list, in
        order. The client is the right-most entry that is not a trusted proxy; if every entry is
        a trusted proxy, the left-most one. ``X-Real-IP`` is used only when ``X-Forwarded-For``
        is absent. When the chosen entry is not an IP address, none is used and the direct
        connection's address is kept.

        Args:
            request: FastAPI request object

        Returns:
            Client IP address, or None if not forwarded or not a valid address
        """
        lines = request.headers.getlist("x-forwarded-for")
        entries = [entry.strip() for line in lines for entry in line.split(",") if entry.strip()]
        if entries:
            addresses = []
            for entry in reversed(entries):
                address = _parse_address(entry)
                if address is None:
                    return None
                if not self._is_trusted_address(address):
                    return str(address)
                addresses.append(address)
            return str(addresses[-1])

        real_ip = request.headers.get("x-real-ip") or ""
        address = _parse_address(real_ip) if real_ip.strip() else None
        return str(address) if address is not None else None

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

        # Record the original client address, so rate limits and audit records name the client
        # rather than the proxy. Kept out of scope["client"]: see FORWARDED_CLIENT_SCOPE_KEY.
        if real_ip:
            request.scope[FORWARDED_CLIENT_SCOPE_KEY] = real_ip

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
