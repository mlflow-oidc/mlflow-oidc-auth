"""Tests for the batch permissions module.

These tests verify the batch permission resolution functions work correctly. Since issue #460
the batch path is a thin wrapper over the grant-context resolver: each test builds a context over
a store holding exactly the grants it names, and checks the decision.
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.utils.batch_permissions import (
    build_user_permission_context,
    resolve_experiment_permission_from_context,
    resolve_model_permission_from_context,
    resolve_prompt_permission_from_context,
    batch_resolve_experiment_permissions,
    batch_resolve_model_permissions,
    batch_resolve_prompt_permissions,
    filter_manageable_experiments,
    filter_manageable_models,
    filter_manageable_prompts,
)
from mlflow_oidc_auth.utils.grant_context import best_matching_regex


def _find(regexes, name, workspace=None):
    rule = best_matching_regex(regexes, name, "model name", workspace)
    return rule.permission if rule is not None else None


class TestMatchRegexPermissionOrNone:
    """Tests for the non-raising regex matcher the batch path uses."""

    def test_finds_matching_regex(self):
        """Should return permission when regex matches."""
        regex_perm = MagicMock()
        regex_perm.regex = "^model-.*"
        regex_perm.permission = "READ"

        result = _find([regex_perm], "model-test")
        assert result == "READ"

    def test_returns_none_when_no_match(self):
        """Should return None when no regex matches."""
        regex_perm = MagicMock()
        regex_perm.regex = "^other-.*"
        regex_perm.permission = "READ"

        result = _find([regex_perm], "model-test")
        assert result is None

    def test_returns_highest_ranked_match_at_equal_priority(self):
        """Of matches at the same priority, the highest-ranked permission decides (issue #459)."""
        regex_perm1 = MagicMock(priority=1, id=1)
        regex_perm1.regex = ".*"
        regex_perm1.permission = "READ"

        regex_perm2 = MagicMock(priority=1, id=2)
        regex_perm2.regex = "^model-.*"
        regex_perm2.permission = "MANAGE"

        result = _find([regex_perm1, regex_perm2], "model-test")
        assert result == "MANAGE"

    def test_empty_list_returns_none(self):
        """Should return None for empty regex list."""
        result = _find([], "model-test")
        assert result is None

    def test_partial_match_with_anchored_regex(self):
        """Should only match if regex pattern matches."""
        regex_perm = MagicMock()
        regex_perm.regex = "^exact$"
        regex_perm.permission = "MANAGE"

        assert _find([regex_perm], "exact") == "MANAGE"
        assert _find([regex_perm], "exact-extra") is None
        assert _find([regex_perm], "not-exact") is None

    def test_pattern_for_another_workspace_does_not_match(self):
        """A pattern recorded for another workspace is out of scope: no match, not an error."""
        regex_perm = MagicMock()
        regex_perm.regex = ".*"
        regex_perm.permission = "MANAGE"
        regex_perm.workspace = "team-b"

        assert _find([regex_perm], "model-test", workspace="team-a") is None
        assert _find([regex_perm], "model-test", workspace="team-b") == "MANAGE"

    def test_other_errors_propagate(self):
        """No match means None; any other error (here an invalid stored pattern) is raised, never swallowed."""
        import re

        regex_perm = MagicMock(regex="(", permission="MANAGE", priority=1, id=1)

        with pytest.raises(re.error):
            _find([regex_perm], "model-test")


_ORDER = ["user", "group", "regex", "group-regex"]


@contextmanager
def _config(order=None, default="NO_PERMISSIONS", workspaces=False):
    """Set the resolver's configuration on the shared config object."""
    from mlflow_oidc_auth.config import config

    with (
        patch.object(config, "PERMISSION_SOURCE_ORDER", list(order or _ORDER)),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", default),
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", workspaces),
    ):
        yield config


def _regex(pattern, permission, priority=1, id_=1, workspace="*"):
    return SimpleNamespace(id=id_, regex=pattern, permission=permission, priority=priority, workspace=workspace)


def _fake_store(
    *,
    group_ids=(1,),
    user_experiments=None,
    group_experiments=None,
    experiment_regex=(),
    group_experiment_regex=(),
    user_models=None,
    group_models=None,
    model_regex=(),
    group_model_regex=(),
    prompt_regex=(),
    group_prompt_regex=(),
):
    """A store holding exactly the given grants, as the grant context reads them (issue #460)."""
    store = MagicMock()
    # An exact-``=`` database: a bulk context matches direct grants in memory.
    store.engine.dialect.name = "sqlite"
    store.get_groups_ids_for_user.return_value = list(group_ids)
    store.list_experiment_permissions.return_value = [SimpleNamespace(experiment_id=k, permission=v) for k, v in (user_experiments or {}).items()]
    store.list_experiment_regex_permissions.return_value = list(experiment_regex)
    store.list_group_experiment_regex_permissions_for_groups_ids.return_value = list(group_experiment_regex)
    store.list_registered_model_permissions.return_value = [SimpleNamespace(name=k, permission=v) for k, v in (user_models or {}).items()]
    store.list_registered_model_regex_permissions.return_value = list(model_regex)
    store.list_group_registered_model_regex_permissions_for_groups_ids.return_value = list(group_model_regex)
    store.list_prompt_regex_permissions.return_value = list(prompt_regex)
    store.list_group_prompt_regex_permissions_for_groups_ids.return_value = list(group_prompt_regex)
    group_rows = {
        "experiment": [SimpleNamespace(experiment_id=k, permission=v) for k, v in (group_experiments or {}).items()],
        "registered_model": [SimpleNamespace(name=k, permission=v) for k, v in (group_models or {}).items()],
    }
    store.list_user_groups_grants.side_effect = lambda resource_type, username: group_rows.get(resource_type, [])
    # The bulk read of direct grants (store.list_user_grants), by grant table.
    store.list_user_grants.side_effect = lambda table, username: {
        "experiment": store.list_experiment_permissions,
        "registered_model": store.list_registered_model_permissions,
    }.get(table, lambda _username: [])(username)
    return store


@contextmanager
def _context(**grants):
    """A batch context over a store holding ``grants``; the store stays patched while it is used."""
    store = _fake_store(**grants)
    with patch("mlflow_oidc_auth.utils.grant_context._store", return_value=store):
        yield build_user_permission_context("testuser"), store


class TestSourceOrder:
    """The batch path walks PERMISSION_SOURCE_ORDER: first source holding a grant wins."""

    GRANTS = dict(
        user_models={"m": "MANAGE"},
        group_models={"m": "READ", "g": "READ"},
        model_regex=[_regex("^(m|g|r)$", "EDIT")],
        group_model_regex=[_regex(".*", "USE")],
    )

    @pytest.mark.parametrize(
        "name, expected",
        [("m", ("user", "MANAGE")), ("g", ("group", "READ")), ("r", ("regex", "EDIT")), ("other", ("group-regex", "USE"))],
    )
    def test_first_source_with_a_grant_wins(self, name, expected):
        with _config(), _context(**self.GRANTS) as (ctx, _):
            result = resolve_model_permission_from_context(ctx, name)
        assert (result.kind, result.permission.name) == expected

    def test_returns_default_permission_when_no_match(self):
        with _config(default="READ"), _context() as (ctx, _):
            result = resolve_model_permission_from_context(ctx, "nothing")
        assert (result.kind, result.permission.name) == ("fallback", "READ")

    def test_respects_custom_source_order(self):
        with _config(order=["group", "user", "regex", "group-regex"]), _context(**self.GRANTS) as (ctx, _):
            result = resolve_model_permission_from_context(ctx, "m")
        assert (result.kind, result.permission.name) == ("group", "READ")


class TestBuildUserPermissionContext:
    """The batch context reads each resource type's grants once, from the store's list queries."""

    def test_builds_context_with_group_ids(self):
        """Grants come from the list queries, read once per type however many resources follow."""
        with _config(), _context(user_experiments={"exp-1": "READ"}, group_experiments={"exp-2": "MANAGE"}, group_ids=(1, 2)) as (ctx, store):
            assert ctx.username == "testuser"
            assert resolve_experiment_permission_from_context(ctx, "exp-1", "e1").permission.name == "READ"
            assert resolve_experiment_permission_from_context(ctx, "exp-2", "e2").permission.name == "MANAGE"
            assert resolve_experiment_permission_from_context(ctx, "exp-3", "e3").kind == "fallback"
            assert ctx.group_ids() == [1, 2]

        store.get_groups_ids_for_user.assert_called_once_with("testuser")
        store.list_experiment_permissions.assert_called_once_with("testuser")
        store.list_user_groups_grants.assert_called_once_with("experiment", "testuser")
        store.list_group_experiment_regex_permissions_for_groups_ids.assert_called_once_with([1, 2])
        # Only the type that was resolved is read.
        store.list_registered_model_permissions.assert_not_called()

    def test_builds_context_without_groups(self):
        """Should skip group regex queries when user has no groups."""
        with _config(), _context(group_ids=()) as (ctx, store):
            resolve_experiment_permission_from_context(ctx, "exp-1", "e1")
            resolve_model_permission_from_context(ctx, "m")
            resolve_prompt_permission_from_context(ctx, "p")
            assert ctx.group_ids() == []

        store.list_group_experiment_regex_permissions_for_groups_ids.assert_not_called()
        store.list_group_registered_model_regex_permissions_for_groups_ids.assert_not_called()
        store.list_group_prompt_regex_permissions_for_groups_ids.assert_not_called()


class TestResolveExperimentPermissionFromContext:
    """Tests for resolving experiment permissions from context."""

    GRANTS = dict(
        user_experiments={"exp-1": "MANAGE"},
        group_experiments={"exp-2": "READ"},
        experiment_regex=[_regex("^test-.*", "EDIT")],
        group_experiment_regex=[_regex("^prod-.*", "READ")],
    )

    @pytest.mark.parametrize("pattern_workspace, expected_kind", [("team-b", "fallback"), ("team-a", "regex")])
    def test_regex_for_another_workspace_is_denied(self, pattern_workspace, expected_kind):
        """A pattern recorded for another workspace than the request's grant workspace never matches."""
        with (
            _config(),
            patch("mlflow_oidc_auth.utils.grant_context._grant_scope", return_value=("team-a", "team-a")),
            _context(experiment_regex=[_regex(".*", "MANAGE", workspace=pattern_workspace)]) as (ctx, _),
        ):
            result = resolve_experiment_permission_from_context(ctx, "exp-1", "any-experiment")

        assert result.kind == expected_kind
        if expected_kind == "fallback":
            assert result.permission.name == "NO_PERMISSIONS"

    @pytest.mark.parametrize(
        "experiment_id, name, expected",
        [
            ("exp-1", "experiment-name", ("user", "MANAGE")),
            ("exp-2", "experiment-name", ("group", "READ")),
            ("exp-unknown", "test-experiment", ("regex", "EDIT")),
            ("exp-unknown", "prod-experiment", ("group-regex", "READ")),
        ],
    )
    def test_resolves_each_source(self, experiment_id, name, expected):
        with _config(), _context(**self.GRANTS) as (ctx, _):
            result = resolve_experiment_permission_from_context(ctx, experiment_id, name)
        assert (result.kind, result.permission.name) == expected

    @patch("mlflow_oidc_auth.utils.permissions._get_tracking_store")
    def test_fetches_experiment_name_when_not_provided(self, mock_get_store):
        """Should fetch experiment name from tracking store when not provided."""
        mock_experiment = MagicMock()
        mock_experiment.name = "test-fetched-experiment"
        mock_get_store.return_value.get_experiment.return_value = mock_experiment

        with _config(), _context(**self.GRANTS) as (ctx, _):
            result = resolve_experiment_permission_from_context(ctx, "exp-unknown", None)

        mock_get_store.return_value.get_experiment.assert_called_once_with("exp-unknown")
        # Should match the regex "^test-.*"
        assert result.permission.name == "EDIT"


class TestResolveModelPermissionFromContext:
    """Tests for resolving model permissions from context."""

    GRANTS = dict(
        user_models={"my-model": "MANAGE"},
        group_models={"team-model": "EDIT"},
        model_regex=[_regex("^ml-.*", "EDIT")],
        group_model_regex=[_regex("^shared-.*", "READ")],
    )

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("my-model", ("user", "MANAGE")),
            ("team-model", ("group", "EDIT")),
            ("ml-classifier", ("regex", "EDIT")),
            ("shared-model", ("group-regex", "READ")),
        ],
    )
    def test_resolves_each_source(self, name, expected):
        with _config(), _context(**self.GRANTS) as (ctx, _):
            result = resolve_model_permission_from_context(ctx, name)
        assert (result.kind, result.permission.name) == expected


