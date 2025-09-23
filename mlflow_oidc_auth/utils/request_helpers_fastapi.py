from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE

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
        user = store.get_user(credentials.username)
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
        raise MlflowException(e.detail, INVALID_PARAMETER_VALUE)


async def get_is_admin(request: Request) -> bool:
    return bool(store.get_user(await get_username(request=request)).is_admin)


async def get_base_path(request: Request) -> str:
    """
    Helper function to get the base path from the request.
    """
    forwarded_prefix = request.headers.get("x-forwarded-prefix", "")
    if forwarded_prefix:
        return forwarded_prefix.rstrip("/")
    elif request.base_url.path:
        return request.base_url.path.rstrip("/")
    return ""
