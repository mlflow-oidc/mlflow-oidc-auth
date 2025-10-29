from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import CreateAccessTokenRequest, CreateUserRequest
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.user import create_user, generate_token
from mlflow_oidc_auth.utils import get_username

from ._prefix import USERS_ROUTER_PREFIX

logger = get_logger()

users_router = APIRouter(
    prefix=USERS_ROUTER_PREFIX,
    tags=["permissions", "users"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_USERS = ""
CREATE_USER = "/create"
CREATE_ACCESS_TOKEN = "/access-token"
DELETE_USER = "/delete"


@users_router.patch(CREATE_ACCESS_TOKEN, summary="Create user access token", description="Creates a new access token for the authenticated user.")
async def create_access_token(token_request: Optional[CreateAccessTokenRequest] = Body(None), current_username: str = Depends(get_username)) -> JSONResponse:
    """
    Create a new access token for the authenticated user.

    This endpoint creates a new access token for the authenticated user.
    Optionally accepts expiration date and username (if different from current user).

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    token_request : Optional[CreateAccessTokenRequest]
        Optional request body with token creation parameters.
    current_username : str
        The authenticated username (injected by dependency).

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
        # Determine which username to use for token creation
        # If no request body or username provided, use the authenticated user
        if token_request and token_request.username:
            target_username = token_request.username
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
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid expiration date format")

        # Check if the target user exists
        user = store.get_user(target_username)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {target_username} not found")

        # Generate new token and update user
        new_token = generate_token()
        store.update_user(username=target_username, password=new_token, password_expiration=expiration)

        return JSONResponse(content={"token": new_token, "message": f"Token for {target_username} has been created"})

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Log unexpected errors and return a generic error response

        logger.error(f"Error creating access token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create access token")


@users_router.get(LIST_USERS, summary="List users", description="Retrieves a list of users in the system.")
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
    CREATE_USER,
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


@users_router.delete(DELETE_USER, summary="Delete a user", description="Deletes a user from the system. Only admins can delete users.")
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
        user = store.get_user(username)
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
