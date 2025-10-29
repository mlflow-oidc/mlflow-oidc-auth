from fastapi import APIRouter
from ._prefix import HEALTH_CHECK_ROUTER_PREFIX

health_check_router = APIRouter(
    prefix=HEALTH_CHECK_ROUTER_PREFIX,
    tags=["health"],
    responses={404: {"description": "Not found"}},
)


@health_check_router.get("/ready")
async def health_check_ready():
    """Health check endpoint for readiness."""
    return {"status": "ready"}


@health_check_router.get("/live")
async def health_check_live():
    """Health check endpoint for liveness."""
    return {"status": "live"}


@health_check_router.get("/startup")
async def health_check_startup():
    """Health check endpoint for startup."""
    return {"status": "startup"}
