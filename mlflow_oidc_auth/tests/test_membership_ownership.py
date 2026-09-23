"""The managed_by guard on group membership, delete and create (issue #360).

Group membership is the privilege carrier, so a guard that protects a user row's flags but not the
user's groups protects the less interesting half. These tests go **through the callers** — the
login path (``_provision_login``), bearer and service-account provisioning, the admin API, the
reconcile CLI — rather than calling the repository with ``written_by=`` spelled out. The #319
review found the guard refusing a directory's own sync because attribution never reached the
store, and every test passed ``written_by`` explicitly, so none of them noticed.
"""

import json
import logging
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from mlflow.exceptions import MlflowException

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth import audit
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.db.cli import commands
from mlflow_oidc_auth.ownership import Enforcement
from mlflow_oidc_auth.provider_registry import ProviderConfig
from mlflow_oidc_auth.routers._prefix import USERS_ROUTER_PREFIX

PASSWORD = "membership-suite"  # not a credential: only ever seeded into a tmp_path database
ALICE = "alice@example.com"
KEEPER = "keeper@example.com"


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(KEEPER, PASSWORD, "Keeper", is_admin=True)
    s.create_scim_user(ALICE, "Alice", "ext-alice")
    s.populate_groups(["mlflow-users", "finance", "legacy", "eng"])
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    yield s
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture(autouse=True)
def login_config(monkeypatch):
    monkeypatch.setattr(config, "OIDC_GROUP_NAME", ["mlflow-users"])
    monkeypatch.setattr(config, "OIDC_ADMIN_GROUP_NAME", ["mlflow-admins"])
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.REPORT)


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)


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


def conflicts(events, operation=None):
    return [e for e in events if e["event"] == "user.ownership_conflict" and (operation is None or e["detail"].get("operation") == operation)]


def owners(store, username):
    """``{group: managed_by}`` for one user, read straight from the table."""
    from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

    with store.ManagedSessionMaker() as session:
        rows = (
            session.query(SqlGroup.group_name, SqlUserGroup.managed_by)
            .join(SqlUserGroup, SqlUserGroup.group_id == SqlGroup.id)
            .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
            .filter(SqlUser.username == username)
            .all()
        )
        return dict(rows)


def provider(mode="authoritative", provider_id="default", **overrides):
    fields = {
        "id": provider_id,
        "type": "oidc",
        "audience": "mlflow",
        "issuer": "https://idp.invalid",
        "provisioning": "jit",
        "group_sync": "every_login",
        "group_sync_mode": mode,
        "admin_source": "claims",
    }
    fields.update(overrides)
    return ProviderConfig(**fields)


def login(username, groups, *, prov=None, method="oidc"):
    """Drive the real login path shared by the OIDC callback and the SAML ACS."""
    from mlflow_oidc_auth.routers.auth import _provision_login

    prov = prov or provider()
    # No ``sub`` for the default provider: the pre-registry single-provider login, which names the
    # account from the claims and adopts the existing row.
    return _provision_login(
        prov, username=username, display_name="Alice", userinfo={"email": username}, user_groups=list(groups), access_token=None, method=method
    )


