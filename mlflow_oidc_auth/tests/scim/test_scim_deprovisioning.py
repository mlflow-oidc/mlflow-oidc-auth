"""De-provisioning lifecycle through SCIM (issue #324).

Through the real ``AuthMiddleware``: a deactivated user's live session and their token must both
stop working on the very next request, and reactivation must bring the account back with every
grant intact.
"""

from datetime import datetime, timedelta, timezone

import pytest

from mlflow_oidc_auth import orphans
from mlflow_oidc_auth.config import config

from .conftest import ADMIN, LOGIN, PROTECTED, USER_PASSWORD, basic, patch_body, user_body

USERS = "/scim/v2/Users"
ALICE = "alice@example.com"
DEACTIVATE = patch_body({"op": "replace", "path": "active", "value": False})
REACTIVATE = patch_body({"op": "replace", "path": "active", "value": True})


@pytest.fixture
def alice(client, scim, bound_store):
    """A SCIM-provisioned user holding a live session and a known basic-auth token."""
    response = client.post(USERS, headers=scim, json=user_body(ALICE, external_id="ext-alice"))
    assert response.status_code == 201
    bound_store.update_user(ALICE, password=USER_PASSWORD, written_by="scim")
    return basic(ALICE, USER_PASSWORD)


def events(audit_events, name):
    return [e for e in audit_events if e["event"] == name]


class TestDeactivation:
    def test_session_and_token_stop_working_on_the_next_request(self, client, scim, alice, bound_store):
        client.get(LOGIN, params={"username": ALICE})
        assert client.get(PROTECTED).status_code == 200, "precondition: live session"
        assert client.get(PROTECTED, headers=alice).status_code == 200, "precondition: working token"

        response = client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)
        assert response.status_code == 200

        assert client.get(PROTECTED).status_code == 401
        assert client.get(PROTECTED, headers=alice).status_code == 401

    def test_the_token_itself_is_revoked_not_only_masked_by_active(self, client, scim, alice, bound_store):
        """``active`` is enforced by the middleware; the credential is revoked independently, so a
        later reactivation does not silently revive a token issued before deprovisioning."""
        client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)

        assert bound_store.authenticate_user(ALICE, USER_PASSWORD) is False
        client.patch(f"{USERS}/{ALICE}", headers=scim, json=REACTIVATE)
        assert bound_store.authenticate_user(ALICE, USER_PASSWORD) is False
        assert client.get(PROTECTED, headers=alice).status_code == 401

    def test_live_sessions_are_revoked_in_the_store(self, client, scim, alice, bound_store):
        sid = bound_store.create_auth_session(ALICE, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        assert bound_store.resolve_auth_session(sid) is not None

        client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)

        assert bound_store.resolve_auth_session(sid) is None

    def test_put_active_false_deactivates(self, client, scim, alice, bound_store):
        response = client.put(f"{USERS}/{ALICE}", headers=scim, json=user_body(ALICE, external_id="ext-alice", active=False))
        assert response.status_code == 200
        assert bound_store.get_user_detail(ALICE)["active"] is False
        assert client.get(PROTECTED, headers=alice).status_code == 401

    def test_audited_once_per_transition(self, client, scim, alice, audit_events):
        client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)
        client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)

        deactivated = events(audit_events, "user.deactivated")
        assert len(deactivated) == 1
        assert deactivated[0]["resource_id"] == ALICE
        assert deactivated[0]["detail"] == {"source": "scim"}
        assert deactivated[0]["actor"] == "scim:entra"


class TestReactivation:
    @pytest.mark.parametrize("verb", ["patch", "put"])
    def test_reasserting_inactive_does_not_touch_the_credential(self, client, scim, bound_store, monkeypatch, verb):
        """Only an active -> inactive transition revokes the credential. Re-sending active:false
        on an already-inactive row is a no-op: not a hash rewrite on every sync, and not a
        credential change the ownership guard would refuse on a row SCIM does not own."""
        from mlflow_oidc_auth.ownership import Enforcement

        bound_store.create_user("hand@example.com", "unused-secret", "Hand Made")
        bound_store.update_user("hand@example.com", active=False)
        with bound_store.ManagedSessionMaker() as session:
            from mlflow_oidc_auth.db.models import SqlUser

            before = session.query(SqlUser.password_hash).filter(SqlUser.username == "hand@example.com").scalar()
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        if verb == "patch":
            response = client.patch(f"{USERS}/hand@example.com", headers=scim, json=DEACTIVATE)
        else:
            response = client.put(f"{USERS}/hand@example.com", headers=scim, json=user_body("hand@example.com", active=False, display_name="Hand Made"))

        assert response.status_code == 200, response.text
        with bound_store.ManagedSessionMaker() as session:
            after = session.query(SqlUser.password_hash).filter(SqlUser.username == "hand@example.com").scalar()
        assert after == before

    def test_access_returns_and_grants_are_untouched(self, client, scim, alice, bound_store, audit_events):
        bound_store.create_experiment_permission("42", ALICE, "EDIT")
        bound_store.create_registered_model_permission("model-a", ALICE, "READ")
        before = (
            [(p.experiment_id, p.permission) for p in bound_store.list_experiment_permissions(ALICE)],
            [(p.name, p.permission) for p in bound_store.list_registered_model_permissions(ALICE)],
        )

        client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)
        response = client.patch(f"{USERS}/{ALICE}", headers=scim, json=REACTIVATE)

        assert response.status_code == 200 and response.json()["active"] is True
        after = (
            [(p.experiment_id, p.permission) for p in bound_store.list_experiment_permissions(ALICE)],
            [(p.name, p.permission) for p in bound_store.list_registered_model_permissions(ALICE)],
        )
        assert after == before

        # A fresh sign-in works again.
        client.get(LOGIN, params={"username": ALICE})
        assert client.get(PROTECTED).status_code == 200

        reactivated = events(audit_events, "user.reactivated")
        assert len(reactivated) == 1 and reactivated[0]["detail"] == {"source": "scim"}


