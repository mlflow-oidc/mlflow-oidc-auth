"""Group → workspace rules (issue #418) against the real store, through the callers.

Groups arrive through SCIM, the admin API and a login; each is driven through its real entry point
with the real ``AuthMiddleware`` and a SQLite store, so these tests show a rule firing where groups
actually arrive — not just that the engine works when called. MLflow's workspace store is the one
stub: a set of workspace names that exist.

The failure modes pinned here are the issue's: a rule overwriting or removing a manual grant, a
partner provider's group matching a tenant's rule, and a rule that fails taking a login with it.
"""

import json
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth import audit, workspace_rules
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.exceptions import register_exception_handlers
from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.ownership import Enforcement
from mlflow_oidc_auth.provider_registry import ProviderConfig
from mlflow_oidc_auth.tests.scim.conftest import basic
from mlflow_oidc_auth.tests.token_helpers import set_known_token

ADMIN = "rules-admin@example.com"
ADMIN_PASSWORD = "rules-suite-admin"  # not a credential: only ever seeded into a tmp_path database
ALICE = "alice@example.com"
RULES = "/api/3.0/mlflow/workspace-rules"
GROUPS = "/api/2.0/mlflow/permissions/groups"
SCIM_GROUPS = "/scim/v2/Groups"
WORKSPACES = {"acme", "beta", "gamma", "default"}
TENANT_PATTERN = r"^team-(?P<ws>[a-z0-9-]+)$"


class _WorkspaceStore:
    """MLflow's workspace store, reduced to the one call rules make."""

    def __init__(self, names):
        self.names = set(names)

    def get_workspace(self, name):
        if name not in self.names:
            raise MlflowException(f"Workspace '{name}' not found", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(name=name)


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils import workspace_cache

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "EDIT")
    monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.REPORT)
    monkeypatch.setattr(config, "OIDC_GROUP_NAME", ["mlflow-users"])
    monkeypatch.setattr(config, "OIDC_ADMIN_GROUP_NAME", ["mlflow-admins"])
    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ADMIN, "Admin", is_admin=True)
    set_known_token(s, ADMIN, ADMIN_PASSWORD)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    workspace_cache.flush_workspace_cache()
    yield s
    workspace_cache.flush_workspace_cache()
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture(autouse=True)
def mlflow_workspaces(monkeypatch):
    from mlflow.server import handlers

    ws_store = _WorkspaceStore(WORKSPACES)
    monkeypatch.setattr(handlers, "_get_workspace_store", lambda *a, **k: ws_store)
    return ws_store


@pytest.fixture
def audit_events():
    records = []

    class _Collector(logging.Handler):
        def emit(self, record):
            records.append(json.loads(record.getMessage()))

    logger = audit._get_audit_logger()
    handler = _Collector(level=logging.DEBUG)
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)


@pytest.fixture
def client(store):
    from mlflow_oidc_auth.dependencies import scim_rate_limiter
    from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
    from mlflow_oidc_auth.routers.scim import scim_router
    from mlflow_oidc_auth.routers.workspace_permissions import workspace_permissions_router
    from mlflow_oidc_auth.routers.workspace_rules import workspace_rules_router

    scim_rate_limiter.reset()
    application = FastAPI()
    register_exception_handlers(application)
    for router in (scim_router, group_permissions_router, workspace_permissions_router, workspace_rules_router):
        application.include_router(router)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    with TestClient(application) as c:
        c.headers.update(basic(ADMIN, ADMIN_PASSWORD))
        yield c


@pytest.fixture
def scim(store):
    _, plaintext = store.create_scim_token("entra", created_by=ADMIN)
    return {"Authorization": f"Bearer {plaintext}", "Content-Type": "application/scim+json"}


def create_rule(client, *, name="tenants", pattern=TENANT_PATTERN, permission="EDIT", mode="enforce", enabled=True):
    response = client.post(RULES, json={"name": name, "pattern": pattern, "permission": permission, "mode": mode, "enabled": enabled})
    assert response.status_code == 201, response.text
    return response.json()