class TestResolvePromptPermissionFromContext:
    """Prompts use the registered-model direct grants, and their own patterns."""

    GRANTS = dict(
        user_models={"my-prompt": "MANAGE"},
        group_models={"shared-prompt": "EDIT"},
        model_regex=[_regex(".*", "MANAGE")],  # a model pattern never applies to a prompt
        prompt_regex=[_regex("^prompt-.*", "EDIT")],
        group_prompt_regex=[_regex("^team-prompt-.*", "READ")],
    )

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("my-prompt", ("user", "MANAGE")),
            ("shared-prompt", ("group", "EDIT")),
            ("prompt-test", ("regex", "EDIT")),
            ("team-prompt-1", ("group-regex", "READ")),
            ("unmatched", ("fallback", "NO_PERMISSIONS")),
        ],
    )
    def test_resolves_each_source(self, name, expected):
        with _config(), _context(**self.GRANTS) as (ctx, _):
            result = resolve_prompt_permission_from_context(ctx, name)
        assert (result.kind, result.permission.name) == expected


class TestBatchResolvePermissions:
    """Tests for the batch permission resolution functions."""

    @patch("mlflow_oidc_auth.utils.batch_permissions.build_user_permission_context")
    @patch("mlflow_oidc_auth.utils.batch_permissions.resolve_model_permission_from_context")
    def test_batch_resolve_model_permissions(self, mock_resolve, mock_build_ctx):
        """Should batch resolve permissions for all models."""
        mock_ctx = MagicMock()
        mock_build_ctx.return_value = mock_ctx

        perm_result = MagicMock()
        perm_result.permission.name = "READ"
        perm_result.kind = "user"
        mock_resolve.return_value = perm_result

        model1 = MagicMock()
        model1.name = "model-1"
        model2 = MagicMock()
        model2.name = "model-2"

        result = batch_resolve_model_permissions("testuser", [model1, model2])

        # Should build context once
        mock_build_ctx.assert_called_once_with("testuser")

        # Should resolve for each model
        assert len(result) == 2
        assert "model-1" in result
        assert "model-2" in result
        assert mock_resolve.call_count == 2

    @patch("mlflow_oidc_auth.utils.batch_permissions.build_user_permission_context")
    @patch("mlflow_oidc_auth.utils.batch_permissions.resolve_experiment_permission_from_context")
    def test_batch_resolve_experiment_permissions(self, mock_resolve, mock_build_ctx):
        """Should batch resolve permissions for all experiments."""
        mock_ctx = MagicMock()
        mock_build_ctx.return_value = mock_ctx

        perm_result = MagicMock()
        perm_result.permission.name = "MANAGE"
        perm_result.kind = "group"
        mock_resolve.return_value = perm_result

        exp1 = MagicMock()
        exp1.experiment_id = "1"
        exp1.name = "experiment-1"
        exp2 = MagicMock()
        exp2.experiment_id = "2"
        exp2.name = "experiment-2"

        result = batch_resolve_experiment_permissions("testuser", [exp1, exp2])

        # Should build context once
        mock_build_ctx.assert_called_once_with("testuser")

        # Should resolve for each experiment
        assert len(result) == 2
        assert "1" in result
        assert "2" in result
        assert mock_resolve.call_count == 2

    @patch("mlflow_oidc_auth.utils.batch_permissions.build_user_permission_context")
    @patch("mlflow_oidc_auth.utils.batch_permissions.resolve_prompt_permission_from_context")
    def test_batch_resolve_prompt_permissions(self, mock_resolve, mock_build_ctx):
        """Should batch resolve permissions for all prompts."""
        mock_ctx = MagicMock()
        mock_build_ctx.return_value = mock_ctx

        perm_result = MagicMock()
        perm_result.permission.name = "EDIT"
        perm_result.kind = "regex"
        mock_resolve.return_value = perm_result

        prompt1 = MagicMock()
        prompt1.name = "prompt-1"
        prompt2 = MagicMock()
        prompt2.name = "prompt-2"

        result = batch_resolve_prompt_permissions("testuser", [prompt1, prompt2])

        # Should build context once
        mock_build_ctx.assert_called_once_with("testuser")

        # Should resolve for each prompt
        assert len(result) == 2
        assert "prompt-1" in result
        assert "prompt-2" in result
        assert mock_resolve.call_count == 2

    @patch("mlflow_oidc_auth.utils.batch_permissions.build_user_permission_context")
    def test_batch_resolve_empty_list(self, mock_build_ctx):
        """Should handle empty input lists."""
        mock_ctx = MagicMock()
        mock_build_ctx.return_value = mock_ctx

        result = batch_resolve_model_permissions("testuser", [])

        assert result == {}
        mock_build_ctx.assert_called_once_with("testuser")


