"""Resource patterns (regex grants) apply in the workspace they were made in, or in every workspace.

A pattern created with a workspace named applies only to that workspace's resources; one created
with none ("All Workspaces") — and every pattern from before patterns carried a workspace — applies
everywhere. Fixtures come from the workspace-scoped grant tests.
"""

import pytest

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.tests.test_workspace_scoped_grants import (  # noqa: F401  (fixtures)
    ALICE,
    USERS_API,
    _clear_cache,
    api,
    in_workspace,
    model_permission,
    store,
)
from mlflow_oidc_auth.utils.grant_workspace import EVERY_WORKSPACE


def gateway_permission(name, username=ALICE):
    from mlflow_oidc_auth.utils.permissions import effective_gateway_endpoint_permission

    return effective_gateway_endpoint_permission(name, username).permission.name


def _pattern_rows(store):
    from mlflow_oidc_auth.db.models import SqlRegisteredModelRegexPermission

    with store.ManagedSessionMaker() as session:
        return sorted(session.query(SqlRegisteredModelRegexPermission.regex, SqlRegisteredModelRegexPermission.workspace).all())


class TestAPatternAppliesWhereItWasMade:
    def test_a_pattern_made_in_a_workspace_applies_only_there(self, store):
        with in_workspace("team-a"):
            store.create_registered_model_regex_permission("^churn.*", 1, "EDIT", ALICE)
        _clear_cache()
        with in_workspace("team-a"):
            assert model_permission("churn-v2") == "EDIT"
        _clear_cache()
        with in_workspace("team-b"):
            assert model_permission("churn-v2") == "NO_PERMISSIONS"

    def test_a_pattern_made_with_no_workspace_named_applies_everywhere(self, store):
        with in_workspace(None):
            store.create_registered_model_regex_permission("^churn.*", 1, "READ", ALICE)
        for workspace in ("team-a", "team-b", "default"):
            _clear_cache()
            with in_workspace(workspace):
                assert model_permission("churn-v2") == "READ", workspace
        assert _pattern_rows(store) == [("^churn.*", EVERY_WORKSPACE)]

    def test_the_same_pattern_may_be_made_once_per_workspace(self, store):
        for workspace, permission in (("team-a", "MANAGE"), ("team-b", "READ")):
            with in_workspace(workspace):
                store.create_registered_model_regex_permission("^churn.*", 1, permission, ALICE)
        _clear_cache()
        with in_workspace("team-a"):
            assert model_permission("churn-v2") == "MANAGE"
        _clear_cache()
        with in_workspace("team-b"):
            assert model_permission("churn-v2") == "READ"

    def test_group_patterns_follow_the_same_rule(self, store):
        with in_workspace("team-a"):
            store.create_group_gateway_endpoint_regex_permission("team", "^chat", 1, "USE")
        _clear_cache()
        with in_workspace("team-a"):
            assert gateway_permission("chat-gpt") == "USE"
        _clear_cache()
        with in_workspace("team-b"):
            assert gateway_permission("chat-gpt") == "NO_PERMISSIONS"