class TestLastAdmin:
    def test_last_admin_is_refused_as_a_scim_error(self, client, scim, bound_store):
        """The fixture creates no other admin, so a SCIM-managed admin here is the only one."""
        client.post(USERS, headers=scim, json=user_body("boss@example.com"))
        bound_store.update_user("boss@example.com", is_admin=True, password=USER_PASSWORD, written_by="scim")

        response = client.patch(f"{USERS}/boss@example.com", headers=scim, json=DEACTIVATE)

        assert response.status_code == 400
        assert response.json()["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]
        assert "only active administrator" in response.json()["detail"]
        assert bound_store.get_user_detail("boss@example.com")["active"] is True
        assert bound_store.authenticate_user("boss@example.com", USER_PASSWORD) is True, "a refused deactivation must not rotate the token"

        delete = client.delete(f"{USERS}/boss@example.com", headers=scim)
        assert delete.status_code == 400
        assert bound_store.has_user("boss@example.com")


class TestOrphans:
    def test_sole_manager_resources_are_reported(self, client, scim, alice, bound_store, audit_events):
        bound_store.create_user("colleague@example.com", "unused-secret", "Colleague")
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")  # alice alone: orphaned
        bound_store.create_experiment_permission("2", ALICE, "MANAGE")  # co-managed: not orphaned
        bound_store.create_experiment_permission("2", "colleague@example.com", "MANAGE")
        bound_store.create_experiment_permission("3", ALICE, "EDIT")  # not a manager: not orphaned
        bound_store.create_registered_model_permission("model-a", ALICE, "MANAGE")  # orphaned
        bound_store.create_registered_model_permission("model-b", ALICE, "MANAGE")  # group-managed
        bound_store.populate_groups(["team"])
        bound_store.add_user_to_group("colleague@example.com", "team")
        bound_store.create_group_model_permission("team", "model-b", "MANAGE")

        response = client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)
        assert response.status_code == 200

        orphaned = {(e["resource_type"], e["resource_id"]) for e in events(audit_events, "resource.orphaned")}
        assert orphaned == {("experiment", "1"), ("registered_model", "model-a")}
        assert all(e["detail"]["user"] == ALICE and e["detail"]["source"] == "scim" for e in events(audit_events, "resource.orphaned"))

    def test_an_inactive_co_manager_does_not_count(self, client, scim, alice, bound_store, audit_events):
        bound_store.create_user("gone@example.com", "unused-secret", "Gone")
        bound_store.update_user("gone@example.com", active=False)
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")
        bound_store.create_experiment_permission("1", "gone@example.com", "MANAGE")

        client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)

        assert ("experiment", "1") in {(e["resource_type"], e["resource_id"]) for e in events(audit_events, "resource.orphaned")}

    def test_orphan_detection_failure_never_blocks_deprovisioning(self, client, scim, alice, bound_store, monkeypatch):
        def explode(*args, **kwargs):
            raise RuntimeError("orphan detection is down")

        monkeypatch.setattr(orphans, "find_orphaned_resources", explode)
        client.get(LOGIN, params={"username": ALICE})

        response = client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)

        assert response.status_code == 200
        assert bound_store.get_user_detail(ALICE)["active"] is False
        assert client.get(PROTECTED).status_code == 401

    def test_hard_delete_hands_orphans_to_the_fallback(self, client, scim, alice, bound_store, monkeypatch, audit_events):
        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")
        bound_store.create_experiment_permission("5", ALICE, "MANAGE")
        bound_store.create_experiment_permission("5", "steward@example.com", "READ")  # raised, not duplicated

        response = client.delete(f"{USERS}/{ALICE}", headers=scim)
        assert response.status_code == 204

        held = {p.experiment_id: p.permission for p in bound_store.list_experiment_permissions("steward@example.com")}
        assert held == {"1": "MANAGE", "5": "MANAGE"}
        transferred = [e for e in events(audit_events, "resource.orphaned") if e["detail"].get("transferred_to") == "steward@example.com"]
        assert len(transferred) == 2

    def test_deactivation_does_not_transfer(self, client, scim, alice, bound_store, monkeypatch):
        """A deactivated user may come back; their grants stay theirs."""
        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")

        client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)

        assert bound_store.list_experiment_permissions("steward@example.com") == []

    def test_transfer_failure_never_blocks_delete(self, client, scim, alice, bound_store, monkeypatch):
        def explode(*args, **kwargs):
            raise RuntimeError("transfer is down")

        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        monkeypatch.setattr(orphans, "_transfer_in_session", explode)
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")

        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        response = client.delete(f"{USERS}/{ALICE}", headers=scim)
        assert response.status_code == 204
        assert not bound_store.has_user(ALICE)
        assert bound_store.list_experiment_permissions("steward@example.com") == []


