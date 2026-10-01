from datetime import datetime, timedelta, timezone
import re
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.dependencies import check_admin_permission, require_interactive_login
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    CreateAccessTokenRequest,
    CreateUserRequest,
    CreateUserTokenRequest,
    CurrentUserProfile,
    GroupRecord,
)
from mlflow_oidc_auth.models.scim import UserActiveRequest
from mlflow_oidc_auth.models.user import ServiceAccountSourceRequest
from mlflow_oidc_auth.orphans import delete_user_reporting_orphans, report_orphans
from mlflow_oidc_auth.ownership import MANUAL, OWNER_PATTERN
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow_oidc_auth.repository.user_token import DEFAULT_TOKEN_NAME, MAX_TOKEN_LIFETIME
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.user import create_user
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.pagination import NO_PAGE, PageParams, PageQuery, paginate_with_headers

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
USER_SESSIONS = "/{username}/sessions"
USER_SESSION = "/{username}/sessions/{session_pk}"
USER_IDENTITIES = "/{username}/identities"
USER_SERVICE_ACCOUNT_SOURCE = "/{username}/service-account-source"
SERVICE_ACCOUNT_SOURCES = "/service-account-sources"
USER_TOKENS = "/current/tokens"
USER_TOKEN = "/current/tokens/{token_id}"
USER_TOKENS_OF = "/{username}/tokens"
USER_TOKEN_OF = "/{username}/tokens/{token_id}"

#: The lifetime of a ``default`` token issued by ``PATCH /users/access-token`` without an expiration.
DEFAULT_TOKEN_LIFETIME = timedelta(days=365)

#: Fields of each object returned by ``GET /users/details`` and ``PATCH /users/{username}/active``.
USER_DETAIL_FIELDS = ("username", "display_name", "is_admin", "is_service_account", "active", "managed_by", "service_account_source")