def group_body_minimal(name: str) -> dict:
    return {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"], "displayName": name}


def grants(store) -> dict:
    """``{(workspace, group): (permission, rule_id)}`` read straight from the table."""
    from mlflow_oidc_auth.db.models import SqlGroup, SqlWorkspaceGroupPermission

    with store.ManagedSessionMaker() as session:
        rows = (
            session.query(
                SqlWorkspaceGroupPermission.workspace, SqlGroup.group_name, SqlWorkspaceGroupPermission.permission, SqlWorkspaceGroupPermission.rule_id
            )
            .join(SqlGroup, SqlGroup.id == SqlWorkspaceGroupPermission.group_id)
            .all()
        )
        return {(w, g): (p, r) for w, g, p, r in rows}


def provider(provider_id="default", **overrides):
    fields = {
        "id": provider_id,
        "type": "oidc",
        "audience": "mlflow",
        "issuer": "https://idp.invalid",
        "provisioning": "jit",
        "group_sync": "every_login",
        "group_sync_mode": "authoritative",
        "admin_source": "claims" if provider_id == "default" else "none",
    }
    fields.update(overrides)
    return ProviderConfig(**fields)


def login(username, groups, *, prov=None):
    """Drive the real login path shared by the OIDC callback and the SAML ACS."""
    from mlflow_oidc_auth.routers.auth import _provision_login

    prov = prov or provider()
    userinfo = {"email": username}
    if prov.id != "default":
        userinfo["sub"] = f"sub-{username}"
    return _provision_login(prov, username=username, display_name="Alice", userinfo=userinfo, user_groups=list(groups), access_token=None, method="oidc")


def events(audit_events, name):
    return [e for e in audit_events if e["event"] == name]


class TestWhereGroupsArrive:
    def test_scim_created_group_matching_rule_gets_workspace_permission(self, client, store, scim):
        rule = create_rule(client)["rule"]

        response = client.post(SCIM_GROUPS, headers=scim, json=group_body_minimal("team-acme"))

        assert response.status_code == 201, response.text
        assert grants(store) == {("acme", "team-acme"): ("EDIT", rule["id"])}

    def test_login_synced_group_gets_permission(self, client, store):
        rule = create_rule(client)["rule"]

        username, errors = login(ALICE, ["mlflow-users", "team-beta"])

        assert (username, errors) == (ALICE, [])
        assert grants(store) == {("beta", "team-beta"): ("EDIT", rule["id"])}
        assert store.get_user_groups_workspace_permission("beta", ALICE).permission == "EDIT"

    def test_login_applies_rules_only_to_groups_it_created(self, client, store):
        store.populate_groups(["team-acme"])
        rule_id = create_rule(client)["rule"]["id"]
        # The backfill granted team-acme; the admin removes that grant by hand. A later login that
        # merely mentions the existing group must not re-apply the rule to it.
        store.delete_workspace_group_permission("acme", "team-acme")

        login(ALICE, ["mlflow-users", "team-acme", "team-gamma"])

        assert grants(store) == {("gamma", "team-gamma"): ("EDIT", rule_id)}

    def test_admin_created_group_gets_permission(self, client, store):
        rule = create_rule(client, permission="USE")["rule"]

        response = client.post(GROUPS, json={"group_name": "team-gamma"})

        assert response.status_code == 201, response.text
        assert grants(store) == {("gamma", "team-gamma"): ("USE", rule["id"])}

    def test_non_default_provider_group_matched_on_namespaced_name(self, client, store):
        """A partner provider asserting ``team-acme`` arrives as ``partner:team-acme``: the tenant's
        rule must not match it, and only a rule written for the partner's namespace does."""
        create_rule(client)
        partner = provider("partner")

        username, errors = login(ALICE, ["mlflow-users", "team-acme"], prov=partner)

        assert (username, errors) == (ALICE, [])
        assert "partner:team-acme" in store.get_groups()
        assert grants(store) == {}, "a partner's group matched a rule written for the deployment's own names"

        partner_rule = create_rule(client, name="partner-tenants", pattern=r"^partner:team-(?P<ws>[a-z0-9-]+)$", permission="READ")["rule"]
        assert grants(store) == {("acme", "partner:team-acme"): ("READ", partner_rule["id"])}

    def test_engine_failure_does_not_fail_login(self, client, store, monkeypatch, audit_events):
        create_rule(client)

        def boom(*args, **kwargs):
            raise RuntimeError("database went away")

        monkeypatch.setattr(store, "reconcile_workspace_group_rule", boom)

        username, errors = login(ALICE, ["mlflow-users", "team-acme"])

        assert (username, errors) == (ALICE, []), "a rule failure must never refuse the login"
        assert "team-acme" in store.get_groups_for_user(ALICE)
        assert grants(store) == {}
        [failed] = events(audit_events, "workspace_rule.failed")
        assert failed["actor"] == "oidc:default" and failed["detail"]["groups"] == ["mlflow-users", "team-acme"]

    def test_engine_failure_does_not_fail_scim(self, client, store, scim, monkeypatch):
        create_rule(client)
        monkeypatch.setattr(store, "list_workspace_group_rules", lambda **kw: (_ for _ in ()).throw(RuntimeError("down")))

        response = client.post(SCIM_GROUPS, headers=scim, json=group_body_minimal("team-acme"))

        assert response.status_code == 201
        assert grants(store) == {}

    def test_nothing_runs_with_workspaces_disabled(self, client, store, monkeypatch):
        create_rule(client)
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)

        login(ALICE, ["mlflow-users", "team-acme"])

        assert grants(store) == {}


