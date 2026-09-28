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


COLLEAGUE = "colleague@example.com"
REAL_EXPERIMENT_NAMES = orphans._experiment_names


def orphaned_events(audit_events):
    return {(e["resource_type"], e["resource_id"]): e["detail"] for e in events(audit_events, "resource.orphaned")}


class TestOrphansThroughGroupsAndRegex:
    """Issue #375: group-derived and regex MANAGE grants count, on both sides of the question."""

    @pytest.fixture(autouse=True)
    def mlflow_lookups(self, monkeypatch):
        """No tracking server here: registered models are models, experiment names unknown."""
        monkeypatch.setattr(orphans, "_prompt_kinds", lambda names: {n: {False} for n in names})
        monkeypatch.setattr(orphans, "_experiment_names", lambda ids: {})

    @pytest.fixture
    def colleague(self, bound_store):
        bound_store.create_user(COLLEAGUE, "unused-secret", "Colleague")
        return COLLEAGUE

    def deactivate(self, client, scim):
        response = client.patch(f"{USERS}/{ALICE}", headers=scim, json=DEACTIVATE)
        assert response.status_code == 200
        return response

    def test_direct_orphans_say_so(self, client, scim, alice, bound_store, audit_events):
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")

        self.deactivate(client, scim)

        assert orphaned_events(audit_events)[("experiment", "1")]["via"] == "direct"

    def test_a_user_regex_held_by_another_active_user_keeps_it_managed(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_registered_model_permission("team-model", ALICE, "MANAGE")
        bound_store.create_registered_model_permission("other-model", ALICE, "MANAGE")
        bound_store.create_registered_model_regex_permission("^team-", 1, "MANAGE", COLLEAGUE)

        self.deactivate(client, scim)

        assert set(orphaned_events(audit_events)) == {("registered_model", "other-model")}, "a pattern that does not match holds nothing"

    def test_a_group_regex_with_another_active_member_keeps_it_managed(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_gateway_endpoint_permission("ep-1", ALICE, "MANAGE")
        bound_store.populate_groups(["platform"])
        bound_store.add_user_to_group(COLLEAGUE, "platform")
        bound_store.create_group_gateway_endpoint_regex_permission("platform", "^ep-", 1, "MANAGE")

        self.deactivate(client, scim)

        assert orphaned_events(audit_events) == {}

    def test_a_group_regex_whose_only_other_member_is_inactive_holds_nothing(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_gateway_endpoint_permission("ep-1", ALICE, "MANAGE")
        bound_store.populate_groups(["platform"])
        bound_store.add_user_to_group(COLLEAGUE, "platform")
        bound_store.add_user_to_group(ALICE, "platform")
        bound_store.create_group_gateway_endpoint_regex_permission("platform", "^ep-", 1, "MANAGE")
        bound_store.update_user(COLLEAGUE, active=False)

        self.deactivate(client, scim)

        assert set(orphaned_events(audit_events)) == {("gateway_endpoint", "ep-1")}

    @pytest.mark.parametrize("holder", ["inactive", "shadowed", "not-manage"])
    def test_a_regex_that_does_not_resolve_to_manage_holds_nothing(self, client, scim, alice, colleague, bound_store, audit_events, holder):
        bound_store.create_gateway_secret_permission("key-1", ALICE, "MANAGE")
        if holder == "inactive":
            bound_store.create_gateway_secret_regex_permission("^key-", 1, "MANAGE", COLLEAGUE)
            bound_store.update_user(COLLEAGUE, active=False)
        elif holder == "shadowed":
            # The resolver takes the best-priority match: READ at priority 1 wins over MANAGE at 2.
            bound_store.create_gateway_secret_regex_permission("^key-", 1, "READ", COLLEAGUE)
            bound_store.create_gateway_secret_regex_permission("^key-1$", 2, "MANAGE", COLLEAGUE)
        else:
            bound_store.create_gateway_secret_regex_permission("^key-", 1, "EDIT", COLLEAGUE)

        self.deactivate(client, scim)

        assert set(orphaned_events(audit_events)) == {("gateway_secret", "key-1")}

    @pytest.mark.parametrize(
        "order, orphaned",
        [(["user", "group", "regex", "group-regex"], True), (["regex", "group-regex", "user", "group"], False)],
    )
    def test_a_direct_grant_the_resolver_reaches_first_shadows_a_manage_pattern(
        self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch, order, orphaned
    ):
        """The colleague's READ grant decides their permission when ``user`` comes first, so their
        MANAGE pattern does not make them a holder; with patterns first, it does."""
        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", order)
        bound_store.create_registered_model_permission("fraud-v2", ALICE, "MANAGE")
        bound_store.create_registered_model_permission("fraud-v2", COLLEAGUE, "READ")
        bound_store.create_registered_model_regex_permission("^fraud-", 1, "MANAGE", COLLEAGUE)

        self.deactivate(client, scim)

        assert (("registered_model", "fraud-v2") in orphaned_events(audit_events)) is orphaned

    def test_a_group_grant_the_resolver_reaches_first_shadows_a_group_pattern(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_gateway_endpoint_permission("ep-1", ALICE, "MANAGE")
        bound_store.populate_groups(["readers", "platform"])
        bound_store.add_user_to_group(COLLEAGUE, "readers")
        bound_store.add_user_to_group(COLLEAGUE, "platform")
        bound_store.create_group_gateway_endpoint_permission("readers", "ep-1", "READ")
        bound_store.create_group_gateway_endpoint_regex_permission("platform", "^ep-", 1, "MANAGE")

        self.deactivate(client, scim)

        assert set(orphaned_events(audit_events)) == {("gateway_endpoint", "ep-1")}

    def test_scorer_patterns_match_the_scorer_name(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_scorer_permission("7", "quality", ALICE, "MANAGE")
        bound_store.create_scorer_permission("7", "latency", ALICE, "MANAGE")
        bound_store.create_scorer_regex_permission("^qual", 1, "MANAGE", COLLEAGUE)

        self.deactivate(client, scim)

        assert set(orphaned_events(audit_events)) == {("scorer", "7/latency")}

    def test_workspace_regex_grants_count(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_workspace_permission("team-a", ALICE, "MANAGE")
        bound_store.create_workspace_permission("solo", ALICE, "MANAGE")
        bound_store.create_workspace_regex_permission("^team-", 1, "MANAGE", COLLEAGUE)

        self.deactivate(client, scim)

        assert set(orphaned_events(audit_events)) == {("workspace", "solo")}

    def test_experiment_patterns_match_the_experiment_name(self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch):
        """Only the tracking store knows an experiment's name; an id it cannot resolve is reported as unresolved."""
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")
        bound_store.create_experiment_permission("2", ALICE, "MANAGE")
        bound_store.create_experiment_permission("3", ALICE, "MANAGE")
        bound_store.create_experiment_regex_permission("^team/", 1, "MANAGE", COLLEAGUE)
        monkeypatch.setattr(orphans, "_experiment_names", lambda ids: {k: v for k, v in {"1": "team/churn", "2": "personal/scratch"}.items() if k in ids})

        self.deactivate(client, scim)

        found = orphaned_events(audit_events)
        assert set(found) == {("experiment", "2"), ("experiment", "3")}
        assert (found[("experiment", "2")]["via"], found[("experiment", "3")]["via"]) == ("direct", "unresolved")

    @pytest.mark.parametrize("is_prompt, orphaned", [(True, False), (False, True)])
    def test_prompt_patterns_apply_only_to_prompts(self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch, is_prompt, orphaned):
        bound_store.create_registered_model_permission("summarize", ALICE, "MANAGE")
        bound_store.create_prompt_regex_permission("^sum", 1, "MANAGE", COLLEAGUE)
        monkeypatch.setattr(orphans, "_prompt_kinds", lambda names: {n: {is_prompt} for n in names})

        self.deactivate(client, scim)

        assert (("registered_model", "summarize") in orphaned_events(audit_events)) is orphaned

    def test_an_unresolvable_prompt_flag_is_reported_not_assumed_held(self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch):
        bound_store.create_registered_model_permission("summarize", ALICE, "MANAGE")
        bound_store.create_prompt_regex_permission("^sum", 1, "MANAGE", COLLEAGUE)
        monkeypatch.setattr(orphans, "_prompt_kinds", lambda names: {})

        self.deactivate(client, scim)

        assert orphaned_events(audit_events)[("registered_model", "summarize")]["via"] == "unresolved"

    def test_a_name_that_is_a_model_and_a_prompt_must_be_held_as_both(self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch):
        """Grants are keyed by name; in different workspaces the name can be both kinds."""
        bound_store.create_registered_model_permission("summarize", ALICE, "MANAGE")
        bound_store.create_prompt_regex_permission("^sum", 1, "MANAGE", COLLEAGUE)
        monkeypatch.setattr(orphans, "_prompt_kinds", lambda names: {n: {True, False} for n in names})

        self.deactivate(client, scim)

        assert orphaned_events(audit_events)[("registered_model", "summarize")]["via"] == "direct"

    def test_last_active_member_of_the_managing_group_orphans_it(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.populate_groups(["solo-team"])
        bound_store.add_user_to_group(ALICE, "solo-team")
        bound_store.create_group_model_permission("solo-team", "model-g", "MANAGE")

        self.deactivate(client, scim)

        assert orphaned_events(audit_events)[("registered_model", "model-g")]["via"] == "group:solo-team"

    @pytest.mark.parametrize("other_member_active, orphaned", [(True, False), (False, True)])
    def test_group_held_depends_on_another_active_member(self, client, scim, alice, colleague, bound_store, audit_events, other_member_active, orphaned):
        bound_store.populate_groups(["team"])
        bound_store.add_user_to_group(ALICE, "team")
        bound_store.add_user_to_group(COLLEAGUE, "team")
        bound_store.create_group_experiment_permission("team", "9", "MANAGE")
        if not other_member_active:
            bound_store.update_user(COLLEAGUE, active=False)

        self.deactivate(client, scim)

        found = orphaned_events(audit_events)
        assert (("experiment", "9") in found) is orphaned
        if orphaned:
            assert found[("experiment", "9")]["via"] == "group:team"

    def test_direct_and_a_group_with_another_active_member_is_not_orphaned(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_experiment_permission("9", ALICE, "MANAGE")
        bound_store.populate_groups(["team"])
        bound_store.add_user_to_group(ALICE, "team")
        bound_store.add_user_to_group(COLLEAGUE, "team")
        bound_store.create_group_experiment_permission("team", "9", "MANAGE")

        self.deactivate(client, scim)

        assert orphaned_events(audit_events) == {}

    def test_a_direct_read_shadows_a_managing_group(self, client, scim, alice, colleague, bound_store, audit_events):
        """Under the default order the colleague resolves to their direct READ, not the group's
        MANAGE, so nobody can manage experiment 9 once Alice leaves."""
        bound_store.create_experiment_permission("9", ALICE, "MANAGE")
        bound_store.create_experiment_permission("9", COLLEAGUE, "READ")
        bound_store.populate_groups(["team"])
        bound_store.add_user_to_group(COLLEAGUE, "team")
        bound_store.create_group_experiment_permission("team", "9", "MANAGE")

        self.deactivate(client, scim)

        assert orphaned_events(audit_events)[("experiment", "9")]["via"] == "direct"

    def test_a_direct_manage_shadows_a_reading_group(self, client, scim, alice, colleague, bound_store, audit_events):
        bound_store.create_experiment_permission("9", ALICE, "MANAGE")
        bound_store.create_experiment_permission("9", COLLEAGUE, "MANAGE")
        bound_store.populate_groups(["team"])
        bound_store.add_user_to_group(COLLEAGUE, "team")
        bound_store.create_group_experiment_permission("team", "9", "READ")

        self.deactivate(client, scim)

        assert orphaned_events(audit_events) == {}

    def test_group_order_first_lets_a_managing_group_win_over_a_direct_read(self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch):
        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["group", "user", "regex", "group-regex"])
        bound_store.create_experiment_permission("9", ALICE, "MANAGE")
        bound_store.create_experiment_permission("9", COLLEAGUE, "READ")
        bound_store.populate_groups(["team"])
        bound_store.add_user_to_group(COLLEAGUE, "team")
        bound_store.create_group_experiment_permission("team", "9", "MANAGE")

        self.deactivate(client, scim)

        assert orphaned_events(audit_events) == {}

    def test_hard_delete_hands_a_group_only_orphan_to_the_fallback(self, client, scim, alice, bound_store, monkeypatch, audit_events):
        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        bound_store.populate_groups(["solo-team"])
        bound_store.add_user_to_group(ALICE, "solo-team")
        bound_store.create_group_experiment_permission("solo-team", "4", "MANAGE")

        response = client.delete(f"{USERS}/{ALICE}", headers=scim)
        assert response.status_code == 204

        assert {p.experiment_id: p.permission for p in bound_store.list_experiment_permissions("steward@example.com")} == {"4": "MANAGE"}
        detail = orphaned_events(audit_events)[("experiment", "4")]
        assert detail["via"] == "group:solo-team" and detail["transferred_to"] == "steward@example.com"

    def test_a_foreign_workspace_experiment_is_found_and_stays_held(self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch):
        """With workspaces on, the tracking store only sees the active workspace; the lookup must
        try each workspace rather than call a foreign experiment orphaned."""
        from types import SimpleNamespace
        from unittest.mock import patch

        from mlflow.exceptions import MlflowException
        from mlflow.utils.workspace_context import get_request_workspace

        def get_experiment(experiment_id):
            if get_request_workspace() != "tenant-b":
                raise MlflowException("No Experiment exists")
            return SimpleNamespace(name="team/churn")

        monkeypatch.setattr(orphans, "_experiment_names", REAL_EXPERIMENT_NAMES)  # exercise the real lookup
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")
        bound_store.create_experiment_regex_permission("^team/", 1, "MANAGE", COLLEAGUE)
        workspaces = SimpleNamespace(list_workspaces=lambda: [SimpleNamespace(name="default"), SimpleNamespace(name="tenant-b")])
        with (
            patch("mlflow.server.handlers._get_workspace_store", return_value=workspaces),
            patch("mlflow.server.handlers._get_tracking_store", return_value=SimpleNamespace(get_experiment=get_experiment)),
        ):
            self.deactivate(client, scim)

        assert orphaned_events(audit_events) == {}

    def test_an_unresolvable_experiment_is_reported_never_handed_over_and_warned(
        self, client, scim, alice, colleague, bound_store, audit_events, monkeypatch, caplog
    ):
        import logging
        from types import SimpleNamespace
        from unittest.mock import patch

        from mlflow.exceptions import MlflowException

        def get_experiment(experiment_id):
            raise MlflowException("No Experiment exists in the active workspace")

        monkeypatch.setattr(orphans, "_experiment_names", REAL_EXPERIMENT_NAMES)  # exercise the real lookup
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")  # regex-held, but unresolvable
        bound_store.create_registered_model_permission("model-z", ALICE, "MANAGE")  # nobody else: a plain orphan
        bound_store.create_experiment_regex_permission("^team/", 1, "MANAGE", COLLEAGUE)
        workspaces = SimpleNamespace(list_workspaces=lambda: [SimpleNamespace(name="default"), SimpleNamespace(name="tenant-b")])
        with (
            patch("mlflow.server.handlers._get_workspace_store", return_value=workspaces),
            patch("mlflow.server.handlers._get_tracking_store", return_value=SimpleNamespace(get_experiment=get_experiment)),
            caplog.at_level(logging.WARNING, logger=orphans.logger.name),
        ):
            response = client.delete(f"{USERS}/{ALICE}", headers=scim)
            assert response.status_code == 204

        found = orphaned_events(audit_events)
        assert found[("experiment", "1")]["via"] == "unresolved" and "transferred_to" not in found[("experiment", "1")]
        assert found[("registered_model", "model-z")]["transferred_to"] == "steward@example.com"
        assert bound_store.list_experiment_permissions("steward@example.com") == []
        assert [p.name for p in bound_store.list_registered_model_permissions("steward@example.com")] == ["model-z"]
        assert any("unresolved" in r.getMessage() and r.levelno >= logging.WARNING for r in caplog.records)

    def test_regex_failure_never_blocks_deactivation(self, client, scim, alice, colleague, bound_store, monkeypatch, audit_events):
        def explode(*args, **kwargs):
            raise RuntimeError("regex resolution is down")

        monkeypatch.setattr(orphans, "_judge_all", explode)
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")
        client.get(LOGIN, params={"username": ALICE})

        self.deactivate(client, scim)

        assert bound_store.get_user_detail(ALICE)["active"] is False
        assert client.get(PROTECTED).status_code == 401
        assert orphaned_events(audit_events) == {}, "a failed check reports nothing rather than something wrong"

    def test_regex_failure_never_blocks_delete_nor_hands_anything_over(self, client, scim, alice, bound_store, monkeypatch, audit_events):
        def explode(*args, **kwargs):
            raise RuntimeError("regex resolution is down")

        bound_store.create_user("steward@example.com", "unused-secret", "Steward")
        monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", "steward@example.com")
        monkeypatch.setattr(orphans, "_judge_all", explode)
        bound_store.create_experiment_permission("1", ALICE, "MANAGE")

        response = client.delete(f"{USERS}/{ALICE}", headers=scim)
        assert response.status_code == 204

        assert not bound_store.has_user(ALICE)
        assert bound_store.list_experiment_permissions("steward@example.com") == []
        assert orphaned_events(audit_events) == {}

    def test_statement_count_does_not_grow_with_resources(self, bound_store, monkeypatch):
        """Deactivation-time only, but still bounded: statements per run are independent of how
        many resources, grants and patterns there are."""
        from sqlalchemy import event

        monkeypatch.setattr(orphans, "_experiment_names", lambda ids: {i: f"exp-{i}" for i in ids})
        bound_store.create_user(ALICE, "unused-secret", "Alice")
        bound_store.create_user(COLLEAGUE, "unused-secret", "Colleague")
        bound_store.populate_groups(["team", "solo"])
        bound_store.add_user_to_group(COLLEAGUE, "team")
        bound_store.add_user_to_group(ALICE, "solo")
        bound_store.create_experiment_regex_permission("^exp-5$", 1, "MANAGE", COLLEAGUE)
        bound_store.create_group_experiment_regex_permission("team", "^exp-6$", 1, "MANAGE")

        def count(n_start, n):
            for i in range(n_start, n_start + n):
                bound_store.create_experiment_permission(str(i), ALICE, "MANAGE")
                bound_store.create_group_experiment_permission("solo", str(1000 + i), "MANAGE")
            statements = []
            listener = lambda *args, **kwargs: statements.append(1)  # noqa: E731
            event.listen(bound_store.engine, "before_cursor_execute", listener)
            try:
                found = orphans.find_orphaned_resources(ALICE, store=bound_store)
            finally:
                event.remove(bound_store.engine, "before_cursor_execute", listener)
            return len(statements), found

        few, found_few = count(10, 3)
        many, found_many = count(100, 40)
        assert found_many and len(found_many) > len(found_few)
        assert many == few


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
