"""SCIM 2.0 provisioning (``/scim/v2``) and its token administration API.

Issues: #321 (dedicated endpoint auth), #322 (``/Users`` and discovery), #324 (de-provisioning),
#323 (``/Groups``).

**Authentication.** ``/scim/v2`` is carved out of ``AuthMiddleware`` and every route here —
discovery included, and the catch-all at the bottom — depends on
:func:`~mlflow_oidc_auth.dependencies.require_scim_token`. Nothing under the prefix falls through
to the Flask mount.

**Identity.** A SCIM ``id`` is the local username. ``userName`` is immutable through SCIM, so the
id is stable, which RFC 7643 §3.1 requires; ``externalId`` is client-controlled and changeable,
so it cannot be the id. ``/Users/{id}`` also accepts an ``externalId`` for clients that address
users that way. See ``docs/scim.md``.

**De-provisioning.** ``active: false`` goes through :meth:`SqlAlchemyStore.update_user`, which
revokes every live session in the same transaction; the user's basic-auth token is replaced with
an undisclosed, already-expired secret in that same write. The account row and every permission
grant are kept, so ``active: true`` restores access (after a fresh sign-in, or a newly issued
token). ``DELETE`` is a hard delete through the existing cascade.
"""

import json
import re
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.routing import Match
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    INVALID_PARAMETER_VALUE,
    INVALID_STATE,
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
    ErrorCode,
)
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.dependencies import ScimRateLimiter, check_admin_permission, require_scim_token
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.scim import (
    GROUP_SCHEMA,
    PATCH_OP_SCHEMA,
    RESOURCE_TYPE_SCHEMA,
    SCHEMA_SCHEMA,
    SCIM_CONTENT_TYPE,
    SERVICE_PROVIDER_CONFIG_SCHEMA,
    USER_SCHEMA,
    CreateScimTokenRequest,
    ScimError,
    ScimGroup,
    ScimGroupInput,
    ScimListResponse,
    ScimMeta,
    ScimPatchRequest,
    ScimUser,
    ScimUserInput,
)
from mlflow_oidc_auth.orphans import delete_user_reporting_orphans, report_orphans
from mlflow_oidc_auth.ownership import MANUAL
from mlflow_oidc_auth.repository.group import UnknownMember
from mlflow_oidc_auth.repository.scim_activity import MAX_PAGE_SIZE as MAX_ACTIVITY_PAGE_SIZE, OUTCOMES, outcome_for
from mlflow_oidc_auth.store import store

from ._prefix import SCIM_ADMIN_ROUTER_PREFIX, SCIM_ROUTER_PREFIX, SCIM_TOKENS_ROUTER_PREFIX

logger = get_logger()

SCIM_SOURCE = "scim"
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 100

_UNSET = object()


# ---------------------------------------------------------------------------------------------
# Errors and responses
# ---------------------------------------------------------------------------------------------


