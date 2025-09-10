"""
UI router for FastAPI application.

This router handles serving the OIDC management UI and static assets.
"""

import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils import get_base_path, is_authenticated

from ._prefix import UI_ROUTER_PREFIX

# Create placeholder router - to be implemented
ui_router = APIRouter(
    prefix=UI_ROUTER_PREFIX,
    tags=["ui"],
    responses={
        404: {"description": "Resource not found"},
    },
)

ui_directory = os.path.join(os.path.dirname(__file__), "..", "ui")


@ui_router.get("/config.json")
async def serve_spa_config(base_path: str = Depends(get_base_path), authenticated: bool = Depends(is_authenticated)):
    return JSONResponse(
        content={
            "basePath": base_path,
            "uiPath": f"{base_path}{UI_ROUTER_PREFIX}",
            "provider": config.OIDC_PROVIDER_DISPLAY_NAME,
            "authenticated": authenticated,
        }
    )


@ui_router.get("/")
async def serve_spa_root():
    """
    Serve the main SPA index.html for the root UI route.
    """
    index_file = os.path.join(ui_directory, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    else:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="UI not found")


@ui_router.get("/{filename:path}")
async def serve_spa(filename: str):
    """
    Serve static files and SPA routes.

    For static files (CSS, JS, images), serve them directly.
    For SPA routes (including auth with parameters), serve index.html.
    """
    file_path = os.path.join(ui_directory, filename)

    # If it's a real file and exists, serve it
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # For SPA routes (like auth, home, etc.), always return index.html
    # This allows Angular router to handle routes like #/auth?error=...
    index_file = os.path.join(ui_directory, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    else:
        # Fallback if index.html doesn't exist
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="UI not found")


@ui_router.get("")
async def redirect_to_ui(request: Request):
    base_path = await get_base_path(request)
    return RedirectResponse(url=f"{base_path}{UI_ROUTER_PREFIX}/", status_code=307)