class TestLoginDoesNotStripTheDirectorysGroups:
    """The issue's first gap: a SCIM-owned user in a SCIM-provisioned group logs in, the provider's
    claims do not mention that group, and ``authoritative`` sync used to replace membership
    wholesale with nothing refused and nothing audited."""

    @pytest.fixture
    def directory_member(self, store):
        store.add_user_to_group(ALICE, "finance", written_by="scim")
        return ALICE

    def test_enforce_keeps_scim_memberships_and_writes_only_its_own(self, store, enforce, directory_member, audit_events):
        username, errors = login(ALICE, ["mlflow-users", "eng"])

        assert (username, errors) == (ALICE, []), "the login itself must not be refused: that would be a lockout"
        assert owners(store, ALICE) == {"finance": "scim", "mlflow-users": "oidc:default", "eng": "oidc:default"}
        [event] = conflicts(audit_events, "membership.remove")
        assert event["status"] == "denied"
        assert event["detail"] | {"reason": None} == {
            "owner": "scim",
            "written_by": "oidc:default",
            "reason": None,
            "permitted": False,
            "operation": "membership.remove",
            "group": "finance",
        }

    def test_report_keeps_them_too_and_records_it(self, store, directory_member, audit_events):
        """A sync never removes another source's membership, in any mode: under ``report`` the
        skipped row is recorded. Every pre-existing row is ``manual``, so a deployment that changes
        nothing sees no change."""
        login(ALICE, ["mlflow-users"])

        assert owners(store, ALICE) == {"finance": "scim", "mlflow-users": "oidc:default"}
        [event] = conflicts(audit_events, "membership.remove")
        assert (event["status"], event["detail"]["permitted"], event["detail"]["group"]) == ("denied", False, "finance")

    def test_off_keeps_them_silently(self, store, directory_member, audit_events, monkeypatch):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.OFF)

        login(ALICE, ["mlflow-users"])

        assert owners(store, ALICE) == {"finance": "scim", "mlflow-users": "oidc:default"}
        assert conflicts(audit_events) == []

    def test_groups_a_login_creates_are_the_providers(self, store):
        login(ALICE, ["mlflow-users", "brand-new"])

        assert store.get_group_detail("brand-new")["managed_by"] == "oidc:default"
        assert store.get_group_detail("mlflow-users")["managed_by"] == "manual", "an existing group keeps its owner"

    def test_the_permission_the_scim_group_carries_survives_the_login(self, store, enforce, directory_member):
        """Membership is only interesting for what it grants: resolve through the real permission path."""
        from mlflow_oidc_auth.utils.permissions import effective_experiment_permission, flush_permission_cache

        store.create_group_experiment_permission("finance", "42", "EDIT")
        flush_permission_cache()

        login(ALICE, ["mlflow-users"])

        result = effective_experiment_permission("42", ALICE)
        assert result.permission.name == "EDIT"
        assert result.kind == "group"


class TestAuthoritativeStillRevokes:
    """Guarding other sources' rows must not turn an authoritative provider into an additive one:
    a membership its claims stop asserting still goes, or revocation stops propagating."""

    def test_its_own_memberships_are_removed_when_the_claims_drop_them(self, store, enforce):
        login(ALICE, ["mlflow-users", "eng"])

        login(ALICE, ["mlflow-users"])

        assert owners(store, ALICE) == {"mlflow-users": "oidc:default"}

    def test_memberships_written_before_ownership_are_still_revoked(self, store, enforce, audit_events):
        """Every membership that predates #360 is ``manual``. Those are unowned and removable by any
        source, so an upgraded deployment keeps revoking exactly what it revoked before — no
        backfill needed."""
        store.add_user_to_group(ALICE, "legacy")  # unattributed: the pre-#360 write
        assert owners(store, ALICE) == {"legacy": "manual"}

        login(ALICE, ["mlflow-users"])

        assert owners(store, ALICE) == {"mlflow-users": "oidc:default"}
        assert conflicts(audit_events) == []

    def test_re_asserting_a_membership_does_not_take_it_over(self, store, enforce):
        store.add_user_to_group(ALICE, "mlflow-users", written_by="scim")

        login(ALICE, ["mlflow-users"])

        assert owners(store, ALICE) == {"mlflow-users": "scim"}

    def test_additive_never_removes(self, store):
        store.add_user_to_group(ALICE, "finance", written_by="scim")
        store.add_user_to_group(ALICE, "legacy")

        login(ALICE, ["mlflow-users"], prov=provider(mode="additive"))

        assert owners(store, ALICE) == {"finance": "scim", "legacy": "manual", "mlflow-users": "oidc:default"}


class TestTwoProviders:
    @pytest.mark.parametrize("mode", list(Enforcement))
    def test_one_providers_authoritative_sync_leaves_the_others_memberships(self, store, monkeypatch, mode):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", mode)
        store.populate_groups(["partner:eng"])
        store.add_user_to_group(ALICE, "partner:eng", written_by="oidc:partner")

        login(ALICE, ["mlflow-users"])

        assert owners(store, ALICE) == {"partner:eng": "oidc:partner", "mlflow-users": "oidc:default"}

    def test_a_saml_login_is_attributed_to_saml(self, store):
        login(ALICE, ["mlflow-users"], method="saml")

        assert owners(store, ALICE) == {"mlflow-users": "saml:default"}


