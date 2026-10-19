"""The audit actor of a grant write is the signed-in caller (#474).

The manage checks (``check_experiment_manage_permission``, ``check_registered_model_manage_permission``)
return ``None``, and grant writes used to record that ``None`` as the audit actor. These tests send
real requests through the routers, with only the caller's identity and the store stubbed, and check
the actor of every ``permission.*`` event, for a non-admin with MANAGE and for an admin.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.routers import _permission_routes, group_permissions, user_permissions
from mlflow_oidc_auth.routers._prefix import GROUP_PERMISSIONS_ROUTER_PREFIX, USER_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.utils import get_is_admin, get_username

U = USER_PERMISSIONS_ROUTER_PREFIX + "/bob"
G = GROUP_PERMISSIONS_ROUTER_PREFIX + "/team"

# Grant routes behind a manage check (or an inline one) that a non-admin with MANAGE may call.
FAMILIES = {
    "user experiment": U + "/experiments/7",
    "user prompt": U + "/prompts/prompt-a",
    "user registered model": U + "/registered-models/model-a",
    "user scorer": U + "/scorers/7/scorer-a",
    "group experiment": G + "/experiments/7",
    "group registered model": G + "/registered-models/model-a",
    "group prompt": G + "/prompts/prompt-a",
    "group scorer": G + "/scorers/7/scorer-a",
}
WRITES = (("post", "permission.create"), ("patch", "permission.update"), ("delete", "permission.delete"))


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(user_permissions.user_permissions_router)
    app.include_router(group_permissions.group_permissions_router)
    return app, TestClient(app, raise_server_exceptions=False)


def _can_manage(*_):
    return SimpleNamespace(permission=SimpleNamespace(can_manage=True))


@pytest.mark.parametrize("is_admin", [False, True], ids=["manager", "admin"])
@pytest.mark.parametrize("method, event", WRITES, ids=[event for _, event in WRITES])
@pytest.mark.parametrize("family", FAMILIES)
def test_audit_actor_is_the_caller(client, family, method, event, is_admin):
    app, http = client
    caller = "alice@example.com"

    async def username():
        return caller

    async def admin():
        return is_admin

    app.dependency_overrides[get_username] = username
    app.dependency_overrides[get_is_admin] = admin
    audit = MagicMock()
    with (
        patch.object(user_permissions, "store", MagicMock()),
        patch.object(group_permissions, "store", MagicMock()),
        patch("mlflow_oidc_auth.dependencies.can_manage_experiment", return_value=True),
        patch("mlflow_oidc_auth.dependencies.effective_registry_permission", return_value=MagicMock(permission=MagicMock(can_manage=True))),
        patch("mlflow_oidc_auth.dependencies.effective_registry_permission", _can_manage),
        patch("mlflow_oidc_auth.dependencies.effective_registry_permission", _can_manage),
        patch.object(_permission_routes, "emit_audit_event", audit),
    ):
        kwargs = {} if method == "delete" else {"json": {"permission": "READ"}}
        response = getattr(http, method)(FAMILIES[family], **kwargs)
    assert response.status_code not in (401, 403, 404, 422), response.text
    assert audit.call_count == 1, response.text
    assert audit.call_args.args[0] == event
    assert audit.call_args.kwargs["actor"] == caller
