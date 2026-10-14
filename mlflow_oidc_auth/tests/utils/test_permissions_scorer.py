"""Tests for scorer and non-gateway permission functions in utils/permissions.py.

Covers:
- _match_regex_permission (for scorer regex matching)
- the scorer's grant sources (read by the grant context, issue #460)
- effective_scorer_permission
- can_manage_scorer
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.utils.permissions import (
    _match_regex_permission,
    can_manage_scorer,
    effective_scorer_permission,
    flush_permission_cache,
    resolve_permission,
)

_MOD = "mlflow_oidc_auth.utils.permissions"


# ---------------------------------------------------------------------------
# _match_regex_permission (scorer regex matching)
# ---------------------------------------------------------------------------


class TestMatchRegexPermissionScorer:
    """Tests for _match_regex_permission used with scorer regexes."""

    def test_returns_matching_permission(self) -> None:
        """Should return the permission when a regex matches the scorer name."""
        regex = MagicMock(regex="^accuracy.*", permission="READ", priority=1)
        result = _match_regex_permission([regex], "accuracy-v1", "scorer name")
        assert result == "READ"

    def test_returns_first_match(self) -> None:
        """Should return the first matching regex by (priority, id), whatever the list order."""
        r1 = MagicMock(regex=".*", permission="READ", priority=10, id=1)
        r2 = MagicMock(regex="^accuracy.*", permission="MANAGE", priority=1, id=2)
        result = _match_regex_permission([r1, r2], "accuracy-v1", "scorer name")
        assert result == "MANAGE"

    def test_raises_when_no_match(self) -> None:
        """Should raise MlflowException when no regex matches."""
        regex = MagicMock(regex="^other-.*", permission="READ", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "accuracy-v1", "scorer name")

    def test_empty_list_raises(self) -> None:
        """Should raise MlflowException when regex list is empty."""
        with pytest.raises(MlflowException):
            _match_regex_permission([], "scorer-1", "scorer name")


# ---------------------------------------------------------------------------
# _match_regex_permission (scorer group regex matching)
# ---------------------------------------------------------------------------


class TestMatchRegexPermissionScorerGroup:
    """Tests for _match_regex_permission used with scorer group regexes."""

    def test_returns_matching_permission(self) -> None:
        """Should return the group permission when a regex matches."""
        regex = MagicMock(regex="^team-scorer-.*", permission="MANAGE", priority=1)
        result = _match_regex_permission([regex], "team-scorer-1", "scorer name")
        assert result == "MANAGE"

    def test_raises_when_no_match(self) -> None:
        """Should raise MlflowException when no regex matches."""
        regex = MagicMock(regex="^private-.*", permission="MANAGE", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "team-scorer-1", "scorer name")

    def test_empty_list_raises(self) -> None:
        """Should raise MlflowException when regex list is empty."""
        with pytest.raises(MlflowException):
            _match_regex_permission([], "any-scorer", "scorer name")


# The scorer's grant sources
# ---------------------------------------------------------------------------


def _scorer_store(user=(), group=(), regex=(), group_regex=(), experiment=()):
    """A store holding only the given grants (``SimpleNamespace`` rows)."""
    store = MagicMock()
    store.get_groups_ids_for_user.return_value = [1]
    store.list_scorer_permissions.return_value = list(user)
    store.list_scorer_regex_permissions.return_value = list(regex)
    store.list_group_scorer_regex_permissions_for_groups_ids.return_value = list(group_regex)
    store.list_experiment_permissions.return_value = list(experiment)
    store.list_experiment_regex_permissions.return_value = []
    store.list_group_experiment_regex_permissions_for_groups_ids.return_value = []
    store.list_user_groups_grants.side_effect = lambda resource_type, username: list(group) if resource_type == "scorer" else []
    # Single checks look direct grants up one at a time (issue #460 review): the same rows, by key.
    store.get_scorer_permission.side_effect = lambda exp, scorer, username: _one(
        [r for r in user if (str(r.experiment_id), r.scorer_name) == (str(exp), scorer)], strongest=False
    )
    store.get_user_groups_scorer_permission.side_effect = lambda exp, scorer, username: _one(
        [r for r in group if (str(r.experiment_id), r.scorer_name) == (str(exp), scorer)], strongest=True
    )
    store.get_experiment_permission.side_effect = lambda exp, username: _one([r for r in experiment if str(r.experiment_id) == str(exp)], strongest=False)
    store.get_user_groups_experiment_permission.side_effect = lambda exp, username: _one([], strongest=True)
    return store


def _one(rows, strongest):
    """The grant a per-resource query returns: the row (or, across groups, the strongest), else RESOURCE_DOES_NOT_EXIST."""
    from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

    from mlflow_oidc_auth.permissions import compare_permissions

    if not rows:
        raise MlflowException("no grant", RESOURCE_DOES_NOT_EXIST)
    best = rows[0]
    for row in rows[1:]:
        if strongest and compare_permissions(best.permission, row.permission):
            best = row
    return best


class TestScorerSources:
    """A scorer's grants are keyed by (experiment, scorer name), for every source."""

    @pytest.fixture(autouse=True)
    def _isolated(self):
        from mlflow_oidc_auth.config import config

        flush_permission_cache()
        with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False), patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"):
            yield
        flush_permission_cache()

    @staticmethod
    def _resolve(store, experiment_id="exp-1", scorer_name="scorer-1"):
        with patch("mlflow_oidc_auth.utils.grant_context._store", return_value=store):
            return resolve_permission("scorer", experiment_id, "alice", scorer_name=scorer_name)

    def test_user_source_reads_the_users_scorer_grants(self) -> None:
        """The user source is the user's scorer grant on that experiment and scorer."""
        store = _scorer_store(user=[SimpleNamespace(experiment_id="exp-1", scorer_name="scorer-1", permission="READ")])
        result = self._resolve(store)
        assert (result.kind, result.permission.name) == ("user", "READ")
        store.get_scorer_permission.assert_called_once_with("exp-1", "scorer-1", "alice")

    def test_group_source_reads_the_users_groups_scorer_grants(self) -> None:
        """The group source is the strongest grant of the user's groups on that scorer."""
        store = _scorer_store(
            group=[
                SimpleNamespace(experiment_id="exp-1", scorer_name="scorer-1", permission="READ"),
                SimpleNamespace(experiment_id="exp-1", scorer_name="scorer-1", permission="EDIT"),
            ]
        )
        result = self._resolve(store)
        assert (result.kind, result.permission.name) == ("group", "EDIT")
        store.get_user_groups_scorer_permission.assert_called_once_with("exp-1", "scorer-1", "alice")

    def test_a_grant_on_another_scorer_or_experiment_does_not_apply(self) -> None:
        """Both parts of the key count: same name in another experiment, other name in the same one."""
        store = _scorer_store(
            user=[
                SimpleNamespace(experiment_id="exp-2", scorer_name="scorer-1", permission="MANAGE"),
                SimpleNamespace(experiment_id="exp-1", scorer_name="scorer-2", permission="MANAGE"),
            ]
        )
        result = self._resolve(store)
        assert (result.kind, result.permission.name) == ("fallback", "NO_PERMISSIONS")

    def test_regex_sources_match_the_scorer_name(self) -> None:
        store = _scorer_store(group_regex=[SimpleNamespace(id=1, regex="^scorer-", priority=1, permission="USE", workspace="*")])
        result = self._resolve(store)
        assert (result.kind, result.permission.name) == ("group-regex", "USE")


