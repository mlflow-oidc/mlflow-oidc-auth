"""Tests for scorer and non-gateway permission functions in utils/permissions.py.

Covers:
- _match_regex_permission (for scorer regex matching)
- _build_scorer_sources
- effective_scorer_permission
- can_manage_scorer
"""

from unittest.mock import MagicMock, patch

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.utils.permissions import (
    _build_scorer_sources,
    _match_regex_permission,
    can_manage_scorer,
    effective_scorer_permission,
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
        """Should return the first matching regex in list order."""
        r1 = MagicMock(regex=".*", permission="READ", priority=10)
        r2 = MagicMock(regex="^accuracy.*", permission="MANAGE", priority=1)
        result = _match_regex_permission([r1, r2], "accuracy-v1", "scorer name")
        assert result == "READ"

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


# ---------------------------------------------------------------------------
# _build_scorer_sources
# ---------------------------------------------------------------------------


class TestBuildScorerSources:
    """Tests for _build_scorer_sources."""

    @patch(f"{_MOD}.store")
    def test_returns_all_four_sources(self, mock_store: MagicMock) -> None:
        """Should return a dict with user, group, regex, group-regex keys."""
        config = _build_scorer_sources("exp-1", "alice", scorer_name="scorer-1")
        assert "user" in config
        assert "group" in config
        assert "regex" in config
        assert "group-regex" in config

    @patch(f"{_MOD}.store")
    def test_user_source_calls_store(self, mock_store: MagicMock) -> None:
        """User source should call store.get_scorer_permission."""
        mock_store.get_scorer_permission.return_value.permission = "READ"
        config = _build_scorer_sources("exp-1", "alice", scorer_name="scorer-1")
        result = config["user"]()
        assert result == "READ"
        mock_store.get_scorer_permission.assert_called_once_with("exp-1", "scorer-1", "alice")

    @patch(f"{_MOD}.store")
    def test_group_source_calls_store(self, mock_store: MagicMock) -> None:
        """Group source should call store.get_user_groups_scorer_permission."""
        mock_store.get_user_groups_scorer_permission.return_value.permission = "EDIT"
        config = _build_scorer_sources("exp-1", "alice", scorer_name="scorer-1")
        result = config["group"]()
        assert result == "EDIT"
        mock_store.get_user_groups_scorer_permission.assert_called_once_with("exp-1", "scorer-1", "alice")


# ---------------------------------------------------------------------------
# effective_scorer_permission
# ---------------------------------------------------------------------------


class TestEffectiveScorerPermission:
    """Tests for effective_scorer_permission."""

    @patch(f"{_MOD}.get_permission_from_store_or_default")
    def test_delegates_to_store_or_default(self, mock_resolver: MagicMock) -> None:
        """Should delegate to get_permission_from_store_or_default."""
        mock_result = MagicMock()
        mock_resolver.return_value = mock_result

        result = effective_scorer_permission("exp-1", "scorer-1", "alice")

        assert result is mock_result
        mock_resolver.assert_called_once()

    @patch(f"{_MOD}.get_permission_from_store_or_default")
    def test_passes_scorer_config(self, mock_resolver: MagicMock) -> None:
        """Should pass scorer-specific config to resolver."""
        effective_scorer_permission("exp-1", "scorer-1", "alice")
        args = mock_resolver.call_args[0][0]
        assert "user" in args
        assert "group" in args
        assert "regex" in args
        assert "group-regex" in args


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
            with patch(f"{_MOD}.config") as config, patch("mlflow_oidc_auth.bridge.user.get_request_workspace", return_value="team-a"):
                config.MLFLOW_ENABLE_WORKSPACES = True
                config.PERMISSION_SOURCE_ORDER = ["user", "group", "regex", "group-regex"]
                config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"
                yield
            flush_permission_cache()

    @staticmethod
    def _resolve(scorer_grant, experiment_grant, workspace_permission, in_workspace):
        from mlflow_oidc_auth.models.permission import PermissionResult
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS, get_permission

        def store_or_default(sources):
            # The scorer's sources carry no "experiment" builder; tell them apart by call order.
            grant = experiment_grant if store_or_default.calls else scorer_grant
            store_or_default.calls += 1
            return PermissionResult(get_permission(grant), "user") if grant else PermissionResult(NO_PERMISSIONS, "fallback")

        store_or_default.calls = 0
        ws = get_permission(workspace_permission) if workspace_permission else None
        with (
            patch(f"{_MOD}.get_permission_from_store_or_default", side_effect=store_or_default),
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
