"""The startup backfill that gives legacy grants on name-keyed resources a workspace."""

import json
import logging
from unittest.mock import patch

import pytest

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth import audit, grant_workspace_backfill
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils.grant_workspace import UNRESOLVED_WORKSPACE as UNRESOLVED

ALICE = "alice@example.com"
BOB = "bob@example.com"


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils import workspace_cache

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ALICE, "Alice")
    s.create_user(BOB, "Bob")
    s.populate_groups(["team"])
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    workspace_cache.flush_workspace_cache()
    yield s
    workspace_cache.flush_workspace_cache()
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


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


def legacy(store, model_name, name, *, user=None, group=None, permission="EDIT"):
    """Insert a grant as it exists right after the migration: no workspace."""
    from mlflow_oidc_auth import db

    model = getattr(db.models, model_name)
    with store.ManagedSessionMaker(read_only=False) as session:
        if user is not None:
            principal = {"user_id": session.query(db.models.SqlUser.id).filter(db.models.SqlUser.username == user).scalar()}
        else:
            principal = {"group_id": session.query(db.models.SqlGroup.id).filter(db.models.SqlGroup.group_name == group).scalar()}
        column = {"SqlRegisteredModelPermission": "name", "SqlRegisteredModelGroupPermission": "name"}.get(model_name, "endpoint_id")
        session.add(model(**{column: name}, permission=permission, workspace=None, **principal))


def rows(store, model_name):
    from mlflow_oidc_auth import db

    model = getattr(db.models, model_name)
    column = "name" if "RegisteredModel" in model_name else "endpoint_id"
    with store.ManagedSessionMaker() as session:
        return sorted((getattr(r, column), r.workspace, r.permission) for r in session.query(model).all())


def resources(**kinds):
    """Stub for MLflow's resources: ``registered_model={"churn": {"team-a"}}`` and so on."""
    base = {"registered_model": {}, "gateway_endpoint": {}, "gateway_secret": {}, "gateway_model_definition": {}}
    base.update({k: {name: set(ws) for name, ws in v.items()} for k, v in kinds.items()})
    return patch.object(grant_workspace_backfill, "_mlflow_resource_workspaces", return_value=base)