class TestTheDirectorysOwnSyncIsNotLockedOut:
    def test_scim_removes_its_own_memberships_under_enforce(self, store, enforce):
        store.add_user_to_group(ALICE, "finance", written_by="scim")

        store.set_user_groups(ALICE, [], written_by="scim")

        assert owners(store, ALICE) == {}

    def test_scim_cannot_strip_a_login_granted_membership_under_enforce(self, store, enforce, audit_events):
        login(ALICE, ["mlflow-users"])

        store.set_user_groups(ALICE, [], written_by="scim")

        assert owners(store, ALICE) == {"mlflow-users": "oidc:default"}
        assert [e["status"] for e in conflicts(audit_events, "membership.remove")] == ["denied"]

    def test_a_directory_may_not_strip_a_hand_made_admins_memberships(self, store, enforce):
        store.add_user_to_group(KEEPER, "legacy")

        store.set_user_groups(KEEPER, [], written_by="scim")

        assert owners(store, KEEPER) == {"legacy": "manual"}

    def test_a_targeted_removal_is_refused_outright(self, store, enforce, audit_events):
        login(ALICE, ["mlflow-users"])

        with pytest.raises(MlflowException, match="managed by 'oidc:default'"):
            store.remove_user_from_group(ALICE, "mlflow-users", written_by="scim")

        assert owners(store, ALICE) == {"mlflow-users": "oidc:default"}
        assert [e["status"] for e in conflicts(audit_events)] == ["denied"]

    def test_an_administrator_override_removes_and_is_recorded(self, store, enforce, audit_events):
        login(ALICE, ["mlflow-users"])

        store.remove_user_from_group(ALICE, "mlflow-users", written_by="manual", admin_override=True)

        assert owners(store, ALICE) == {}
        [event] = conflicts(audit_events)
        assert event["status"] == "success" and "override" in event["detail"]["reason"]


class TestProvisioningPathsAreAttributed:
    def test_bearer_provisioning(self, store, monkeypatch):
        import mlflow_oidc_auth.auth as auth_module
        from unittest.mock import MagicMock

        from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware

        monkeypatch.setattr(config, "OIDC_PROVISION_ON_BEARER_AUTH", True)
        monkeypatch.setattr(config, "OIDC_GROUP_DETECTION_PLUGIN", None)
        monkeypatch.setattr(config, "OIDC_GROUPS_ATTRIBUTE", "groups")
        monkeypatch.setattr(auth_module, "resolve_token_provider", lambda token: provider(provider_id="corp"))

        AuthMiddleware(app=MagicMock())._maybe_provision_bearer_user("bob@example.com", "token", {"groups": ["mlflow-users"], "name": "Bob"})

        assert owners(store, "bob@example.com") == {"mlflow-users": "oidc:corp"}

    def test_service_account_provisioning(self, store):
        from unittest.mock import MagicMock

        from mlflow_oidc_auth.kubernetes import ServiceAccount
        from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware

        account = ServiceAccount(namespace="ml", name="trainer")
        AuthMiddleware(app=MagicMock())._provision_service_account(account, SimpleNamespace(id="cluster"))

        assert owners(store, account.username) == {account.group: "oidc:cluster"}


@pytest.fixture
def admin_api(store):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import mlflow_oidc_auth.routers.users as users_router
    from mlflow_oidc_auth.dependencies import check_admin_permission

    app = FastAPI()
    app.include_router(users_router.users_router)
    app.dependency_overrides[check_admin_permission] = lambda: KEEPER
    with TestClient(app) as client:
        yield client


class TestDeleteIsGuarded:
    def test_a_foreign_source_may_not_delete_under_enforce(self, store, enforce, audit_events):
        with pytest.raises(MlflowException, match="managed by 'scim'"):
            store.delete_user(ALICE, written_by="oidc:default")

        assert store.has_user(ALICE)
        [event] = conflicts(audit_events, "delete")
        assert event["status"] == "denied"

    def test_the_owner_may(self, store, enforce, audit_events):
        store.delete_user(ALICE, written_by="scim")

        assert not store.has_user(ALICE)
        assert conflicts(audit_events) == []

    def test_report_deletes_and_records_after_the_commit(self, store, audit_events):
        store.delete_user(ALICE, written_by="oidc:default")

        assert not store.has_user(ALICE)
        [event] = conflicts(audit_events, "delete")
        assert event["status"] == "success"

    def test_the_admin_api_goes_through_the_repository_guard(self, store, enforce, admin_api, audit_events):
        response = admin_api.request("DELETE", USERS_ROUTER_PREFIX, json={"username": ALICE})

        assert response.status_code == 409
        assert store.has_user(ALICE)
        [event] = conflicts(audit_events, "delete")
        assert (event["actor"], event["status"]) == (KEEPER, "denied")