class TestWorkspacesDisabled:
    def test_patterns_for_every_workspace_apply_and_others_do_not(self, store, monkeypatch):
        with in_workspace("team-a"):
            store.create_registered_model_regex_permission("^team-a-only", 1, "MANAGE", ALICE)
        with in_workspace(None):
            store.create_registered_model_regex_permission("^everywhere", 1, "READ", ALICE)
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        _clear_cache()

        assert model_permission("team-a-only-model") == "NO_PERMISSIONS"
        assert model_permission("everywhere-model") == "READ"

    def test_a_new_pattern_applies_everywhere(self, store, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        store.create_registered_model_regex_permission("^x", 1, "READ", ALICE)

        assert _pattern_rows(store) == [("^x", EVERY_WORKSPACE)]


class TestDeletingAWorkspace:
    def test_its_patterns_go_and_patterns_for_every_workspace_stay(self, store):
        with in_workspace("team-a"):
            store.create_registered_model_regex_permission("^a", 1, "READ", ALICE)
        with in_workspace(None):
            store.create_registered_model_regex_permission("^all", 1, "READ", ALICE)

        store.wipe_workspace_permissions("team-a")

        assert _pattern_rows(store) == [("^all", EVERY_WORKSPACE)]


class TestThePermissionApi:
    def test_a_pattern_records_the_workspace_the_request_names_and_reports_it(self, api, store):
        response = api.admin.post(
            f"{USERS_API}/{ALICE}/registered-models-patterns",
            json={"regex": "^churn.*", "priority": 1, "permission": "READ"},
            headers={"X-MLFLOW-WORKSPACE": "team-a"},
        )
        assert response.status_code == 201, response.text
        listed = api.admin.get(f"{USERS_API}/{ALICE}/registered-models-patterns", headers={"X-MLFLOW-WORKSPACE": "team-a"}).json()

        assert _pattern_rows(store) == [("^churn.*", "team-a")]
        assert [(p["regex"], p.get("workspace")) for p in listed] == [("^churn.*", "team-a")]

    def test_with_no_workspace_named_a_pattern_applies_everywhere(self, api, store):
        response = api.admin.post(f"{USERS_API}/{ALICE}/registered-models-patterns", json={"regex": "^x", "priority": 1, "permission": "READ"})
        assert response.status_code == 201, response.text

        assert _pattern_rows(store) == [("^x", EVERY_WORKSPACE)]


@pytest.mark.parametrize("workspace, applies", [("team-a", True), ("team-b", False), (EVERY_WORKSPACE, True)])
def test_pattern_in_scope(workspace, applies):
    from types import SimpleNamespace

    from mlflow_oidc_auth.utils.grant_workspace import pattern_in_scope

    assert pattern_in_scope(SimpleNamespace(workspace="team-a"), workspace) is applies
    assert pattern_in_scope(SimpleNamespace(workspace=EVERY_WORKSPACE), workspace) is True


def test_orphan_detection_counts_only_patterns_for_the_resources_workspace():
    """Replaying who still manages a resource uses the patterns that apply in its workspace."""
    from types import SimpleNamespace

    from mlflow_oidc_auth.orphans import _regex_permission

    rule = SimpleNamespace(regex="^churn", permission="MANAGE", priority=1, workspace="team-a")

    assert _regex_permission([rule], "churn", False, "team-a") == "MANAGE"
    assert _regex_permission([rule], "churn", False, "team-b") is None
    assert _regex_permission([rule], "churn", False, None) == "MANAGE"  # workspace not known: may apply


class TestOrphanDetection:
    """Who else still manages a resource is replayed with the patterns that apply in its workspace."""

    def test_a_pattern_for_another_workspace_does_not_keep_a_resource_held(self, store):
        from mlflow_oidc_auth.orphans import find_orphaned_resources
        from mlflow_oidc_auth.tests.test_workspace_scoped_grants import VICTOR

        with in_workspace("team-a"):
            # As a model and as a prompt, so the verdict does not hinge on which ``churn`` is.
            store.create_registered_model_regex_permission("^churn", 1, "MANAGE", VICTOR)
            store.create_prompt_regex_permission("^churn", 1, "MANAGE", VICTOR)
        with in_workspace("team-b"):
            store.create_registered_model_permission("churn", ALICE, "MANAGE")

        assert find_orphaned_resources(ALICE, store=store) == [("registered_model", "team-b/churn")]

    def test_a_pattern_for_its_own_workspace_keeps_it_held(self, store):
        from mlflow_oidc_auth.orphans import find_orphaned_resources
        from mlflow_oidc_auth.tests.test_workspace_scoped_grants import VICTOR

        with in_workspace("team-b"):
            store.create_registered_model_regex_permission("^churn", 1, "MANAGE", VICTOR)
            store.create_prompt_regex_permission("^churn", 1, "MANAGE", VICTOR)
            store.create_registered_model_permission("churn", ALICE, "MANAGE")

        assert find_orphaned_resources(ALICE, store=store) == []


def test_with_workspaces_disabled_orphan_detection_counts_only_patterns_that_apply(store, monkeypatch):
    """As at request time: with workspaces disabled only patterns for every workspace (or default) apply."""
    from mlflow_oidc_auth.orphans import find_orphaned_resources
    from mlflow_oidc_auth.tests.test_workspace_scoped_grants import VICTOR

    with in_workspace("team-a"):
        store.create_registered_model_regex_permission("^churn", 1, "MANAGE", VICTOR)
        store.create_prompt_regex_permission("^churn", 1, "MANAGE", VICTOR)
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    store.create_registered_model_permission("churn", ALICE, "MANAGE")

    assert find_orphaned_resources(ALICE, store=store) == [("registered_model", "churn")]