class TestBackfillAndModes:
    def test_backfill_on_rule_create(self, client, store):
        store.populate_groups(["team-acme", "team-beta", "unrelated"])

        body = create_rule(client)

        rule_id = body["rule"]["id"]
        assert grants(store) == {("acme", "team-acme"): ("EDIT", rule_id), ("beta", "team-beta"): ("EDIT", rule_id)}
        assert [(c["action"], c["group"], c["applied"]) for c in body["changes"]] == [("grant", "team-acme", True), ("grant", "team-beta", True)]

    def test_report_mode_writes_nothing(self, client, store, scim):
        store.populate_groups(["team-acme"])

        body = create_rule(client, mode="report")
        client.post(SCIM_GROUPS, headers=scim, json=group_body_minimal("team-beta"))
        login(ALICE, ["mlflow-users", "team-gamma"])

        assert grants(store) == {}
        assert [(c["action"], c["workspace"], c["applied"]) for c in body["changes"]] == [("grant", "acme", False)]

    def test_switching_to_enforce_backfills_and_back_to_report_removes(self, client, store):
        store.populate_groups(["team-acme"])
        rule_id = create_rule(client, mode="report")["rule"]["id"]

        client.patch(f"{RULES}/{rule_id}", json={"mode": "enforce"})
        assert grants(store) == {("acme", "team-acme"): ("EDIT", rule_id)}

        body = client.patch(f"{RULES}/{rule_id}", json={"mode": "report"}).json()
        assert grants(store) == {}
        assert ("remove", "team-acme", True) in [(c["action"], c["group"], c["applied"]) for c in body["changes"]]

    def test_narrowing_a_pattern_removes_what_it_no_longer_matches(self, client, store):
        store.populate_groups(["team-acme", "team-beta"])
        rule_id = create_rule(client)["rule"]["id"]

        client.patch(f"{RULES}/{rule_id}", json={"pattern": r"^team-(?P<ws>acme)$", "permission": "READ"})

        assert grants(store) == {("acme", "team-acme"): ("READ", rule_id)}

    def test_missing_workspace_is_skipped_and_reported(self, client, store, audit_events):
        store.populate_groups(["team-nowhere", "team-acme"])

        body = create_rule(client)

        assert ("acme", "team-acme") in grants(store)
        assert ("nowhere", "team-nowhere") not in grants(store)
        skipped = [c for c in body["changes"] if c["group"] == "team-nowhere"]
        assert skipped == [
            {
                "action": "skip",
                "group": "team-nowhere",
                "workspace": "nowhere",
                "permission": "EDIT",
                "reason": "workspace does not exist",
                "previous": None,
                "applied": False,
                "rule_id": body["rule"]["id"],
            }
        ]
        [event] = events(audit_events, "workspace_rule.skipped")
        assert event["detail"] == {
            "rule_id": body["rule"]["id"],
            "workspace": "nowhere",
            "group": "team-nowhere",
            "permission": "EDIT",
            "reason": "workspace does not exist",
        }

    def test_lowering_the_ceiling_stops_an_over_ceiling_rule(self, client, store, monkeypatch):
        rule_id = create_rule(client, permission="EDIT")["rule"]["id"]
        monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "READ")

        client.post(GROUPS, json={"group_name": "team-acme"})

        assert grants(store) == {}
        [line] = client.get(f"{RULES}/{rule_id}/preview").json()["changes"]
        assert (line["action"], line["reason"]) == ("skip", "permission above WORKSPACE_RULES_MAX_PERMISSION")


