"""
UI router for FastAPI application.

This router handles serving the OIDC management UI and static assets.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils import get_base_path, is_authenticated

from ._prefix import UI_ROUTER_PREFIX

ui_router = APIRouter(
    prefix=UI_ROUTER_PREFIX,
    tags=["ui"],
    responses={
        404: {"description": "Resource not found"},
    },
)


def _get_ui_directory() -> tuple[Path, Path]:
    ui_directory = Path(__file__).parent.parent / "ui"
    ui_dir_path = ui_directory.resolve()
    index_file = ui_dir_path / "index.html"
    if not ui_dir_path.is_dir():
        raise RuntimeError(f"UI directory not found at {ui_dir_path}")
    if not index_file.is_file():
        raise RuntimeError(f"UI index.html not found at {index_file}")
    return ui_dir_path, index_file


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
    _, index_file = _get_ui_directory()
    return FileResponse(str(index_file))


@ui_router.get("/{filename:path}")
async def serve_spa(filename: str):
    """
    Serve static files and SPA routes.

    For static files (CSS, JS, images), serve them directly.
    For SPA routes (including auth with parameters), serve index.html.
    """
    ui_dir_path, index_file = _get_ui_directory()
    requested_path = (ui_dir_path / filename).resolve()

    if requested_path.is_relative_to(ui_dir_path) and requested_path.is_file():
        return FileResponse(str(requested_path))

    return FileResponse(str(index_file))


@ui_router.get("")
async def redirect_to_ui(request: Request):
    base_path = await get_base_path(request)
    return RedirectResponse(url=f"{base_path}{UI_ROUTER_PREFIX}/", status_code=307)
