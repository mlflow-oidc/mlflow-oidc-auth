"""Group names containing "/" on the group permission routes, through the real server.

A group name with a "/" comes from two places: Keycloak's full group paths (``/mlflow-users``, which
group sync stores as sent) and an administrator creating one. Clients percent-encode it as ``%2F``,
and the group routes match the name as one segment of the path as sent (``routers/_group_route.py``),
which only holds if the server hands the route the raw path. A name made of route keywords
(``team-<id>/experiments``) must still reach its own grants, never another group's.
"""

from __future__ import annotations

import uuid
from typing import Optional
from urllib.parse import quote

import httpx2 as httpx
import pytest

from mlflow_oidc_auth.tests.e2e import flows

pytestmark = pytest.mark.e2e

ALICE = "alice@example.com"
ROOT = "root@example.com"
GROUPS = "/api/2.0/mlflow/permissions/groups"
KEYCLOAK_GROUP = "/mlflow-users"


def _call(app, method: str, path: str, cookie: str, json: Optional[dict] = None) -> httpx.Response:
    headers = {**flows.API_HEADERS, "Cookie": f"{flows.SESSION_COOKIE}={cookie}"}
    return httpx.request(method, f"{app.url}{path}", json=json, headers=headers, timeout=60.0)


def _group(name: str) -> str:
    return f"{GROUPS}/{quote(name, safe='')}"


def _experiment_grant(app, cookie: str, group: str, experiment_id: str) -> Optional[str]:
    response = _call(app, "GET", f"{_group(group)}/experiments", cookie)
    assert response.status_code == 200, response.text
    return {row["id"]: row["permission"] for row in response.json()}.get(experiment_id)


def test_slash_group_names_reach_their_own_grants(workspaces_app_server):
    app = workspaces_app_server
    # Group sync creates the Keycloak group at its first member's login.
    flows.login(app, ALICE)
    root = flows.session_cookie(flows.login(app, ROOT))
    # Made of route keywords, and new to this run: the server outlives the test.
    confusable_group = f"team-{uuid.uuid4().hex[:8]}/experiments"

    created = _call(app, "POST", GROUPS, root, json={"group_name": confusable_group})
    assert created.status_code == 201, created.text

    experiment = _call(app, "POST", "/api/2.0/mlflow/experiments/create", root, json={"name": f"e2e-group-names-{uuid.uuid4().hex[:8]}"})
    assert experiment.status_code == 200, experiment.text
    experiment_id = experiment.json()["experiment_id"]

    for group, permission in ((KEYCLOAK_GROUP, "READ"), (confusable_group, "EDIT")):
        granted = _call(app, "POST", f"{_group(group)}/experiments/{experiment_id}", root, json={"permission": permission})
        assert granted.status_code in (200, 201), f"{group}: {granted.text}"

    assert _experiment_grant(app, root, KEYCLOAK_GROUP, experiment_id) == "READ"
    assert _experiment_grant(app, root, confusable_group, experiment_id) == "EDIT"

    updated = _call(app, "PATCH", f"{_group(confusable_group)}/experiments/{experiment_id}", root, json={"permission": "MANAGE"})
    assert updated.status_code == 200, updated.text
    assert _experiment_grant(app, root, confusable_group, experiment_id) == "MANAGE"
    assert _experiment_grant(app, root, KEYCLOAK_GROUP, experiment_id) == "READ"

    for group in (KEYCLOAK_GROUP, confusable_group):
        removed = _call(app, "DELETE", f"{_group(group)}/experiments/{experiment_id}", root)
        assert removed.status_code == 200, f"{group}: {removed.text}"
    assert _experiment_grant(app, root, KEYCLOAK_GROUP, experiment_id) is None
    assert _experiment_grant(app, root, confusable_group, experiment_id) is None