class TestOwnership:
    def test_manual_grant_is_never_overwritten(self, client, store, audit_events):
        store.populate_groups(["team-acme"])
        store.create_workspace_group_permission("acme", "team-acme", "READ")

        body = create_rule(client, permission="EDIT")
        rule_id = body["rule"]["id"]

        assert grants(store) == {("acme", "team-acme"): ("READ", None)}
        assert [(c["action"], c["reason"]) for c in body["changes"]] == [("skip", "manual grant")]
        assert [e["detail"]["reason"] for e in events(audit_events, "workspace_rule.skipped")] == ["manual grant"]

        client.patch(f"{RULES}/{rule_id}", json={"enabled": False})
        client.delete(f"{RULES}/{rule_id}")
        assert grants(store) == {("acme", "team-acme"): ("READ", None)}, "removing the rule touched a manual grant"

    def test_admin_edit_turns_rule_grant_manual(self, client, store):
        store.populate_groups(["team-acme"])
        rule_id = create_rule(client)["rule"]["id"]
        assert grants(store) == {("acme", "team-acme"): ("EDIT", rule_id)}

        response = client.patch("/api/3.0/mlflow/permissions/workspaces/acme/groups/team-acme", json={"group_name": "team-acme", "permission": "READ"})
        assert response.status_code == 200, response.text
        assert grants(store) == {("acme", "team-acme"): ("READ", None)}

        client.delete(f"{RULES}/{rule_id}")
        assert grants(store) == {("acme", "team-acme"): ("READ", None)}

    def test_delete_rule_removes_only_its_grants(self, client, store, audit_events):
        store.populate_groups(["team-acme", "team-beta", "ops-gamma", "manual-beta"])
        store.create_workspace_group_permission("beta", "manual-beta", "USE")
        tenants = create_rule(client)["rule"]["id"]
        ops = create_rule(client, name="ops", pattern=r"^ops-(?P<ws>.+)$", permission="READ")["rule"]["id"]

        response = client.delete(f"{RULES}/{tenants}")

        assert response.status_code == 200
        assert grants(store) == {("gamma", "ops-gamma"): ("READ", ops), ("beta", "manual-beta"): ("USE", None)}
        assert sorted((c["group"], c["action"]) for c in response.json()["changes"]) == [("team-acme", "remove"), ("team-beta", "remove")]
        result = client.get(f"{RULES}/{tenants}")
        assert result.status_code == 404

    def test_disable_rule_removes_only_its_grants(self, client, store):
        store.populate_groups(["team-acme", "ops-gamma", "manual-beta"])
        store.create_workspace_group_permission("beta", "manual-beta", "USE")
        tenants = create_rule(client)["rule"]["id"]
        ops = create_rule(client, name="ops", pattern=r"^ops-(?P<ws>.+)$", permission="READ")["rule"]["id"]

        response = client.patch(f"{RULES}/{tenants}", json={"enabled": False})

        assert response.status_code == 200
        assert grants(store) == {("gamma", "ops-gamma"): ("READ", ops), ("beta", "manual-beta"): ("USE", None)}

        client.patch(f"{RULES}/{tenants}", json={"enabled": True})
        assert grants(store)[("acme", "team-acme")] == ("EDIT", tenants), "re-enabling backfills"

    def test_lowest_id_rule_wins_and_other_is_shadowed(self, client, store, scim):
        first = create_rule(client, name="first", pattern=r"^team-(?P<ws>[a-z]+)$", permission="READ")["rule"]["id"]
        second = create_rule(client, name="second", pattern=r"^(?:team|squad)-(?P<ws>[a-z]+)$", permission="EDIT")["rule"]["id"]

        client.post(SCIM_GROUPS, headers=scim, json=group_body_minimal("team-acme"))
        client.post(SCIM_GROUPS, headers=scim, json=group_body_minimal("squad-beta"))

        assert grants(store) == {("acme", "team-acme"): ("READ", first), ("beta", "squad-beta"): ("EDIT", second)}
        lines = {c["group"]: c for c in client.get(f"{RULES}/{second}/preview").json()["changes"]}
        assert lines["team-acme"]["action"] == "shadowed" and lines["team-acme"]["reason"].startswith(f"rule {first} ")
        assert lines["squad-beta"]["action"] == "keep"

        # Deleting the winner removes its grant, and the rule it shadowed takes the group over.
        body = client.delete(f"{RULES}/{first}").json()
        assert grants(store) == {("acme", "team-acme"): ("EDIT", second), ("beta", "squad-beta"): ("EDIT", second)}
        assert [(c["action"], c["group"], c["rule_id"]) for c in body["changes"]] == [("remove", "team-acme", first), ("grant", "team-acme", second)]

    def test_a_lower_id_rule_enabled_later_takes_over_and_hands_back(self, client, store):
        """Rule 1 was in report mode when rule 2 granted; enforcing rule 1 must win (decision 4),
        and disabling it again must not leave the group with nothing."""
        store.populate_groups(["team-acme"])
        first = create_rule(client, name="first", permission="READ", mode="report")["rule"]["id"]
        second = create_rule(client, name="second", permission="EDIT")["rule"]["id"]
        assert grants(store) == {("acme", "team-acme"): ("EDIT", second)}

        body = client.patch(f"{RULES}/{first}", json={"mode": "enforce"}).json()
        assert grants(store) == {("acme", "team-acme"): ("READ", first)}
        assert ("remove", second) in [(c["action"], c["rule_id"]) for c in body["changes"]]

        client.patch(f"{RULES}/{first}", json={"enabled": False})
        assert grants(store) == {("acme", "team-acme"): ("EDIT", second)}