class ScimHTTPError(HTTPException):
    """An error to render in the RFC 7644 §3.12 shape."""

    def __init__(self, status_code: int, detail: str, scim_type: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.scim_type = scim_type


def scim_response(content: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    return JSONResponse(content=content, status_code=status_code, media_type=SCIM_CONTENT_TYPE, headers=headers)


def scim_error(status_code: int, detail: str, scim_type: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    body = ScimError(status=str(status_code), scimType=scim_type, detail=detail).to_wire()
    return scim_response(body, status_code=status_code, headers=headers)


def _audit_status(status_code: int) -> str:
    if status_code < 400:
        return "success"
    if status_code in (401, 403, 429):
        return "denied"
    return "error"


_ROUTE_PARAM = re.compile(r"\{([^}:]+)(?::[^}]*)?\}")
#: Anything shaped like a SCIM token that might have found its way into an error message.
_TOKEN_LIKE = re.compile(r"scim_[0-9a-fA-F]{8}_\S+")
_SWEEP_INTERVAL_SECONDS = 3600
#: Unauthenticated rows per minute, per process, across *all* clients. The per-client throttle
#: alone is keyed on the peer address, which an attacker holding many addresses can rotate.
ANONYMOUS_ACTIVITY_PER_MINUTE = 60
anonymous_activity_limiter = ScimRateLimiter()
_sweep_state = {"last": None}
_sweep_lock = threading.Lock()


def _activity_target(request: Request) -> tuple:
    """``(path, resource_id)`` for the activity log: the route template and the SCIM id.

    The template (``/Users/{user_id}``) goes in ``path`` so the column never holds a username;
    the concrete id goes in ``resource_id``, where an administrator expects to find one.
    """
    route = request.scope.get("route")
    template = getattr(route, "path", None) or request.url.path
    if template.startswith(SCIM_ROUTER_PREFIX):
        template = template[len(SCIM_ROUTER_PREFIX) :] or "/"
    params = request.scope.get("path_params") or {}
    resource_id = next((str(value) for value in params.values() if value not in (None, "")), None)
    return _ROUTE_PARAM.sub(lambda match: "{" + match.group(1) + "}", template), resource_id


def _activity_error(status_code: int, detail: Optional[str], scim_type: Optional[str]) -> Optional[str]:
    """The short, SCIM-level reason for a failed request. Never a body, never a token."""
    if status_code < 400:
        return None
    text = f"{scim_type}: {detail}" if scim_type and detail else (detail or scim_type or f"HTTP {status_code}")
    return _TOKEN_LIKE.sub("scim_[redacted]", text)[:500]


def _sweep_due() -> bool:
    import time

    now = time.monotonic()
    with _sweep_lock:
        last = _sweep_state["last"]
        if last is not None and now - last < _SWEEP_INTERVAL_SECONDS:
            return False
        _sweep_state["last"] = now
        return True


def _write_activity(fields: Dict[str, Any]) -> None:
    """Insert the row and, at most hourly per process, sweep what retention has expired."""
    store.record_scim_activity(**fields)
    if _sweep_due():
        days = int(getattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 30) or 0)
        if days > 0:
            store.delete_scim_activity_before(datetime.now(timezone.utc) - timedelta(days=days))


async def _record_activity(request: Request, status_code: int, detail: Optional[str], scim_type: Optional[str], started: float) -> None:
    """One ``scim_activity`` row for this request (#325). Best effort: never raises.

    Unauthenticated requests are recorded on the same throttle as their ``scim.auth_failed``
    audit event — at most one per client per minute — and at most
    ``ANONYMOUS_ACTIVITY_PER_MINUTE`` across all clients, so neither one anonymous client nor
    many can fill the table.
    """
    import asyncio
    import time

    try:
        token = getattr(request.state, "scim_token", None)
        if token is None and not getattr(request.state, "scim_auth_failure_recorded", False):
            return
        if token is None and not anonymous_activity_limiter.allow("anonymous", ANONYMOUS_ACTIVITY_PER_MINUTE):
            return
        path, resource_id = _activity_target(request)
        fields = {
            "token_id": token.id if token is not None else None,
            "token_name": token.name if token is not None else None,
            "method": request.method,
            "path": path,
            "resource_id": resource_id,
            "status": status_code,
            "outcome": outcome_for(status_code, authenticated=token is not None),
            "error": _activity_error(status_code, detail, scim_type),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        await asyncio.get_running_loop().run_in_executor(None, _write_activity, fields)
    except Exception:
        logger.warning("Could not record SCIM activity for %s", request.method, exc_info=True)


class ScimRoute(APIRoute):
    """Renders every error as a SCIM error, and audits and records every request, authenticated or not."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            import time

            started = time.monotonic()
            status_code = 500
            detail: Optional[str] = None
            scim_type: Optional[str] = None
            try:
                response = await original(request)
                status_code = response.status_code
                return response
            except ScimHTTPError as exc:
                status_code, detail, scim_type = exc.status_code, str(exc.detail), exc.scim_type
                return scim_error(exc.status_code, str(exc.detail), exc.scim_type, exc.headers)
            except StarletteHTTPException as exc:
                status_code, detail = exc.status_code, str(exc.detail)
                return scim_error(exc.status_code, str(exc.detail), None, exc.headers)
            except RequestValidationError:
                status_code, detail, scim_type = 400, "The request is not valid SCIM", "invalidSyntax"
                return scim_error(400, "The request is not valid SCIM", "invalidSyntax")
            except Exception:
                logger.exception("Unhandled error serving SCIM %s %s", request.method, request.url.path)
                status_code, detail = 500, "Internal error"
                return scim_error(500, "Internal error")
            finally:
                token = getattr(request.state, "scim_token", None)
                # Unauthenticated requests are recorded, throttled per client, as
                # ``scim.auth_failed`` by ``require_scim_token``: one line per anonymous request
                # would let anyone flood the audit log.
                if token is not None:
                    emit_audit_event(
                        "scim.request",
                        actor=f"scim:{token.name}",
                        resource_type="scim",
                        resource_id=request.url.path,
                        detail={"token": token.name, "token_id": token.id, "method": request.method, "path": request.url.path, "status": status_code},
                        status=_audit_status(status_code),
                    )
                await _record_activity(request, status_code, detail, scim_type, started)

        return handler


scim_router = APIRouter(
    prefix=SCIM_ROUTER_PREFIX,
    tags=["scim"],
    route_class=ScimRoute,
    dependencies=[Depends(require_scim_token)],
)


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _location(request: Request, user_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}{SCIM_ROUTER_PREFIX}/Users/{quote(user_id, safe='@')}"


def _to_scim_user(detail: Dict[str, Any], request: Request) -> Dict[str, Any]:
    user = ScimUser(
        id=detail["username"],
        userName=detail["username"],
        externalId=detail.get("external_id"),
        displayName=detail.get("display_name"),
        name={"formatted": detail["display_name"]} if detail.get("display_name") else None,
        active=bool(detail["active"]),
        meta=ScimMeta(
            resourceType="User",
            created=_iso(detail.get("created_at")),
            lastModified=_iso(detail.get("updated_at")),
            location=_location(request, detail["username"]),
        ),
    )
    return user.to_wire()


def _find_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a SCIM id — the username, and nothing else.

    ``user_id`` is the already percent-decoded path segment (the per-user routes use the
    ``path`` convertor, so a legacy name holding a ``/`` still reaches its row). An
    ``externalId`` is deliberately *not* tried as a fallback: the client controls it, so one
    user's externalId could equal another user's name and redirect a write. Clients that know
    only an externalId look it up with ``filter=externalId eq "..."``. Service accounts are not
    directory users and are invisible here.
    """
    detail = store.get_user_detail(user_id)
    if detail is None or detail["is_service_account"]:
        return None
    return detail


def _require_user(user_id: str) -> Dict[str, Any]:
    detail = _find_user(user_id)
    if detail is None:
        raise ScimHTTPError(404, f"User {user_id} not found")
    return detail


async def _json_body(request: Request) -> Dict[str, Any]:
    raw = await request.body()
    try:
        body = json.loads(raw or b"null")
    except (ValueError, UnicodeDecodeError):
        raise ScimHTTPError(400, "The request body is not valid JSON", "invalidSyntax")
    if not isinstance(body, dict):
        raise ScimHTTPError(400, "The request body must be a JSON object", "invalidSyntax")
    return body


def _coerce_active(value: Any) -> bool:
    """RFC 7643 says boolean; Entra has been known to send the strings "True"/"False"."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ScimHTTPError(400, f"active must be a boolean, got {value!r}", "invalidValue")


def _optional_str(value: Any, attribute: str) -> Optional[str]:
    if value is None or isinstance(value, str):
        return value or None
    raise ScimHTTPError(400, f"{attribute} must be a string", "invalidValue")


def _actor(request: Request) -> str:
    token = getattr(request.state, "scim_token", None)
    return f"scim:{token.name}" if token else "scim"


def _raise_for_store_error(exc: MlflowException, username: str) -> None:
    code = exc.error_code
    if code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
        raise ScimHTTPError(404, f"User {username} not found")
    if code == ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
        raise ScimHTTPError(409, exc.message, "uniqueness")
    if code == ErrorCode.Name(INVALID_STATE):
        # The last-active-admin invariant. Refused, never a 500: the directory should surface it.
        raise ScimHTTPError(400, exc.message)
    if code == ErrorCode.Name(INVALID_PARAMETER_VALUE):
        # The managed_by guard (#319) refusing a write to a row another source owns, or to a
        # hand-made administrator. A conflict with the row's current state, not a malformed request.
        raise ScimHTTPError(409, exc.message, "mutability")
    logger.error("SCIM write for %s failed: %s", username, exc)
    raise ScimHTTPError(500, "Internal error")


def _apply_changes(
    request: Request,
    detail: Dict[str, Any],
    *,
    active: Optional[bool] = None,
    display_name: Optional[str] = None,
    external_id: Any = _UNSET,
) -> Dict[str, Any]:
    """Write a SCIM change set for one user, in one transaction, and record what it did.

    **Ownership.** SCIM claims a row (``managed_by='scim'``) only when provisioning it: here,
    when it binds an ``externalId`` to a hand-made, non-administrator row that had none. Every
    other write on a row SCIM does not own goes through the ownership guard as ``scim`` like any
    other writer — under ``enforce`` it is refused, under ``report`` it is applied and recorded,
    and in neither case does ownership change. A hand-made administrator is never claimed.
    """
    username = detail["username"]
    if external_id is not _UNSET and external_id:
        holder = store.get_username_by_external_id(external_id)
        if holder is not None and holder != username:
            raise ScimHTTPError(409, f"externalId {external_id!r} is already bound to another user", "uniqueness")

    claim = (
        external_id is not _UNSET
        and bool(external_id)
        and not detail.get("external_id")
        and (detail.get("managed_by") or MANUAL) == MANUAL
        and not detail["is_admin"]
    )
    try:
        store.update_user_from_directory(
            username,
            active=active,
            display_name=display_name,
            external_id=None if external_id is _UNSET else external_id,
            set_external_id=external_id is not _UNSET,
            claim=claim,
            # Revoke the user's own credential alongside their sessions, in the same transaction:
            # the basic-auth token is replaced by a secret nobody is told, already expired.
            # Only on the active -> inactive transition: re-asserting active:false on a row that
            # is already inactive changes nothing, so it must not rewrite the hash (every sync)
            # nor count as a credential write the ownership guard would weigh.
            revoke_credential=active is False and bool(detail["active"]),
        )
    except MlflowException as exc:
        _raise_for_store_error(exc, username)

    actor = _actor(request)
    if claim:
        emit_audit_event("user.ownership_claimed", actor=actor, resource_type="user", resource_id=username, detail={"from": MANUAL, "to": SCIM_SOURCE})
    was_active = bool(detail["active"])
    if active is False and was_active:
        emit_audit_event("user.deactivated", actor=actor, resource_type="user", resource_id=username, detail={"source": SCIM_SOURCE})
        # After the commit, and never raising: deprovisioning has already happened.
        report_orphans(username, actor=actor, source=SCIM_SOURCE, store=store)
    elif active is True and not was_active:
        emit_audit_event("user.reactivated", actor=actor, resource_type="user", resource_id=username, detail={"source": SCIM_SOURCE})

    return store.get_user_detail(username)


MAX_USERNAME_LENGTH = 255
_URL_RESERVED = frozenset("/?#%")


def _canonical_username(value: Any, scim_type: str = "invalidValue") -> str:
    """Validate a ``userName`` and return the form it is stored and compared in.

    Stripped, non-empty, at most 255 characters, no control or other non-printing characters,
    and already in its compatibility-normalised, case-folded form. That last rule is how
    look-alikes collide: rather than scanning every row for a user whose NFKC/casefold key
    matches, a name is accepted only when that key *is* its stored (lower-case) form — so two
    accepted names that look alike are the same string, and the unique index sees the clash. A
    fullwidth or ligature spelling of an existing name is refused instead of becoming a second
    account. Stored names stay lower-case, the form every login lookup uses.
    """
    if not isinstance(value, str):
        raise ScimHTTPError(400, "userName must be a string", scim_type)
    name = value.strip()
    if not name:
        raise ScimHTTPError(400, "userName must not be empty", scim_type)
    if len(name) > MAX_USERNAME_LENGTH:
        raise ScimHTTPError(400, f"userName must be at most {MAX_USERNAME_LENGTH} characters", scim_type)
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise ScimHTTPError(400, "userName must not contain control or non-printing characters", scim_type)
    try:
        name.encode("utf-8")
    except UnicodeError:
        raise ScimHTTPError(400, "userName is not valid Unicode", scim_type)
    lowered = name.lower()
    if unicodedata.normalize("NFKC", name).casefold() != lowered:
        raise ScimHTTPError(400, "userName must be in normalised form (NFKC, case-folded)", scim_type)
    return lowered


_FILTER = re.compile(r'^\s*(userName|externalId)\s+eq\s+"((?:[^"\\]|\\.)*)"\s*$', re.IGNORECASE)


def _parse_filter(expression: Optional[str]):
    if expression is None or not expression.strip():
        return None, None
    match = _FILTER.match(expression)
    if not match:
        raise ScimHTTPError(400, 'Only userName eq "..." and externalId eq "..." filters are supported', "invalidFilter")
    attribute = match.group(1).lower()
    try:
        # strict JSON string decoding: a bad escape or a raw control character is refused.
        value = json.loads(f'"{match.group(2)}"')
        # A lone surrogate decodes but cannot be sent to the database.
        value.encode("utf-8")
    except (ValueError, UnicodeError):
        raise ScimHTTPError(400, "The filter value is not a valid string", "invalidFilter")
    if attribute == "username":
        return "username", _canonical_username(value, scim_type="invalidFilter")
    return "external_id", value


# ---------------------------------------------------------------------------------------------
# Discovery (RFC 7644 §4)
# ---------------------------------------------------------------------------------------------

_USER_SCHEMA_DEFINITION = {
    "schemas": [SCHEMA_SCHEMA],
    "id": USER_SCHEMA,
    "name": "User",
    "description": "User account. Only the attributes listed here are stored.",
    "attributes": [
        {
            "name": "userName",
            "type": "string",
            "multiValued": False,
            "required": True,
            "caseExact": False,
            "mutability": "immutable",
            "returned": "default",
            "uniqueness": "server",
            "description": "The local username. Case-insensitive, stored lower-case. Also the SCIM id.",
        },
        {
            "name": "displayName",
            "type": "string",
            "multiValued": False,
            "required": False,
            "caseExact": False,
            "mutability": "readWrite",
            "returned": "default",
            "uniqueness": "none",
        },
        {
            "name": "name",
            "type": "complex",
            "multiValued": False,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
            "uniqueness": "none",
            "description": "Only 'formatted' is stored, as the display name. givenName and familyName are accepted and not stored.",
            "subAttributes": [
                {
                    "name": n,
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "readWrite",
                    "returned": "default",
                    "uniqueness": "none",
                }
                for n in ("formatted", "givenName", "familyName")
            ],
        },
        {
            "name": "active",
            "type": "boolean",
            "multiValued": False,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
            "description": "false revokes every session and the user's token; grants are retained.",
        },
        {
            "name": "externalId",
            "type": "string",
            "multiValued": False,
            "required": False,
            "caseExact": True,
            "mutability": "readWrite",
            "returned": "default",
            "uniqueness": "server",
        },
    ],
    "meta": {"resourceType": "Schema", "location": f"{SCIM_ROUTER_PREFIX}/Schemas/{USER_SCHEMA}"},
}


_GROUP_SCHEMA_DEFINITION = {
    "schemas": [SCHEMA_SCHEMA],
    "id": GROUP_SCHEMA,
    "name": "Group",
    "description": "Group. Only the attributes listed here are stored.",
    "attributes": [
        {
            "name": "displayName",
            "type": "string",
            "multiValued": False,
            "required": True,
            "caseExact": True,
            "mutability": "immutable",
            "returned": "default",
            "uniqueness": "server",
            "description": "The group name, compared with IdP group claims as-is. Also the SCIM id.",
        },
        {
            "name": "externalId",
            "type": "string",
            "multiValued": False,
            "required": False,
            "caseExact": True,
            "mutability": "readWrite",
            "returned": "default",
            "uniqueness": "server",
        },
        {
            "name": "members",
            "type": "complex",
            "multiValued": True,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
            "uniqueness": "none",
            "description": "Users only. Memberships written through SCIM are owned by SCIM; others may be listed and are left to their owner.",
            "subAttributes": [
                {
                    "name": "value",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": True,
                    "mutability": "immutable",
                    "returned": "default",
                    "uniqueness": "none",
                    "description": "The member's user id (username).",
                },
                {
                    "name": "$ref",
                    "type": "reference",
                    "referenceTypes": ["User"],
                    "multiValued": False,
                    "required": False,
                    "caseExact": True,
                    "mutability": "immutable",
                    "returned": "default",
                    "uniqueness": "none",
                },
                {
                    "name": "type",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "canonicalValues": ["User"],
                    "mutability": "immutable",
                    "returned": "default",
                    "uniqueness": "none",
                },
            ],
        },
    ],
    "meta": {"resourceType": "Schema", "location": f"{SCIM_ROUTER_PREFIX}/Schemas/{GROUP_SCHEMA}"},
}


def _user_resource_type(request: Request) -> Dict[str, Any]:
    return {
        "schemas": [RESOURCE_TYPE_SCHEMA],
        "id": "User",
        "name": "User",
        "endpoint": "/Users",
        "description": "User account",
        "schema": USER_SCHEMA,
        "meta": {"resourceType": "ResourceType", "location": f"{str(request.base_url).rstrip('/')}{SCIM_ROUTER_PREFIX}/ResourceTypes/User"},
    }


@scim_router.get("/ServiceProviderConfig", summary="SCIM service provider configuration")
async def scim_service_provider_config(request: Request) -> JSONResponse:
    return scim_response(
        {
            "schemas": [SERVICE_PROVIDER_CONFIG_SCHEMA],
            "documentationUri": "https://github.com/mlflow-oidc/mlflow-oidc-auth/blob/main/docs/scim.md",
            "patch": {"supported": True},
            "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
            "filter": {"supported": True, "maxResults": MAX_PAGE_SIZE},
            "changePassword": {"supported": False},
            "sort": {"supported": False},
            "etag": {"supported": False},
            "authenticationSchemes": [
                {
                    "type": "oauthbearertoken",
                    "name": "SCIM bearer token",
                    "description": "A token issued by an administrator at /api/2.0/mlflow/scim/tokens. User credentials are not accepted.",
                    "primary": True,
                }
            ],
            "meta": {"resourceType": "ServiceProviderConfig", "location": f"{str(request.base_url).rstrip('/')}{SCIM_ROUTER_PREFIX}/ServiceProviderConfig"},
        }
    )


def _group_resource_type(request: Request) -> Dict[str, Any]:
    return {
        "schemas": [RESOURCE_TYPE_SCHEMA],
        "id": "Group",
        "name": "Group",
        "endpoint": "/Groups",
        "description": "Group",
        "schema": GROUP_SCHEMA,
        "meta": {"resourceType": "ResourceType", "location": f"{str(request.base_url).rstrip('/')}{SCIM_ROUTER_PREFIX}/ResourceTypes/Group"},
    }


_RESOURCE_TYPES = {"User": _user_resource_type, "Group": _group_resource_type}


@scim_router.get("/ResourceTypes", summary="SCIM resource types")
async def scim_resource_types(request: Request) -> JSONResponse:
    resources = [build(request) for build in _RESOURCE_TYPES.values()]
    return scim_response(ScimListResponse(totalResults=len(resources), startIndex=1, itemsPerPage=len(resources), Resources=resources).to_wire())


@scim_router.get("/ResourceTypes/{resource_type}", summary="One SCIM resource type")
async def scim_resource_type(resource_type: str, request: Request) -> JSONResponse:
    build = _RESOURCE_TYPES.get(resource_type)
    if build is None:
        raise ScimHTTPError(404, f"Resource type {resource_type} not found")
    return scim_response(build(request))


_SCHEMAS = {USER_SCHEMA: _USER_SCHEMA_DEFINITION, GROUP_SCHEMA: _GROUP_SCHEMA_DEFINITION}


@scim_router.get("/Schemas", summary="SCIM schemas")
async def scim_schemas() -> JSONResponse:
    resources = list(_SCHEMAS.values())
    return scim_response(ScimListResponse(totalResults=len(resources), startIndex=1, itemsPerPage=len(resources), Resources=resources).to_wire())


@scim_router.get("/Schemas/{schema_id:path}", summary="One SCIM schema")
async def scim_schema(schema_id: str) -> JSONResponse:
    schema = _SCHEMAS.get(schema_id)
    if schema is None:
        raise ScimHTTPError(404, f"Schema {schema_id} not found")
    return scim_response(schema)


# ---------------------------------------------------------------------------------------------
# /Users (RFC 7644 §3)
# ---------------------------------------------------------------------------------------------


@scim_router.get("/Users", summary="List or filter users")
async def scim_list_users(request: Request, filter: Optional[str] = None, startIndex: int = 1, count: int = DEFAULT_PAGE_SIZE) -> JSONResponse:
    field, value = _parse_filter(filter)
    start_index = max(1, startIndex)
    page_size = min(max(0, count), MAX_PAGE_SIZE)
    kwargs: Dict[str, Any] = {"is_service_account": False, "offset": start_index - 1, "limit": page_size}
    if field:
        kwargs[field] = value
    total, rows = store.list_user_details(**kwargs)
    resources = [_to_scim_user(row, request) for row in rows]
    return scim_response(ScimListResponse(totalResults=total, startIndex=start_index, itemsPerPage=len(resources), Resources=resources).to_wire())


@scim_router.get("/Users/{user_id:path}", name="scim_get_user", summary="Get a user")
async def scim_get_user(user_id: str, request: Request) -> JSONResponse:
    return scim_response(_to_scim_user(_require_user(user_id), request))


@scim_router.post("/Users", status_code=201, summary="Provision a user")
async def scim_create_user(request: Request) -> JSONResponse:
    body = await _json_body(request)
    try:
        payload = ScimUserInput.model_validate(body)
    except ValidationError:
        raise ScimHTTPError(400, "userName is required", "invalidValue")
    user_name = _canonical_username(payload.user_name)
    if any(ch in _URL_RESERVED for ch in user_name):
        # The userName is the SCIM id and becomes a /Users/{id} path segment; these would split
        # or re-encode it. Checked on creation only, so a legacy row holding one can still be
        # found by filter, updated and de-provisioned.
        raise ScimHTTPError(400, "userName must not contain '/', '?', '#' or '%'", "invalidValue")
    active = True if payload.active is None else _coerce_active(payload.active)
    external_id = _optional_str(payload.external_id, "externalId")

    if store.get_user_detail(user_name) is not None:
        raise ScimHTTPError(409, f"User {user_name} already exists", "uniqueness")
    if external_id and store.get_username_by_external_id(external_id) is not None:
        raise ScimHTTPError(409, f"externalId {external_id!r} is already bound to another user", "uniqueness")

    try:
        detail = store.create_scim_user(user_name, payload.resolved_display_name(), external_id, active=active)
    except MlflowException as exc:
        if exc.error_code == ErrorCode.Name(INVALID_PARAMETER_VALUE):
            raise ScimHTTPError(400, exc.message, "invalidValue")
        _raise_for_store_error(exc, user_name)

    emit_audit_event(
        "user.create",
        actor=_actor(request),
        resource_type="user",
        resource_id=detail["username"],
        detail={"source": SCIM_SOURCE, "active": active, "external_id": external_id},
    )
    resource = _to_scim_user(detail, request)
    return scim_response(resource, status_code=201, headers={"Location": resource["meta"]["location"]})


@scim_router.put("/Users/{user_id:path}", summary="Replace a user")
async def scim_replace_user(user_id: str, request: Request) -> JSONResponse:
    detail = _require_user(user_id)
    body = await _json_body(request)
    try:
        payload = ScimUserInput.model_validate(body)
    except ValidationError:
        raise ScimHTTPError(400, "userName is required", "invalidValue")
    if _canonical_username(payload.user_name) != detail["username"]:
        raise ScimHTTPError(400, "userName is immutable", "mutability")
    updated = _apply_changes(
        request,
        detail,
        # An omitted ``active`` keeps the current state. Defaulting it to true would let any PUT
        # that simply leaves the attribute out reactivate a deprovisioned user.
        active=None if payload.active is None else _coerce_active(payload.active),
        display_name=payload.resolved_display_name(),
        # PUT replaces: an absent externalId clears it.
        external_id=_optional_str(payload.external_id, "externalId"),
    )
    return scim_response(_to_scim_user(updated, request))


_URN_PREFIX = USER_SCHEMA + ":"


def _patch_changes(detail: Dict[str, Any], request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Translate RFC 7644 §3.5.2 operations into a change set, refusing anything unsupported."""
    try:
        patch = ScimPatchRequest.model_validate(request_body)
    except ValidationError:
        raise ScimHTTPError(400, "A PATCH body needs a non-empty Operations list", "invalidSyntax")
    if PATCH_OP_SCHEMA not in patch.schemas:
        raise ScimHTTPError(400, f"schemas must include {PATCH_OP_SCHEMA}", "invalidSyntax")

    changes: Dict[str, Any] = {}

    def assign(path: str, value: Any) -> None:
        key = path[len(_URN_PREFIX) :] if path.startswith(_URN_PREFIX) else path
        lowered = key.lower()
        if lowered == "active":
            changes["active"] = _coerce_active(value)
        elif lowered == "username":
            if _canonical_username(value) != detail["username"]:
                raise ScimHTTPError(400, "userName is immutable", "mutability")
        elif lowered == "displayname":
            changes["display_name"] = _optional_str(value, "displayName")
        elif lowered == "externalid":
            changes["external_id"] = _optional_str(value, "externalId")
        elif lowered == "name.formatted":
            if "display_name" not in changes:
                changes["display_name"] = _optional_str(value, "name.formatted")
        elif lowered in ("name.givenname", "name.familyname"):
            _optional_str(value, key)  # accepted, validated, not stored
        elif lowered == "name":
            if not isinstance(value, dict):
                raise ScimHTTPError(400, "name must be an object", "invalidValue")
            for sub, sub_value in value.items():
                assign(f"name.{sub}", sub_value)
        else:
            raise ScimHTTPError(400, f"Unsupported attribute path {path!r}", "invalidPath")

    for operation in patch.operations:
        op = (operation.op or "").strip().lower()
        if op not in ("add", "replace"):
            raise ScimHTTPError(400, f"Unsupported PATCH op {operation.op!r}; only add and replace are supported", "invalidSyntax")
        if operation.path:
            assign(operation.path.strip(), operation.value)
        else:
            if not isinstance(operation.value, dict):
                raise ScimHTTPError(400, "An operation without a path needs an object value", "invalidValue")
            for attribute, value in operation.value.items():
                if attribute == "schemas":
                    continue
                assign(attribute, value)
    return changes


@scim_router.patch("/Users/{user_id:path}", summary="Modify a user")
async def scim_patch_user(user_id: str, request: Request) -> JSONResponse:
    detail = _require_user(user_id)
    changes = _patch_changes(detail, await _json_body(request))
    updated = _apply_changes(
        request,
        detail,
        active=changes.get("active"),
        display_name=changes.get("display_name"),
        external_id=changes.get("external_id", _UNSET),
    )
    return scim_response(_to_scim_user(updated, request))


@scim_router.delete("/Users/{user_id:path}", status_code=204, summary="Delete a user")
async def scim_delete_user(user_id: str, request: Request) -> Response:
    detail = _require_user(user_id)
    username = detail["username"]

    actor = _actor(request)
    # The ownership guard (#360) runs inside the delete as ``scim``: under enforce a row SCIM may
    # not write — another source's, a hand-made administrator — is refused (409 mutability) and
    # nothing, orphan hand-over included, is written. Orphan detection and the
    # ORPHAN_FALLBACK_PRINCIPAL hand-over run inside the delete's own transaction, so a refused
    # delete (the last active administrator) rolls them back too.
    try:
        delete_user_reporting_orphans(username, actor=actor, source=SCIM_SOURCE, store=store, written_by=SCIM_SOURCE)
    except MlflowException as exc:
        _raise_for_store_error(exc, username)
    emit_audit_event("user.delete", actor=actor, resource_type="user", resource_id=username, detail={"source": SCIM_SOURCE})
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# /Groups (RFC 7644 §3, #323)
# ---------------------------------------------------------------------------------------------
#
# **Identity.** A group's SCIM ``id`` is its name, as a user's is their username. ``displayName`` is
# therefore immutable through SCIM, like ``userName``: renaming would change the id. ``externalId``
# is stored on the group (``groups.external_id``, unique when present) and is found with
# ``filter=externalId eq "..."`` only, never as an id, for the same reason as for users.
#
# **Group ownership.** Groups record who created them (``groups.managed_by``). Every write to a
# group checks its owner first: under ``enforce`` SCIM writes only ``scim``-owned groups, so a SCIM
# token cannot put users into, or delete, a login-derived, Kubernetes namespace or hand-made group.
#
# **Membership ownership (#360).** Every membership SCIM writes is ``managed_by='scim'``, per row,
# so it coexists with memberships an administrator or a login's claims granted. A ``PUT`` or a
# ``replace`` of ``members`` is a sync and never removes another source's row; a ``remove`` names
# what it removes and, under ``enforce``, is refused outright (409 ``mutability``) with nothing
# applied. See ``repository/group.py``.
#
# **Service accounts** are invisible here as they are on ``/Users``: never listed as members, never
# addable, and never removed by a ``PUT``.


def _group_location(request: Request, group_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}{SCIM_ROUTER_PREFIX}/Groups/{quote(group_id, safe='@')}"


def _to_scim_group(detail: Dict[str, Any], request: Request) -> Dict[str, Any]:
    members = None
    if "members" in detail:
        members = [
            {
                # No ``display``: it is read-only and server-computed, and clients (and scim2-tester)
                # compare members as they wrote them. The user resource carries the display name.
                "value": member["username"],
                "type": "User",
                "$ref": _location(request, member["username"]),
            }
            for member in detail["members"]
        ]
    group = ScimGroup(
        id=detail["group_name"],
        displayName=detail["group_name"],
        externalId=detail.get("external_id"),
        members=members,
        meta=ScimMeta(
            resourceType="Group",
            created=_iso(detail.get("created_at")),
            lastModified=_iso(detail.get("updated_at")),
            location=_group_location(request, detail["group_name"]),
        ),
    )
    return group.to_wire()


def _require_group(group_id: str, *, with_members: bool = True) -> Dict[str, Any]:
    """Resolve a SCIM group id — the group name, and nothing else (never an externalId)."""
    detail = store.get_group_detail(group_id, with_members=with_members)
    if detail is None:
        raise ScimHTTPError(404, f"Group {group_id} not found")
    return detail


MAX_GROUP_NAME_LENGTH = 255


def _group_name(value: Any, scim_type: str = "invalidValue") -> str:
    """Validate a ``displayName`` for a new group.

    Group names are case-sensitive — they are compared with IdP claims as they are — so, unlike a
    ``userName``, they are not folded. Stripped, non-empty, at most 255 characters, no control or
    non-printing characters, and none of ``/ ? # %``: the name becomes a ``/Groups/{id}`` segment.
    """
    if not isinstance(value, str):
        raise ScimHTTPError(400, "displayName must be a string", scim_type)
    name = value.strip()
    if not name:
        raise ScimHTTPError(400, "displayName must not be empty", scim_type)
    if len(name) > MAX_GROUP_NAME_LENGTH:
        raise ScimHTTPError(400, f"displayName must be at most {MAX_GROUP_NAME_LENGTH} characters", scim_type)
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise ScimHTTPError(400, "displayName must not contain control or non-printing characters", scim_type)
    try:
        name.encode("utf-8")
    except UnicodeError:
        raise ScimHTTPError(400, "displayName is not valid Unicode", scim_type)
    return name


def _member_ids(value: Any) -> list:
    """The usernames a ``members`` value names.

    Each entry is ``{"value": "<user id>"}``, optionally with ``display`` (ignored), ``$ref`` and ``type``.
    ``value`` is authoritative; ``display`` and ``$ref`` are informational. Only users can be
    members: a ``type`` of ``Group`` (a nested group) is refused rather than resolved as a user of
    the same name.
    """
    if value is None:
        return []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ScimHTTPError(400, "members must be a list", "invalidValue")
    ids = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ScimHTTPError(400, "each member must be an object with a value", "invalidValue")
        member_type = entry.get("type")
        if member_type is not None and (not isinstance(member_type, str) or member_type.strip().lower() != "user"):
            raise ScimHTTPError(400, "only users can be group members; nested groups are not supported", "invalidValue")
        member_id = entry.get("value")
        if not isinstance(member_id, str) or not member_id.strip():
            raise ScimHTTPError(400, "each member needs a string value", "invalidValue")
        ids.append(member_id.strip())
    return ids


_GROUP_FILTER = re.compile(r'^\s*(displayName|externalId)\s+eq\s+"((?:[^"\\]|\\.)*)"\s*$', re.IGNORECASE)
_MEMBER_PATH_FILTER = re.compile(r'^members\s*\[\s*value\s+eq\s+"((?:[^"\\]|\\.)*)"\s*\]$', re.IGNORECASE)
_GROUP_URN_PREFIX = GROUP_SCHEMA + ":"


def _decode_filter_value(raw: str) -> str:
    try:
        value = json.loads(f'"{raw}"')
        value.encode("utf-8")
    except (ValueError, UnicodeError):
        raise ScimHTTPError(400, "The filter value is not a valid string", "invalidFilter")
    return value


def _parse_group_filter(expression: Optional[str]):
    if expression is None or not expression.strip():
        return None, None
    match = _GROUP_FILTER.match(expression)
    if not match:
        raise ScimHTTPError(400, 'Only displayName eq "..." and externalId eq "..." filters are supported', "invalidFilter")
    value = _decode_filter_value(match.group(2))
    return ("group_name" if match.group(1).lower() == "displayname" else "external_id"), value


def _excludes_members(excluded_attributes: Optional[str]) -> bool:
    if not excluded_attributes:
        return False
    names = {part.strip().lower() for part in excluded_attributes.split(",")}
    return bool(names & {"members", _GROUP_URN_PREFIX.lower() + "members"})


def _raise_for_group_store_error(exc: MlflowException, group_id: str) -> None:
    if isinstance(exc, UnknownMember):
        raise ScimHTTPError(400, f"member {exc.username} is not a known user", "invalidValue")
    code = exc.error_code
    if code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
        raise ScimHTTPError(404, f"Group {group_id} not found")
    if code == ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
        raise ScimHTTPError(409, exc.message, "uniqueness")
    if code == ErrorCode.Name(INVALID_PARAMETER_VALUE):
        # The managed_by guard (#360) refusing a targeted membership removal or a group delete.
        raise ScimHTTPError(409, exc.message, "mutability")
    logger.error("SCIM write for group %s failed: %s", group_id, exc)
    raise ScimHTTPError(500, "Internal error")


def _audit_membership_change(request: Request, group_name: str, outcome) -> None:
    """One ``group.members_changed`` event per write that changed membership, after the commit."""
    if outcome is None or not outcome.changed:
        return
    emit_audit_event(
        "group.members_changed",
        actor=_actor(request),
        resource_type="group",
        resource_id=group_name,
        detail={
            "source": SCIM_SOURCE,
            "added": [username for username, _ in outcome.added],
            "removed": [username for username, _ in outcome.removed],
            "kept": [c.username for c in outcome.refused],
        },
    )


def _apply_group_changes(request: Request, detail: Dict[str, Any], operations, external_id: Any = _UNSET) -> Dict[str, Any]:
    group_name = detail["group_name"]
    kwargs: Dict[str, Any] = {"written_by": SCIM_SOURCE, "actor": _actor(request)}
    if external_id is not _UNSET:
        kwargs["external_id"] = external_id
        if external_id:
            holder = store.list_group_details_page(external_id=external_id, limit=1, with_members=False)[1]
            if holder and holder[0]["group_name"] != group_name:
                raise ScimHTTPError(409, f"externalId {external_id!r} is already bound to another group", "uniqueness")
    try:
        outcome, updated = store.apply_group_changes(group_name, operations, **kwargs)
    except MlflowException as exc:
        _raise_for_group_store_error(exc, group_name)
    _audit_membership_change(request, group_name, outcome)
    if external_id is not _UNSET and (external_id or None) != detail.get("external_id"):
        emit_audit_event(
            "group.external_id_set",
            actor=_actor(request),
            resource_type="group",
            resource_id=group_name,
            detail={"source": SCIM_SOURCE, "from": detail.get("external_id"), "to": external_id or None},
        )
    return updated


@scim_router.get("/Groups", summary="List or filter groups")
async def scim_list_groups(
    request: Request,
    filter: Optional[str] = None,
    startIndex: int = 1,
    count: int = DEFAULT_PAGE_SIZE,
    excludedAttributes: Optional[str] = None,
) -> JSONResponse:
    field, value = _parse_group_filter(filter)
    start_index = max(1, startIndex)
    page_size = min(max(0, count), MAX_PAGE_SIZE)
    kwargs: Dict[str, Any] = {"offset": start_index - 1, "limit": page_size, "with_members": not _excludes_members(excludedAttributes)}
    if field:
        kwargs[field] = value
    total, rows = store.list_group_details_page(**kwargs)
    resources = [_to_scim_group(row, request) for row in rows]
    return scim_response(ScimListResponse(totalResults=total, startIndex=start_index, itemsPerPage=len(resources), Resources=resources).to_wire())


@scim_router.get("/Groups/{group_id:path}", summary="Get a group")
async def scim_get_group(group_id: str, request: Request, excludedAttributes: Optional[str] = None) -> JSONResponse:
    return scim_response(_to_scim_group(_require_group(group_id, with_members=not _excludes_members(excludedAttributes)), request))


@scim_router.post("/Groups", status_code=201, summary="Provision a group")
async def scim_create_group(request: Request) -> JSONResponse:
    body = await _json_body(request)
    try:
        payload = ScimGroupInput.model_validate(body)
    except ValidationError:
        raise ScimHTTPError(400, "displayName is required", "invalidValue")
    name = _group_name(payload.display_name)
    if any(ch in _URL_RESERVED for ch in name):
        raise ScimHTTPError(400, "displayName must not contain '/', '?', '#' or '%'", "invalidValue")
    external_id = _optional_str(payload.external_id, "externalId")
    members = _member_ids(payload.members)

    if store.get_group_detail(name, with_members=False) is not None:
        raise ScimHTTPError(409, f"Group {name} already exists", "uniqueness")
    try:
        detail = store.create_directory_group(name, external_id, members, written_by=SCIM_SOURCE)
    except MlflowException as exc:
        _raise_for_group_store_error(exc, name)

    emit_audit_event(
        "group.create",
        actor=_actor(request),
        resource_type="group",
        resource_id=name,
        detail={"source": SCIM_SOURCE, "external_id": external_id, "members": [m["username"] for m in detail["members"]]},
    )
    resource = _to_scim_group(detail, request)
    return scim_response(resource, status_code=201, headers={"Location": resource["meta"]["location"]})


@scim_router.put("/Groups/{group_id:path}", summary="Replace a group")
async def scim_replace_group(group_id: str, request: Request) -> JSONResponse:
    """Okta's shape: the whole group, ``members`` included.

    ``displayName`` must be unchanged (it is the id). ``externalId`` is replaced, and an absent one
    is cleared. ``members`` replaces the membership as a sync: SCIM's own and unowned memberships
    not in the list are removed, another source's are left in place under ``enforce``. An omitted
    ``members`` leaves membership alone, so a PUT that only carries attributes never empties a group.
    """
    detail = _require_group(group_id, with_members=False)
    body = await _json_body(request)
    try:
        payload = ScimGroupInput.model_validate(body)
    except ValidationError:
        raise ScimHTTPError(400, "displayName is required", "invalidValue")
    if _group_name(payload.display_name) != detail["group_name"]:
        raise ScimHTTPError(400, "displayName is immutable", "mutability")
    operations = [] if payload.members is None else [("replace", _member_ids(payload.members))]
    updated = _apply_group_changes(request, detail, operations, external_id=_optional_str(payload.external_id, "externalId"))
    return scim_response(_to_scim_group(updated, request))


def _group_patch_operations(detail: Dict[str, Any], request_body: Dict[str, Any]):
    """Translate RFC 7644 §3.5.2 operations on a group into ``(membership operations, externalId)``.

    Supported, with ``op`` case-insensitive and paths optionally URN-qualified:

    * ``add`` ``members`` with a list — Entra and Okta both.
    * ``remove`` ``members[value eq "<id>"]`` — Entra's filtered path.
    * ``remove`` ``members`` with a list of values — Entra's other remove shape; without a value,
      every member.
    * ``replace`` ``members`` with a list — a full replacement.
    * ``add`` / ``replace`` / ``remove`` ``externalId``.
    * ``add`` / ``replace`` ``displayName`` (unchanged only), and a path-less ``add`` / ``replace``
      whose object holds any of the above.

    Anything else is refused with 400 and nothing is applied.
    """
    try:
        patch = ScimPatchRequest.model_validate(request_body)
    except ValidationError:
        raise ScimHTTPError(400, "A PATCH body needs a non-empty Operations list", "invalidSyntax")
    if PATCH_OP_SCHEMA not in patch.schemas:
        raise ScimHTTPError(400, f"schemas must include {PATCH_OP_SCHEMA}", "invalidSyntax")

    operations = []
    changes: Dict[str, Any] = {}

    def assign(op: str, path: str, value: Any) -> None:
        key = path[len(_GROUP_URN_PREFIX) :] if path.startswith(_GROUP_URN_PREFIX) else path
        lowered = key.lower()
        filtered = _MEMBER_PATH_FILTER.match(key.strip())
        if filtered:
            if op != "remove":
                raise ScimHTTPError(400, f"A filtered members path is supported with remove only, not {op}", "invalidPath")
            operations.append(("remove", [_decode_filter_value(filtered.group(1))]))
        elif lowered.startswith("members[") or lowered.startswith("members."):
            raise ScimHTTPError(400, f'Unsupported members path {path!r}; only members[value eq "..."] is supported', "invalidPath")
        elif lowered == "members":
            if op == "add":
                operations.append(("add", _member_ids(value)))
            elif op == "replace":
                operations.append(("replace", _member_ids(value)))
            else:
                operations.append(("remove", None if value is None else _member_ids(value)))
        elif lowered == "externalid":
            changes["external_id"] = None if op == "remove" else _optional_str(value, "externalId")
        elif lowered == "displayname":
            if op == "remove" or _group_name(value) != detail["group_name"]:
                raise ScimHTTPError(400, "displayName is immutable", "mutability")
        elif lowered == "id" and op != "remove" and value == detail["group_name"]:
            pass  # re-asserting the id is harmless
        else:
            raise ScimHTTPError(400, f"Unsupported attribute path {path!r}", "invalidPath")

    for operation in patch.operations:
        op = (operation.op or "").strip().lower()
        if op not in ("add", "replace", "remove"):
            raise ScimHTTPError(400, f"Unsupported PATCH op {operation.op!r}", "invalidSyntax")
        if operation.path:
            assign(op, operation.path.strip(), operation.value)
        else:
            if op == "remove":
                raise ScimHTTPError(400, "A remove operation needs a path", "noTarget")
            if not isinstance(operation.value, dict):
                raise ScimHTTPError(400, "An operation without a path needs an object value", "invalidValue")
            for attribute, value in operation.value.items():
                if attribute == "schemas":
                    continue
                assign(op, attribute, value)
    return operations, changes.get("external_id", _UNSET)


@scim_router.patch("/Groups/{group_id:path}", summary="Modify a group")
async def scim_patch_group(group_id: str, request: Request) -> JSONResponse:
    detail = _require_group(group_id, with_members=False)
    operations, external_id = _group_patch_operations(detail, await _json_body(request))
    updated = _apply_group_changes(request, detail, operations, external_id=external_id)
    return scim_response(_to_scim_group(updated, request))


@scim_router.delete("/Groups/{group_id:path}", status_code=204, summary="Delete a group")
async def scim_delete_group(group_id: str, request: Request) -> Response:
    """Delete the group, its memberships and every permission granted to it.

    Refused (409 ``mutability``) under ``enforce`` when the group holds any membership SCIM does not
    own — hand-made (``manual``) ones included: deleting the group takes it away from those members
    too. Under ``report`` it proceeds and each such membership is recorded. Never refused for
    orphan reasons.
    """
    detail = _require_group(group_id, with_members=False)
    name = detail["group_name"]
    try:
        removed, grants = store.delete_directory_group(name, written_by=SCIM_SOURCE, actor=_actor(request))
    except MlflowException as exc:
        _raise_for_group_store_error(exc, name)
    emit_audit_event(
        "group.delete",
        actor=_actor(request),
        resource_type="group",
        resource_id=name,
        detail={"source": SCIM_SOURCE, "members_removed": [username for username, _ in removed], "grants_removed": grants},
    )
    return Response(status_code=204)


class _AnyMethodScimRoute(ScimRoute):
    """A route that matches *every* HTTP method, not only the ones it lists.

    Starlette reports a path match with a method the route does not declare as a *partial* match
    and keeps looking; the Flask app mounted at ``/`` then matches in full and wins. For the SCIM
    catch-all that would hand ``TRACE``, ``PROPFIND`` or any invented verb under ``/scim/v2`` to a
    WSGI app that ``AuthMiddleware`` never authenticated. So the catch-all claims every method,
    and every one of them still goes through ``require_scim_token``.
    """

    def matches(self, scope):
        match, child_scope = super().matches(scope)
        if match == Match.PARTIAL:
            return Match.FULL, child_scope
        return match, child_scope

    async def handle(self, scope, receive, send) -> None:
        # Route.handle answers 405 for an undeclared method; skip that and serve.
        await self.app(scope, receive, send)


async def scim_not_found(unsupported: str) -> JSONResponse:
    """Everything else under the prefix — ``/Bulk``, ``/Me``, ``/.search`` — is a SCIM 404.

    Also what guarantees nothing under ``/scim/v2`` reaches the Flask mount, which would see a
    request that ``AuthMiddleware`` never authenticated.
    """
    raise ScimHTTPError(404, f"{SCIM_ROUTER_PREFIX}/{unsupported} is not supported")


scim_router.add_api_route(
    "/{unsupported:path}",
    scim_not_found,
    methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE", "TRACE", "CONNECT"],
    include_in_schema=False,
    route_class_override=_AnyMethodScimRoute,
)


# ---------------------------------------------------------------------------------------------
# Token administration (admin only)
# ---------------------------------------------------------------------------------------------

scim_tokens_router = APIRouter(
    prefix=SCIM_TOKENS_ROUTER_PREFIX,
    tags=["scim"],
    responses={403: {"description": "Forbidden - Administrator privileges required"}},
)

_NO_STORE = {"Cache-Control": "no-store"}


def _parse_expiry(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=400, detail="expires_at must be an ISO 8601 timestamp")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _token_http_error(exc: MlflowException) -> HTTPException:
    code = exc.error_code
    if code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
        return HTTPException(status_code=404, detail=exc.message)
    if code == ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
        return HTTPException(status_code=409, detail=exc.message)
    if code in (ErrorCode.Name(INVALID_PARAMETER_VALUE), ErrorCode.Name(INVALID_STATE)):
        return HTTPException(status_code=400, detail=exc.message)
    logger.error("SCIM token operation failed: %s", exc)
    return HTTPException(status_code=500, detail="SCIM token operation failed")


@scim_tokens_router.get("", summary="List SCIM tokens", description="Lists SCIM tokens. Hashes and plaintexts are never returned. Admins only.")
async def list_scim_tokens(admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    return JSONResponse(content=[record.to_json() for record in store.list_scim_tokens()])


@scim_tokens_router.post(
    "",
    status_code=201,
    summary="Issue a SCIM token",
    description="Issues a SCIM token. The plaintext is in this response and is never retrievable again. Admins only.",
)
async def create_scim_token(
    token_request: CreateScimTokenRequest = Body(...),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    expires_at = _parse_expiry(token_request.expires_at)
    try:
        record, plaintext = store.create_scim_token(token_request.name, admin_username, expires_at)
    except MlflowException as exc:
        raise _token_http_error(exc)
    emit_audit_event("scim_token.create", actor=admin_username, resource_type="scim_token", resource_id=str(record.id), detail={"name": record.name})
    return JSONResponse(content={**record.to_json(), "token": plaintext}, status_code=201, headers=_NO_STORE)


@scim_tokens_router.post(
    "/{token_id}/rotate",
    status_code=201,
    summary="Rotate a SCIM token",
    description="Issues a replacement. The old token keeps working for SCIM_TOKEN_ROTATION_OVERLAP_SECONDS. Admins only.",
)
async def rotate_scim_token(token_id: int, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    overlap = int(getattr(config, "SCIM_TOKEN_ROTATION_OVERLAP_SECONDS", 3600))
    try:
        record, plaintext = store.rotate_scim_token(token_id, overlap)
    except MlflowException as exc:
        raise _token_http_error(exc)
    emit_audit_event(
        "scim_token.rotate",
        actor=admin_username,
        resource_type="scim_token",
        resource_id=str(record.id),
        detail={"name": record.name, "replaces": token_id, "overlap_seconds": overlap},
    )
    return JSONResponse(content={**record.to_json(), "token": plaintext, "replaces": token_id}, status_code=201, headers=_NO_STORE)


@scim_tokens_router.delete("/{token_id}", summary="Revoke a SCIM token", description="Revokes a SCIM token immediately. Admins only.")
async def revoke_scim_token(token_id: int, admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    try:
        record = store.revoke_scim_token(token_id)
    except MlflowException as exc:
        raise _token_http_error(exc)
    emit_audit_event("scim_token.revoke", actor=admin_username, resource_type="scim_token", resource_id=str(record.id), detail={"name": record.name})
    return JSONResponse(content=record.to_json())


# ---------------------------------------------------------------------------------------------
# Provisioning status and activity (admin only, #325)
# ---------------------------------------------------------------------------------------------

scim_admin_router = APIRouter(
    prefix=SCIM_ADMIN_ROUTER_PREFIX,
    tags=["scim"],
    responses={403: {"description": "Forbidden - Administrator privileges required"}},
)


@scim_admin_router.get(
    "/activity",
    summary="Recent SCIM requests",
    description="The SCIM activity log, newest first. Page with `before` set to the last row's `id`. Admins only.",
)
async def list_scim_activity(
    limit: int = Query(50, ge=1, le=MAX_ACTIVITY_PAGE_SIZE),
    before: Optional[int] = Query(None, ge=1),
    outcome: Optional[str] = Query(None),
    token_id: Optional[int] = Query(None),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """Recorded ``/scim/v2`` requests (see ``docs/scim.md``, "Provisioning status").

    Raises:
        HTTPException: 400 for an unknown ``outcome``.
    """
    if outcome is not None and outcome not in OUTCOMES:
        raise HTTPException(status_code=400, detail=f"outcome must be one of {', '.join(OUTCOMES)}")
    entries = store.list_scim_activity(limit=limit, before=before, outcome=outcome, token_id=token_id)
    return JSONResponse(content={"activity": [entry.to_json() for entry in entries], "next_before": entries[-1].id if len(entries) == limit else None})


@scim_admin_router.get(
    "/status",
    summary="SCIM provisioning status",
    description="Whether provisioning is working: last success and last error overall and per token, and 24-hour counts. Admins only.",
)
async def get_scim_status(admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    window = int(getattr(config, "SCIM_ACTIVITY_HEALTHY_WINDOW_SECONDS", 86400) or 86400)
    status = store.scim_provisioning_status(window)
    status["healthy_window_seconds"] = window
    status["retention_days"] = int(getattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 30) or 0)
    return JSONResponse(content=status)
