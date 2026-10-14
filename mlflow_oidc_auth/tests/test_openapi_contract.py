"""The OpenAPI contract the React UI's types are generated from (#458).

``scripts/export_openapi.py`` writes ``openapi.json`` from the routers; CI regenerates it and fails
on drift. These tests hold the properties that make that contract trustworthy: every route says
what it returns, the export needs no database and matches the committed file, the ``/ajax-api``
twins stay out, no response documents a credential beyond the one-time token-creation responses,
and the response checker in ``tests/contract.py`` — which validates every body the suite
receives — really rejects a body that strays from its model.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import pytest
from fastapi import FastAPI
from fastapi.datastructures import DefaultPlaceholder
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import BaseModel

from mlflow_oidc_auth.tests.contract import CREDENTIAL_PROPERTIES, ContractViolation, check_body, check_response

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTER = REPO_ROOT / "scripts" / "export_openapi.py"
CONSTRAINTS = REPO_ROOT / "scripts" / "openapi-constraints.txt"

#: The documented exceptions: ``(method, path, property) -> why it is allowed``. Each is a
#: one-time token-creation response — the only moment the plaintext exists — sent with
#: ``Cache-Control: no-store`` and never retrievable again.
ONE_TIME_TOKEN_RESPONSES: Dict[Tuple[str, str, str], str] = {
    ("patch", "/api/2.0/mlflow/users/access-token", "token"): "rotates the caller's default access token; the new plaintext is shown once",
    ("post", "/api/2.0/mlflow/users/current/tokens", "token"): "issues a named access token for the caller; the plaintext is shown once",
    ("post", "/api/2.0/mlflow/users/{username}/tokens", "token"): "an admin issues a named access token for a user; the plaintext is shown once",
    ("post", "/api/2.0/mlflow/scim/tokens", "token"): "issues a SCIM bearer token; the plaintext is shown once",
    ("post", "/api/2.0/mlflow/scim/tokens/{token_id}/rotate", "token"): "rotates a SCIM bearer token; the replacement plaintext is shown once",
}


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def exporter():
    return _load_exporter()


@pytest.fixture(scope="module")
def openapi(exporter) -> Dict[str, Any]:
    return exporter.build_openapi()


def _all_routes() -> Iterator[APIRoute]:
    from mlflow_oidc_auth.routers import get_all_routers
    from mlflow_oidc_auth.routers.workspace_permissions import workspace_permissions_router
    from mlflow_oidc_auth.routers.workspace_regex_permissions import workspace_regex_permissions_router

    for router in [*get_all_routers(), workspace_permissions_router, workspace_regex_permissions_router]:
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield route


def test_every_route_has_a_declared_response():
    """A route with neither a ``response_model`` nor an explicit ``response_class`` documents "anything"."""
    undeclared = [
        f"{sorted(route.methods)} {route.path} ({route.endpoint.__module__}.{route.endpoint.__name__})"
        for route in _all_routes()
        if route.response_model is None and isinstance(route.response_class, DefaultPlaceholder)
    ]
    assert not undeclared, "routes without a declared response:\n" + "\n".join(undeclared)


def test_contract_has_no_ajax_twins(openapi):
    assert openapi["paths"], "the contract lists no paths"
    assert not [path for path in openapi["paths"] if path.startswith("/ajax-api")]


def test_contract_covers_workspace_routers(openapi):
    """Workspace routers are mounted only with MLFLOW_ENABLE_WORKSPACES; the contract has them regardless."""
    assert "/api/3.0/mlflow/permissions/workspaces/{workspace}/users" in openapi["paths"]
    assert "/api/3.0/mlflow/permissions/workspaces/regex/user" in openapi["paths"]


def _pinned_versions_installed() -> Optional[str]:
    """None when the generator's pinned versions are installed, else what differs."""
    differences = []
    for line in CONSTRAINTS.read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==(\S+)$", line.strip())
        if not match:
            continue
        name, pinned = match.groups()
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != pinned:
            differences.append(f"{name} {installed} (pinned {pinned})")
    return ", ".join(differences) or None


def test_committed_contract_is_current(exporter, openapi):
    """``openapi.json`` is what the routers export now: rerun ``scripts/export_openapi.py`` if not.

    The document's exact form depends on FastAPI and Pydantic, so this compares only under the
    versions it is generated with (``scripts/openapi-constraints.txt``). CI's frontend job always
    installs those and runs the same comparison.
    """
    differs = _pinned_versions_installed()
    if differs:
        pytest.skip(f"openapi.json is generated with the pinned versions; installed: {differs}")
    committed = (REPO_ROOT / "openapi.json").read_text(encoding="utf-8")
    assert exporter.render(openapi) == committed, "openapi.json is stale: run `python scripts/export_openapi.py` and commit the result"


