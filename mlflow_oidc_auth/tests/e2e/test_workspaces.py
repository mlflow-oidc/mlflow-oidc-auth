"""Workspace group permissions for a Keycloak group path, on an app with workspaces on (#466).

Keycloak sends a group's full path by default (``/mlflow-users``), and that name is what group sync
stores. Granting such a group a workspace permission takes the name in the body, but updating or
removing it takes the name in the URL, where the "/" once kept the request from reaching the route.
The client percent-encodes the name as the UI does; the server sees "/" again once it decodes it.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

import httpx2 as httpx
import pytest

from mlflow_oidc_auth.tests.e2e import flows

pytestmark = pytest.mark.e2e

ALICE = "alice@example.com"
ROOT = "root@example.com"
GROUP = "/mlflow-users"
WORKSPACE = "default"
WORKSPACE_GROUPS = f"/api/3.0/mlflow/permissions/workspaces/{WORKSPACE}/groups"
WORKSPACE_GROUP = f"{WORKSPACE_GROUPS}/{quote(GROUP, safe='')}"


def _call(app, method: str, path: str, cookie: str, json: Optional[dict] = None) -> httpx.Response:
    headers = {**flows.API_HEADERS, "Cookie": f"{flows.SESSION_COOKIE}={cookie}"}
    return httpx.request(method, f"{app.url}{path}", json=json, headers=headers, timeout=60.0)


def _group_grants(app, cookie: str) -> dict:
    response = flows.api_get(app, WORKSPACE_GROUPS, cookie)
    assert response.status_code == 200, response.text
    return {row["group_name"]: row["permission"] for row in response.json()}


def test_a_keycloak_group_path_grant_can_be_updated_and_removed(workspaces_app_server):
    app = workspaces_app_server
    root = flows.session_cookie(flows.login(app, ROOT))
    alice = flows.session_cookie(flows.login(app, ALICE))

    # Group sync stored the full path, as Keycloak sent it.
    profile = flows.api_get(app, flows.CURRENT_USER, alice)
    assert profile.status_code == 200, profile.text
    assert GROUP in {group["group_name"] for group in profile.json()["groups"]}

    created = _call(app, "POST", WORKSPACE_GROUPS, root, json={"group_name": GROUP, "permission": "READ"})
    assert created.status_code == 201, created.text
    assert _group_grants(app, root)[GROUP] == "READ"

    # A member of the group holds READ through it, not MANAGE: the route is reached, and its MANAGE
    # check refuses her. Asserted on the detail, since an unmatched path is refused by default too.
    for refused in (
        _call(app, "PATCH", WORKSPACE_GROUP, alice, json={"group_name": GROUP, "permission": "MANAGE"}),
        _call(app, "DELETE", WORKSPACE_GROUP, alice),
    ):
        assert refused.status_code == 403, refused.text
        assert refused.json()["detail"] == f"MANAGE permission required on workspace '{WORKSPACE}'"
    assert _group_grants(app, root)[GROUP] == "READ"

    updated = _call(app, "PATCH", WORKSPACE_GROUP, root, json={"group_name": GROUP, "permission": "EDIT"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["group_name"] == GROUP
    assert _group_grants(app, root)[GROUP] == "EDIT"

    removed = _call(app, "DELETE", WORKSPACE_GROUP, root)
    assert removed.status_code == 204, removed.text
    assert GROUP not in _group_grants(app, root)
