"""Admin lifecycle API and detail listings for the UI (issue #320)."""

import pytest

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.ownership import Enforcement

from .conftest import ADMIN, LOGIN, PROTECTED, USER_PASSWORD, basic, user_body

USERS_API = "/api/2.0/mlflow/users"
GROUPS_API = "/api/2.0/mlflow/permissions/groups"
BOB = "bob@example.com"


@pytest.fixture
def bob(bound_store):
    bound_store.create_user(BOB, USER_PASSWORD, "Bob")
    return basic(BOB, USER_PASSWORD)


class TestUserDetails:
    def test_shape(self, client, admin, bob, bound_store):
        bound_store.create_user("svc-bot", "unused-secret", "Bot", is_service_account=True)
        response = client.get(f"{USERS_API}/details", headers=admin)
        assert response.status_code == 200
        rows = {row["username"]: row for row in response.json()}
        assert rows[BOB] == {
            "username": BOB,
            "display_name": "Bob",
            "is_admin": False,
            "is_service_account": False,
            "active": True,
            "managed_by": "manual",
        }
        assert rows[ADMIN]["is_admin"] is True
        assert rows["svc-bot"]["is_service_account"] is True

    def test_service_filter(self, client, admin, bob, bound_store):
        bound_store.create_user("svc-bot", "unused-secret", "Bot", is_service_account=True)
        assert [r["username"] for r in client.get(f"{USERS_API}/details", headers=admin, params={"service": True}).json()] == ["svc-bot"]
        assert "svc-bot" not in [r["username"] for r in client.get(f"{USERS_API}/details", headers=admin, params={"service": False}).json()]

    def test_non_admin_is_forbidden(self, client, admin, bob):
        assert client.get(f"{USERS_API}/details", headers=bob).status_code == 403

    def test_plain_list_is_unchanged(self, client, admin, bob):
        """The UI and API clients depend on ``GET /users`` returning ``string[]``."""
        body = client.get(USERS_API, headers=bob).json()
        assert isinstance(body, list) and all(isinstance(u, str) for u in body)


class TestGroupDetails:
    def test_shape(self, client, admin, bob, bound_store):
        bound_store.populate_groups(["team-a", "team-b"])
        bound_store.add_user_to_group(BOB, "team-a")
        response = client.get(f"{GROUPS_API}/details", headers=admin)
        assert response.status_code == 200
        assert response.json() == [
            {"group_name": "team-a", "external_id": None, "member_count": 1},
            {"group_name": "team-b", "external_id": None, "member_count": 0},
        ]

    def test_non_admin_is_forbidden(self, client, admin, bob):
        assert client.get(f"{GROUPS_API}/details", headers=bob).status_code == 403


class TestSetActive:
    def test_non_admin_is_forbidden(self, client, admin, bob, bound_store):
        bound_store.create_user("carol@example.com", "unused-secret", "Carol")
        response = client.patch(f"{USERS_API}/carol@example.com/active", headers=bob, json={"active": False})
        assert response.status_code == 403
        assert bound_store.get_user_detail("carol@example.com")["active"] is True

    def test_unauthenticated_is_refused(self, client, bob):
        assert client.patch(f"{USERS_API}/{BOB}/active", json={"active": False}).status_code == 401

    def test_deactivate_and_reactivate(self, client, admin, bob, bound_store, audit_events):
        client.get(LOGIN, params={"username": BOB})
        assert client.get(PROTECTED).status_code == 200

        response = client.patch(f"{USERS_API}/{BOB}/active", headers=admin, json={"active": False})
        assert response.status_code == 200
        assert response.json() == {
            "username": BOB,
            "display_name": "Bob",
            "is_admin": False,
            "is_service_account": False,
            "active": False,
            "managed_by": "manual",
        }
        assert client.get(PROTECTED).status_code == 401, "the live session is revoked"
        assert client.get(PROTECTED, headers=bob).status_code == 401, "the token is revoked"

        assert client.patch(f"{USERS_API}/{BOB}/active", headers=admin, json={"active": True}).json()["active"] is True
        client.get(LOGIN, params={"username": BOB})
        assert client.get(PROTECTED).status_code == 200

        names = [(e["event"], e["detail"]) for e in audit_events if e["event"] in ("user.deactivated", "user.reactivated")]
        assert names == [("user.deactivated", {"source": "admin"}), ("user.reactivated", {"source": "admin"})]

    def test_unknown_user_is_404(self, client, admin):
        assert client.patch(f"{USERS_API}/ghost@example.com/active", headers=admin, json={"active": False}).status_code == 404

    def test_last_admin_is_refused(self, client, admin, bound_store):
        response = client.patch(f"{USERS_API}/{ADMIN}/active", headers=admin, json={"active": False})
        assert response.status_code == 409
        assert bound_store.get_user_detail(ADMIN)["active"] is True

    def test_guard_applies_to_a_scim_managed_user_under_enforce(self, client, admin, bound_store, monkeypatch, scim):
        client.post("/scim/v2/Users", headers=scim, json=user_body("dir@example.com"))
        assert bound_store.get_user_detail("dir@example.com")["managed_by"] == "scim"
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        refused = client.patch(f"{USERS_API}/dir@example.com/active", headers=admin, json={"active": False})
        assert refused.status_code == 409
        assert bound_store.get_user_detail("dir@example.com")["active"] is True

        overridden = client.patch(f"{USERS_API}/dir@example.com/active", headers=admin, json={"active": False, "admin_override": True})
        assert overridden.status_code == 200
        assert bound_store.get_user_detail("dir@example.com")["active"] is False
        assert bound_store.get_user_detail("dir@example.com")["managed_by"] == "scim", "an override does not change ownership"

    def test_report_mode_permits_and_records(self, client, admin, bound_store, scim, audit_events):
        client.post("/scim/v2/Users", headers=scim, json=user_body("dir@example.com"))
        assert client.patch(f"{USERS_API}/dir@example.com/active", headers=admin, json={"active": False}).status_code == 200
        assert any(e["event"] == "user.ownership_conflict" for e in audit_events)


