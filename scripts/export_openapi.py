#!/usr/bin/env python
"""Write the plugin's OpenAPI contract to ``openapi.json`` (#458).

The contract is derived from the code: the routers' Pydantic models are the source of truth, and
the React UI's TypeScript types are generated from the file this writes (``yarn gen:api``).

It builds a bare ``FastAPI()`` holding only this plugin's routers. It deliberately does **not**
import ``mlflow_oidc_auth.app``: that module runs ``create_app()`` at import time, which touches
the database and mounts MLflow's Flask app. Nothing here opens a database or needs a secret.

The workspace routers, which the app adds only when ``MLFLOW_ENABLE_WORKSPACES`` is set, are
always included so the contract covers every endpoint. The ``/ajax-api`` twins are never
included: they are the same endpoints under MLflow's UI prefix.

Usage::

    python scripts/export_openapi.py            # writes ./openapi.json at the repository root
    python scripts/export_openapi.py OUT.json   # writes OUT.json instead

CI regenerates the file and fails on any difference, so commit the result of running this. The
output depends on the installed FastAPI and Pydantic; CI pins them with
``scripts/openapi-constraints.txt`` — generate with the same versions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: ``info`` of the contract. Not the package version: a release must not change the contract.
TITLE = "MLflow OIDC Auth plugin API"
CONTRACT_VERSION = "1"


def build_openapi() -> dict:
    """Return the OpenAPI document of every plugin router, without the ``/ajax-api`` twins."""
    from fastapi import FastAPI

    from mlflow_oidc_auth.routers import get_all_routers
    from mlflow_oidc_auth.routers.workspace_permissions import workspace_permissions_router
    from mlflow_oidc_auth.routers.workspace_regex_permissions import workspace_regex_permissions_router

    app = FastAPI(title=TITLE, version=CONTRACT_VERSION, description="Authentication and permission API of the mlflow-oidc-auth plugin.")
    for router in [*get_all_routers(), workspace_permissions_router, workspace_regex_permissions_router]:
        app.include_router(router)
    document = app.openapi()
    leaked = [path for path in document.get("paths", {}) if path.startswith("/ajax-api")]
    if leaked:
        raise RuntimeError(f"/ajax-api routes must not be in the contract: {leaked}")
    return document


def render(document: dict) -> str:
    """Serialize deterministically: sorted keys, two-space indent, trailing newline."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    output = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "openapi.json"
    output.write_text(render(build_openapi()), encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