class TestWorkspacesDisabled:
    def test_every_legacy_grant_gets_the_default_workspace_and_a_rerun_is_a_no_op(self, store, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        legacy(store, "SqlGatewayEndpointGroupPermission", "chat", group="team")

        with patch.object(grant_workspace_backfill, "_mlflow_resource_workspaces") as lookup:
            report = grant_workspace_backfill.backfill_grant_workspaces(store)
            lookup.assert_not_called()

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", "default", "EDIT")]
        assert rows(store, "SqlGatewayEndpointGroupPermission") == [("chat", "default", "EDIT")]
        assert sum(report.assigned.values()) == 2

        again = grant_workspace_backfill.backfill_grant_workspaces(store)
        assert sum(again.assigned.values()) == 0 and again.unresolved_count == 0


class TestWorkspacesEnabled:
    @pytest.fixture(autouse=True)
    def workspaces_on(self, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)

    def test_a_name_in_one_workspace_is_assigned_to_it_when_the_grantee_reaches_it(self, store):
        store.create_workspace_permission("team-a", ALICE, "READ")
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with resources(registered_model={"churn": {"team-a"}}):
            grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", "team-a", "EDIT")]

    def test_a_name_in_one_workspace_the_grantee_cannot_reach_is_not_assigned(self, store):
        """The old name-only grant also reached a same-named resource another tenant created later:
        being the only workspace with the name is no evidence the grant was meant for it."""
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE, permission="MANAGE")
        with resources(registered_model={"churn": {"team-b"}}):
            report = grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", UNRESOLVED, "MANAGE")]
        assert report.unresolved_count == 1

    def test_the_default_workspace_keeps_grants_made_before_workspaces(self, store):
        """Resources from before workspaces live in default; their grants stay there."""
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with resources(registered_model={"churn": {"default", "team-b"}}):
            grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", "default", "EDIT")]

    def test_a_tenant_who_reaches_a_namesake_does_not_keep_defaults_resource(self, store):
        """A tenant who created ``churn`` in their own workspace got a name-only grant that also
        reached ``default``'s ``churn``: the backfill places it only in the tenant's workspace."""
        store.create_workspace_permission("team-b", ALICE, "MANAGE")
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE, permission="MANAGE")
        with resources(registered_model={"churn": {"default", "team-b"}}):
            grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", "team-b", "MANAGE")]

    def test_a_grantee_with_a_permission_on_default_keeps_it_there_too(self, store):
        store.create_workspace_permission("default", ALICE, "READ")
        store.create_workspace_permission("team-b", ALICE, "READ")
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with resources(registered_model={"churn": {"default", "team-b"}}):
            grant_workspace_backfill.backfill_grant_workspaces(store)

        # default keeps the grant; team-b's copy carries no more than Alice's READ on team-b.
        assert sorted(rows(store, "SqlRegisteredModelPermission")) == [("churn", "default", "EDIT"), ("churn", "team-b", "READ")]

    def test_a_name_in_several_workspaces_goes_only_where_the_grantee_reaches(self, store):
        store.create_workspace_permission("team-a", ALICE, "READ")
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE, permission="MANAGE")
        with resources(registered_model={"churn": {"team-a", "team-b"}}):
            grant_workspace_backfill.backfill_grant_workspaces(store)

        # Two workspaces hold the name: the grant carries no more than Alice holds on team-a.
        assert rows(store, "SqlRegisteredModelPermission") == [("churn", "team-a", "READ")]

    def test_a_group_grant_is_copied_to_every_workspace_the_group_reaches(self, store):
        store.create_workspace_group_permission("team-a", "team", "READ")
        store.create_workspace_group_permission("team-b", "team", "EDIT")
        legacy(store, "SqlGatewayEndpointGroupPermission", "chat", group="team", permission="USE")
        with resources(gateway_endpoint={"chat": {"team-a", "team-b", "team-c"}}):
            report = grant_workspace_backfill.backfill_grant_workspaces(store)

        # Capped at the group's permission on each workspace: READ on team-a, USE fits under EDIT on team-b.
        assert rows(store, "SqlGatewayEndpointGroupPermission") == [("chat", "team-a", "READ"), ("chat", "team-b", "USE")]
        assert sum(report.assigned.values()) == 1 and sum(report.copied.values()) == 1

    @pytest.mark.parametrize("found", [set(), {"team-a", "team-b"}], ids=["deleted", "ambiguous"])
    def test_an_unresolvable_grant_is_marked_and_reported(self, store, audit_events, found):
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with resources(registered_model={"churn": found} if found else {}):
            report = grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", UNRESOLVED, "EDIT")]
        assert report.unresolved_count == 1
        [event] = [e for e in audit_events if e["event"] == "permission.workspace_unresolved"]
        assert event["resource_type"] == "registered_model_permissions" and event["detail"]["count"] == 1

    def test_an_explicit_grant_wins_over_the_legacy_row(self, store):
        store.create_workspace_permission("team-a", ALICE, "READ")
        from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        token = set_auth_context(AuthContext(username=ALICE, is_admin=False, workspace="team-a"))
        try:
            store.create_registered_model_permission("churn", ALICE, "READ")
        finally:
            clear_auth_context(token)
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE, permission="MANAGE")
        with resources(registered_model={"churn": {"team-a"}}):
            report = grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", "team-a", "READ")]
        assert sum(report.merged.values()) == 1

    def test_an_unresolved_grant_is_never_placed_later(self, store):
        """A same-named resource created after the first run — here in default — must not pick up
        the grant, even though a default-workspace name is otherwise kept without a reach check."""
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE, permission="MANAGE")
        with resources(registered_model={}):
            grant_workspace_backfill.backfill_grant_workspaces(store)
        with resources(registered_model={"churn": {"default"}}):
            report = grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", UNRESOLVED, "MANAGE")]
        assert sum(report.assigned.values()) == 0

    def test_an_unresolved_grant_does_not_count_with_workspaces_off_either(self, store, monkeypatch):
        from mlflow_oidc_auth.utils import effective_registered_model_permission, permissions

        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE, permission="MANAGE")
        with resources(registered_model={}):
            grant_workspace_backfill.backfill_grant_workspaces(store)
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        permissions._get_permission_cache().clear()

        assert effective_registered_model_permission("churn", ALICE).permission.name == "NO_PERMISSIONS"

    def test_unreadable_mlflow_changes_nothing(self, store):
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with patch.object(grant_workspace_backfill, "_mlflow_resource_workspaces", return_value=None):
            grant_workspace_backfill.backfill_grant_workspaces(store)

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", None, "EDIT")]

    def test_a_failure_never_raises(self, store):
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with patch.object(grant_workspace_backfill, "_mlflow_resource_workspaces", side_effect=RuntimeError("boom")):
            assert grant_workspace_backfill.backfill_grant_workspaces(store) is None

    def test_duplicate_unresolvable_grants_collapse_instead_of_breaking_the_run(self, store, monkeypatch):
        """A rolling upgrade can leave two unassigned copies; marking both unresolved would break the
        unique constraint and roll back every assignment on every start."""
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE, permission="MANAGE")
        legacy(store, "SqlRegisteredModelPermission", "fraud", user=ALICE)
        with resources(registered_model={"fraud": {"default"}}):
            grant_workspace_backfill.backfill_grant_workspaces(store)

        assert sorted(rows(store, "SqlRegisteredModelPermission")) == [("churn", UNRESOLVED, "EDIT"), ("fraud", "default", "EDIT")]

    def test_a_wrapped_unique_violation_is_the_race_not_a_failure(self, store, monkeypatch, caplog):
        from mlflow.exceptions import MlflowException
        from sqlalchemy.exc import IntegrityError

        def raced(*_args, **_kwargs):
            try:
                raise IntegrityError("INSERT", {}, Exception("unique"))
            except IntegrityError as e:
                raise MlflowException("database error") from e

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with patch.object(grant_workspace_backfill, "_place", side_effect=raced), caplog.at_level(logging.INFO):
            assert grant_workspace_backfill.backfill_grant_workspaces(store) is None

        assert "another process placed the same grants first" in caplog.text
        assert "backfill failed" not in caplog.text

    def test_losing_a_race_with_another_worker_rolls_back_and_never_raises(self, store, monkeypatch):
        from sqlalchemy.exc import IntegrityError

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        legacy(store, "SqlRegisteredModelPermission", "churn", user=ALICE)
        with patch.object(grant_workspace_backfill, "_place", side_effect=IntegrityError("INSERT", {}, Exception("unique"))):
            assert grant_workspace_backfill.backfill_grant_workspaces(store) is None

        assert rows(store, "SqlRegisteredModelPermission") == [("churn", None, "EDIT")]