class TestHandoverIsPartOfTheDelete:
    def test_a_refused_delete_rolls_the_handover_back(self, client, scim, bound_store, monkeypatch, audit_events):
        """The only active admin cannot be deleted; the hand-over ran in the same transaction and
        must not survive the refusal."""
        client.post(USERS, headers=scim, json=user_body("boss@example.com"))
        bound_store.update_user("boss@example.com", is_admin=True, written_by="scim")
        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        bound_store.create_experiment_permission("1", "boss@example.com", "MANAGE")

        response = client.delete(f"{USERS}/boss@example.com", headers=scim)

        assert response.status_code == 400
        assert bound_store.has_user("boss@example.com")
        assert bound_store.list_experiment_permissions("steward@example.com") == []
        assert not events(audit_events, "resource.orphaned"), "nothing was orphaned: the user is still here"

    def test_a_failing_cascade_leaves_no_handover_behind(self, client, scim, alice, bound_store, monkeypatch):
        """On SQLite a savepoint opened before any write would itself begin (and its RELEASE
        commit) the transaction; the hand-over must not depend on that. A delete that fails in
        the cascade leaves the fallback with nothing."""
        from sqlalchemy import event

        from mlflow_oidc_auth.db.models import SqlUser

        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")

        def explode(mapper, connection, target):
            raise RuntimeError("cascade failed")

        event.listen(SqlUser, "before_delete", explode)
        try:
            with pytest.raises(Exception, match="cascade failed"):
                orphans.delete_user_reporting_orphans(ALICE, actor=ADMIN, source="test", store=bound_store)
        finally:
            event.remove(SqlUser, "before_delete", explode)

        assert bound_store.has_user(ALICE)
        assert bound_store.list_experiment_permissions("steward@example.com") == []
        assert [p.experiment_id for p in bound_store.list_experiment_permissions(ALICE)] == ["1"]

    @pytest.mark.parametrize("kind", ["service_account", "inactive", "missing", "self"])
    def test_an_unfit_fallback_is_skipped_without_blocking(self, client, scim, alice, bound_store, monkeypatch, audit_events, kind):
        fallback = {"service_account": "svc-bot", "inactive": "gone@example.com", "missing": "nobody@example.com", "self": ALICE}[kind]
        if kind == "service_account":
            bound_store.create_user("svc-bot", "unused-secret", "Bot", is_service_account=True)
        if kind == "inactive":
            bound_store.create_user("gone@example.com", "unused-secret", "Gone")
            bound_store.update_user("gone@example.com", active=False)
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", fallback)
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")

        response = client.delete(f"{USERS}/{ALICE}", headers=scim)
        assert response.status_code == 204

        assert not bound_store.has_user(ALICE)
        orphaned = events(audit_events, "resource.orphaned")
        assert [(e["resource_id"], "transferred_to" in e["detail"]) for e in orphaned] == [("1", False)]
        if kind in ("service_account", "inactive"):
            assert bound_store.list_experiment_permissions(fallback) == []


class TestSingleTransaction:
    def test_external_id_conflict_leaves_nothing_applied(self, client, scim, alice, bound_store, monkeypatch):
        """Beat the router's pre-check (a concurrent writer could) so the unique index is what
        refuses — and the deactivation, session revocation and token change in the same PATCH
        must roll back with it."""
        client.post(USERS, headers=scim, json=user_body("bob@example.com", external_id="ext-bob"))
        client.get(LOGIN, params={"username": ALICE})
        monkeypatch.setattr(bound_store, "get_username_by_external_id", lambda external_id: None)

        ops = patch_body({"op": "replace", "path": "active", "value": False}, {"op": "replace", "path": "externalId", "value": "ext-bob"})
        response = client.patch(f"{USERS}/{ALICE}", headers=scim, json=ops)

        assert response.status_code == 409
        detail = bound_store.get_user_detail(ALICE)
        assert (detail["active"], detail["external_id"]) == (True, "ext-alice")
        assert client.get(PROTECTED).status_code == 200, "the session was not revoked"
        assert client.get(PROTECTED, headers=alice).status_code == 200, "the token was not rotated"
