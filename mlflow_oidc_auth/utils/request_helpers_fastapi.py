from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, UNAUTHENTICATED

from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.store import store

# Initialize security schemes
basic_security = HTTPBasic(auto_error=False)
bearer_security = HTTPBearer(auto_error=False)

logger = get_logger()


async def get_username_from_session(request: Request) -> Optional[str]:
    """
    Extract username from the session or request state.

    This function first checks request.state (set by AuthMiddleware) and then
    falls back to the session for backward compatibility.

    Parameters:
    -----------
    request : Request
        The FastAPI request object containing the session or state.

    Returns:
    --------
    Optional[str]
        The authenticated username or None if not found.
    """
    # First try to get username from request state (set by AuthMiddleware)
    if hasattr(request.state, "username") and request.state.username:
        logger.debug(f"Username from request state: {request.state.username}")
        return request.state.username
    else:
        logger.debug(f"Request state username not found. Has username attr: {hasattr(request.state, 'username')}")
        if hasattr(request.state, "username"):
            logger.debug(f"Request state username value: {request.state.username}")

    # Fallback to session for backward compatibility
    try:
        session = request.session
        username = session.get("username")
        if username:
            logger.debug(f"Username from session: {username}")
            return username
        else:
            logger.debug("No username found in session")
    except Exception as e:
        logger.debug(f"Error accessing session: {e}")

    logger.debug("No username found in request state or session")
    return None


async def get_username_from_basic_auth(credentials: Optional[HTTPBasicCredentials] = Depends(basic_security)) -> Optional[str]:
    """
    Extract and validate username from basic authentication.

    Parameters:
    -----------
    credentials : Optional[HTTPBasicCredentials]
        The parsed basic auth credentials.

    Returns:
    --------
    Optional[str]
        The authenticated username or None if basic auth is not provided or invalid.
    """
    if not credentials:
        return None

    try:
        user = store.get_user_profile(credentials.username)
        if user and user.username:
            logger.debug(f"Username from basic auth: {user.username}")
            return user.username
    except Exception as e:
        logger.debug(f"Error validating basic auth credentials: {e}")

    return None


async def get_username_from_bearer_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_security)) -> Optional[str]:
    """
    Extract and validate username from bearer token.

    Parameters:
    -----------
    credentials : Optional[HTTPAuthorizationCredentials]
        The parsed bearer token credentials.

    Returns:
    --------
    Optional[str]
        The authenticated username or None if token is not provided or invalid.
    """
    if not credentials:
        return None

    try:
        token_data = validate_token(credentials.credentials)
        username = token_data.get("email")
        if username:
            logger.debug(f"Username from bearer token: {username}")
            return username
    except Exception as e:
        logger.debug(f"Error validating bearer token: {e}")

    return None


async def get_authenticated_username(
    request: Request,
    basic_username: Optional[str] = Depends(get_username_from_basic_auth),
    bearer_username: Optional[str] = Depends(get_username_from_bearer_token),
) -> str:
    """
    Get authenticated username using multiple authentication methods.

    This function tries to authenticate the user in the following order:
    1. Session-based authentication
    2. Basic authentication (username/password)
    3. Bearer token authentication (JWT/OIDC)

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    basic_username : Optional[str]
        Username from basic auth (injected by dependency).
    bearer_username : Optional[str]
        Username from bearer token (injected by dependency).

    Returns:
    --------
    str
        The authenticated username.

    Raises:
    -------
    HTTPException
        If no valid authentication is provided.
    """
    # Try session authentication first
    username = await get_username_from_session(request)

    # If session auth failed, try basic auth
    if not username and basic_username:
        username = basic_username

    # If basic auth failed, try bearer token
    if not username and bearer_username:
        username = bearer_username

    # If all authentication methods failed
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide valid credentials.",
            headers={"WWW-Authenticate": "Basic, Bearer"},
        )

    return username


async def get_username(request: Request) -> str:
    """
    Legacy function to extract username from session or authentication headers.

    This function maintains compatibility with existing code but uses
    the new dependency-based authentication system internally.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.

    Returns:
    --------
    str
        The authenticated username.

    Raises:
    -------
    MlflowException
        If authentication is required but not provided.
    """
    try:
        return await get_authenticated_username(
            request=request, basic_username=await get_username_from_basic_auth(None), bearer_username=await get_username_from_bearer_token(None)
        )
    except HTTPException as e:
        # Convert FastAPI exception to MLflow exception for backward compatibility
        if "Authentication" in e.detail or "credentials" in e.detail:
            raise MlflowException(e.detail, UNAUTHENTICATED)
        else:
            raise MlflowException(e.detail, INVALID_PARAMETER_VALUE)


async def get_is_admin(request: Request) -> bool:
    """Return whether the authenticated user is an admin.

    Prefer a lightweight store call to avoid loading full permission graphs.
    """

    username = await get_username(request=request)
    getter = getattr(store, "get_user_profile", None) or getattr(store, "get_user")
    user = getter(username)
    return bool(getattr(user, "is_admin", False))


async def is_authenticated(request: Request) -> bool:
    """
    Check if the user is authenticated.

    This function returns True if the user is authenticated via session,
    basic auth, or bearer token. Otherwise, it returns False.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.

    Returns:
    --------
    bool
        True if the user is authenticated, False otherwise.
    """
    try:
        username = await get_authenticated_username(
            request=request, basic_username=await get_username_from_basic_auth(None), bearer_username=await get_username_from_bearer_token(None)
        )
        return bool(username)
    except HTTPException:
        return False


async def get_base_path(request: Request) -> str:
    """
    Helper function to get the base path from the request.

    This function extracts the base path for the application, taking into account
    proxy headers set by reverse proxies (nginx, etc.). The base path is used
    for constructing proper URLs and redirects when the application is behind a proxy.

    Priority order:
    1. X-Forwarded-Prefix header (most common proxy setup)
    2. root_path from ASGI scope (set by ProxyHeadersMiddleware)
    3. request.base_url.path (direct access)
    4. Empty string (default)

    Args:
        request: FastAPI request object

    Returns:
        Base path string (without trailing slash)
    """
    # First check X-Forwarded-Prefix header (nginx, apache, etc.)
    headers = getattr(request, "headers", {}) or {}
    forwarded_prefix = headers.get("x-forwarded-prefix", "")
    if forwarded_prefix:
        return forwarded_prefix.rstrip("/")

    # Then check root_path from ASGI scope (set by ProxyHeadersMiddleware or ASGI server)
    scope = getattr(request, "scope", None) or {}
    root_path = scope.get("root_path", "")
    if root_path:
        return root_path.rstrip("/")

    # Fallback to base URL path for direct access
    base_url = getattr(request, "base_url", None)
    base_url_path = getattr(base_url, "path", "") if base_url is not None else ""
    if base_url_path and base_url_path != "/":
        return base_url_path.rstrip("/")

    # Default to empty string (no prefix)
    return ""
