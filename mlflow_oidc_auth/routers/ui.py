"""
UI router for FastAPI application.

This router handles serving the OIDC management UI and static assets.
"""

import os.path
from pathlib import Path

from fastapi import APIRouter, Depends, Request
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
async def serve_spa_config(
    base_path: str = Depends(get_base_path),
    authenticated: bool = Depends(is_authenticated),
):
    return JSONResponse(
        content={
            "basePath": base_path,
            "uiPath": f"{base_path}{UI_ROUTER_PREFIX}",
            "provider": config.OIDC_PROVIDER_DISPLAY_NAME,
            "authenticated": authenticated,
            "gen_ai_gateway_enabled": config.OIDC_GEN_AI_GATEWAY_ENABLED,
            "workspaces_enabled": config.MLFLOW_ENABLE_WORKSPACES,
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

    # Normalize the joined path to collapse any ".." segments, then verify
    # it still lives under the UI directory.  This uses the os.path.normpath +
    # startswith pattern that CodeQL recognises as a path-injection sanitiser
    # (see CWE-22 / py/path-injection).
    safe_root = str(ui_dir_path) + os.sep
    candidate = os.path.normpath(os.path.join(str(ui_dir_path), filename))
    if not candidate.startswith(safe_root):
        return FileResponse(str(index_file))

    if os.path.isfile(candidate):
        return FileResponse(candidate)

    return FileResponse(str(index_file))


@ui_router.get("")
async def redirect_to_ui(request: Request):
    base_path = await get_base_path(request)
    return RedirectResponse(url=f"{base_path}{UI_ROUTER_PREFIX}/", status_code=307)