class TestDeleteThenCreateCannotLaunderOwnership:
    """``create`` used to apply the ``manual`` default, so a source that could delete a
    ``scim``-owned row and create it again had a row anyone could write."""

    def test_delete_is_refused_so_the_name_is_never_freed(self, store, enforce, admin_api):
        assert admin_api.request("DELETE", USERS_ROUTER_PREFIX, json={"username": ALICE}).status_code == 409

        admin_api.post(USERS_ROUTER_PREFIX, json={"username": ALICE, "display_name": "Taken Over"})

        assert store.get_user_detail(ALICE)["managed_by"] == "scim"

    @pytest.mark.parametrize("mode", list(Enforcement))
    def test_create_over_an_existing_row_never_re_owns(self, store, monkeypatch, audit_events, mode):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", mode)

        with pytest.raises(MlflowException) as refused:
            store.create_user(ALICE, PASSWORD, "Taken Over", written_by="oidc:default")

        assert refused.value.error_code == "RESOURCE_ALREADY_EXISTS"
        detail = store.get_user_detail(ALICE)
        assert (detail["managed_by"], detail["display_name"]) == ("scim", "Alice")
        expected = [] if mode == Enforcement.OFF else ["denied"]
        assert [e["status"] for e in conflicts(audit_events, "create")] == expected

    def test_a_create_over_an_unowned_row_is_just_already_exists(self, store, audit_events):
        with pytest.raises(MlflowException, match="already exists"):
            store.create_user(KEEPER, PASSWORD, "Again", written_by="oidc:default")

        assert conflicts(audit_events) == []


class TestBreakGlassForMemberships:
    """A guard whose only recovery needs database access has produced the state it exists to
    prevent. A decommissioned source's memberships must be recoverable without it."""

    @pytest.fixture
    def stuck(self, store):
        store.populate_groups(["gone:eng"])
        store.add_user_to_group(ALICE, "gone:eng", written_by="oidc:gone")
        return ALICE

    def test_stuck_under_enforce(self, store, enforce, stuck):
        login(ALICE, ["mlflow-users"])

        assert "gone:eng" in owners(store, ALICE)

    def test_the_admin_api_hands_memberships_back(self, store, enforce, stuck, admin_api, audit_events):
        response = admin_api.patch(f"{USERS_ROUTER_PREFIX}/ownership", json={"username": ALICE, "managed_by": "manual", "memberships": True})

        assert response.status_code == 200, response.text
        assert response.json()["memberships"] == [{"group": "gone:eng", "from": "oidc:gone"}]
        [event] = [e for e in audit_events if e["event"] == "user.ownership_set"]
        assert event["detail"]["memberships"] == [{"group": "gone:eng", "from": "oidc:gone"}]

        login(ALICE, ["mlflow-users"])

        assert owners(store, ALICE) == {"mlflow-users": "oidc:default"}

    def test_without_the_flag_memberships_are_untouched(self, store, stuck, admin_api):
        admin_api.patch(f"{USERS_ROUTER_PREFIX}/ownership", json={"username": ALICE, "managed_by": "manual"})

        assert owners(store, ALICE) == {"gone:eng": "oidc:gone"}

    def test_the_cli_hands_memberships_back_and_can_undo_it(self, store, enforce, stuck, tmp_path):
        url = str(store.engine.url)
        journal = tmp_path / "journal.json"

        dry = CliRunner().invoke(commands, ["reconcile-ownership", "--url", url, "--set-owner", "manual", "--from-owner", "oidc:gone", "--memberships"])
        assert dry.exit_code == 0, dry.output
        assert f"{ALICE} in gone:eng: oidc:gone -> manual" in dry.output
        assert owners(store, ALICE) == {"gone:eng": "oidc:gone"}

        applied = CliRunner().invoke(
            commands,
            ["reconcile-ownership", "--url", url, "--set-owner", "manual", "--from-owner", "oidc:gone", "--memberships", "--apply", "--journal", str(journal)],
        )
        assert applied.exit_code == 0, applied.output
        assert owners(store, ALICE) == {"gone:eng": "manual"}
        assert store.get_user_detail(ALICE)["managed_by"] == "scim", "--from-owner matched no user row"

        restored = CliRunner().invoke(commands, ["restore-ownership", "--url", url, "--journal", str(journal), "--apply"])
        assert restored.exit_code == 0, restored.output
        assert owners(store, ALICE) == {"gone:eng": "oidc:gone"}

    def test_without_the_flag_the_cli_leaves_memberships_alone(self, store, stuck):
        result = CliRunner().invoke(
            commands, ["reconcile-ownership", "--url", str(store.engine.url), "--set-owner", "manual", "--from-owner", "oidc:gone", "--apply"]
        )

        assert result.exit_code == 0, result.output
        assert "no rows to change" in result.output
        assert owners(store, ALICE) == {"gone:eng": "oidc:gone"}