class TestHardening:
    """Regressions from the security review of #418."""

    def test_unprefixed_group_from_a_non_default_provider_is_never_matched(self, client, store):
        """However a partner provider's group came to exist, a name it chose outside its own
        ``<id>:`` namespace is not something a rule may trust."""
        store.populate_groups(["team-acme"], written_by="oidc:partner")
        store.populate_groups(["team-beta"], written_by="scim")
        store.populate_groups(["partner:team-gamma"], written_by="oidc:partner")
        tenants = create_rule(client)
        partner = create_rule(client, name="partner", pattern=r"^partner:team-(?P<ws>[a-z]+)$", permission="READ")

        assert grants(store) == {("beta", "team-beta"): ("EDIT", tenants["rule"]["id"]), ("gamma", "partner:team-gamma"): ("READ", partner["rule"]["id"])}
        assert "team-acme" not in {c["group"] for c in tenants["changes"]}

        # Nor on arrival.
        store.populate_groups(["team-delta"], written_by="saml:partner")
        result = workspace_rules.apply_rules_for_groups(["team-delta"], source="saml:partner")
        assert result == []

    def test_the_default_workspace_is_never_granted(self, client, store):
        store.populate_groups(["team-default"])

        body = create_rule(client)

        assert grants(store) == {}
        assert [(c["action"], c["reason"]) for c in body["changes"]] == [("skip", "the default workspace is never granted by a rule")]

    def test_lowering_the_ceiling_removes_existing_grants_at_startup(self, client, store, monkeypatch, audit_events):
        monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "MANAGE")
        store.populate_groups(["team-acme", "ops-beta"])
        manage = create_rule(client, name="managers", permission="MANAGE")["rule"]["id"]
        ops = create_rule(client, name="ops", pattern=r"^ops-(?P<ws>.+)$", permission="READ")["rule"]["id"]
        assert grants(store) == {("acme", "team-acme"): ("MANAGE", manage), ("beta", "ops-beta"): ("READ", ops)}

        monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "EDIT")
        removed = workspace_rules.enforce_ceiling()

        assert [(c.group, c.action) for c in removed] == [("team-acme", "remove")]
        assert grants(store) == {("beta", "ops-beta"): ("READ", ops)}
        [event] = events(audit_events, "permission.deprovisioned")
        assert event["actor"] == workspace_rules.CEILING_ACTOR and event["detail"]["rule_id"] == manage
        assert store.get_workspace_group_rule(manage).permission == "MANAGE", "the rule itself stays"

    def test_a_stale_plan_does_not_recreate_a_grant_a_disable_removed(self, client, store):
        """The race: a login evaluates an enabled rule, an admin disables it, then the login writes."""
        rule_id = create_rule(client)["rule"]["id"]
        store.populate_groups(["team-acme"])
        stale = store.get_workspace_group_rule(rule_id)
        plan = workspace_rules.evaluate(stale, ["team-acme"], competitors=[stale])

        client.patch(f"{RULES}/{rule_id}", json={"enabled": False})
        changes = store.reconcile_workspace_group_rule(rule_id, plan.desired, scope={"team-acme"}, retain=plan.retain, expected=stale)

        assert changes == []
        assert grants(store) == {}

    def test_a_grant_cannot_point_at_a_deleted_rule(self, client, store):
        rule_id = create_rule(client)["rule"]["id"]
        store.populate_groups(["team-acme"])
        stale = store.get_workspace_group_rule(rule_id)
        plan = workspace_rules.evaluate(stale, ["team-acme"], competitors=[stale])

        client.delete(f"{RULES}/{rule_id}")

        result = store.reconcile_workspace_group_rule(rule_id, plan.desired, scope={"team-acme"}, expected=stale)
        assert result == []
        assert grants(store) == {}

    def test_workspace_cache_is_invalidated_even_if_the_permission_cache_flush_fails(self, client, store, monkeypatch):
        from mlflow_oidc_auth.utils import permissions
        from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

        store.create_user(ALICE, "Alice")
        store.populate_groups(["team-acme"])
        store.set_user_groups(ALICE, ["team-acme"])
        rule_id = create_rule(client, permission="READ")["rule"]["id"]
        assert get_workspace_permission_cached(ALICE, "acme").name == "READ"

        def broken():
            raise RuntimeError("cache backend down")

        monkeypatch.setattr(permissions, "flush_permission_cache", broken)
        client.patch(f"{RULES}/{rule_id}", json={"enabled": False})

        assert get_workspace_permission_cached(ALICE, "acme") is None