class TestFilterManageableFunctions:
    """Tests for the filter_manageable_* helper functions."""

    @patch("mlflow_oidc_auth.utils.batch_permissions.batch_resolve_experiment_permissions")
    def test_filter_manageable_experiments(self, mock_batch_resolve):
        """Should filter experiments to only those user can manage."""
        exp1 = MagicMock()
        exp1.experiment_id = "1"
        exp1.name = "can-manage"

        exp2 = MagicMock()
        exp2.experiment_id = "2"
        exp2.name = "cannot-manage"

        exp3 = MagicMock()
        exp3.experiment_id = "3"
        exp3.name = "also-can-manage"

        perm_manage = MagicMock()
        perm_manage.permission.can_manage = True

        perm_no_manage = MagicMock()
        perm_no_manage.permission.can_manage = False

        mock_batch_resolve.return_value = {
            "1": perm_manage,
            "2": perm_no_manage,
            "3": perm_manage,
        }

        result = filter_manageable_experiments("testuser", [exp1, exp2, exp3])

        assert len(result) == 2
        assert exp1 in result
        assert exp2 not in result
        assert exp3 in result
        mock_batch_resolve.assert_called_once_with("testuser", [exp1, exp2, exp3])

    @patch("mlflow_oidc_auth.utils.batch_permissions.batch_resolve_model_permissions")
    def test_filter_manageable_models(self, mock_batch_resolve):
        """Should filter models to only those user can manage."""
        model1 = MagicMock()
        model1.name = "can-manage"

        model2 = MagicMock()
        model2.name = "cannot-manage"

        perm_manage = MagicMock()
        perm_manage.permission.can_manage = True

        perm_no_manage = MagicMock()
        perm_no_manage.permission.can_manage = False

        mock_batch_resolve.return_value = {
            "can-manage": perm_manage,
            "cannot-manage": perm_no_manage,
        }

        result = filter_manageable_models("testuser", [model1, model2])

        assert len(result) == 1
        assert model1 in result
        assert model2 not in result
        mock_batch_resolve.assert_called_once_with("testuser", [model1, model2])

    @patch("mlflow_oidc_auth.utils.batch_permissions.batch_resolve_prompt_permissions")
    def test_filter_manageable_prompts(self, mock_batch_resolve):
        """Should filter prompts to only those user can manage."""
        prompt1 = MagicMock()
        prompt1.name = "can-manage"

        prompt2 = MagicMock()
        prompt2.name = "cannot-manage"

        perm_manage = MagicMock()
        perm_manage.permission.can_manage = True

        perm_no_manage = MagicMock()
        perm_no_manage.permission.can_manage = False

        mock_batch_resolve.return_value = {
            "can-manage": perm_manage,
            "cannot-manage": perm_no_manage,
        }

        result = filter_manageable_prompts("testuser", [prompt1, prompt2])

        assert len(result) == 1
        assert prompt1 in result
        assert prompt2 not in result
        mock_batch_resolve.assert_called_once_with("testuser", [prompt1, prompt2])

    @patch("mlflow_oidc_auth.utils.batch_permissions.batch_resolve_experiment_permissions")
    def test_filter_manageable_returns_empty_when_none_manageable(self, mock_batch_resolve):
        """Should return empty list when no items are manageable."""
        exp1 = MagicMock()
        exp1.experiment_id = "1"

        perm_no_manage = MagicMock()
        perm_no_manage.permission.can_manage = False

        mock_batch_resolve.return_value = {"1": perm_no_manage}

        result = filter_manageable_experiments("testuser", [exp1])

        assert result == []

    @patch("mlflow_oidc_auth.utils.batch_permissions.batch_resolve_model_permissions")
    def test_filter_manageable_returns_all_when_all_manageable(self, mock_batch_resolve):
        """Should return all items when all are manageable."""
        model1 = MagicMock()
        model1.name = "model-1"

        model2 = MagicMock()
        model2.name = "model-2"

        perm_manage = MagicMock()
        perm_manage.permission.can_manage = True

        mock_batch_resolve.return_value = {
            "model-1": perm_manage,
            "model-2": perm_manage,
        }

        result = filter_manageable_models("testuser", [model1, model2])

        assert len(result) == 2
        assert model1 in result
        assert model2 in result

    @patch("mlflow_oidc_auth.utils.batch_permissions.batch_resolve_prompt_permissions")
    def test_filter_manageable_empty_input(self, mock_batch_resolve):
        """Should handle empty input list."""
        mock_batch_resolve.return_value = {}

        result = filter_manageable_prompts("testuser", [])

        assert result == []