def test_export_does_not_touch_db(tmp_path):
    """The exporter must not import the app, open a database or need a secret."""
    db_dir = tmp_path / "no-such-dir"
    db_file = db_dir / "auth.db"
    output = tmp_path / "openapi.json"
    env = {key: value for key, value in os.environ.items() if not key.startswith(("OIDC_", "MLFLOW_", "SECRET_KEY"))}
    env["OIDC_USERS_DB_URI"] = f"sqlite:///{db_file}"
    env["MLFLOW_TRACKING_URI"] = f"sqlite:///{db_dir / 'mlflow.db'}"
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run([sys.executable, str(EXPORTER), str(output)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr[-4000:]
    assert json.loads(output.read_text())["paths"]
    assert not db_file.exists()
    assert not db_dir.exists()
    assert not (tmp_path / "auth.db").exists()
    assert not (tmp_path / "mlflow.db").exists()


# ---------------------------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------------------------


def _property_names(openapi: Dict[str, Any], schema: Any, seen: Set[str]) -> Iterator[str]:
    """Every property name reachable from ``schema``, following each ``$ref`` once."""
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if ref:
            if ref not in seen:
                seen.add(ref)
                yield from _property_names(openapi, openapi["components"]["schemas"][ref.rsplit("/", 1)[-1]], seen)
            return
        yield from schema.get("properties", {})
        for value in schema.values():
            yield from _property_names(openapi, value, seen)
    elif isinstance(schema, list):
        for item in schema:
            yield from _property_names(openapi, item, seen)


def _documented_credentials(openapi: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    found = []
    for path, item in openapi["paths"].items():
        for method, operation in item.items():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            for response in operation["responses"].values():
                for media in response.get("content", {}).values():
                    for name in _property_names(openapi, media.get("schema", {}), set()):
                        if name.lower() in CREDENTIAL_PROPERTIES:
                            found.append((method, path, name.lower()))
    return found


def test_user_response_has_no_password_hash(openapi):
    """No response, on any path, documents a credential — except the one-time token-creation responses."""
    found = _documented_credentials(openapi)
    unexpected = sorted({entry for entry in found if entry not in ONE_TIME_TOKEN_RESPONSES})
    assert not unexpected, "responses document credentials:\n" + "\n".join(f"{m.upper()} {p}: {n}" for m, p, n in unexpected)


def test_one_time_token_allowlist_is_exact(openapi):
    """Every allow-listed response exists and still returns its token: a stale entry is a hole."""
    found = set(_documented_credentials(openapi))
    stale = [entry for entry in ONE_TIME_TOKEN_RESPONSES if entry not in found]
    assert not stale, f"allow-list entries no longer in the contract: {stale}"


def test_credential_scan_sees_nested_and_mixed_case_properties():
    """The scan recurses into nested schemas and ignores case."""
    document = {
        "paths": {"/x": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Outer"}}}}}}}},
        "components": {
            "schemas": {
                "Outer": {"properties": {"items": {"type": "array", "items": {"$ref": "#/components/schemas/Inner"}}}},
                "Inner": {"properties": {"Refresh_Token": {"type": "string"}}},
            }
        },
    }
    assert _documented_credentials(document) == [("get", "/x", "refresh_token")]


# ---------------------------------------------------------------------------------------------
# The response checker the whole suite runs every response through (tests/contract.py)
# ---------------------------------------------------------------------------------------------


class _Inner(BaseModel):
    name: str


class _Outer(BaseModel):
    id: int
    inner: Optional[_Inner] = None
    items: List[_Inner] = []


@pytest.mark.parametrize(
    "body",
    [
        {"id": 1, "inner": {"name": "a"}, "items": [{"name": "b"}]},
        {"id": 1, "inner": None, "items": []},
        {"id": 1},
    ],
)
def test_checker_accepts_a_matching_body(body):
    check_body(_Outer, json.dumps(body).encode())


@pytest.mark.parametrize(
    "body, problem",
    [
        ({"id": 1, "token_hash": "x"}, "token_hash"),
        ({"id": 1, "inner": {"name": "a", "session_id": "s"}}, "session_id"),
        ({"id": 1, "items": [{"name": "a", "secret": "s"}]}, "secret"),
        ({"id": "1"}, "id"),
        ({"inner": {"name": "a"}}, "id"),
    ],
)
def test_checker_rejects_a_stray_body(body, problem):
    with pytest.raises(ContractViolation, match=problem):
        check_body(_Outer, json.dumps(body).encode())


def test_checker_runs_on_every_test_client_response():
    """A route that returns more than its model declares fails the test that calls it."""
    app = FastAPI()

    @app.get("/leaky", response_model=_Outer)
    async def leaky():
        return JSONResponse({"id": 1, "password_hash": "x"})

    with pytest.raises(ContractViolation, match="password_hash"):
        TestClient(app).get("/leaky")


def test_checker_resolves_routes_under_mounts_and_root_path():
    """A route behind a Mount, or served under a root_path, is still found and checked."""
    inner = FastAPI()

    @inner.get("/api/2.0/mlflow/thing", response_model=_Outer)
    async def thing():
        return JSONResponse({"id": 1, "session_id": "x"})

    outer = FastAPI()
    outer.mount("/prefix", inner)
    with pytest.raises(ContractViolation, match="session_id"):
        TestClient(outer).get("/prefix/api/2.0/mlflow/thing")
    with pytest.raises(ContractViolation, match="session_id"):
        TestClient(inner, root_path="/proxy").get("/proxy/api/2.0/mlflow/thing")


def test_checker_fails_a_plugin_response_no_route_resolves():
    """A JSON body on a plugin path that no route explains is a failure, not a skip."""
    app = FastAPI()

    @app.middleware("http")
    async def answer(request, call_next):
        return JSONResponse({"anything": True})

    with pytest.raises(ContractViolation, match="no route resolves"):
        TestClient(app).get("/api/2.0/mlflow/users/nobody-routes-this")


def test_checker_leaves_router_404s_and_non_plugin_paths_alone():
    assert TestClient(FastAPI()).get("/api/2.0/mlflow/does-not-exist").status_code == 404

    app = FastAPI()

    @app.middleware("http")
    async def answer(request, call_next):
        return JSONResponse({"anything": True})

    assert TestClient(app).get("/elsewhere").status_code == 200


def test_checker_skips_non_json_and_unmodelled_responses():
    app = FastAPI()

    @app.get("/api/2.0/mlflow/plain")
    async def plain():
        return {"free": "form"}

    response = TestClient(app).get("/api/2.0/mlflow/plain")
    check_response(app, response)