class TestWorkspaceStoreOutage:
    """An unreachable workspace store must never read as "every workspace is missing"."""

    @pytest.fixture
    def outage(self, monkeypatch):
        from mlflow.server import handlers

        def down(*args, **kwargs):
            raise RuntimeError("workspace database unreachable")

        return lambda: monkeypatch.setattr(handlers, "_get_workspace_store", down)

    def test_a_backfill_during_an_outage_keeps_every_grant(self, client, store, outage, audit_events):
        store.populate_groups(["team-acme", "team-beta"])
        rule_id = create_rule(client)["rule"]["id"]
        before = grants(store)
        assert len(before) == 2
        outage()

        response = client.patch(f"{RULES}/{rule_id}", json={"permission": "READ"})

        assert response.status_code == 200
        assert "workspace store is unavailable" in response.json()["error"]
        assert grants(store) == before, "an outage removed grants"
        assert events(audit_events, "permission.deprovisioned") == []
        assert events(audit_events, "workspace_rule.failed")[0]["detail"]["operation"] == "backfill"

    def test_a_workspace_store_error_is_not_a_missing_workspace(self, client, store, mlflow_workspaces, monkeypatch):
        from mlflow.protos.databricks_pb2 import INTERNAL_ERROR

        store.populate_groups(["team-acme"])
        rule_id = create_rule(client)["rule"]["id"]

        def broken(name):
            raise MlflowException("database is locked", INTERNAL_ERROR)

        monkeypatch.setattr(mlflow_workspaces, "get_workspace", broken)
        client.patch(f"{RULES}/{rule_id}", json={"permission": "READ"})

        assert grants(store) == {("acme", "team-acme"): ("EDIT", rule_id)}

    def test_preview_during_an_outage_is_503(self, client, store, outage):
        rule_id = create_rule(client, mode="report")["rule"]["id"]
        store.populate_groups(["team-acme"])
        outage()

        result = client.get(f"{RULES}/{rule_id}/preview")
        assert result.status_code == 503

    def test_arrival_during_an_outage_writes_nothing_and_does_not_fail(self, client, store, scim, outage, audit_events):
        create_rule(client)
        outage()

        response = client.post(SCIM_GROUPS, headers=scim, json=group_body_minimal("team-acme"))

        assert response.status_code == 201
        assert grants(store) == {}
        assert events(audit_events, "workspace_rule.failed")


