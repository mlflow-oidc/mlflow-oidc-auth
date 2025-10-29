"""
URI construction and validation utilities for MLflow OIDC Auth.

This module provides functionality to dynamically construct OIDC redirect URIs
and other URI-related operations based on the current request context. With ProxyFix
middleware configured, FastAPI's request object automatically contains the correct
values from proxy headers.

Key Features:
- Dynamic OIDC redirect URI construction
- URL normalization (port handling)
- Proxy-aware URI building
- Request context utilities

Dependencies:
- FastAPI request context (requires active request)
- ProxyFix middleware for proper proxy header handling
"""

from typing import Optional
from urllib.parse import urlparse, urlunparse


def normalize_url_port(url: str) -> str:
    """
    Normalize URL by removing standard ports (80 for HTTP, 443 for HTTPS).

    This ensures that OIDC redirect URIs don't include redundant port numbers
    that might cause mismatches with provider configurations. Standard ports
    are automatically omitted while custom ports are preserved.

    Args:
        url (str): The URL to normalize

    Returns:
        str: URL with standard ports removed

    Examples:
        >>> normalize_url_port("http://example.com:80/path")
        "http://example.com/path"
        >>> normalize_url_port("https://example.com:443/path")
        "https://example.com/path"
        >>> normalize_url_port("https://example.com:8443/path")
        "https://example.com:8443/path"

    Edge Cases:
        - Invalid URLs: Returns original URL unchanged
        - URLs without ports: Returns original URL unchanged
        - Non-standard ports: Preserves the port in the URL
        - None input: Raises TypeError
        - Empty string: Returns empty string unchanged
    """
    # Handle None input explicitly
    if url is None:
        raise TypeError("normalize_url_port() missing 1 required positional argument: 'url'")

    # Handle empty string
    if not url:
        return url

    try:
        parsed = urlparse(url)

        # Check if port should be omitted (standard ports only)
        should_omit_port = (parsed.scheme == "http" and parsed.port == 80) or (parsed.scheme == "https" and parsed.port == 443)

        if should_omit_port:
            # Reconstruct URL without port by setting netloc without port
            # netloc format: [userinfo@]host[:port]
            if "@" in parsed.netloc:
                userinfo, host_port = parsed.netloc.rsplit("@", 1)
                host = host_port.split(":")[0]
                new_netloc = f"{userinfo}@{host}"
            else:
                host = parsed.netloc.split(":")[0]
                new_netloc = host

            # Create new parsed URL with modified netloc
            normalized = parsed._replace(netloc=new_netloc)
            return urlunparse(normalized)

        return url

    except (ValueError, AttributeError) as e:
        # Handle malformed URLs gracefully by returning original
        from flask import current_app

        if current_app:
            current_app.logger.warning(f"Failed to normalize URL '{url}': {e}")
        return url


from fastapi import Request


def _get_base_url_from_request(request: Request) -> str:
    """
    Extract the base URL from the current FastAPI request context.

    With ProxyFix middleware configured, this function automatically handles
    proxy headers (X-Forwarded-Proto, X-Forwarded-Host, X-Forwarded-Prefix)
    to construct the correct base URL regardless of proxy configuration.

    Returns:
        str: The normalized base URL for the current request

    Examples:
        Direct access: "http://localhost:5000"
        Behind proxy: "https://example.com/my-app"

    Edge Cases:
        - No active request context: Raises RuntimeError
        - Invalid request data: Returns best-effort URL construction

    Note:
        This function requires an active FastAPI request context and should
        only be called during request processing.
    """
    if request is None:
        raise RuntimeError("_get_base_url_from_request() requires an active FastAPI request context")

    parsed_url = urlparse(str(request.url))
    # Use root_path for the base path (proxy prefix), default to "" if empty
    base_path = request.scope.get("root_path", "")

    # Reconstruct the base URL with the correct base path
    base_url_parts = (parsed_url.scheme, parsed_url.netloc, base_path, "", "", "")
    raw_base_url = urlunparse(base_url_parts)

    # Normalize to remove standard ports for consistency
    return normalize_url_port(raw_base_url)


def _get_dynamic_redirect_uri(request: Request, callback_path: str) -> str:
    """
    Dynamically construct the OIDC redirect URI based on the current request context.

    With ProxyFix middleware configured, Flask's request object automatically
    contains the correct scheme, host, and URL from X-Forwarded-* headers.
    This allows the redirect URI to adapt automatically to different proxy
    configurations without requiring manual configuration.

    Args:
        callback_path (str): The callback path to append to the base URL.
                           Defaults to the value from mlflow_oidc_auth.routes.CALLBACK

    Returns:
        str: The complete OIDC redirect URI

    Examples:
        Direct access: "http://localhost:5000/callback"
        Behind proxy: "https://example.com/my-app/callback"
        Custom callback: "https://example.com/my-app/auth/callback"

    Edge Cases:
        - callback_path without leading slash: Automatically adds leading slash
        - Empty callback_path: Uses "/" as callback path
        - No active request context: Raises RuntimeError

    Note:
        This function requires an active Flask request context and should
        only be called during OIDC authentication flow.
    """
    base_url = _get_base_url_from_request(request=request)

    # Ensure callback path starts with /
    if not callback_path:
        callback_path = "/"
    elif not callback_path.startswith("/"):
        callback_path = f"/{callback_path}"

    redirect_uri = f"{base_url}{callback_path}"

    return redirect_uri


def get_configured_or_dynamic_redirect_uri(request: Request, callback_path: str, configured_uri: Optional[str]) -> str:
    """
    Get the OIDC redirect URI, using configured value if available, otherwise calculate dynamically.

    This function provides a fallback mechanism that uses a manually configured
    redirect URI if available, but falls back to dynamic calculation if not set.
    This approach provides flexibility for both automated deployments and cases
    where manual override is needed.

    Args:
        configured_uri (Optional[str]): The manually configured redirect URI (can be None)
        callback_path (str): The callback path for dynamic calculation.
                           Defaults to the value from mlflow_oidc_auth.routes.CALLBACK

    Returns:
        str: The OIDC redirect URI to use
    """
    # Use configured URI if it's provided and not empty/whitespace
    if configured_uri and configured_uri.strip():
        return configured_uri.strip()

    # Fall back to dynamic calculation
    return _get_dynamic_redirect_uri(request=request, callback_path=callback_path)
