"""Grant routes map MlflowException error codes to HTTP statuses (#475).

``MlflowException.error_code`` is the code's NAME (``"RESOURCE_ALREADY_EXISTS"``), so the old
comparison with the proto int never matched: a duplicate grant came back as an unhandled error
instead of a 409. These tests raise a real ``MlflowException(error_code=...)`` from the store and
check the status and detail each generated route answers.
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


def _send(http, method, path, body, code):
    error = MlflowException("store says no", error_code=code)
    with patch.object(user_permissions, "store", RaisingStore(error)), patch.object(group_permissions, "store", RaisingStore(error)):
        return getattr(http, method)(path, json=body)


@pytest.mark.parametrize(
    "method, path, body, code, status, detail",
    [
        ("post", U + "/prompts/p", GRANT, RESOURCE_ALREADY_EXISTS, 409, "Prompt permission already exists"),
        ("post", U + "/prompts/p", GRANT, INVALID_PARAMETER_VALUE, 400, "store says no"),
        ("patch", U + "/prompts/p", GRANT, RESOURCE_DOES_NOT_EXIST, 404, "Prompt permission does not exist"),
        ("patch", U + "/prompts/p", GRANT, INVALID_PARAMETER_VALUE, 400, "store says no"),
        ("post", U + "/registered-models/m", GRANT, RESOURCE_ALREADY_EXISTS, 409, "Registered model permission already exists"),
        ("patch", U + "/registered-models/m", GRANT, RESOURCE_DOES_NOT_EXIST, 404, "Registered model permission does not exist"),
        ("post", U + "/scorers/7/s", GRANT, RESOURCE_ALREADY_EXISTS, 409, "Scorer permission already exists"),
        ("patch", U + "/scorers/7/s", GRANT, RESOURCE_DOES_NOT_EXIST, 404, "Scorer permission does not exist"),
        ("post", U + "/scorer-patterns", PATTERN, RESOURCE_ALREADY_EXISTS, 409, "Scorer pattern permission already exists"),
        ("post", U + "/scorer-patterns", PATTERN, INVALID_PARAMETER_VALUE, 400, "store says no"),
    ],
)
def test_error_code_maps_to_status(http, method, path, body, code, status, detail):
    response = _send(http, method, path, body, code)
    assert (response.status_code, response.json()["detail"]) == (status, detail)


def test_unmapped_error_code_is_not_a_conflict(http):
    """An MlflowException with no mapping keeps propagating, as before."""
    response = _send(http, "post", U + "/prompts/p", GRANT, INTERNAL_ERROR)
    assert response.status_code == 500


PATTERN_KINDS = {
    "experiment-patterns": "experiment",
    "registered-models-patterns": "registered model",
    "prompts-patterns": "prompt",
    "scorer-patterns": "scorer",
    "gateways/endpoints-patterns": "gateway endpoint",
    "gateways/model-definitions-patterns": "gateway model definition",
    "gateways/secrets-patterns": "gateway secret",
}


@pytest.mark.parametrize("subject, prefix", [(U, ""), (G, "group ")], ids=["user", "group"])
@pytest.mark.parametrize("segment", PATTERN_KINDS)
def test_pattern_update_onto_an_existing_regex_is_409(http, subject, prefix, segment):
    """A pattern updated onto another pattern's regex is a conflict; any other store failure stays a 500."""
    noun = f"{prefix}{PATTERN_KINDS[segment]} pattern permission"
    conflict = _send(http, "patch", f"{subject}/{segment}/5", PATTERN, RESOURCE_ALREADY_EXISTS)
    assert (conflict.status_code, conflict.json()["detail"]) == (409, f"{noun[0].upper()}{noun[1:]} already exists")
    other = _send(http, "patch", f"{subject}/{segment}/5", PATTERN, RESOURCE_DOES_NOT_EXIST)
    assert (other.status_code, other.json()["detail"]) == (500, f"Failed to update {noun}")
