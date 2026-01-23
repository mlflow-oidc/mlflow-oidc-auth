from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    CreateAccessTokenRequest,
    CreateUserRequest,
    CreateUserTokenRequest,
    CurrentUserProfile,
    GroupRecord,
    UserTokenCreatedResponse,
    UserTokenListResponse,
    UserTokenResponse,
)
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.user import create_user, generate_token
from mlflow_oidc_auth.utils import get_is_admin, get_username

from ._prefix import USERS_ROUTER_PREFIX

logger = get_logger()

users_router = APIRouter(
    prefix=USERS_ROUTER_PREFIX,
    tags=["users"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


USERS_ROOT = ""
CREATE_ACCESS_TOKEN = "/access-token"
CURRENT_USER = "/current"
USERNAME = "/{username}"
TOKENS = "/tokens"
TOKEN_BY_ID = "/tokens/{token_id}"
USER_TOKENS = "/{username}/tokens"
USER_TOKEN_BY_ID = "/{username}/tokens/{token_id}"


# Default token name for backwards compatibility with legacy single-token API
DEFAULT_TOKEN_NAME = "default"


@users_router.patch(CREATE_ACCESS_TOKEN, summary="Create user access token", description="Creates a new access token for the authenticated user.")
async def create_access_token(
    token_request: Optional[CreateAccessTokenRequest] = Body(None),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    """
    Create a new access token for the authenticated user.

    This endpoint creates a new access token for the authenticated user.
    Optionally accepts expiration date and username (if different from current user).

    Note: This endpoint maintains backwards compatibility by rotating the "default"
    token. For managing multiple named tokens, use the /tokens endpoints.

    Parameters:
    -----------
    token_request : Optional[CreateAccessTokenRequest]
        Optional request body with token creation parameters.
    current_username : str
        The authenticated username (injected by dependency).
    is_admin : bool
        Whether the authenticated user has admin permissions.

    Returns:
    --------
    JSONResponse
        A JSON response containing the new access token.

    Raises:
    -------
    HTTPException
        If there is an error creating the access token.
    """
    try:
        # Determine which username to use for token creation.
        # - Default: rotate the authenticated user's token.
        # - Admins: may rotate tokens for other users.
        # - Non-admins: may not rotate tokens for other users.
        if token_request and token_request.username:
            target_username = token_request.username
            if target_username != current_username and not is_admin:
                raise HTTPException(status_code=403, detail="Administrator privileges required for this operation")
        else:
            target_username = current_username

        # Parse expiration date if provided
        expiration = None
        if token_request and token_request.expiration:
            expiration_str = token_request.expiration
            # Handle ISO 8601 with 'Z' (UTC) at the end
            if expiration_str.endswith("Z"):
                expiration_str = expiration_str[:-1] + "+00:00"

            try:
                expiration = datetime.fromisoformat(expiration_str)
                now = datetime.now(timezone.utc)

                if expiration < now:
                    raise HTTPException(status_code=400, detail="Expiration date must be in the future")

                if expiration > now + timedelta(days=366):
                    raise HTTPException(status_code=400, detail="Expiration date must be less than 1 year in the future")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid expiration date format")

        # Check if the target user exists
        user = store.get_user_profile(target_username)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {target_username} not found")

        # Delete existing default token if it exists (rotate behavior)
        existing_tokens = store.list_user_tokens(target_username)
        for token in existing_tokens:
            if token.name == DEFAULT_TOKEN_NAME:
                store.delete_user_token(token.id, target_username)
                break

        # Generate and store new token
        new_token = generate_token()
        store.create_user_token(username=target_username, name=DEFAULT_TOKEN_NAME, token=new_token, expires_at=expiration)

        return JSONResponse(content={"token": new_token, "message": f"Token for {target_username} has been created"})

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Log unexpected errors and return a generic error response
        logger.error(f"Error creating access token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create access token")


@users_router.get(USERS_ROOT, summary="List users", description="Retrieves a list of users in the system.")
async def list_users(service: bool = False, username: str = Depends(get_username)) -> JSONResponse:
    """
    List users in the system.

    This endpoint returns all users in the system. Any authenticated user can access this endpoint.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    service : bool
        Whether to filter for service accounts only.
    username : str
        The authenticated username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of users.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the users.
    """
    try:
        from mlflow_oidc_auth.store import store

        # Get users filtered by service account type
        users = [user.username for user in store.list_users(is_service_account=service)]

        return JSONResponse(content=users)

    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve users")


@users_router.post(
    USERS_ROOT,
    summary="Create a new user or service account",
    description="Creates a new user or service account in the system. Only admins can create users.",
)
async def create_new_user(
    user_request: CreateUserRequest = Body(..., description="User creation details"), admin_username: str = Depends(check_admin_permission)
) -> JSONResponse:
    """
    Create a new user or service account in the system.

    Only administrators can create new users. This endpoint creates a new user
    with the specified permissions and account type.

    Parameters:
    -----------
    user_request : CreateUserRequest
        The user creation request containing username, display name, and flags.
    admin_username : str
        The authenticated admin username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response indicating success or failure of user creation.

    Raises:
    -------
    HTTPException
        If there is an error creating the user.
    """
    try:
        # Call the user creation implementation
        status, message = create_user(
            username=user_request.username,
            display_name=user_request.display_name,
            is_admin=user_request.is_admin,
            is_service_account=user_request.is_service_account,
        )

        if status:
            # User was created successfully
            return JSONResponse(content={"message": message}, status_code=201)
        else:
            # User already exists (updated)
            return JSONResponse(content={"message": message}, status_code=200)

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user")


@users_router.delete(USERS_ROOT, summary="Delete a user", description="Deletes a user from the system. Only admins can delete users.")
async def delete_user(
    username: str = Body(..., description="The username to delete", embed=True), admin_username: str = Depends(check_admin_permission)
) -> JSONResponse:
    """
    Delete a user from the system.

    Only administrators can delete users. This endpoint removes the user
    and all associated permissions from the system.

    Parameters:
    -----------
    username : str
        The username of the user to delete.
    admin_username : str
        The authenticated admin username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response indicating success or failure of user deletion.

    Raises:
    -------
    HTTPException
        If there is an error deleting the user or user is not found.
    """
    try:
        # Check if user exists before attempting deletion
        user = store.get_user_profile(username)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        # Delete the user
        store.delete_user(username)

        return JSONResponse(content={"message": f"User {username} has been successfully deleted"})

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error deleting user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user")


@users_router.get(
    CURRENT_USER,
    response_model=CurrentUserProfile,
    summary="Get current user information",
    description="Retrieves basic information (no permissions) about the currently authenticated user.",
)
async def get_current_user_information(current_username: str = Depends(get_username)) -> CurrentUserProfile:
    """
    Get information about the currently authenticated user.

    This endpoint returns the user profile information for the authenticated user,
    including username, display name, admin status, and other user attributes.

    Parameters:
    -----------
    current_username : str
        The authenticated username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the user's information.

    Raises:
    -------
    HTTPException
        If the user is not found or there's an error retrieving user information.
    """
    try:
        user = store.get_user_profile(current_username)
        return CurrentUserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=bool(user.is_admin),
            is_service_account=bool(user.is_service_account),
            password_expiration=user.password_expiration.isoformat() if user.password_expiration else None,
            groups=[GroupRecord(**g.to_json()) for g in (user.groups or [])],
        )
    except Exception as e:
        logger.error(f"Error getting current user information: {str(e)}")
        raise HTTPException(status_code=404, detail="User not found")


# =============================================================================
# Token Management Endpoints (Multi-Token API)
# =============================================================================
# NOTE: These routes MUST be defined BEFORE the /{username} route below,
# otherwise FastAPI will match /tokens as a username parameter.


def _token_to_response(token) -> UserTokenResponse:
    """Convert a UserToken entity to a response model."""
    return UserTokenResponse(
        id=token.id,
        name=token.name,
        created_at=token.created_at.isoformat() if token.created_at else None,
        expires_at=token.expires_at.isoformat() if token.expires_at else None,
        last_used_at=token.last_used_at.isoformat() if token.last_used_at else None,
    )


def _parse_expiration(expiration_str: Optional[str]) -> Optional[datetime]:
    """Parse and validate an expiration date string."""
    if not expiration_str:
        return None

    # Handle ISO 8601 with 'Z' (UTC) at the end
    if expiration_str.endswith("Z"):
        expiration_str = expiration_str[:-1] + "+00:00"

    try:
        expiration = datetime.fromisoformat(expiration_str)
        now = datetime.now(timezone.utc)

        if expiration < now:
            raise HTTPException(status_code=400, detail="Expiration date must be in the future")

        if expiration > now + timedelta(days=366):
            raise HTTPException(status_code=400, detail="Expiration date must be less than 1 year in the future")

        return expiration
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration date format")


@users_router.get(
    TOKENS,
    response_model=UserTokenListResponse,
    summary="List user tokens",
    description="List all tokens for the authenticated user.",
)
async def list_tokens(current_username: str = Depends(get_username)) -> UserTokenListResponse:
    """List all tokens for the authenticated user."""
    try:
        tokens = store.list_user_tokens(current_username)
        return UserTokenListResponse(tokens=[_token_to_response(t) for t in tokens])
    except Exception as e:
        logger.error(f"Error listing tokens: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list tokens")


@users_router.post(
    TOKENS,
    response_model=UserTokenCreatedResponse,
    status_code=201,
    summary="Create a named token",
    description="Create a new named token for the authenticated user.",
)
async def create_token(
    token_request: CreateUserTokenRequest,
    current_username: str = Depends(get_username),
) -> UserTokenCreatedResponse:
    """Create a new named token for the authenticated user."""
    try:
        expiration = _parse_expiration(token_request.expiration)

        # Generate and store new token
        new_token = generate_token()
        created = store.create_user_token(
            username=current_username,
            name=token_request.name,
            token=new_token,
            expires_at=expiration,
        )

        return UserTokenCreatedResponse(
            id=created.id,
            name=created.name,
            token=new_token,  # Only shown once at creation
            created_at=created.created_at.isoformat() if created.created_at else None,
            expires_at=created.expires_at.isoformat() if created.expires_at else None,
            message=f"Token '{token_request.name}' created successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Token with name '{token_request.name}' already exists")
        logger.error(f"Error creating token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create token")


@users_router.delete(
    TOKEN_BY_ID,
    summary="Delete a token",
    description="Delete a specific token by ID.",
)
async def delete_token(
    token_id: int,
    current_username: str = Depends(get_username),
) -> JSONResponse:
    """Delete a specific token by ID."""
    try:
        store.delete_user_token(token_id, current_username)
        return JSONResponse(content={"message": "Token deleted successfully"})
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Token with id={token_id} not found")
        logger.error(f"Error deleting token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete token")


# =============================================================================
# User Information Endpoint (with path parameter)
# =============================================================================
# NOTE: This route MUST be defined AFTER all specific routes like /tokens,
# /tokens/{token_id}, etc. to avoid catching them as username values.


@users_router.get(
    USERNAME,
    response_model=CurrentUserProfile,
    summary="Get user information",
    description="Retrieves basic user information (no permissions) about a specified user. Admin-only.",
)
async def get_user_information(username: str, admin_username: str = Depends(check_admin_permission)) -> CurrentUserProfile:
    """
    Get information about a specified user.

    This endpoint returns the user profile information for the specified user,
    including username, display name, admin status, and other user attributes.

    Parameters:
    -----------
    username : str
        The username of the user to retrieve information for.
    admin_username : str
        The authenticated admin username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the user's information.

    Raises:
    -------
    HTTPException
        If the user is not found or there's an error retrieving user information.
    """
    try:
        user = store.get_user_profile(username)
        return CurrentUserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=bool(user.is_admin),
            is_service_account=bool(user.is_service_account),
            password_expiration=user.password_expiration.isoformat() if user.password_expiration else None,
            groups=[GroupRecord(**g.to_json()) for g in (user.groups or [])],
        )
    except Exception as e:
        logger.error(f"Error getting user information for {username}: {str(e)}")
        raise HTTPException(status_code=404, detail="User not found")


# =============================================================================
# Admin Token Management Endpoints
# =============================================================================


@users_router.get(
    USER_TOKENS,
    response_model=UserTokenListResponse,
    summary="List user tokens (admin)",
    description="List all tokens for a specific user. Admin only.",
)
async def list_user_tokens_admin(
    username: str,
    admin_username: str = Depends(check_admin_permission),
) -> UserTokenListResponse:
    """List all tokens for a specific user (admin only)."""
    try:
        # Verify user exists
        user = store.get_user_profile(username)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        tokens = store.list_user_tokens(username)
        return UserTokenListResponse(tokens=[_token_to_response(t) for t in tokens])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tokens for user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list tokens")


@users_router.post(
    USER_TOKENS,
    response_model=UserTokenCreatedResponse,
    status_code=201,
    summary="Create token for user (admin)",
    description="Create a new named token for a specific user. Admin only.",
)
async def create_user_token_admin(
    username: str,
    token_request: CreateUserTokenRequest,
    admin_username: str = Depends(check_admin_permission),
) -> UserTokenCreatedResponse:
    """Create a new named token for a specific user (admin only)."""
    try:
        # Verify user exists
        user = store.get_user_profile(username)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        expiration = _parse_expiration(token_request.expiration)

        # Generate and store new token
        new_token = generate_token()
        created = store.create_user_token(
            username=username,
            name=token_request.name,
            token=new_token,
            expires_at=expiration,
        )

        return UserTokenCreatedResponse(
            id=created.id,
            name=created.name,
            token=new_token,
            created_at=created.created_at.isoformat() if created.created_at else None,
            expires_at=created.expires_at.isoformat() if created.expires_at else None,
            message=f"Token '{token_request.name}' created for user '{username}'",
        )
    except HTTPException:
        raise
    except Exception as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Token with name '{token_request.name}' already exists for user '{username}'")
        logger.error(f"Error creating token for user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create token")


@users_router.delete(
    USER_TOKEN_BY_ID,
    summary="Delete user token (admin)",
    description="Delete a specific token for a user. Admin only.",
)
async def delete_user_token_admin(
    username: str,
    token_id: int,
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Delete a specific token for a user (admin only)."""
    try:
        store.delete_user_token(token_id, username)
        return JSONResponse(content={"message": f"Token deleted successfully for user '{username}'"})
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Token with id={token_id} not found for user '{username}'")
        logger.error(f"Error deleting token for user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete token")
