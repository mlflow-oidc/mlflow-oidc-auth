"""Every generated grant route maps store failures the same way (#475, #473 review).

``MlflowException.error_code`` holds the code's NAME (``"RESOURCE_ALREADY_EXISTS"``); the old
comparison with the proto int never matched. Now every generated route, user and group, exact and
pattern, all kinds, answers:

* ``RESOURCE_ALREADY_EXISTS`` -> 409 "<Grant> already exists",
* ``INVALID_PARAMETER_VALUE`` -> 400 with the store's message,
* ``RESOURCE_DOES_NOT_EXIST`` -> 404 "<Grant> not found",
* anything else -> 500 "Failed to <verb> <grant>".

A string pattern id that is not an integer is a 400 "Invalid pattern ID format"; no other
``ValueError`` is. The tests raise real exceptions from the store and assert status and detail.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INTERNAL_ERROR, INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.routers import group_permissions, user_permissions
from mlflow_oidc_auth.routers._prefix import GROUP_PERMISSIONS_ROUTER_PREFIX, USER_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.utils import get_is_admin, get_username

U = USER_PERMISSIONS_ROUTER_PREFIX + "/bob"
G = GROUP_PERMISSIONS_ROUTER_PREFIX + "/team"
GRANT = {"permission": "READ"}
PATTERN = {"regex": "^x", "priority": 1, "permission": "READ"}
VERB = {"post": "create", "get": "get", "patch": "update", "delete": "delete"}

GATEWAYS = {"endpoints": "gateway endpoint", "model-definitions": "gateway model definition", "secrets": "gateway secret"}

# (path of one grant, the grant as details name it, methods the route family serves)
EXACT = [
    (U + "/experiments/7", "experiment permission", ("post", "get", "patch", "delete")),
    (U + "/prompts/p", "prompt permission", ("post", "get", "patch", "delete")),
    (U + "/registered-models/m", "registered model permission", ("post", "get", "patch", "delete")),
    (U + "/scorers/7/s", "scorer permission", ("post", "get", "patch", "delete")),
    (G + "/experiments/7", "group experiment permission", ("post", "patch", "delete")),
    (G + "/registered-models/m", "group registered model permission", ("post", "patch", "delete")),
    (G + "/prompts/p", "group prompt permission", ("post", "patch", "delete")),
    (G + "/scorers/7/s", "group scorer permission", ("post", "patch", "delete")),
    *[(U + f"/gateways/{kind}/n", f"{label} permission", ("post", "get", "patch", "delete")) for kind, label in GATEWAYS.items()],
    *[(G + f"/gateways/{kind}/n", f"group {label} permission", ("post", "get", "patch", "delete")) for kind, label in GATEWAYS.items()],
]

PATTERN_KINDS = {
    "experiment-patterns": "experiment",
    "registered-models-patterns": "registered model",
    "prompts-patterns": "prompt",
    "scorer-patterns": "scorer",
    **{f"gateways/{kind}-patterns": label for kind, label in GATEWAYS.items()},
}
# (path the method is sent to, the grant as details name it, method)
PATTERNS = [
    (f"{subject}/{segment}" + ("" if method == "post" else "/5"), f"{prefix}{label} pattern permission", method)
    for subject, prefix in ((U, ""), (G, "group "))
    for segment, label in PATTERN_KINDS.items()
    for method in ("post", "get", "patch", "delete")
]

CASES = [(path, noun, method) for path, noun, methods in EXACT for method in methods] + PATTERNS


class RaisingStore:
    """A store whose every method raises the given error."""

    def __init__(self, error):
        self.error = error

    def __getattr__(self, name):
        def method(*args, **kwargs):
            raise self.error

        return method


@pytest.fixture
def http():
    app = FastAPI()
    app.include_router(user_permissions.user_permissions_router)
    app.include_router(group_permissions.group_permissions_router)

    async def admin_name():
        return "admin@example.com"

    async def yes():
        return True

    app.dependency_overrides[check_admin_permission] = admin_name
    app.dependency_overrides[get_username] = admin_name
    app.dependency_overrides[get_is_admin] = yes
    return TestClient(app, raise_server_exceptions=False)


def _send(http, method, path, error):
    body = None if method in ("get", "delete") else (PATTERN if "-patterns" in path else GRANT)
    with patch.object(user_permissions, "store", RaisingStore(error)), patch.object(group_permissions, "store", RaisingStore(error)):
        return http.request(method.upper(), path, json=body)


def _cap(noun):
    return noun[:1].upper() + noun[1:]


def test_cases_cover_every_generated_route_on_one_grant():
    """User exact 4 kinds x 4, group exact 4 kinds x 3, gateway exact 6 x 4, pattern 14 kinds x 4 (create/get/update/delete)."""
    assert len(CASES) == len(set(CASES)) == 4 * 4 + 3 * 4 + 4 * 6 + 4 * 14


@pytest.mark.parametrize("path, noun, method", CASES, ids=[f"{m.upper()} {p}" for p, _, m in CASES])
def test_store_failures_map_the_same_on_every_route(http, path, noun, method):
    exists = _send(http, method, path, MlflowException("already there", error_code=RESOURCE_ALREADY_EXISTS))
    assert (exists.status_code, exists.json()["detail"]) == (409, f"{_cap(noun)} already exists")
    invalid = _send(http, method, path, MlflowException("store says no", error_code=INVALID_PARAMETER_VALUE))
    assert (invalid.status_code, invalid.json()["detail"]) == (400, "store says no")
    missing = _send(http, method, path, MlflowException("no such grant", error_code=RESOURCE_DOES_NOT_EXIST))
    assert (missing.status_code, missing.json()["detail"]) == (404, f"{_cap(noun)} not found")
    other = _send(http, method, path, MlflowException("boom", error_code=INTERNAL_ERROR))
    assert (other.status_code, other.json()["detail"]) == (500, f"Failed to {VERB[method]} {noun}")
    plain = _send(http, method, path, RuntimeError("boom"))
    assert (plain.status_code, plain.json()["detail"]) == (500, f"Failed to {VERB[method]} {noun}")


STRING_ID_PATTERNS = [f"{U}/{segment}/abc" for segment in ("experiment-patterns", "registered-models-patterns", "prompts-patterns")]


@pytest.mark.parametrize("path", STRING_ID_PATTERNS)
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_only_an_unparseable_pattern_id_is_a_bad_id(http, path, method):
    """A non-integer id is a 400 before the store is called; a ValueError from the store is not."""
    bad = _send(http, method, path, AssertionError("the store must not be called"))
    assert (bad.status_code, bad.json()["detail"]) == (400, "Invalid pattern ID format. Expected an integer.")
    good_path = path.replace("/abc", "/5")
    store_error = _send(http, method, good_path, ValueError("bad regex"))
    assert store_error.status_code == 500
    assert store_error.json()["detail"].startswith("Failed to ")


PATTERN_WRITES = [(path, noun, method) for path, noun, method in PATTERNS if method in ("post", "patch")]
BAD_REGEXES = {
    "invalid": ("([", "Invalid regex pattern: ([."),
    "redos": ("(a+)+$", "Regex pattern rejected: nested quantifiers detected (potential ReDoS)."),
}


def test_pattern_writes_cover_every_kind():
    assert len(PATTERN_WRITES) == 2 * 14


@pytest.mark.parametrize("kind", BAD_REGEXES)
@pytest.mark.parametrize("path, noun, method", PATTERN_WRITES, ids=[f"{m.upper()} {p}" for p, _, m in PATTERN_WRITES])
def test_rejected_regex_is_a_400_before_the_store(http, path, noun, method, kind):
    """An invalid or ReDoS-prone regex is refused with the validator's reason; the store is never called."""
    regex, reason = BAD_REGEXES[kind]
    store = RaisingStore(AssertionError("the store must not be called"))
    with patch.object(user_permissions, "store", store), patch.object(group_permissions, "store", store):
        response = http.request(method.upper(), path, json={**PATTERN, "regex": regex})
    assert response.status_code == 400
    assert response.json()["detail"].startswith(reason)