class TestApplyWorkspaceFallback:
    """The batch path's workspace fallback (the shared ``grant_context.workspace_fallback``)."""

    @staticmethod
    def _resolve(*, workspaces=True, request_workspace="my-workspace", workspace_permission=None, default="READ", **grants):
        with (
            _config(default=default, workspaces=workspaces),
            patch("mlflow.utils.workspace_context.get_request_workspace", return_value=request_workspace),
            patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=workspace_permission) as ws,
            _context(**grants) as (ctx, _),
        ):
            return resolve_model_permission_from_context(ctx, "model-1"), ws

    def test_returns_original_when_kind_is_not_fallback(self):
        """A resource-level grant is final: no workspace lookup."""
        result, ws = self._resolve(user_models={"model-1": "READ"})
        assert (result.kind, result.permission.name) == ("user", "READ")
        ws.assert_not_called()

    def test_returns_original_when_workspaces_disabled(self):
        result, ws = self._resolve(workspaces=False)
        assert (result.kind, result.permission.name) == ("fallback", "READ")
        ws.assert_not_called()

    def test_returns_workspace_kind_when_workspace_permission_exists(self):
        from mlflow_oidc_auth.permissions import EDIT

        result, ws = self._resolve(workspace_permission=EDIT)
        assert (result.kind, result.permission.name) == ("workspace", "EDIT")
        ws.assert_called_once_with("testuser", "my-workspace")

    def test_returns_workspace_deny_when_no_workspace_permission(self):
        result, _ = self._resolve(request_workspace="restricted-ws", workspace_permission=None)
        assert (result.kind, result.permission.name) == ("workspace-deny", "NO_PERMISSIONS")

    def test_returns_original_fallback_when_no_active_workspace(self):
        result, ws = self._resolve(request_workspace=None)
        assert (result.kind, result.permission.name) == ("fallback", "READ")
        ws.assert_not_called()

    def test_workspace_permission_is_looked_up_once_per_batch(self):
        """Every resource of a batch shares one workspace lookup (the context memo, issue #253)."""
        from mlflow_oidc_auth.permissions import READ

        with (
            _config(workspaces=True),
            patch("mlflow.utils.workspace_context.get_request_workspace", return_value="ws"),
            patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=READ) as ws,
            _context() as (ctx, _),
        ):
            for i in range(20):
                resolve_model_permission_from_context(ctx, f"model-{i}")
        ws.assert_called_once()


