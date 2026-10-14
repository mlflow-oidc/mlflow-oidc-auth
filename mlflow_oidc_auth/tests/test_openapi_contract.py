"""The OpenAPI contract the React UI's types are generated from (#458).

``scripts/export_openapi.py`` writes ``openapi.json`` from the routers; CI regenerates it and fails
on drift. These tests hold the properties that make that contract trustworthy: every route says
what it returns, the export needs no database, the ``/ajax-api`` twins stay out, and no user or
service-account response documents a credential beyond the one-time token-creation responses.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, Set

import pytest
from fastapi.datastructures import DefaultPlaceholder
from fastapi.routing import APIRoute

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTER = REPO_ROOT / "scripts" / "export_openapi.py"

#: Property names no user or service-account response may document.
CREDENTIAL_PROPERTIES = {"password", "password_hash", "token", "secret", "client_secret"}

#: The documented one-time token-creation responses: each returns the plaintext ``token`` once.
ONE_TIME_TOKEN_OPERATIONS = {
    ("patch", "/api/2.0/mlflow/users/access-token"),
    ("post", "/api/2.0/mlflow/users/current/tokens"),
    ("post", "/api/2.0/mlflow/users/{username}/tokens"),
    ("post", "/api/2.0/mlflow/scim/tokens"),
    ("post", "/api/2.0/mlflow/scim/tokens/{token_id}/rotate"),
}

#: What a one-time token-creation response may carry from ``CREDENTIAL_PROPERTIES``.
ONE_TIME_TOKEN_PROPERTIES = {"token"}


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def openapi() -> Dict[str, Any]:
    return _load_exporter().build_openapi()


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


def test_render_is_deterministic(openapi):
    exporter = _load_exporter()
    text = exporter.render(openapi)
    assert text.endswith("}\n")
    assert text == exporter.render(json.loads(text))


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


def _resolve(openapi: Dict[str, Any], schema: Any, seen: Set[str]) -> Iterator[Dict[str, Any]]:
    """Every object schema reachable from ``schema``, following ``$ref``s once each."""
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if ref:
            if ref in seen:
                return
            seen.add(ref)
            name = ref.rsplit("/", 1)[-1]
            yield from _resolve(openapi, openapi["components"]["schemas"][name], seen)
            return
        if "properties" in schema:
            yield schema
        for value in schema.values():
            yield from _resolve(openapi, value, seen)
    elif isinstance(schema, list):
        for item in schema:
            yield from _resolve(openapi, item, seen)


def _response_properties(openapi: Dict[str, Any], operation: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for response in operation.get("responses", {}).values():
        for media in response.get("content", {}).values():
            for schema in _resolve(openapi, media.get("schema", {}), set()):
                names.update(schema["properties"])
    return names


def test_user_response_has_no_password_hash(openapi):
    """No user or service-account response documents a credential, except the one-time token responses."""
    checked = 0
    for path, item in openapi["paths"].items():
        if not path.startswith(("/api/2.0/mlflow/users", "/api/2.0/mlflow/scim")):
            continue
        for method, operation in item.items():
            leaked = _response_properties(openapi, operation) & CREDENTIAL_PROPERTIES
            if (method, path) in ONE_TIME_TOKEN_OPERATIONS:
                leaked -= ONE_TIME_TOKEN_PROPERTIES
            assert not leaked, f"{method.upper()} {path} documents {sorted(leaked)}"
            checked += 1
    assert checked >= 20, "the user and SCIM admin endpoints were not found in the contract"

    # The same holds for every user-shaped schema, wherever it is used.
    for name, schema in openapi["components"]["schemas"].items():
        if not name.startswith(("User", "CurrentUser", "ServiceAccount", "ScimToken")):
            continue
        leaked = set(schema.get("properties", {})) & CREDENTIAL_PROPERTIES
        if name in {"UserTokenCreatedResponse", "ScimTokenCreatedResponse", "ScimTokenRotatedResponse"}:
            leaked -= ONE_TIME_TOKEN_PROPERTIES
        assert not leaked, f"schema {name} documents {sorted(leaked)}"


def test_one_time_token_responses_are_the_only_ones_with_a_token(openapi):
    """The allow-list above stays honest: each entry exists and really is a token-creation response."""
    for method, path in ONE_TIME_TOKEN_OPERATIONS:
        operation = openapi["paths"][path][method]
        assert "token" in _response_properties(openapi, operation), f"{method.upper()} {path}"
