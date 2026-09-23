from datetime import datetime, timedelta, timezone
import re
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    CreateAccessTokenRequest,
    CreateUserRequest,
    CurrentUserProfile,
    GroupRecord,
)
from mlflow_oidc_auth.models.scim import UserActiveRequest
from mlflow_oidc_auth.orphans import delete_user_reporting_orphans, report_orphans
from mlflow_oidc_auth.ownership import MANUAL, evaluate_write
from mlflow.protos.databricks_pb2 import INVALID_STATE, ErrorCode
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
USER_OWNERSHIP = "/ownership"
CURRENT_USER = "/current"
USERNAME = "/{username}"
USERS_DETAILS = "/details"
USER_ACTIVE = "/{username}/active"

#: Fields of each object returned by ``GET /users/details`` and ``PATCH /users/{username}/active``.
USER_DETAIL_FIELDS = ("username", "display_name", "is_admin", "is_service_account", "active", "managed_by")


@users_router.patch(
    CREATE_ACCESS_TOKEN,
    summary="Create user access token",
    description="Creates a new access token for the authenticated user.",
)
async def create_access_token(
    token_request: Optional[CreateAccessTokenRequest] = Body(None),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    """
    Create a new access token for the authenticated user.

    This endpoint creates a new access token for the authenticated user.
    Optionally accepts expiration date and username (if different from current user).

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
                raise HTTPException(
                    status_code=403,
                    detail="Administrator privileges required for this operation",
                )
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
                # An ISO 8601 timestamp carries no offset unless one is written, and both
                # "2027-01-01" and "2027-01-01T00:00:00" are valid. Comparing a naive datetime
                # to an aware one raises TypeError, which is not a ValueError and so used to
                # escape as a 500. This layer deals in UTC — the 'Z' handling above says so —
                # so read a missing offset as UTC rather than rejecting the request (issue #338).
                if expiration.tzinfo is None:
                    expiration = expiration.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)

                if expiration < now:
                    raise HTTPException(status_code=400, detail="Expiration date must be in the future")

                if expiration > now + timedelta(days=366):
                    raise HTTPException(
                        status_code=400,
                        detail="Expiration date must be less than 1 year in the future",
                    )
            except (ValueError, TypeError):
                # TypeError is belt-and-braces: the normalization above should make it
                # unreachable, but a bad expiration must never become a 500.
                raise HTTPException(status_code=400, detail=f"Invalid expiration date format")

        # Check if the target user exists. get_user_profile raises rather than returning None,
        # so without this the outer handler turns a mistyped username into a 500 (issue #338).
        try:
            user = store.get_user_profile(target_username)
        except MlflowException:
            raise HTTPException(status_code=404, detail=f"User {target_username} not found")
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {target_username} not found")

        # Generate new token and update user. The new token carries exactly the expiration
        # requested here; it never inherits the previous token's (issue #338).
        previous_expiration = user.password_expiration
        new_token = generate_token()
        # An administrator acting through the admin API is break glass by definition: they must
        # be able to repair a row a directory owns, and the attempt is audited either way (#319).
        store.update_user(username=target_username, password=new_token, password_expiration=expiration, written_by="manual", admin_override=True)
        emit_audit_event(
            "user.token_rotate",
            actor=current_username,
            resource_type="user",
            resource_id=target_username,
            detail={
                "expiration": expiration.isoformat() if expiration else None,
                # Rotating without an expiration replaces an expiring token with one that does
                # not expire. That is a deliberate widening of the credential's lifetime, so it
                # is recorded rather than left silent.
                "expiration_cleared": previous_expiration is not None and expiration is None,
            },
        )

        return JSONResponse(
            content={
                "token": new_token,
                "message": f"Token for {target_username} has been created",
            }
        )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Log unexpected errors and return a generic error response

        logger.error(f"Error creating access token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create access token")


@users_router.get(
    USERS_ROOT,
    summary="List users",
    description="Retrieves a list of users in the system.",
)
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

        # Use lightweight query that only fetches usernames,
        # avoiding eager loading of all permission relationships per user.
        users = store.list_usernames(is_service_account=service)

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
    user_request: CreateUserRequest = Body(..., description="User creation details"),
    admin_username: str = Depends(check_admin_permission),
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
            emit_audit_event(
                "user.create",
                actor=admin_username,
                resource_type="user",
                resource_id=user_request.username,
                detail={
                    "is_admin": user_request.is_admin,
                    "is_service_account": user_request.is_service_account,
                },
            )
            return JSONResponse(content={"message": message}, status_code=201)
        else:
            # User already exists (updated)
            return JSONResponse(content={"message": message}, status_code=200)

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user")


@users_router.patch(
    USER_OWNERSHIP,
    summary="Change which source owns a user",
    description="Sets a user's managed_by. Admins only. This is the break-glass path when a directory is decommissioned.",
)
async def set_user_ownership(
    username: str = Body(..., description="The user whose ownership is being changed"),
    managed_by: str = Body(..., description="The new owner: 'manual', 'scim', or 'oidc:<provider-id>'"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Hand a user row to a different source (issue #319).

    The guard's whole failure mode is lockout, and lockout is only survivable if an
    administrator can undo it *without* database access. That is what this is: an explicit,
    audited administrator write, permitted in every enforcement mode.

    The common case is a directory being decommissioned — its rows are set back to ``manual``
    and become editable again. ``mlflow-oidc db reconcile-ownership`` does the same thing in
    bulk, for an operator who does have a shell.

    Parameters:
        username: The user whose ownership is being changed.
        managed_by: The new owner.
        admin_username: The authenticated administrator (injected).

    Returns:
        JSONResponse: What changed.

    Raises:
        HTTPException: 400 if the owner is not one a source presents, 404 if there is no such
            user.
    """
    if not re.fullmatch(r"manual|scim|oidc:[A-Za-z0-9._-]+", managed_by or ""):
        raise HTTPException(status_code=400, detail="managed_by must be 'manual', 'scim', or 'oidc:<provider-id>'")

    try:
        store.get_user_profile(username)
    except MlflowException:
        raise HTTPException(status_code=404, detail=f"User {username} not found")

    previous = store.get_user_profile(username).managed_by
    store.update_user(username=username, managed_by=managed_by, written_by="manual", admin_override=True)
    emit_audit_event(
        "user.ownership_set",
        actor=admin_username,
        resource_type="user",
        resource_id=username,
        detail={"from": previous, "to": managed_by},
    )
    logger.info("Administrator %s set ownership of %s from %s to %s", admin_username, username, previous, managed_by)
    return JSONResponse(content={"username": username, "managed_by": managed_by, "previous": previous}, status_code=200)


def _audit_delete_conflict(username: str, decision, admin_username: str) -> None:
    emit_audit_event(
        "user.ownership_conflict",
        actor=admin_username,
        resource_type="user",
        resource_id=username,
        detail={"owner": decision.owner, "written_by": MANUAL, "reason": decision.reason, "permitted": decision.allowed, "operation": "delete"},
        status="success" if decision.allowed else "denied",
    )


@users_router.delete(
    USERS_ROOT,
    summary="Delete a user",
    description="Deletes a user from the system. Only admins can delete users.",
)
async def delete_user(
    username: str = Body(..., description="The username to delete", embed=True),
    admin_username: str = Depends(check_admin_permission),
    admin_override: Annotated[bool, Body(embed=True, description="Break glass: delete a row another source owns. Always audited.")] = False,
) -> JSONResponse:
    """
    Delete a user from the system.

    Only administrators can delete users. This endpoint removes the user
    and all associated permissions from the system.

    Goes through the same ownership guard as ``PATCH /users/{username}/active``, as
    ``written_by='manual'``: a directory-owned user is refused under
    ``MANAGED_BY_ENFORCEMENT=enforce`` unless the request says ``admin_override: true``.
    Otherwise an administrator refused a deactivation could hard-delete the same user instead.
    Every conflict is audited as ``user.ownership_conflict`` (``operation: delete``).

    Parameters:
    -----------
    username : str
        The username of the user to delete.
    admin_username : str
        The authenticated admin username (injected by dependency).
    admin_override : bool
        Break glass for a row another source owns. Defaults to False.

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
        detail = store.get_user_detail(username)
        if not detail:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        decision = evaluate_write(
            detail.get("managed_by"),
            MANUAL,
            enforcement=config.MANAGED_BY_ENFORCEMENT,
            admin_override=admin_override is True,
            fields={"deleted"},
            target_is_admin=bool(detail.get("is_admin")),
        )
        if decision.conflict and not decision.allowed:
            _audit_delete_conflict(username, decision, admin_username)
            raise HTTPException(status_code=409, detail=f"User {username} is managed by {decision.owner!r}: {decision.reason}")

        # Orphan detection and the ORPHAN_FALLBACK_PRINCIPAL hand-over run inside the delete's own
        # transaction, before the cascade removes the grants they read: a refused delete (the last
        # active administrator) rolls the hand-over back too. They never block the delete (#324).
        try:
            delete_user_reporting_orphans(username, actor=admin_username, source="admin", store=store)
        except MlflowException as e:
            if e.error_code == ErrorCode.Name(INVALID_STATE):
                raise HTTPException(status_code=409, detail=e.message)
            raise
        if decision.conflict:
            # A permitted cross-source delete (report mode, or the override), recorded only once
            # the delete has committed.
            _audit_delete_conflict(username, decision, admin_username)
        emit_audit_event(
            "user.delete",
            actor=admin_username,
            resource_type="user",
            resource_id=username,
        )

        return JSONResponse(content={"message": f"User {username} has been successfully deleted"})

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error deleting user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user")


@users_router.get(
    USERS_DETAILS,
    summary="List users with lifecycle state",
    description="Lists users with their admin, service-account, active and managed_by state. Admins only.",
)
async def list_user_details(service: Optional[bool] = None, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """List users as objects, for the admin UI (issue #320).

    ``GET /users`` keeps returning a bare ``string[]`` — the UI and API clients depend on it —
    so the richer shape is a separate, admin-only endpoint: ``managed_by`` and ``is_admin`` are
    administrative information.

    Parameters:
        service: True for service accounts only, False for users only, omitted for both.
        admin_username: The authenticated administrator (injected).

    Returns:
        JSONResponse: ``[{"username", "display_name", "is_admin", "is_service_account", "active",
        "managed_by"}]``, ordered by creation.
    """
    try:
        _, rows = store.list_user_details(is_service_account=service)
    except Exception as e:
        logger.error(f"Error listing user details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve users")
    return JSONResponse(content=[{key: row[key] for key in USER_DETAIL_FIELDS} for row in rows])


@users_router.patch(
    USER_ACTIVE,
    summary="Activate or deactivate a user",
    description="Sets a user's active flag. Deactivating revokes their sessions and token and keeps their grants. Admins only.",
)
async def set_user_active(
    username: str,
    active_request: UserActiveRequest = Body(...),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Deactivate or reactivate a user from the admin API (issues #320, #324).

    Goes through the same store write as a SCIM de-provision, as ``written_by='manual'``: a
    directory-owned user is refused under ``MANAGED_BY_ENFORCEMENT=enforce`` unless the request
    says ``admin_override: true`` — break glass, always audited.

    Deactivation revokes every live session and replaces the user's token with an undisclosed,
    already-expired secret in one transaction. Grants are retained, so reactivation restores
    access once the user signs in again or is issued a new token.

    Raises:
        HTTPException: 404 for an unknown user; 409 when the ownership guard refuses the write
            or it would leave no active administrator.
    """
    detail = store.get_user_detail(username)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"User {username} not found")

    kwargs = {"active": active_request.active, "written_by": "manual", "admin_override": active_request.admin_override}
    if active_request.active is False:
        kwargs["password"] = generate_token()
        kwargs["password_expiration"] = datetime.now(timezone.utc)
    try:
        store.update_user(detail["username"], **kwargs)
    except MlflowException as e:
        # The ownership guard and the last-active-admin invariant: both a refusal, never a 500.
        raise HTTPException(status_code=409, detail=e.message)

    target = detail["username"]
    if active_request.active is False and detail["active"]:
        emit_audit_event("user.deactivated", actor=admin_username, resource_type="user", resource_id=target, detail={"source": "admin"})
        report_orphans(target, actor=admin_username, source="admin", store=store)
    elif active_request.active is True and not detail["active"]:
        emit_audit_event("user.reactivated", actor=admin_username, resource_type="user", resource_id=target, detail={"source": "admin"})

    updated = store.get_user_detail(target)
    return JSONResponse(content={key: updated[key] for key in USER_DETAIL_FIELDS})


@users_router.get(
    CURRENT_USER,
    response_model=CurrentUserProfile,
    summary="Get current user information",
    description="Retrieves basic information (no permissions) about the currently authenticated user.",
)
async def get_current_user_information(
    current_username: str = Depends(get_username),
) -> CurrentUserProfile:
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