class TestWorkspaceFallbackIntegration:
    """Tests for workspace fallback integration in resolve_*_permission_from_context."""

    @staticmethod
    @contextmanager
    def _workspace(request_workspace, workspace_permission, default="READ", **grants):
        with (
            _config(default=default, workspaces=True),
            patch("mlflow.utils.workspace_context.get_request_workspace", return_value=request_workspace),
            patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=workspace_permission),
            _context(**grants) as (ctx, _),
        ):
            yield ctx

    def test_experiment_resolver_applies_workspace_fallback(self):
        """An experiment of the request's workspace (from its entity) takes the workspace permission."""
        from mlflow_oidc_auth.permissions import MANAGE

        with self._workspace("dev-ws", MANAGE) as ctx:
            result = resolve_experiment_permission_from_context(ctx, "exp-1", "experiment-name", "dev-ws")

        assert result.kind == "workspace"
        assert result.permission.name == "MANAGE"

    def test_experiment_of_another_workspace_gets_nothing(self):
        """An experiment of another workspace is judged in that workspace (issue #460).

        The caller's MANAGE on the request workspace never reaches it; without access to its own
        workspace it gets nothing, and with access the fallback is the permission held there.
        """
        from mlflow_oidc_auth.permissions import MANAGE, READ

        held = {"dev-ws": MANAGE}
        with (
            self._workspace("dev-ws", MANAGE) as ctx,
            patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", side_effect=lambda u, ws: held.get(ws)),
        ):
            result = resolve_experiment_permission_from_context(ctx, "exp-1", "experiment-name", "other-ws")
        assert (result.kind, result.permission.can_read) == ("workspace-deny", False)

        held["other-ws"] = READ
        with (
            self._workspace("dev-ws", MANAGE) as ctx,
            patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", side_effect=lambda u, ws: held.get(ws)),
        ):
            result = resolve_experiment_permission_from_context(ctx, "exp-1", "experiment-name", "other-ws")
        assert (result.kind, result.permission.name) == ("workspace", "READ")

    def test_experiment_without_entity_workspace_is_looked_up(self):
        """Without the entity's workspace, MLflow is asked whether the experiment is in the request's."""
        from mlflow_oidc_auth.permissions import MANAGE

        with (
            self._workspace("dev-ws", MANAGE) as ctx,
            patch("mlflow_oidc_auth.utils.permissions._experiment_in_request_workspace", return_value=False) as in_ws,
        ):
            result = resolve_experiment_permission_from_context(ctx, "exp-1", "experiment-name")

        in_ws.assert_called_once_with("exp-1")
        assert result.kind == "workspace-deny"

    def test_model_resolver_applies_workspace_fallback(self):
        """resolve_model_permission_from_context should apply workspace fallback."""
        from mlflow_oidc_auth.permissions import EDIT

        with self._workspace("dev-ws", EDIT) as ctx:
            result = resolve_model_permission_from_context(ctx, "model-1")

        assert result.kind == "workspace"
        assert result.permission.name == "EDIT"

    def test_prompt_resolver_applies_workspace_fallback(self):
        """resolve_prompt_permission_from_context should apply workspace fallback."""
        from mlflow_oidc_auth.permissions import READ

        with self._workspace("prod-ws", READ, default="NO_PERMISSIONS") as ctx:
            result = resolve_prompt_permission_from_context(ctx, "prompt-1")

        assert result.kind == "workspace"
        assert result.permission.name == "READ"

    def test_direct_permission_takes_priority_over_workspace(self):
        """Direct user permission should take priority over workspace fallback."""
        with self._workspace("dev-ws", None, user_experiments={"exp-1": "MANAGE"}) as ctx:
            result = resolve_experiment_permission_from_context(ctx, "exp-1", "experiment-name")

        assert result.kind == "user"
        assert result.permission.name == "MANAGE"


