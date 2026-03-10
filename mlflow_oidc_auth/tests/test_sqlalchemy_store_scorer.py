"""Tests for scorer-related methods and other non-gateway methods in sqlalchemy_store.py.

Covers the delegation from SqlAlchemyStore scorer methods to the underlying
repository classes, plus ping() and get_user_profile().
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore


@pytest.fixture
def store_with_mocked_repos() -> SqlAlchemyStore:
    """Create a SqlAlchemyStore with scorer and user repositories mocked out."""
    s = object.__new__(SqlAlchemyStore)

    # Scorer repos
    s.scorer_repo = MagicMock()
    s.scorer_group_repo = MagicMock()
    s.scorer_regex_repo = MagicMock()
    s.scorer_group_regex_repo = MagicMock()

    # User repo
    s.user_repo = MagicMock()

    # Engine for ping
    s.engine = MagicMock()

    # ManagedSessionMaker for inline queries
    s.ManagedSessionMaker = MagicMock()

    return s


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------


class TestPing:
    """Tests for SqlAlchemyStore.ping() health check."""

    def test_returns_true_on_success(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should return True when database is reachable."""
        result = store_with_mocked_repos.ping()
        assert result is True

    def test_returns_false_on_failure(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should return False when database is unreachable."""
        store_with_mocked_repos.engine.connect.side_effect = Exception("connection refused")
        result = store_with_mocked_repos.ping()
        assert result is False


# ---------------------------------------------------------------------------
# get_user_profile
# ---------------------------------------------------------------------------


class TestGetUserProfile:
    """Tests for SqlAlchemyStore.get_user_profile()."""

    def test_delegates_to_user_repo(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate to user_repo.get_profile."""
        expected = MagicMock()
        store_with_mocked_repos.user_repo.get_profile.return_value = expected

        result = store_with_mocked_repos.get_user_profile("alice")

        assert result is expected
        store_with_mocked_repos.user_repo.get_profile.assert_called_once_with("alice")


# ---------------------------------------------------------------------------
# Scorer User-Scoped CRUD
# ---------------------------------------------------------------------------


class TestScorerPermissions:
    """Tests for scorer user-scoped permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate create to scorer_repo.grant_permission."""
        store_with_mocked_repos.create_scorer_permission("exp-1", "accuracy", "alice", "READ")
        store_with_mocked_repos.scorer_repo.grant_permission.assert_called_once_with("exp-1", "accuracy", "alice", "READ")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate get to scorer_repo.get_permission."""
        store_with_mocked_repos.get_scorer_permission("exp-1", "accuracy", "alice")
        store_with_mocked_repos.scorer_repo.get_permission.assert_called_once_with("exp-1", "accuracy", "alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate list to scorer_repo.list_permissions_for_user."""
        store_with_mocked_repos.list_scorer_permissions("alice")
        store_with_mocked_repos.scorer_repo.list_permissions_for_user.assert_called_once_with("alice")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate update to scorer_repo.update_permission."""
        store_with_mocked_repos.update_scorer_permission("exp-1", "accuracy", "alice", "MANAGE")
        store_with_mocked_repos.scorer_repo.update_permission.assert_called_once_with("exp-1", "accuracy", "alice", "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate delete to scorer_repo.revoke_permission."""
        store_with_mocked_repos.delete_scorer_permission("exp-1", "accuracy", "alice")
        store_with_mocked_repos.scorer_repo.revoke_permission.assert_called_once_with("exp-1", "accuracy", "alice")


# ---------------------------------------------------------------------------
# Scorer Cascading Delete (inline SQL logic)
# ---------------------------------------------------------------------------


class TestDeleteScorerPermissionsForScorer:
    """Tests for SqlAlchemyStore.delete_scorer_permissions_for_scorer()."""

    def test_deletes_user_and_group_permissions(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delete both user and group scorer permissions."""
        mock_session = MagicMock()
        store_with_mocked_repos.ManagedSessionMaker.return_value.__enter__ = MagicMock(return_value=mock_session)
        store_with_mocked_repos.ManagedSessionMaker.return_value.__exit__ = MagicMock(return_value=False)

        store_with_mocked_repos.delete_scorer_permissions_for_scorer("exp-1", "accuracy")

        # Should have called query().filter().delete() twice (user + group)
        assert mock_session.query.call_count == 2
        mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Scorer Group-Scoped CRUD
# ---------------------------------------------------------------------------


class TestScorerGroupPermissions:
    """Tests for scorer group-scoped permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate create to scorer_group_repo.grant_group_permission."""
        store_with_mocked_repos.create_group_scorer_permission("team-a", "exp-1", "accuracy", "EDIT")
        store_with_mocked_repos.scorer_group_repo.grant_group_permission.assert_called_once_with("team-a", "exp-1", "accuracy", "EDIT")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate update to scorer_group_repo.update_group_permission."""
        store_with_mocked_repos.update_group_scorer_permission("team-a", "exp-1", "accuracy", "MANAGE")
        store_with_mocked_repos.scorer_group_repo.update_group_permission.assert_called_once_with("team-a", "exp-1", "accuracy", "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate delete to scorer_group_repo.revoke_group_permission."""
        store_with_mocked_repos.delete_group_scorer_permission("team-a", "exp-1", "accuracy")
        store_with_mocked_repos.scorer_group_repo.revoke_group_permission.assert_called_once_with("team-a", "exp-1", "accuracy")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate list to scorer_group_repo.list_permissions_for_group."""
        store_with_mocked_repos.list_group_scorer_permissions("team-a")
        store_with_mocked_repos.scorer_group_repo.list_permissions_for_group.assert_called_once_with("team-a")

    def test_get_user_groups(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate to scorer_group_repo.get_group_permission_for_user_scorer."""
        store_with_mocked_repos.get_user_groups_scorer_permission("exp-1", "accuracy", "alice")
        store_with_mocked_repos.scorer_group_repo.get_group_permission_for_user_scorer.assert_called_once_with("exp-1", "accuracy", "alice")


# ---------------------------------------------------------------------------
# Scorer Regex (User-Scoped) CRUD
# ---------------------------------------------------------------------------


class TestScorerRegexPermissions:
    """Tests for scorer user-scoped regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate create to scorer_regex_repo.grant."""
        store_with_mocked_repos.create_scorer_regex_permission("^acc.*", 1, "READ", "alice")
        store_with_mocked_repos.scorer_regex_repo.grant.assert_called_once_with(regex="^acc.*", priority=1, permission="READ", username="alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate list to scorer_regex_repo.list_regex_for_user."""
        store_with_mocked_repos.list_scorer_regex_permissions("alice")
        store_with_mocked_repos.scorer_regex_repo.list_regex_for_user.assert_called_once_with("alice")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate get to scorer_regex_repo.get."""
        store_with_mocked_repos.get_scorer_regex_permission("alice", 42)
        store_with_mocked_repos.scorer_regex_repo.get.assert_called_once_with(username="alice", id=42)

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate update to scorer_regex_repo.update."""
        store_with_mocked_repos.update_scorer_regex_permission(42, "^new.*", 2, "MANAGE", "alice")
        store_with_mocked_repos.scorer_regex_repo.update.assert_called_once_with(id=42, regex="^new.*", priority=2, permission="MANAGE", username="alice")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate delete to scorer_regex_repo.revoke."""
        store_with_mocked_repos.delete_scorer_regex_permission(42, "alice")
        store_with_mocked_repos.scorer_regex_repo.revoke.assert_called_once_with(id=42, username="alice")


# ---------------------------------------------------------------------------
# Scorer Regex (Group-Scoped) CRUD
# ---------------------------------------------------------------------------


class TestScorerGroupRegexPermissions:
    """Tests for scorer group-scoped regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate create to scorer_group_regex_repo.grant."""
        store_with_mocked_repos.create_group_scorer_regex_permission("team-a", "^acc.*", 1, "READ")
        store_with_mocked_repos.scorer_group_regex_repo.grant.assert_called_once_with(group_name="team-a", regex="^acc.*", priority=1, permission="READ")

    def test_list_for_groups_ids(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate list to scorer_group_regex_repo.list_permissions_for_groups_ids."""
        store_with_mocked_repos.list_group_scorer_regex_permissions_for_groups_ids([1, 2])
        store_with_mocked_repos.scorer_group_regex_repo.list_permissions_for_groups_ids.assert_called_once_with([1, 2])

    def test_list_by_group_name_found(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should look up group by name and list regex permissions."""
        mock_session = MagicMock()
        mock_group = MagicMock()
        mock_group.id = 99
        mock_session.query.return_value.filter.return_value.one_or_none.return_value = mock_group
        store_with_mocked_repos.ManagedSessionMaker.return_value.__enter__ = MagicMock(return_value=mock_session)
        store_with_mocked_repos.ManagedSessionMaker.return_value.__exit__ = MagicMock(return_value=False)

        store_with_mocked_repos.list_group_scorer_regex_permissions("team-a")

        store_with_mocked_repos.scorer_group_regex_repo.list_permissions_for_groups_ids.assert_called_once_with([99])

    def test_list_by_group_name_not_found(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should return empty list when group is not found."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one_or_none.return_value = None
        store_with_mocked_repos.ManagedSessionMaker.return_value.__enter__ = MagicMock(return_value=mock_session)
        store_with_mocked_repos.ManagedSessionMaker.return_value.__exit__ = MagicMock(return_value=False)

        result = store_with_mocked_repos.list_group_scorer_regex_permissions("nonexistent")

        assert result == []
        store_with_mocked_repos.scorer_group_regex_repo.list_permissions_for_groups_ids.assert_not_called()

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate get to scorer_group_regex_repo.get."""
        store_with_mocked_repos.get_group_scorer_regex_permission("team-a", 42)
        store_with_mocked_repos.scorer_group_regex_repo.get.assert_called_once_with(group_name="team-a", id=42)

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate update to scorer_group_regex_repo.update."""
        store_with_mocked_repos.update_group_scorer_regex_permission(42, "team-a", "^new.*", 2, "MANAGE")
        store_with_mocked_repos.scorer_group_regex_repo.update.assert_called_once_with(
            id=42, group_name="team-a", regex="^new.*", priority=2, permission="MANAGE"
        )

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        """Should delegate delete to scorer_group_regex_repo.revoke."""
        store_with_mocked_repos.delete_group_scorer_regex_permission(42, "team-a")
        store_with_mocked_repos.scorer_group_regex_repo.revoke.assert_called_once_with(id=42, group_name="team-a")