def _parse_expiration(value: Optional[str]) -> datetime:
    """Parse a requested token expiry, as an aware UTC datetime.

    Raises:
        HTTPException: 400 when it is not ISO 8601, is in the past, or is more than a year away.
    """
    expiration_str = value or ""
    # Handle ISO 8601 with 'Z' (UTC) at the end
    if expiration_str.endswith("Z"):
        expiration_str = expiration_str[:-1] + "+00:00"
    try:
        expiration = datetime.fromisoformat(expiration_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid expiration date format")
    # An ISO 8601 timestamp carries no offset unless one is written, and both "2027-01-01" and
    # "2027-01-01T00:00:00" are valid. This layer deals in UTC — the 'Z' handling above says so —
    # so a missing offset is read as UTC rather than rejected (issue #338).
    if expiration.tzinfo is None:
        expiration = expiration.replace(tzinfo=timezone.utc)
    expiration = expiration.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if expiration <= now:
        raise HTTPException(status_code=400, detail="Expiration date must be in the future")
    if expiration > now + MAX_TOKEN_LIFETIME:
        raise HTTPException(status_code=400, detail="Expiration date must be less than 1 year in the future")
    return expiration


_TOKEN_ERROR_STATUS = {
    ErrorCode.Name(INVALID_PARAMETER_VALUE): 400,
    ErrorCode.Name(RESOURCE_DOES_NOT_EXIST): 404,
    ErrorCode.Name(RESOURCE_ALREADY_EXISTS): 409,
    ErrorCode.Name(INVALID_STATE): 409,
}


def _token_http_error(e: MlflowException) -> HTTPException:
    """Map a token repository refusal to its HTTP status. Anything unexpected is a 500."""
    status = _TOKEN_ERROR_STATUS.get(e.error_code)
    if status is None:
        logger.error("Access token operation failed: %s", type(e).__name__)
        return HTTPException(status_code=500, detail="Access token operation failed")
    return HTTPException(status_code=status, detail=e.message)


def _require_user(username: str) -> str:
    """The stored username of ``username``, or a 404."""
    try:
        user = store.get_user_profile(username)
    except MlflowException:
        user = None
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {username} not found")
    return user.username


@users_router.get(
    SERVICE_ACCOUNT_SOURCES,
    summary="List the sources a service account can sign in through",
    description="Internal (issued access tokens only) and each OIDC provider. Admin only.",
)
async def list_service_account_sources(admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """The choices for :func:`set_service_account_source` and service account creation."""
    from mlflow_oidc_auth.utils.service_accounts import selectable_sources

    return JSONResponse(content=selectable_sources())


@users_router.patch(
    CREATE_ACCESS_TOKEN,
    summary="Create user access token",
    description="Issues a new 'default' access token for the authenticated user, replacing the previous one. "
    "Admins may issue one for another user. The token expires at most one year from now. Requires a signed-in "
    "session: a request authenticated with an access token is refused.",
    dependencies=[Depends(require_interactive_login)],
)
async def create_access_token(
    token_request: Optional[CreateAccessTokenRequest] = Body(None),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    """Replace a user's ``default`` access token (issue #189).

    The endpoint every existing client uses. It now issues a named token, ``default``, and deletes
    the previous ``default`` token in the same transaction; the user's other named tokens are left
    as they are (``DELETE /users/{username}/tokens`` revokes them all). Tokens must expire: an
    omitted ``expiration`` means one year from now, never "does not expire".

    Parameters:
        token_request: Optional ``username`` (admins only, for another user) and ``expiration``.
        current_username: The authenticated username (injected).
        is_admin: Whether the authenticated user is an administrator (injected).

    Returns:
        JSONResponse: ``{"token", "expires_at", "message"}``. The token is shown only here.

    Like every endpoint that issues a token, it refuses a request authenticated with an access
    token (``require_interactive_login``): a leaked token must not be able to mint another.

    Raises:
        HTTPException: 403 for a non-admin naming another user or when authenticated with an
            access token, 404 for an unknown user, 400 for a bad expiration, 409 at the per-user
            token cap.
    """
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

    if token_request and token_request.expiration:
        expiration = _parse_expiration(token_request.expiration)
        expiration_defaulted = False
    else:
        expiration = datetime.now(timezone.utc) + DEFAULT_TOKEN_LIFETIME
        expiration_defaulted = True

    # get_user_profile raises rather than returning None; a mistyped username is a 404, not a 500
    # (issue #338).
    target_username = _require_user(target_username)
    _refuse_tokens_for_external_service_account(target_username)
    try:
        record, plaintext, replaced = store.replace_user_token(target_username, DEFAULT_TOKEN_NAME, expiration, created_by=current_username)
    except MlflowException as e:
        raise _token_http_error(e)

    emit_audit_event(
        "user.token_rotate",
        actor=current_username,
        resource_type="user",
        resource_id=target_username,
        detail={
            "token_id": record.id,
            "token_prefix": record.token_prefix,
            "name": record.name,
            "expiration": record.to_json()["expires_at"],
            "expiration_defaulted": expiration_defaulted,
            "replaced": replaced,
        },
    )
    return JSONResponse(
        content={
            "token": plaintext,
            "expires_at": record.to_json()["expires_at"],
            "message": f"Token for {target_username} has been created",
        },
        headers={"Cache-Control": "no-store"},
    )


def _refuse_tokens_for_external_service_account(username: str) -> None:
    """No access token is issued for an external service account: its lifecycle lives in its IdP.

    Raises:
        HTTPException: 409 for an external service account.
    """
    from mlflow_oidc_auth.utils.service_accounts import is_external

    profile = store.get_user_profile(username)
    if profile.is_service_account is True and is_external(profile.service_account_source):
        raise HTTPException(
            status_code=409, detail="An external service account signs in with its identity provider's tokens; no access token is issued for it"
        )


def _issue_token(target_username: str, token_request: CreateUserTokenRequest, actor: str) -> JSONResponse:
    expiration = _parse_expiration(token_request.expiration)
    target_username = _require_user(target_username)
    _refuse_tokens_for_external_service_account(target_username)
    try:
        record, plaintext = store.create_user_token(target_username, token_request.name, expiration, created_by=actor)
    except MlflowException as e:
        raise _token_http_error(e)
    emit_audit_event(
        "user.token_create",
        actor=actor,
        resource_type="user",
        resource_id=target_username,
        detail={"token_id": record.id, "token_prefix": record.token_prefix, "name": record.name, "expiration": record.to_json()["expires_at"]},
    )
    return JSONResponse(content={**record.to_json(), "token": plaintext}, status_code=201, headers={"Cache-Control": "no-store"})


def _list_tokens(target_username: str, page: PageParams = NO_PAGE) -> JSONResponse:
    """The ``{"tokens": [...]}`` body of a user's tokens, optionally paged and searched by name.

    Parameters:
        target_username: Whose tokens to list. The caller has already been authorized for them.
        page: Opt-in ``limit`` / ``offset`` / ``search`` on the token name.

    Returns:
        JSONResponse: ``{"tokens": [...]}``, never cached, with ``X-Total-Count`` when paged.

    Raises:
        HTTPException: 404 for an unknown user.
    """
    target_username = _require_user(target_username)
    try:
        records = store.list_user_tokens(target_username)
    except MlflowException as e:
        raise _token_http_error(e)
    records, headers = paginate_with_headers(records, key=lambda r: r.name, params=page, tiebreak=lambda r: r.id)
    return JSONResponse(content={"tokens": [r.to_json() for r in records]}, headers={"Cache-Control": "no-store", **headers})


def _delete_token(target_username: str, token_id: int, actor: str) -> JSONResponse:
    target_username = _require_user(target_username)
    try:
        record = store.delete_user_token(target_username, token_id)
    except MlflowException as e:
        raise _token_http_error(e)
    emit_audit_event(
        "user.token_delete",
        actor=actor,
        resource_type="user",
        resource_id=target_username,
        detail={"token_id": record.id, "token_prefix": record.token_prefix, "name": record.name},
    )
    return JSONResponse(content={"deleted": 1})


@users_router.get(
    USER_TOKENS,
    summary="List my access tokens",
    description="Lists the authenticated user's access tokens, expired ones included. Never returns a token's secret.",
)
async def list_my_tokens(current_username: str = Depends(get_username), page: PageQuery = NO_PAGE) -> JSONResponse:
    """The caller's own access tokens (issue #189), optionally paged (``limit`` / ``offset`` / ``search``)."""
    return _list_tokens(current_username, page)


@users_router.post(
    USER_TOKENS,
    summary="Create an access token",
    description="Issues a named access token for the authenticated user. Requires a signed-in session: "
    "a request authenticated with an access token is refused. The token is returned once.",
    dependencies=[Depends(require_interactive_login)],
)
async def create_my_token(
    token_request: CreateUserTokenRequest = Body(...),
    current_username: str = Depends(get_username),
) -> JSONResponse:
    """Issue a named token for the caller (issue #189).

    Raises:
        HTTPException: 403 when authenticated with an access token, 400 for a bad name or
            expiration, 409 for a duplicate name or at the per-user cap.
    """
    return _issue_token(current_username, token_request, actor=current_username)


@users_router.delete(
    USER_TOKEN,
    summary="Delete one of my access tokens",
    description="Deletes one of the authenticated user's access tokens. It stops working immediately.",
)
async def delete_my_token(token_id: int, current_username: str = Depends(get_username)) -> JSONResponse:
    """Delete one of the caller's tokens (issue #189). Allowed with any credential: it only removes access.

    Raises:
        HTTPException: 404 if the caller holds no token with that id — someone else's token reads
            exactly like one that does not exist.
    """
    return _delete_token(current_username, token_id, actor=current_username)


@users_router.get(
    USERS_ROOT,
    summary="List users",
    description="Retrieves a list of users in the system.",
)
async def list_users(service: bool = False, username: str = Depends(get_username), page: PageQuery = NO_PAGE) -> JSONResponse:
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
    page : PageParams
        Opt-in ``limit`` / ``offset`` / ``search`` on the username (see ``utils/pagination.py``).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of users — a bare ``string[]``, paged or not. When
        paged or searched, ``X-Total-Count`` carries the number of matching usernames.

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
        users, headers = paginate_with_headers(users, key=lambda u: u, params=page)

        return JSONResponse(content=users, headers=headers)

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
    from mlflow_oidc_auth.utils.service_accounts import INTERNAL_SOURCE, apply_source, validate_source

    source = None
    if user_request.is_service_account:
        try:
            source = validate_source(user_request.service_account_source or INTERNAL_SOURCE, user_request.subject, is_admin=user_request.is_admin)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if (user_request.service_account_source or user_request.subject) and store.has_user(user_request.username):
            raise HTTPException(status_code=409, detail=f"{user_request.username} already exists; change how it signs in with its service-account-source")
        if user_request.subject and store.user_identity_repo.get_username_by_identity(source, user_request.subject.strip()):
            raise HTTPException(status_code=409, detail="That subject is already bound to another account")
    elif user_request.service_account_source or user_request.subject:
        raise HTTPException(status_code=400, detail="service_account_source and subject apply to a service account only")
    try:
        # Call the user creation implementation
        status, message = create_user(
            username=user_request.username,
            display_name=user_request.display_name,
            is_admin=user_request.is_admin,
            is_service_account=user_request.is_service_account,
            written_by="manual",
            service_account_source=source,
        )
        if status and source and user_request.subject:
            try:
                apply_source(user_request.username, source, user_request.subject)
            except Exception:
                # Never leave an external account behind unbound: its provider's first token
                # would bind whatever subject it carries.
                store.delete_user(user_request.username)
                raise HTTPException(status_code=409, detail="That subject could not be bound to the new service account")

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
                    **({"service_account_source": source} if source else {}),
                },
            )
            return JSONResponse(content={"message": message}, status_code=201)
        else:
            # User already exists (updated)
            return JSONResponse(content={"message": message}, status_code=200)

    except HTTPException:
        raise
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
    managed_by: str = Body(..., description="The new owner: 'manual', 'scim', 'oidc:<provider-id>' or 'saml:<provider-id>'"),
    memberships: bool = Body(False, description="Also hand every group membership of the user to the new owner"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Hand a user row to a different source (issue #319).

    The guard's whole failure mode is lockout, and lockout is only survivable if an
    administrator can undo it *without* database access. That is what this is: an explicit,
    audited administrator write, permitted in every enforcement mode.

    The common case is a directory being decommissioned — its rows are set back to ``manual``
    and become editable again. ``mlflow-oidc db reconcile-ownership`` does the same thing in
    bulk, for an operator who does have a shell.

    With ``memberships: true`` the user's group memberships (#360), which carry their own owner,
    are handed over too — otherwise a decommissioned source's grants could not be removed by any
    other source under ``enforce``.

    Parameters:
        username: The user whose ownership is being changed.
        managed_by: The new owner.
        memberships: Whether to re-own the user's group memberships as well.
        admin_username: The authenticated administrator (injected).

    Returns:
        JSONResponse: What changed.

    Raises:
        HTTPException: 400 if the owner is not one a source presents, 404 if there is no such
            user.
    """
    if not re.fullmatch(OWNER_PATTERN, managed_by or ""):
        raise HTTPException(status_code=400, detail="managed_by must be 'manual', 'scim', 'oidc:<provider-id>' or 'saml:<provider-id>'")

    try:
        store.get_user_profile(username)
    except MlflowException:
        raise HTTPException(status_code=404, detail=f"User {username} not found")

    try:
        # One transaction for the user row and its memberships: a failure in either half leaves
        # both as they were.
        result = store.hand_over_user(username, managed_by, memberships=memberships is True, actor=admin_username)
    except Exception as e:
        logger.error("Handing %s to %s failed: %s", username, managed_by, type(e).__name__)
        emit_audit_event(
            "user.ownership_set",
            actor=admin_username,
            resource_type="user",
            resource_id=username,
            detail={"to": managed_by, "memberships": memberships is True, "applied": False},
            status="error",
        )
        raise HTTPException(status_code=500, detail="Failed to change ownership; nothing was changed")
    previous = result["previous"]
    detail = {"from": previous, "to": managed_by}
    content = {"username": username, "managed_by": managed_by, "previous": previous}
    if memberships is True:
        detail["memberships"] = [{"group": group, "from": owner} for group, owner in result["memberships"]]
        content["memberships"] = detail["memberships"]
    emit_audit_event(
        "user.ownership_set",
        actor=admin_username,
        resource_type="user",
        resource_id=username,
        detail=detail,
    )
    logger.info("Administrator %s set ownership of %s from %s to %s", admin_username, username, previous, managed_by)
    return JSONResponse(content=content, status_code=200)


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

        # The ownership guard (#360) runs inside the delete, as ``manual``: refused under enforce
        # unless ``admin_override``, recorded as ``user.ownership_conflict`` (``operation: delete``)
        # either way, and before anything else — so a refused delete detects and hands over nothing.
        # Orphan detection and the ORPHAN_FALLBACK_PRINCIPAL hand-over run inside the delete's own
        # transaction, before the cascade removes the grants they read: a refused delete (the last
        # active administrator) rolls the hand-over back too. They never block the delete (#324).
        try:
            delete_user_reporting_orphans(
                username,
                actor=admin_username,
                source="admin",
                store=store,
                written_by=MANUAL,
                admin_override=admin_override is True,
            )
        except MlflowException as e:
            # The ownership guard (INVALID_PARAMETER_VALUE) and the last-active-admin invariant
            # (INVALID_STATE): both a refusal, never a 500.
            if e.error_code in (ErrorCode.Name(INVALID_STATE), ErrorCode.Name(INVALID_PARAMETER_VALUE)):
                raise HTTPException(status_code=409, detail=e.message)
            raise
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
async def list_user_details(service: Optional[bool] = None, admin_username: str = Depends(check_admin_permission), page: PageQuery = NO_PAGE) -> JSONResponse:
    """List users as objects, for the admin UI (issue #320).

    ``GET /users`` keeps returning a bare ``string[]`` — the UI and API clients depend on it —
    so the richer shape is a separate, admin-only endpoint: ``managed_by`` and ``is_admin`` are
    administrative information.

    Parameters:
        service: True for service accounts only, False for users only, omitted for both.
        admin_username: The authenticated administrator (injected).
        page: Opt-in ``limit`` / ``offset`` / ``search`` on ``username`` (see
            ``utils/pagination.py``). When given, rows are ordered by username instead.

    Returns:
        JSONResponse: ``[{"username", "display_name", "is_admin", "is_service_account", "active",
        "managed_by"}]``, ordered by creation.

    Raises:
        HTTPException: 500 when the users cannot be read.
    """
    try:
        _, rows = store.list_user_details(is_service_account=service)
    except Exception as e:
        logger.error(f"Error listing user details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve users")
    rows, headers = paginate_with_headers(rows, key=lambda row: row["username"], params=page)
    return JSONResponse(content=[{key: row[key] for key in USER_DETAIL_FIELDS} for row in rows], headers=headers)


@users_router.patch(
    USER_ACTIVE,
    summary="Activate or deactivate a user",
    description="Sets a user's active flag. Deactivating revokes their sessions and tokens and keeps their grants. Admins only.",
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

    Deactivation revokes every live session and deletes every access token of the user in one
    transaction. Grants are retained, so reactivation restores access once the user signs in again
    or is issued a new token.

    Raises:
        HTTPException: 404 for an unknown user; 409 when the ownership guard refuses the write
            or it would leave no active administrator.
    """
    detail = store.get_user_detail(username)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"User {username} not found")

    kwargs = {"active": active_request.active, "written_by": "manual", "admin_override": active_request.admin_override}
    if active_request.active is False:
        kwargs["revoke_tokens"] = True
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


def _require_user_detail(username: str) -> dict:
    detail = store.get_user_detail(username)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"User {username} not found")
    return detail


@users_router.get(
    USER_SESSIONS,
    summary="List a user's live sessions",
    description="Lists a user's live server-side sessions. Returns a short id prefix and an opaque `pk`, never the session id. Admins only.",
)
async def list_user_sessions(username: str, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """A user's live sessions, newest first (issue #325).

    The full session id is a bearer credential, so it is never returned: ``session_id_prefix``
    tells sessions apart and ``pk`` addresses one for revocation. ``last_seen_at`` is recorded
    only where something writes it; the per-request authentication path does not.

    Raises:
        HTTPException: 404 for an unknown user.
    """
    target = _require_user_detail(username)["username"]
    return JSONResponse(
        content={"sessions": [summary.to_json() for summary in store.list_live_auth_session_details(target)]}, headers={"Cache-Control": "no-store"}
    )


@users_router.delete(
    USER_SESSION,
    summary="Revoke one of a user's sessions",
    description="Revokes one live session of this user, addressed by the `pk` from the session list. Admins only.",
)
async def revoke_user_session(username: str, session_pk: int, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """Revoke one session (issue #325). Effective on the session's next request.

    Raises:
        HTTPException: 404 for an unknown user, or a ``pk`` that is not a live session of *this*
            user — another user's session reads exactly like one that does not exist.
    """
    target = _require_user_detail(username)["username"]
    if not store.revoke_auth_session_by_pk(target, session_pk):
        raise HTTPException(status_code=404, detail="Session not found")
    emit_audit_event(
        "session.revoked",
        actor=admin_username,
        resource_type="user",
        resource_id=target,
        detail={"source": "admin", "sessions": 1, "session_pk": session_pk, "reason": "admin_revoke"},
    )
    return JSONResponse(content={"revoked": 1})


@users_router.delete(
    USER_SESSIONS,
    summary="Revoke all of a user's sessions",
    description="Revokes every live session of this user. Their access tokens are not affected. Admins only.",
)
async def revoke_user_sessions(username: str, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """Sign a user out everywhere (issue #325). Their account, grants and access tokens are untouched.

    Raises:
        HTTPException: 404 for an unknown user.
    """
    target = _require_user_detail(username)["username"]
    count = store.revoke_all_auth_sessions(target)
    emit_audit_event(
        "session.revoked",
        actor=admin_username,
        resource_type="user",
        resource_id=target,
        detail={"source": "admin", "sessions": count, "reason": "admin_revoke_all"},
    )
    return JSONResponse(content={"revoked": count})


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
            groups=[GroupRecord(**g.to_json()) for g in (user.groups or [])],
        )
    except Exception as e:
        logger.error(f"Error getting user information for {username}: {str(e)}")
        raise HTTPException(status_code=404, detail="User not found")


@users_router.get(
    USER_TOKENS_OF,
    summary="List a user's access tokens",
    description="Lists a user's access tokens, expired ones included. Never returns a token's secret. Admins only.",
)
async def list_user_tokens(username: str, admin_username: str = Depends(check_admin_permission), page: PageQuery = NO_PAGE) -> JSONResponse:
    """Another user's access tokens (issue #189), optionally paged (``limit`` / ``offset`` / ``search``).

    Raises:
        HTTPException: 404 for an unknown user.
    """
    return _list_tokens(username, page)


@users_router.post(
    USER_TOKENS_OF,
    summary="Create an access token for a user",
    description="Issues a named access token for a user or service account. Admins only, from a signed-in session. " "The token is returned once.",
    dependencies=[Depends(require_interactive_login)],
)
async def create_user_token(
    username: str,
    token_request: CreateUserTokenRequest = Body(...),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Issue a named token for another user (issue #189). Audited as ``user.token_create``.

    Raises:
        HTTPException: 403 unless an administrator in a signed-in session, 404 for an unknown user,
            400 for a bad name or expiration, 409 for a duplicate name or at the per-user cap.
    """
    return _issue_token(username, token_request, actor=admin_username)


@users_router.delete(
    USER_TOKEN_OF,
    summary="Delete one of a user's access tokens",
    description="Deletes one access token of a user. It stops working immediately. Admins only.",
)
async def delete_user_token(username: str, token_id: int, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """Delete one of another user's tokens (issue #189). Audited as ``user.token_delete``.

    Raises:
        HTTPException: 404 for an unknown user, or a token id that is not one of *this* user's.
    """
    return _delete_token(username, token_id, actor=admin_username)


@users_router.delete(
    USER_TOKENS_OF,
    summary="Revoke all of a user's access tokens",
    description="Deletes every access token of a user — the response to a leaked token. Their sessions are not affected. Admins only.",
)
async def revoke_user_tokens(username: str, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """Delete every token of a user (issue #189). Audited as ``user.tokens_revoked``.

    Raises:
        HTTPException: 404 for an unknown user.
    """
    target = _require_user(username)
    try:
        count = store.delete_user_tokens(target)
    except MlflowException as e:
        raise _token_http_error(e)
    emit_audit_event(
        "user.tokens_revoked",
        actor=admin_username,
        resource_type="user",
        resource_id=target,
        detail={"tokens": count, "reason": "admin_revoke_all"},
    )
    return JSONResponse(content={"revoked": count})


@users_router.get(
    USER_IDENTITIES,
    summary="List a user's identity bindings",
    description="Lists the (provider, subject) identities bound to a user. Admin only.",
)
async def list_user_identities(username: str, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    """The identities that reach ``username``: each ``{"provider_id", "subject"}``, oldest first.

    Raises:
        HTTPException: 404 for an unknown user.
    """
    if not store.has_user(username):
        raise HTTPException(status_code=404, detail=f"User {username} not found")
    identities = store.user_identity_repo.list_identities_for_username(username)
    return JSONResponse(content=[{"provider_id": provider_id, "subject": subject} for provider_id, subject in identities])


@users_router.delete(
    USER_IDENTITIES,
    summary="Remove an identity binding from a user",
    description="Unbinds one (provider, subject) identity from a user, so a changed subject can be bound "
    "again on the next login (or first bearer use, for a provider with bearer_adopts_unbound_accounts). Admin only.",
)
async def delete_user_identity(
    username: str,
    provider_id: str = Query(..., description="The provider the identity belongs to"),
    subject: str = Query(..., description="The provider's subject (sub) for the principal"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Remove one identity binding, audited. The subject goes in the query: it may contain ``/``.

    Raises:
        HTTPException: 404 when no such binding names the user.
    """
    if not store.user_identity_repo.unlink(provider_id, subject, username):
        raise HTTPException(status_code=404, detail="No such identity is bound to this user")
    emit_audit_event(
        "user.identity_unbound",
        actor=admin_username,
        resource_type="user",
        resource_id=username,
        detail={"provider": provider_id},
    )
    return JSONResponse(content={"deleted": 1})


@users_router.put(
    USER_SERVICE_ACCOUNT_SOURCE,
    summary="Set how a service account signs in",
    description="'internal' (issued access tokens only) or an OIDC provider id, with an optional subject to bind now. "
    "Becoming external revokes the account's access tokens; changing the source unbinds identities that no longer apply. Admin only.",
)
async def set_service_account_source(
    username: str,
    body: ServiceAccountSourceRequest = Body(...),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Re-point a service account.

    Raises:
        HTTPException: 400 for an unknown source or a subject on an internal account; 404 for an
            unknown user; 409 for an account that is not a service account.
    """
    from mlflow_oidc_auth.utils.service_accounts import apply_source

    if not store.has_user(username):
        raise HTTPException(status_code=404, detail=f"User {username} not found")
    try:
        apply_source(username, body.source, body.subject)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MlflowException as e:
        if e.error_code == ErrorCode.Name(INVALID_PARAMETER_VALUE):
            raise HTTPException(status_code=409, detail=f"{username} is not a service account")
        if e.error_code == ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
            raise HTTPException(status_code=409, detail="That subject is already bound to another account")
        raise
    emit_audit_event(
        "user.service_account_source",
        actor=admin_username,
        resource_type="user",
        resource_id=username,
        detail={"source": body.source.strip(), "subject_bound": bool(body.subject)},
    )
    return JSONResponse(content={"username": username, "service_account_source": body.source.strip()})