def test_header_less_request_workspace_sources_are_unchanged():
    """A header-less request with workspaces on, as on main (#480 tracks aligning them).

    MLflow serves it from its own workspace ("ws-x" here). Experiments, models and prompts without
    a grant of their own fall back to the caller's permission there. Gateway listings follow the
    single-resource gateway checks, which read the request header: with none, the global default.
    """
    from mlflow_oidc_auth.permissions import MANAGE
    from mlflow_oidc_auth.utils.batch_permissions import filter_manageable_gateway_endpoints, filter_manageable_gateway_secrets

    with (
        _config(workspaces=True),
        patch("mlflow.utils.workspace_context.get_request_workspace", return_value="ws-x"),
        patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value=None),
        patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=MANAGE),
        patch("mlflow_oidc_auth.utils.grant_context._store", return_value=_fake_store()),
    ):
        experiments = [SimpleNamespace(experiment_id="1", name="e", workspace="ws-x")]
        models = [SimpleNamespace(name="m")]
        assert filter_manageable_experiments("testuser", experiments) == experiments
        assert filter_manageable_models("testuser", models) == models
        assert filter_manageable_prompts("testuser", models) == models
        kinds = {r.kind for r in batch_resolve_model_permissions("testuser", models).values()}
        assert filter_manageable_gateway_endpoints("testuser", [{"name": "ep"}]) == []
        assert filter_manageable_gateway_secrets("testuser", [{"secret_name": "s"}]) == []
    assert kinds == {"workspace"}