class TestAdminDeleteReportsOrphans:
    def test_orphans_are_reported_on_admin_delete(self, client, admin, bob, bound_store, audit_events):
        bound_store.create_experiment_permission("7", BOB, "MANAGE")
        response = client.request("DELETE", USERS_API, headers=admin, json={"username": BOB})
        assert response.status_code == 200
        orphaned = [e for e in audit_events if e["event"] == "resource.orphaned"]
        assert [(e["resource_type"], e["resource_id"], e["detail"]["source"]) for e in orphaned] == [("experiment", "7", "admin")]

    def test_refused_last_admin_delete_hands_nothing_over(self, client, admin, bound_store, monkeypatch, audit_events):
        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        bound_store.create_experiment_permission("9", ADMIN, "MANAGE")

        response = client.request("DELETE", USERS_API, headers=admin, json={"username": ADMIN})

        assert response.status_code == 409
        assert bound_store.has_user(ADMIN)
        assert bound_store.list_experiment_permissions("steward@example.com") == []
        assert not [e for e in audit_events if e["event"] == "resource.orphaned"]


class TestAdminDeleteGoesThroughTheOwnershipGuard:
    """An admin refused a deactivate under enforce must not be able to hard-delete the same
    directory-owned user instead, silently: the same guard, the same break-glass override."""

    @pytest.fixture
    def directory_user(self, client, scim, bound_store):
        client.post("/scim/v2/Users", headers=scim, json=user_body("dir@example.com"))
        assert bound_store.get_user_detail("dir@example.com")["managed_by"] == "scim"
        return "dir@example.com"

    def test_refused_under_enforce_and_audited(self, client, admin, bound_store, monkeypatch, audit_events, directory_user):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        response = client.request("DELETE", USERS_API, headers=admin, json={"username": directory_user})

        assert response.status_code == 409
        assert bound_store.has_user(directory_user)
        conflicts = [e for e in audit_events if e["event"] == "user.ownership_conflict"]
        assert len(conflicts) == 1
        assert conflicts[0]["status"] == "denied"
        assert conflicts[0]["actor"] == ADMIN
        assert conflicts[0]["detail"]["operation"] == "delete"
        assert conflicts[0]["detail"]["owner"] == "scim"
        assert conflicts[0]["detail"]["permitted"] is False
        assert not [e for e in audit_events if e["event"] == "user.delete"]

    def test_admin_override_deletes_and_is_audited(self, client, admin, bound_store, monkeypatch, audit_events, directory_user):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        response = client.request("DELETE", USERS_API, headers=admin, json={"username": directory_user, "admin_override": True})

        assert response.status_code == 200
        assert not bound_store.has_user(directory_user)
        conflicts = [e for e in audit_events if e["event"] == "user.ownership_conflict"]
        assert [(c["status"], c["detail"]["permitted"]) for c in conflicts] == [("success", True)]

    def test_report_mode_deletes_and_records(self, client, admin, bound_store, audit_events, directory_user):
        response = client.request("DELETE", USERS_API, headers=admin, json={"username": directory_user})

        assert response.status_code == 200
        assert not bound_store.has_user(directory_user)
        assert any(e["event"] == "user.ownership_conflict" and e["status"] == "success" for e in audit_events)

    def test_a_manual_user_is_deleted_under_enforce_without_a_conflict(self, client, admin, bob, bound_store, monkeypatch, audit_events):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        assert client.request("DELETE", USERS_API, headers=admin, json={"username": BOB}).status_code == 200
        assert not bound_store.has_user(BOB)
        assert not [e for e in audit_events if e["event"] == "user.ownership_conflict"]
