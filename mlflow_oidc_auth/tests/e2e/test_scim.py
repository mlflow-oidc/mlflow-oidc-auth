"""SCIM 2.0 against the real server: a conformance smoke test, vendor-shaped deprovisioning, and
vendor-shaped group membership.

The deprovisioning tests drive the whole loop an enterprise relies on: a user signed in through
Keycloak, holding a grant and an access token, is deactivated by a directory in the exact shape
Entra ID or Okta sends; every credential stops working on the next request, a new Keycloak login
is refused by the app, and reactivation restores access with the grant intact.

The group tests do the same for membership (#323): a user Keycloak provisioned (by signing in) is
added to a directory group in Entra's ``PATCH`` shape or Okta's ``PUT`` shape, gains what the
group is granted, and loses it when the directory removes them — Entra through its filtered path
``members[value eq "..."]``.

``scim2-tester`` runs as a smoke test. The checks it reports as failures for features this
endpoint deliberately does not implement are excluded by tag or listed in ``KNOWN_UNSUPPORTED``
(see "Supported operations" in docs/scim.md); anything else failing fails the test.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from mlflow_oidc_auth.tests.e2e import flows
from mlflow_oidc_auth.tests.e2e.harness import NAMED_OIDC_PROVIDER_ID, SAML_PROVIDER_ID

pytestmark = pytest.mark.e2e

ALICE = "alice@example.com"
BOB = "bob@example.com"
CAROL = "carol@example.com"
ROOT = "root@example.com"
SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
PATCH_OP_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
SCIM_JSON = "application/scim+json"

# scim2-tester tags for features the endpoint does not implement, by design (docs/scim.md):
# attribute projection (``attributes`` / ``excludedAttributes``) and POST ``/.search`` are not
# supported, and PATCH supports ``add`` / ``replace`` only. The checks still run (the tester's own
# ``exclude_tags`` also skips the discovery checks in 0.4.0); their results are set aside here.
UNSUPPORTED_TAGS = {"crud:read:attributes", "patch:remove"}
# Individual checks inside otherwise-supported tags. ``name.givenName`` / ``familyName`` are
# accepted and not stored, so the tester reads back a different ``name`` than it wrote.
KNOWN_UNSUPPORTED = {("check_add_attribute", "'name'"), ("check_replace_attribute", "'name'")}


@pytest.fixture(scope="module")
def root_cookie(app_server) -> str:
    return flows.session_cookie(flows.login(app_server, ROOT))


@pytest.fixture(scope="module")
def scim_token(app_server, root_cookie) -> str:
    response = httpx.post(
        f"{app_server.url}/api/2.0/mlflow/scim/tokens",
        json={"name": f"e2e-{uuid.uuid4().hex[:8]}", "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        headers={"Cookie": f"{flows.SESSION_COOKIE}={root_cookie}"},
        timeout=30.0,
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    assert token.startswith("scim_")
    return token


def _scim(app_server, token: str, method: str, path: str, body=None) -> httpx.Response:
    return httpx.request(
        method,
        f"{app_server.url}/scim/v2{path}",
        json=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": SCIM_JSON, "Accept": SCIM_JSON},
        timeout=30.0,
    )


def test_scim2_tester_conformance_smoke(app_server, scim_token):
    httpx2 = pytest.importorskip("httpx2", reason="install scim2-tester[httpx2] (tox -e e2e does)")
    from scim2_client.engines.httpx2 import SyncSCIMClient
    from scim2_tester import Status, check_server

    client = SyncSCIMClient(httpx2.Client(base_url=f"{app_server.url}/scim/v2", headers={"Authorization": f"Bearer {scim_token}"}))
    client.discover()
    results = check_server(client)

    passed = {result.title for result in results if result.status in (Status.SUCCESS, Status.COMPLIANT, Status.ACCEPTABLE)}
    # Guard against a vacuous pass: discovery and the User CRUD cycle must actually have run.
    for check in ("service_provider_config_endpoint", "object_creation", "object_query", "object_replacement", "object_deletion"):
        assert check in passed, f"scim2-tester did not run {check}: {[(r.title, r.status.name) for r in results]}"
    # ...and the Group one (#323), now that /ResourceTypes advertises it.
    passed_by_type = {(result.title, result.resource_type) for result in results if result.status in (Status.SUCCESS, Status.COMPLIANT, Status.ACCEPTABLE)}
    for check in ("object_creation", "object_query", "object_replacement", "object_deletion"):
        assert (check, "Group") in passed_by_type, f"scim2-tester did not run {check} on Group: {[(r.title, r.resource_type, r.status.name) for r in results]}"

    failures = [
        (result.title, result.resource_type, result.reason)
        for result in results
        if result.status in (Status.ERROR, Status.CRITICAL)
        and not (result.tags & UNSUPPORTED_TAGS)
        and not any(result.title == title and marker in (result.reason or "") for title, marker in KNOWN_UNSUPPORTED)
    ]
    assert failures == [], failures


def _entra_deactivate(app_server, token):
    # Entra ID sends PATCH with a capitalised op and the boolean as a *string*.
    return _scim(
        app_server,
        token,
        "PATCH",
        f"/Users/{ALICE}",
        {"schemas": [PATCH_OP_SCHEMA], "Operations": [{"op": "Replace", "path": "active", "value": "False"}]},
    )


def _entra_reactivate(app_server, token):
    return _scim(
        app_server,
        token,
        "PATCH",
        f"/Users/{ALICE}",
        {"schemas": [PATCH_OP_SCHEMA], "Operations": [{"op": "Replace", "path": "active", "value": "True"}]},
    )


def _okta_put(app_server, token, active: bool):
    # Okta replaces the whole user with PUT and sends attributes the endpoint does not store.
    return _scim(
        app_server,
        token,
        "PUT",
        f"/Users/{ALICE}",
        {
            "schemas": [SCIM_USER_SCHEMA],
            "id": ALICE,
            "userName": ALICE,
            "name": {"givenName": "Alice", "familyName": "E2E"},
            "displayName": "Alice E2E",
            "emails": [{"primary": True, "value": ALICE, "type": "work"}],
            "active": active,
        },
    )


VENDORS = {
    "entra-patch": (_entra_deactivate, _entra_reactivate),
    "okta-put": (lambda app, token: _okta_put(app, token, False), lambda app, token: _okta_put(app, token, True)),
}


@pytest.mark.parametrize("vendor", sorted(VENDORS))
def test_directory_deprovisioning_cuts_every_credential_and_keeps_grants(app_server, keycloak, scim_token, root_cookie, vendor):
    deactivate, reactivate = VENDORS[vendor]
    root_headers = {"Cookie": f"{flows.SESSION_COOKIE}={root_cookie}"}

    # A live Keycloak session, a grant and an access token — everything deprovisioning must cut.
    alice = flows.session_cookie(flows.login(app_server, ALICE))
    alice_headers = {"Cookie": f"{flows.SESSION_COOKIE}={alice}"}
    created = httpx.post(
        f"{app_server.url}/api/2.0/mlflow/experiments/create", json={"name": f"e2e-scim-{vendor}-{uuid.uuid4().hex[:8]}"}, headers=root_headers, timeout=30.0
    )
    assert created.status_code == 200, created.text
    experiment_id = created.json()["experiment_id"]
    get_experiment = f"/api/2.0/mlflow/experiments/get?experiment_id={experiment_id}"
    assert flows.api_get(app_server, get_experiment, alice).status_code == 403  # deny by default
    granted = httpx.post(
        f"{app_server.url}/api/2.0/mlflow/permissions/users/{ALICE}/experiments/{experiment_id}",
        json={"permission": "READ"},
        headers=root_headers,
        timeout=30.0,
    )
    assert granted.status_code in (200, 201), granted.text
    assert _eventually_status(app_server, get_experiment, alice, 200)

    issued = httpx.patch(f"{app_server.url}/api/2.0/mlflow/users/access-token", json={}, headers=alice_headers, timeout=30.0)
    assert issued.status_code == 200, issued.text
    access_token = issued.json()["token"]
    assert httpx.get(f"{app_server.url}{flows.CURRENT_USER}", auth=(ALICE, access_token), timeout=30.0).status_code == 200

    # The directory deprovisions her.
    response = deactivate(app_server, scim_token)
    assert response.status_code == 200, response.text
    assert response.json()["active"] is False
    assert response.headers["content-type"].startswith(SCIM_JSON)

    # The live OIDC session dies on its next request, and so does the token.
    assert flows.api_get(app_server, flows.CURRENT_USER, alice).status_code == 401
    assert flows.api_get(app_server, get_experiment, alice).status_code == 401
    assert httpx.get(f"{app_server.url}{flows.CURRENT_USER}", auth=(ALICE, access_token), timeout=30.0).status_code == 401

    # Keycloak still vouches for her; the app does not take its word.
    denied_before = len(app_server.audit_events("auth.denied_inactive"))
    refused = flows.login(app_server, ALICE)
    assert flows.auth_status(app_server, flows.session_cookie(refused))["authenticated"] is False
    landing = flows.landing_url(refused.history[-1])
    assert "/oidc/ui/auth" in landing and "error" in landing
    assert len(app_server.audit_events("auth.denied_inactive")) == denied_before + 1

    # Repeating the deactivation is a no-op, as directories re-send state on every sync.
    assert deactivate(app_server, scim_token).status_code == 200

    # Reactivated: she signs in again and the grant is still there. The old token is not revived.
    response = reactivate(app_server, scim_token)
    assert response.status_code == 200, response.text
    assert response.json()["active"] is True
    back = flows.session_cookie(flows.login(app_server, ALICE))
    assert flows.auth_status(app_server, back)["username"] == ALICE
    assert _eventually_status(app_server, get_experiment, back, 200)
    assert httpx.get(f"{app_server.url}{flows.CURRENT_USER}", auth=(ALICE, access_token), timeout=30.0).status_code == 401


def test_scim_token_authenticates_nothing_but_scim(app_server, scim_token):
    assert httpx.get(f"{app_server.url}{flows.CURRENT_USER}", headers={"Authorization": f"Bearer {scim_token}"}, timeout=30.0).status_code == 401
    assert _scim(app_server, "scim_bogus_" + "x" * 40, "GET", "/Users").status_code == 401


def test_a_user_session_cannot_call_scim(app_server, root_cookie):
    # Not even an administrator's: /scim/v2 accepts the SCIM token and nothing else.
    response = httpx.get(f"{app_server.url}/scim/v2/Users", headers={"Cookie": f"{flows.SESSION_COOKIE}={root_cookie}"}, timeout=30.0)
    assert response.status_code == 401


def _group_members(app_server, token: str, group: str) -> list:
    response = _scim(app_server, token, "GET", f"/Groups/{group}")
    assert response.status_code == 200, response.text
    return sorted(member["value"] for member in response.json().get("members", []))


@pytest.fixture
def group_grant(app_server, root_cookie, scim_token):
    """A fresh directory group with ``READ`` on a fresh experiment. Returns ``(group, get_path)``."""
    root_headers = {"Cookie": f"{flows.SESSION_COOKIE}={root_cookie}"}
    group = f"e2e-dir-{uuid.uuid4().hex[:8]}"
    created = _scim(app_server, scim_token, "POST", "/Groups", {"schemas": [SCIM_GROUP_SCHEMA], "displayName": group, "externalId": f"ext-{group}"})
    assert created.status_code == 201, created.text
    assert created.json()["id"] == group

    experiment = httpx.post(f"{app_server.url}/api/2.0/mlflow/experiments/create", json={"name": f"{group}-exp"}, headers=root_headers, timeout=30.0)
    assert experiment.status_code == 200, experiment.text
    experiment_id = experiment.json()["experiment_id"]
    granted = httpx.post(
        f"{app_server.url}/api/2.0/mlflow/permissions/groups/{group}/experiments/{experiment_id}",
        json={"permission": "READ"},
        headers=root_headers,
        timeout=30.0,
    )
    assert granted.status_code in (200, 201), granted.text
    yield group, f"/api/2.0/mlflow/experiments/get?experiment_id={experiment_id}"
    _scim(app_server, scim_token, "DELETE", f"/Groups/{group}")


def test_entra_filtered_patch_adds_and_removes_a_keycloak_user(app_server, keycloak, scim_token, group_grant):
    group, get_experiment = group_grant
    # Provisioned by Keycloak: carol exists because she signed in. Through the named OIDC provider,
    # the one the rest of the suite binds her to — a second provider may not claim her account.
    carol = flows.session_cookie(flows.login(app_server, CAROL, provider=NAMED_OIDC_PROVIDER_ID))
    assert flows.api_get(app_server, get_experiment, carol).status_code == 403  # deny by default

    # Entra looks the group up first, without members, then adds with a capitalised op.
    found = _scim(app_server, scim_token, "GET", f"/Groups?filter=displayName%20eq%20%22{group}%22&excludedAttributes=members")
    assert found.status_code == 200, found.text
    assert [(r["id"], "members" in r) for r in found.json()["Resources"]] == [(group, False)]
    added = _scim(
        app_server,
        scim_token,
        "PATCH",
        f"/Groups/{group}",
        {"schemas": [PATCH_OP_SCHEMA], "Operations": [{"op": "Add", "path": "members", "value": [{"value": CAROL}]}]},
    )
    assert added.status_code == 200, added.text
    assert _group_members(app_server, scim_token, group) == [CAROL]
    assert _eventually_status(app_server, get_experiment, carol, 200), "the group's grant must reach the member"

    # Entra's filtered remove path — the shape naive PATCH implementations get wrong.
    removed = _scim(
        app_server,
        scim_token,
        "PATCH",
        f"/Groups/{group}",
        {"schemas": [PATCH_OP_SCHEMA], "Operations": [{"op": "Remove", "path": f'members[value eq "{CAROL}"]'}]},
    )
    assert removed.status_code == 200, removed.text
    assert _group_members(app_server, scim_token, group) == []
    assert _eventually_status(app_server, get_experiment, carol, 403), "removing the membership must revoke the grant"

    changes = [e for e in app_server.audit_events("group.members_changed") if e.get("resource_id") == group]
    assert [(e["detail"]["added"], e["detail"]["removed"]) for e in changes] == [([CAROL], []), ([], [CAROL])]


def test_okta_put_replaces_membership_for_keycloak_users(app_server, keycloak, scim_token, group_grant):
    group, get_experiment = group_grant
    # Keycloak-provisioned through two different protocols: bob over SAML, carol over OIDC.
    bob = flows.session_cookie(flows.login(app_server, BOB, provider=SAML_PROVIDER_ID))
    carol = flows.session_cookie(flows.login(app_server, CAROL, provider=NAMED_OIDC_PROVIDER_ID))

    def okta_put(members):
        # Okta sends the whole group, members and all, with display names it keeps itself.
        return _scim(
            app_server,
            scim_token,
            "PUT",
            f"/Groups/{group}",
            {
                "schemas": [SCIM_GROUP_SCHEMA],
                "id": group,
                "displayName": group,
                "externalId": f"ext-{group}",
                "members": [{"value": member, "display": member.split("@")[0].title()} for member in members],
            },
        )

    response = okta_put([BOB, CAROL])
    assert response.status_code == 200, response.text
    assert _group_members(app_server, scim_token, group) == [BOB, CAROL]
    assert _eventually_status(app_server, get_experiment, bob, 200)
    assert _eventually_status(app_server, get_experiment, carol, 200)

    response = okta_put([CAROL])
    assert response.status_code == 200, response.text
    assert _group_members(app_server, scim_token, group) == [CAROL]
    assert _eventually_status(app_server, get_experiment, bob, 403)
    assert flows.api_get(app_server, get_experiment, carol).status_code == 200


def test_an_authoritative_login_under_report_removes_the_directory_membership_and_records_it(app_server, keycloak, scim_token, group_grant):
    """The documented interplay under the default MANAGED_BY_ENFORCEMENT=report (#360): Keycloak's
    claims do not carry the directory group, the default provider syncs authoritatively, and the
    login removes the SCIM membership exactly as before — but no longer silently."""
    group, _ = group_grant
    flows.login(app_server, ALICE)
    added = _scim(
        app_server,
        scim_token,
        "PATCH",
        f"/Groups/{group}",
        {"schemas": [PATCH_OP_SCHEMA], "Operations": [{"op": "add", "path": "members", "value": [{"value": ALICE}]}]},
    )
    assert added.status_code == 200, added.text

    flows.login(app_server, ALICE)

    assert _group_members(app_server, scim_token, group) == []
    conflicts = [
        e
        for e in app_server.audit_events("user.ownership_conflict")
        if e.get("detail", {}).get("group") == group and e["detail"].get("operation") == "membership.remove"
    ]
    assert [(e["detail"]["owner"], e["detail"]["written_by"], e["detail"]["permitted"]) for e in conflicts] == [("scim", "oidc:default", True)]


def _eventually_status(app_server, path: str, cookie: str, expected: int, attempts: int = 10) -> bool:
    """Poll for ``expected``: with several workers a grant may sit behind another process's cache."""
    for _ in range(attempts):
        if flows.api_get(app_server, path, cookie).status_code == expected:
            return True
        time.sleep(0.5)
    return False
