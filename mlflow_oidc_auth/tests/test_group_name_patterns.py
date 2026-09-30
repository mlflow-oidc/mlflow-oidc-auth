"""OIDC_GROUP_NAME_PATTERN at the login gate (issue #78, PR #301).

Driven through ``_provision_login`` — the step the OIDC callback and the SAML ACS share — with a
real store, so the gate, the provisioning and the audit trail are exercised together.

What these pin:

* a pattern admits a user whose group matches it, on OIDC and on SAML, and says so in the audit log;
* ``OIDC_GROUP_NAME`` stays exact: an entry that looks like a pattern matches only itself;
* with no pattern configured — every existing deployment — nothing new is admitted;
* a pattern never makes anyone an administrator.
"""

import json
import logging

import pytest

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth import audit
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.ownership import Enforcement
from mlflow_oidc_auth.provider_registry import ProviderConfig

KEEPER = "keeper@example.com"
NEWCOMER = "newcomer@example.com"


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(KEEPER, "Keeper", is_admin=True)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    yield s
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture(autouse=True)
def login_config(monkeypatch):
    monkeypatch.setattr(config, "OIDC_GROUP_NAME", ["mlflow"])
    monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", [])
    monkeypatch.setattr(config, "OIDC_ADMIN_GROUP_NAME", ["mlflow-admin"])
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.REPORT)


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


def _provider():
    return ProviderConfig(
        id="default",
        type="oidc",
        audience="mlflow",
        issuer="https://idp.invalid",
        provisioning="jit",
        group_sync="every_login",
        group_sync_mode="authoritative",
        admin_source="claims",
    )


def login(groups, *, method="oidc", username=NEWCOMER):
    from mlflow_oidc_auth.routers.auth import _provision_login

    return _provision_login(
        _provider(), username=username, display_name="Newcomer", userinfo={"email": username}, user_groups=groups, access_token=None, method=method
    )


def pattern_events(events):
    return [e for e in events if e["event"] == "auth.admitted_by_group_pattern"]


class TestPatternsAdmit:
    @pytest.mark.parametrize("method", ["oidc", "saml"])
    def test_a_matching_group_is_admitted_and_audited(self, store, audit_events, monkeypatch, method):
        monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", ["mlflow-*"])

        username, errors = login(["mlflow-team-new", "unrelated"], method=method)

        assert (username, errors) == (NEWCOMER, [])
        assert store.has_user(NEWCOMER)
        (event,) = pattern_events(audit_events)
        assert event["resource_id"] == NEWCOMER
        assert event["detail"] == {"provider": "default", "method": method, "pattern": "mlflow-*", "group": "mlflow-team-new"}

    def test_every_claimed_group_is_still_synchronised(self, store, monkeypatch):
        """The pattern decides admission only; membership sync is unchanged."""
        monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", ["mlflow-*"])

        login(["mlflow-team-new", "shared-platform"])

        assert sorted(g.group_name for g in store.get_user_profile(NEWCOMER).groups) == ["mlflow-team-new", "shared-platform"]

    def test_no_admission_is_recorded_when_the_login_then_fails(self, store, audit_events, monkeypatch):
        """The gate passing is not a login: a deactivated account matched by a pattern is still
        refused, and must not leave an admission event that reads like a success."""
        monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", ["mlflow-*"])
        store.create_user(NEWCOMER, "Newcomer")
        store.update_user(NEWCOMER, active=False)

        username, errors = login(["mlflow-team-new"])

        assert username is None and errors
        assert pattern_events(audit_events) == []

    def test_admission_by_name_is_not_reported_as_a_pattern(self, store, audit_events, monkeypatch):
        monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", ["mlflow*"])

        login(["mlflow"])

        assert pattern_events(audit_events) == []

    def test_a_pattern_never_confers_admin(self, store, monkeypatch):
        monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", ["*"])

        login(["mlflow-admins-lookalike"])

        assert store.get_user_profile(NEWCOMER).is_admin is False


class TestNothingChangesWithoutOptIn:
    def test_without_patterns_a_new_group_is_refused(self, store):
        """Every deployment that does not set OIDC_GROUP_NAME_PATTERN admits exactly what it did."""
        username, errors = login(["mlflow-team-new"])

        assert username is None and errors == ["User is not allowed to login"]
        assert not store.has_user(NEWCOMER)

    @pytest.mark.parametrize("name, group", [("mlflow-*", "mlflow-team"), ("Data Science [EU]", "Data Science E")])
    def test_an_exact_name_that_looks_like_a_pattern_matches_only_itself(self, store, monkeypatch, name, group):
        monkeypatch.setattr(config, "OIDC_GROUP_NAME", [name])

        assert login([group])[0] is None
        assert login([name])[0] == NEWCOMER

    @pytest.mark.parametrize("groups", [None, [""], {"mlflow-team": True}])
    def test_an_unusable_claim_is_refused_even_by_star(self, store, monkeypatch, groups):
        monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", ["*"])

        assert login(groups)[0] is None