# ---------------------------------------------------------------------------
# effective_scorer_permission
# ---------------------------------------------------------------------------


class TestEffectiveScorerPermission:
    """Tests for effective_scorer_permission."""

    @patch(f"{_MOD}.resolve_scorer")
    def test_delegates_to_store_or_default(self, mock_resolver: MagicMock) -> None:
        """Should delegate to the grant context's one scorer resolver (issue #460)."""
        mock_result = MagicMock()
        mock_resolver.return_value = mock_result

        result = effective_scorer_permission("exp-1", "scorer-1", "alice")

        assert result is mock_result
        mock_resolver.assert_called_once()

    @patch(f"{_MOD}.resolve_scorer")
    def test_passes_scorer_config(self, mock_resolver: MagicMock) -> None:
        """Should resolve the scorer by experiment id and scorer name."""
        effective_scorer_permission("exp-1", "scorer-1", "alice")
        args, _ = mock_resolver.call_args
        assert args[0].username == "alice"
        assert args[1:] == ("exp-1", "scorer-1")


class TestEffectiveScorerPermissionInheritsExperiment:
    """A scorer with no grant of its own takes its experiment's effective permission.

    The experiment's resolution brings its own workspace fallback, so with workspaces enabled a
    scorer reaches exactly what its experiment reaches — never more.
    """

    @pytest.fixture(autouse=True)
    def _workspaces(self):
        from flask import Flask

        from mlflow_oidc_auth.utils.permissions import flush_permission_cache

        app = Flask(__name__)
        with app.test_request_context("/"):
            flush_permission_cache()
            from mlflow_oidc_auth.config import config

            with (
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True),
                patch.object(config, "PERMISSION_SOURCE_ORDER", ["user", "group", "regex", "group-regex"]),
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
                patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value="team-a"),
            ):
                yield
            flush_permission_cache()

    @staticmethod
    def _resolve(scorer_grant, experiment_grant, workspace_permission, in_workspace):
        from mlflow_oidc_auth.permissions import get_permission

        store = _scorer_store(
            user=[SimpleNamespace(experiment_id="exp-1", scorer_name="judge", permission=scorer_grant)] if scorer_grant else [],
            experiment=[SimpleNamespace(experiment_id="exp-1", permission=experiment_grant)] if experiment_grant else [],
        )
        ws = get_permission(workspace_permission) if workspace_permission else None
        with (
            patch("mlflow_oidc_auth.utils.grant_context._store", return_value=store),
            patch(f"{_MOD}._experiment_in_request_workspace", return_value=in_workspace),
            patch("mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached", return_value=ws),
        ):
            return effective_scorer_permission("exp-1", "judge", "alice")

    def test_no_grants_inherit_the_workspace_permission_through_the_experiment(self) -> None:
        result = self._resolve(None, None, "EDIT", in_workspace=True)
        assert (result.kind, result.permission.can_update) == ("workspace", True)

    def test_experiment_of_another_workspace_gives_nothing(self) -> None:
        result = self._resolve(None, None, "MANAGE", in_workspace=False)
        assert (result.kind, result.permission.can_read) == ("workspace-deny", False)

    def test_explicit_experiment_grant_decides_as_on_experiment_routes(self) -> None:
        result = self._resolve(None, "READ", "MANAGE", in_workspace=True)
        assert (result.kind, result.permission.can_read, result.permission.can_update) == ("user", True, False)

    def test_explicit_experiment_no_permissions_overrides_the_workspace(self) -> None:
        result = self._resolve(None, "NO_PERMISSIONS", "EDIT", in_workspace=True)
        assert result.permission.can_read is False

    def test_a_scorer_grant_wins_over_its_experiment(self) -> None:
        result = self._resolve("NO_PERMISSIONS", "MANAGE", "MANAGE", in_workspace=True)
        assert result.permission.can_read is False


# ---------------------------------------------------------------------------
# can_manage_scorer
# ---------------------------------------------------------------------------


class TestCanManageScorer:
    """Tests for can_manage_scorer."""

    @patch(f"{_MOD}.effective_scorer_permission")
    def test_returns_true_when_manageable(self, mock_eff: MagicMock) -> None:
        """Should return True when permission has can_manage."""
        mock_eff.return_value.permission.can_manage = True
        assert can_manage_scorer("exp-1", "scorer-1", "alice") is True

    @patch(f"{_MOD}.effective_scorer_permission")
    def test_returns_false_when_not_manageable(self, mock_eff: MagicMock) -> None:
        """Should return False when permission lacks can_manage."""
        mock_eff.return_value.permission.can_manage = False
        assert can_manage_scorer("exp-1", "scorer-1", "alice") is False