class TestReadingMlflowsResources:
    def test_every_workspaces_resources_are_seen(self, tmp_path, monkeypatch):
        """Against MLflow's real SQL stores: names are collected from all workspaces at once."""
        from mlflow.store.model_registry.dbmodels.models import SqlRegisteredModel
        from mlflow.store.model_registry.sqlalchemy_store import SqlAlchemyStore as RegistryStore
        from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore as TrackingStore

        uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
        tracking = TrackingStore(uri, str(tmp_path / "artifacts"))
        registry = RegistryStore(uri)
        with registry.ManagedSessionMaker(read_only=False) as session:
            session.add(SqlRegisteredModel(name="churn", workspace="team-a", creation_time=1, last_updated_time=1))
            session.add(SqlRegisteredModel(name="churn", workspace="team-b", creation_time=1, last_updated_time=1))
            session.add(SqlRegisteredModel(name="solo", workspace="default", creation_time=1, last_updated_time=1))

        with (
            patch("mlflow.server.handlers._get_model_registry_store", return_value=registry),
            patch("mlflow.server.handlers._get_tracking_store", return_value=tracking),
        ):
            found = grant_workspace_backfill._mlflow_resource_workspaces()

        assert found["registered_model"] == {"churn": {"team-a", "team-b"}, "solo": {"default"}}
        assert found["gateway_endpoint"] == {} and found["gateway_secret"] == {}