class TestRetryAndTakeoverReporting:
    def test_saving_again_retries_a_failed_backfill(self, client, store, mlflow_workspaces, monkeypatch):
        from mlflow.server import handlers

        store.populate_groups(["team-acme"])
        monkeypatch.setattr(handlers, "_get_workspace_store", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
        body = create_rule(client)
        assert body["error"] and grants(store) == {}

        monkeypatch.setattr(handlers, "_get_workspace_store", lambda *a, **k: mlflow_workspaces)
        result = client.patch(f"{RULES}/{body['rule']['id']}", json={"permission": "EDIT"})

        assert result.json()["error"] is None
        assert grants(store) == {("acme", "team-acme"): ("EDIT", body["rule"]["id"])}

    def test_a_takeover_keeps_the_winners_other_removals_audited(self, client, store, audit_events):
        """Rule 1 moves from acme to beta for the same group, where rule 2 holds the grant: its
        removal on acme must still be reported and audited alongside the takeover on beta."""
        store.populate_groups(["team-acme-beta"])
        first = create_rule(client, name="first", pattern=r"^team-(?P<ws>[a-z]+)-[a-z]+$", permission="READ")["rule"]["id"]
        second = create_rule(client, name="second", pattern=r"^team-[a-z]+-(?P<ws>[a-z]+)$", permission="EDIT")["rule"]["id"]
        assert grants(store) == {("acme", "team-acme-beta"): ("READ", first), ("beta", "team-acme-beta"): ("EDIT", second)}
        audit_events.clear()

        result = client.patch(f"{RULES}/{first}", json={"pattern": r"^team-[a-z]+-(?P<ws>[a-z]+)$"})

        assert grants(store) == {("beta", "team-acme-beta"): ("READ", first)}
        lines = {(c["action"], c["workspace"], c["rule_id"]) for c in result.json()["changes"]}
        assert {("remove", "acme", first), ("grant", "beta", first), ("remove", "beta", second)} <= lines
        deprovisioned = {(e["detail"]["workspace"], e["detail"]["rule_id"]) for e in events(audit_events, "permission.deprovisioned")}
        assert deprovisioned == {("acme", first), ("beta", second)}

    def test_a_preview_shows_a_takeover_as_a_grant(self, client, store):
        store.populate_groups(["team-acme"])
        first = create_rule(client, name="first", permission="READ", mode="report")["rule"]["id"]
        second = create_rule(client, name="second", permission="EDIT")["rule"]["id"]

        [line] = client.get(f"{RULES}/{first}/preview").json()["changes"]

        assert (line["action"], line["reason"]) == ("grant", f"takes over from rule {second}")


class TestRenameOnly:
    def test_a_rename_touches_no_grant(self, client, store, audit_events):
        store.populate_groups(["team-acme"])
        rule_id = create_rule(client)["rule"]["id"]
        store.delete_workspace_group_permission("acme", "team-acme")
        audit_events.clear()

        body = client.patch(f"{RULES}/{rule_id}", json={"name": "tenants-renamed"}).json()

        assert body["rule"]["name"] == "tenants-renamed" and body["changes"] == []
        assert grants(store) == {}, "a rename re-created a grant the admin removed"
        assert [e["event"] for e in audit_events] == ["workspace_rule.update"]


class TestAuditAndCache:
    def test_every_grant_and_revoke_is_audited(self, client, store, audit_events):
        store.populate_groups(["team-acme", "team-beta"])

        rule_id = create_rule(client, permission="READ")["rule"]["id"]
        client.patch(f"{RULES}/{rule_id}", json={"permission": "EDIT"})
        client.delete(f"{RULES}/{rule_id}")

        lifecycle = [e["event"] for e in audit_events if e["event"].startswith("workspace_rule.")]
        assert lifecycle == ["workspace_rule.create", "workspace_rule.update", "workspace_rule.delete"]
        provisioned = [(e["detail"]["group"], e["detail"]["permission"], e["detail"].get("previous")) for e in events(audit_events, "permission.provisioned")]
        assert provisioned == [("team-acme", "READ", None), ("team-beta", "READ", None), ("team-acme", "EDIT", "READ"), ("team-beta", "EDIT", "READ")]
        deprovisioned = [(e["detail"]["group"], e["detail"]["workspace"], e["detail"]["rule_id"]) for e in events(audit_events, "permission.deprovisioned")]
        assert deprovisioned == [("team-acme", "acme", rule_id), ("team-beta", "beta", rule_id)]
        assert all(e["actor"] == ADMIN for e in audit_events if e["event"].startswith(("permission.", "workspace_rule.")))

    def test_arrival_is_audited_as_its_source(self, client, store, scim, audit_events):
        create_rule(client)

        client.post(SCIM_GROUPS, headers=scim, json=group_body_minimal("team-acme"))

        [event] = events(audit_events, "permission.provisioned")
        assert event["actor"] == "scim"

    def test_members_cache_invalidated_on_grant(self, client, store):
        from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

        store.create_user(ALICE, "Alice")
        store.populate_groups(["team-acme"])
        store.set_user_groups(ALICE, ["team-acme"])
        rule_id = create_rule(client, permission="READ")["rule"]["id"]
        assert get_workspace_permission_cached(ALICE, "acme").name == "READ", "precondition: cache warm"

        client.patch(f"{RULES}/{rule_id}", json={"permission": "EDIT"})
        assert get_workspace_permission_cached(ALICE, "acme").name == "EDIT", "upgrade not visible"

        client.patch(f"{RULES}/{rule_id}", json={"enabled": False})
        assert get_workspace_permission_cached(ALICE, "acme") is None, "revoked rule grant still served from cache (fail-open)"


class TestEvaluate:
    """The pure part: matching is fullmatch on the whole local name."""

    def _rule(self, rule_id=1, pattern=TENANT_PATTERN, permission="EDIT"):
        from datetime import datetime

        from mlflow_oidc_auth.entities.workspace_rule import WorkspaceGroupRule

        now = datetime(2026, 9, 30)
        return WorkspaceGroupRule(rule_id, f"r{rule_id}", pattern, permission, "enforce", True, None, now, now)

    def test_partial_matches_do_not_count(self, store):
        plan = workspace_rules.evaluate(
            self._rule(pattern=r"team-(?P<ws>[a-z]+)"), ["xteam-acme", "team-acme-extra", "team-acme"], competitors=[], workspace_exists=lambda _: True
        )
        assert plan.desired == {("acme", "team-acme"): "EDIT"}

    def test_empty_workspace_capture_matches_nothing(self, store):
        plan = workspace_rules.evaluate(self._rule(pattern=r"^team-(?P<ws>[a-z]*)$"), ["team-"], competitors=[], workspace_exists=lambda _: True)
        assert plan.desired == {} and plan.items == []
