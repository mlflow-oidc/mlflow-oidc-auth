"""Quota management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username

from ._prefix import QUOTA_ROUTER_PREFIX, EXPERIMENT_OWNERSHIP_ROUTER_PREFIX

logger = get_logger()

quota_router = APIRouter(
    prefix=QUOTA_ROUTER_PREFIX,
    tags=["quota"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)

ownership_router = APIRouter(
    prefix=EXPERIMENT_OWNERSHIP_ROUTER_PREFIX,
    tags=["quota"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


class SetQuotaRequest(BaseModel):
    quota_bytes: Optional[int] = None
    soft_cap_fraction: Optional[float] = None


class TransferOwnershipRequest(BaseModel):
    new_owner: str


def _quota_to_dict(quota) -> dict:
    return {
        "user_id": quota.user_id,
        "quota_bytes": quota.quota_bytes,
        "used_bytes": quota.used_bytes,
        "soft_cap_fraction": quota.soft_cap_fraction,
        "hard_blocked": quota.hard_blocked,
        "email": quota.email,
        "last_reconciled_at": quota.last_reconciled_at.isoformat() if quota.last_reconciled_at else None,
        "soft_notified_at": quota.soft_notified_at.isoformat() if quota.soft_notified_at else None,
    }


@quota_router.get("/users", summary="List all user quotas")
async def list_user_quotas(admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    try:
        quotas = store.list_all_user_quotas()
        result = []
        for q in quotas:
            user = store.get_user_by_id(q.user_id)
            d = _quota_to_dict(q)
            d["username"] = user.username if user else None
            result.append(d)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error listing quotas: {e}")
        raise HTTPException(status_code=500, detail="Failed to list quotas")


@quota_router.get("/users/{username}", summary="Get quota for a user")
async def get_user_quota(
    username: str,
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    if not is_admin and current_username != username:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        quota = store.get_user_quota(username)
        if quota is None:
            return JSONResponse(content={"username": username, "quota_bytes": None, "used_bytes": 0, "hard_blocked": False})
        d = _quota_to_dict(quota)
        d["username"] = username
        return JSONResponse(content=d)
    except Exception as e:
        logger.error(f"Error getting quota for {username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quota")


@quota_router.put("/users/{username}", summary="Set quota for a user")
async def set_user_quota(
    username: str,
    quota_request: SetQuotaRequest = Body(...),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    try:
        user = store.get_user_profile(username)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {username} not found")
        store.set_user_quota(username, quota_request.quota_bytes, quota_request.soft_cap_fraction)
        return JSONResponse(content={"message": f"Quota set for {username}"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting quota for {username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to set quota")


@quota_router.delete("/users/{username}", summary="Remove quota for a user (unlimited)")
async def delete_user_quota(
    username: str,
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    try:
        store.delete_user_quota(username)
        return JSONResponse(content={"message": f"Quota removed for {username}"})
    except Exception as e:
        logger.error(f"Error deleting quota for {username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete quota")


@quota_router.post("/reconcile", summary="Trigger manual quota reconciliation")
async def trigger_reconcile(admin_username: str = Depends(check_admin_permission)) -> JSONResponse:
    try:
        from mlflow_oidc_auth.utils.quota import reconcile_all_quotas

        reconcile_all_quotas()
        return JSONResponse(content={"message": "Quota reconciliation triggered"})
    except Exception as e:
        logger.error(f"Error triggering reconciliation: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger reconciliation")


@ownership_router.post("/{experiment_id}/transfer-ownership", summary="Transfer experiment ownership")
async def transfer_experiment_ownership(
    experiment_id: str,
    body: TransferOwnershipRequest = Body(...),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    from mlflow_oidc_auth.permissions import MANAGE, OWNER
    from mlflow_oidc_auth.utils.quota import get_experiment_owner

    try:
        # Check that the requester is the current OWNER or an admin
        current_owner = get_experiment_owner(experiment_id)
        if not is_admin and current_username != current_owner:
            raise HTTPException(status_code=403, detail="Only the experiment owner or an admin can transfer ownership")

        new_owner = body.new_owner
        if current_owner == new_owner:
            return JSONResponse(content={"message": "No change — new owner is already the owner"})

        # Ensure new_owner exists
        new_owner_user = store.get_user_profile(new_owner)
        if new_owner_user is None:
            raise HTTPException(status_code=404, detail=f"User {new_owner} not found")

        # Downgrade current owner's permission to MANAGE
        if current_owner:
            try:
                store.update_experiment_permission(experiment_id, current_owner, MANAGE.name)
            except Exception:
                pass  # May not have an existing permission row if they were deleted

        # Upgrade (or create) new owner's permission to OWNER
        try:
            store.update_experiment_permission(experiment_id, new_owner, OWNER.name)
        except Exception:
            store.create_experiment_permission(experiment_id, new_owner, OWNER.name)

        return JSONResponse(content={"message": f"Ownership of experiment {experiment_id} transferred to {new_owner}"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transferring ownership of experiment {experiment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to transfer ownership")
