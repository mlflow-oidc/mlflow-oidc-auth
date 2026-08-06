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

from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import Permission
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
