"""Tests for workspace permission cache module."""

import importlib
from contextlib import contextmanager
import pytest
from unittest.mock import MagicMock, patch

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.permissions import EDIT, MANAGE, READ, USE


@contextmanager
def _patched_lookup():
    """Stand in for the source walk: ``mock_lookup`` returns the permission, never an error."""
    mock_lookup = MagicMock()
    with patch(
        "mlflow_oidc_auth.utils.workspace_cache._resolve_workspace_permission",
        side_effect=lambda username, workspace: (mock_lookup(username, workspace), False),
    ):
        yield mock_lookup


class TestGetWorkspacePermissionCached:
    """Test get_workspace_permission_cached() function."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset module-level cache between tests."""
        wc = importlib.import_module("mlflow_oidc_auth.utils.workspace_cache")

        wc._cache = None
        wc._denial_cache = None
        yield
        wc._cache = None
        wc._denial_cache = None

    def test_returns_none_when_workspaces_disabled(self):
        """get_workspace_permission_cached() returns None when MLFLOW_ENABLE_WORKSPACES is False."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = False

        with patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config):
            result = get_workspace_permission_cached("user1", "ws1")
            assert result is None

    def test_default_workspace_resolved_via_normal_lookup(self):
        """get_workspace_permission_cached('user1', 'default') uses normal lookup — no implicit grant."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            _patched_lookup() as mock_lookup,
        ):
            mock_lookup.return_value = READ
            result = get_workspace_permission_cached("user1", "default")
            assert result == READ
            mock_lookup.assert_called_once_with("user1", "default")

    def test_default_workspace_returns_none_when_no_permission(self):
        """get_workspace_permission_cached('user1', 'default') returns None when user has no permission — no implicit grant."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            _patched_lookup() as mock_lookup,
        ):
            mock_lookup.return_value = None
            result = get_workspace_permission_cached("user1", "default")
            assert result is None
            mock_lookup.assert_called_once_with("user1", "default")

    def test_calls_lookup_on_cache_miss(self):
        """get_workspace_permission_cached() calls _lookup_workspace_permission on cache miss."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            _patched_lookup() as mock_lookup,
        ):
            mock_lookup.return_value = READ
            result = get_workspace_permission_cached("user1", "ws1")
            mock_lookup.assert_called_once_with("user1", "ws1")
            assert result == READ

    def test_returns_cached_value_on_hit(self):
        """get_workspace_permission_cached() returns cached value on cache hit without DB query."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            _patched_lookup() as mock_lookup,
        ):
            mock_lookup.return_value = MANAGE
            # First call — cache miss
            get_workspace_permission_cached("user1", "ws1")
            # Second call — cache hit
            result = get_workspace_permission_cached("user1", "ws1")
            assert result == MANAGE
            # lookup should only be called once (not twice)
            assert mock_lookup.call_count == 1

    def test_caches_denial(self):
        """A denial is cached (issue #456), but only for that exact user and workspace.

        Before, denials were never cached, so a user with no grant re-walked every source on
        every request. The cached denial lives under the ``username:workspace`` key, so it must
        never be served to another user or for another workspace.
        """
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30

        grants = {("user2", "ws1"): MANAGE, ("user1", "ws2"): READ}

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            _patched_lookup() as mock_lookup,
        ):
            mock_lookup.side_effect = lambda username, workspace: grants.get((username, workspace))

            assert get_workspace_permission_cached("user1", "ws1") is None
            assert get_workspace_permission_cached("user1", "ws1") is None
            assert mock_lookup.call_count == 1, "denial was not cached"

            # Another user in the same workspace, and the same user in another workspace,
            # are resolved on their own — the denial is not served to them.
            assert get_workspace_permission_cached("user2", "ws1") == MANAGE
            assert get_workspace_permission_cached("user1", "ws2") == READ
            assert mock_lookup.call_count == 3

            # And the denial itself is unaffected by their grants.
            assert get_workspace_permission_cached("user1", "ws1") is None
            assert mock_lookup.call_count == 3

    def test_grant_clears_cached_denial(self):
        """The invalidation a grant write performs drops a cached denial, so the grant applies at once."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
            invalidate_workspace_permission,
        )

        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            _patched_lookup() as mock_lookup,
        ):
            mock_lookup.return_value = None
            assert get_workspace_permission_cached("user1", "ws1") is None
            assert get_workspace_permission_cached("user1", "ws1") is None
            assert mock_lookup.call_count == 1, "precondition: denial cached"

            # A grant is written; the store wrapper invalidates the user's entry.
            mock_lookup.return_value = READ
            invalidate_workspace_permission("user1", "ws1")

            assert get_workspace_permission_cached("user1", "ws1") == READ
            assert mock_lookup.call_count == 2


class TestLookupWorkspacePermission:
    """Test _lookup_workspace_permission() function."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset module-level cache between tests."""
        wc = importlib.import_module("mlflow_oidc_auth.utils.workspace_cache")

        wc._cache = None
        wc._denial_cache = None
        yield
        wc._cache = None
        wc._denial_cache = None

    def test_tries_user_permission_first(self):
        """_lookup_workspace_permission() tries user-level permission first."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()

        mock_config.PERMISSION_SOURCE_ORDER = ["user", "group", "regex", "group-regex"]

        mock_store = MagicMock()
        mock_perm = MagicMock()
        mock_perm.permission = "MANAGE"
        mock_store.get_workspace_permission.return_value = mock_perm

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "ws1")
            assert result == MANAGE
            mock_store.get_workspace_permission.assert_called_once_with("ws1", "user1")

    def test_falls_through_to_group_permission(self):
        """_lookup_workspace_permission() tries group-level when user-level fails."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()

        mock_config.PERMISSION_SOURCE_ORDER = ["user", "group", "regex", "group-regex"]

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        mock_group_perm = MagicMock()
        mock_group_perm.permission = "READ"
        mock_store.get_user_groups_workspace_permission.return_value = mock_group_perm

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "ws1")
            assert result == READ
            mock_store.get_user_groups_workspace_permission.assert_called_once_with("ws1", "user1")

    def test_returns_none_when_no_permission(self):
        """_lookup_workspace_permission() returns None when no user or group permission exists."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()

        mock_config.PERMISSION_SOURCE_ORDER = ["user", "group", "regex", "group-regex"]

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        mock_store.get_user_groups_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        mock_store.list_workspace_regex_permissions.return_value = []
        mock_store.get_groups_ids_for_user.return_value = []

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "ws1")
            assert result is None


class TestFlushWorkspaceCache:
    """Test flush_workspace_cache() function."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset module-level cache between tests."""
        wc = importlib.import_module("mlflow_oidc_auth.utils.workspace_cache")

        wc._cache = None
        wc._denial_cache = None
        yield
        wc._cache = None
        wc._denial_cache = None

    def test_flush_clears_all_entries(self):
        """flush_workspace_cache() clears the entire cache."""
        from mlflow_oidc_auth.utils.workspace_cache import (
            flush_workspace_cache,
            _get_cache,
        )

        mock_config = MagicMock()
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30
        mock_config.CACHE_BACKEND = "local"

        with patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config):
            cache = _get_cache()
            cache.set("user1:ws1", MANAGE)
            cache.set("user2:ws2", READ)
            assert cache.get("user1:ws1") == MANAGE
            assert cache.get("user2:ws2") == READ

            flush_workspace_cache()
            assert cache.get("user1:ws1") is None
            assert cache.get("user2:ws2") is None

    def test_flush_on_empty_cache(self):
        """flush_workspace_cache() succeeds even on empty cache."""
        from mlflow_oidc_auth.utils.workspace_cache import flush_workspace_cache

        mock_config = MagicMock()
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = 300
        mock_config.PERMISSION_CACHE_TTL_SECONDS = 30
        mock_config.CACHE_BACKEND = "local"

        with patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config):
            flush_workspace_cache()  # Should not raise


class TestMatchWorkspaceRegexPermission:
    """Test grant_context.match_workspace_pattern(), the workspace pattern matcher."""

    _next_id = 0

    def _make_regex_perm(self, regex, priority, permission, id_=None):
        """Helper to create a mock regex permission entity (ids ascend in creation order)."""
        TestMatchWorkspaceRegexPermission._next_id += 1
        perm = MagicMock()
        perm.regex = regex
        perm.priority = priority
        perm.permission = permission
        perm.id = id_ if id_ is not None else TestMatchWorkspaceRegexPermission._next_id
        return perm

    def test_returns_none_for_empty_list(self):
        """Returns None when no regexes provided."""
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        result = match_workspace_pattern([], "prod-workspace")
        assert result is None

    def test_returns_permission_for_matching_regex(self):
        """Returns permission for the first matching regex."""
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        regexes = [self._make_regex_perm("^prod-.*", 10, "MANAGE")]
        result = match_workspace_pattern(regexes, "prod-workspace")
        assert result == MANAGE

    def test_returns_none_when_no_match(self):
        """Returns None when no regex matches the workspace name."""
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        regexes = [self._make_regex_perm("^staging-.*", 10, "READ")]
        result = match_workspace_pattern(regexes, "prod-workspace")
        assert result is None

    def test_priority_ordering_lower_wins(self):
        """Lower priority number wins (D-07)."""
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        regexes = [
            self._make_regex_perm("^prod-.*", 5, "READ"),
            self._make_regex_perm("^prod-.*", 10, "MANAGE"),
        ]
        result = match_workspace_pattern(regexes, "prod-workspace")
        assert result == READ

    def test_same_priority_most_permissive_wins(self):
        """When multiple regexes match at the same priority, return most permissive (D-08)."""
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        regexes = [
            self._make_regex_perm("^prod-.*", 10, "READ"),
            self._make_regex_perm("^prod-work.*", 10, "MANAGE"),
        ]
        result = match_workspace_pattern(regexes, "prod-workspace")
        assert result == MANAGE

    def test_short_circuits_on_higher_priority_match(self):
        """Stops checking once a higher-priority tier is exhausted."""
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        regexes = [
            self._make_regex_perm("^prod-.*", 5, "EDIT"),
            self._make_regex_perm("^prod-work.*", 10, "MANAGE"),
        ]
        # Even though the second regex also matches and has higher permission,
        # it's at lower priority tier so should be ignored
        result = match_workspace_pattern(regexes, "prod-workspace")
        assert result == EDIT

    @pytest.mark.parametrize("first, second", [("MANAGE", "NO_PERMISSIONS"), ("NO_PERMISSIONS", "MANAGE")])
    def test_same_priority_no_permissions_wins(self, first, second):
        """NO_PERMISSIONS ranks highest, so it wins an equal-priority tie, as for resource patterns."""
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        regexes = [self._make_regex_perm("^prod-.*", 10, first), self._make_regex_perm("^prod-work.*", 10, second)]
        assert match_workspace_pattern(regexes, "prod-workspace") == NO_PERMISSIONS

    @pytest.mark.parametrize(
        "order",
        [(0, 1, 2), (2, 1, 0), (1, 2, 0), (2, 0, 1)],
        ids=["sorted", "reversed", "rotated", "mixed"],
    )
    def test_unsorted_input_resolves_as_sorted(self, order):
        """Unsorted input gives the sorted result: best priority tier, most permissive in it (D-07, D-08)."""
        from mlflow_oidc_auth.utils.grant_context import (
            match_workspace_pattern,
        )

        rules = [
            self._make_regex_perm("^prod-.*", 5, "READ", id_=30),
            self._make_regex_perm("^prod-work.*", 5, "EDIT", id_=20),
            self._make_regex_perm("^prod-.*", 10, "MANAGE", id_=10),
        ]
        result = match_workspace_pattern([rules[i] for i in order], "prod-workspace")
        # Unsorted, a list starting with the priority-10 MANAGE rule used to return MANAGE: the scan
        # took the first match's tier. Sorted, the priority-5 tier wins, and EDIT is its most permissive.
        assert result == EDIT


def _resolve_one_source(mock_store, source, username, workspace):
    """``grant_context.resolve_workspace_permission`` restricted to one source (issue #460)."""
    from mlflow_oidc_auth.utils.grant_context import resolve_workspace_permission

    with patch("mlflow_oidc_auth.store.store", mock_store):
        return resolve_workspace_permission(username, workspace, [source])


class TestResolveUserRegex:
    """The user-regex source of the workspace walk (formerly ``_resolve_user_regex``)."""

    def test_matches_workspace_against_user_regexes(self):
        """Calls store.list_workspace_regex_permissions and matches against workspace name."""
        mock_store = MagicMock()
        regex_perm = MagicMock()
        regex_perm.regex = "^prod-.*"
        regex_perm.priority = 10
        regex_perm.permission = "MANAGE"
        mock_store.list_workspace_regex_permissions.return_value = [regex_perm]

        result = _resolve_one_source(mock_store, "regex", "user1", "prod-workspace")
        assert result == (MANAGE, False)
        mock_store.list_workspace_regex_permissions.assert_called_once_with("user1")

    def test_returns_none_when_store_returns_empty_list(self):
        """Returns None when store returns empty list."""
        mock_store = MagicMock()
        mock_store.list_workspace_regex_permissions.return_value = []

        assert _resolve_one_source(mock_store, "regex", "user1", "prod-workspace") == (None, False)

    def test_returns_none_on_store_exception(self):
        """A store error denies, and is reported as an error so it is never cached."""
        mock_store = MagicMock()
        mock_store.list_workspace_regex_permissions.side_effect = Exception("DB error")

        assert _resolve_one_source(mock_store, "regex", "user1", "prod-workspace") == (None, True)


class TestResolveGroupRegex:
    """The group-regex source of the workspace walk (formerly ``_resolve_group_regex``)."""

    def test_matches_workspace_against_group_regexes(self):
        """Gets user's group IDs and matches workspace against group regex permissions."""
        mock_store = MagicMock()
        mock_store.get_groups_ids_for_user.return_value = [1, 2]
        regex_perm = MagicMock()
        regex_perm.regex = "^team-.*"
        regex_perm.priority = 5
        regex_perm.permission = "EDIT"
        mock_store.list_workspace_group_regex_permissions_for_groups_ids.return_value = [regex_perm]

        result = _resolve_one_source(mock_store, "group-regex", "user1", "team-workspace")
        assert result == (EDIT, False)
        mock_store.get_groups_ids_for_user.assert_called_once_with("user1")
        mock_store.list_workspace_group_regex_permissions_for_groups_ids.assert_called_once_with([1, 2])

    def test_returns_none_when_user_has_no_groups(self):
        """Returns None when user has no groups."""
        mock_store = MagicMock()
        mock_store.get_groups_ids_for_user.return_value = []

        assert _resolve_one_source(mock_store, "group-regex", "user1", "team-workspace") == (None, False)

    def test_returns_none_when_no_group_regex_matches(self):
        """Returns None when no group regex matches the workspace."""
        mock_store = MagicMock()
        mock_store.get_groups_ids_for_user.return_value = [1]
        regex_perm = MagicMock()
        regex_perm.regex = "^staging-.*"
        regex_perm.priority = 10
        regex_perm.permission = "READ"
        mock_store.list_workspace_group_regex_permissions_for_groups_ids.return_value = [regex_perm]

        assert _resolve_one_source(mock_store, "group-regex", "user1", "prod-workspace") == (None, False)

    def test_returns_none_on_store_exception(self):
        """A store error denies, and is reported as an error so it is never cached."""
        mock_store = MagicMock()
        mock_store.get_groups_ids_for_user.side_effect = Exception("DB error")

        assert _resolve_one_source(mock_store, "group-regex", "user1", "team-workspace") == (None, True)


class TestLookupWithRegexSources:
    """Integration-level tests for _lookup_workspace_permission() with regex sources."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset module-level cache between tests."""
        wc = importlib.import_module("mlflow_oidc_auth.utils.workspace_cache")

        wc._cache = None
        wc._denial_cache = None
        yield
        wc._cache = None
        wc._denial_cache = None

    def test_falls_through_to_user_regex(self):
        """When user-direct and group-direct fail, user-regex matches."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()

        mock_config.PERMISSION_SOURCE_ORDER = ["user", "group", "regex", "group-regex"]

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        mock_store.get_user_groups_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        regex_perm = MagicMock()
        regex_perm.regex = "^prod-.*"
        regex_perm.priority = 10
        regex_perm.permission = "EDIT"
        mock_store.list_workspace_regex_permissions.return_value = [regex_perm]

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "prod-workspace")
            assert result == EDIT

    def test_falls_through_to_group_regex(self):
        """When all direct and user-regex fail, group-regex matches."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()

        mock_config.PERMISSION_SOURCE_ORDER = ["user", "group", "regex", "group-regex"]

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        mock_store.get_user_groups_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        mock_store.list_workspace_regex_permissions.return_value = []
        mock_store.get_groups_ids_for_user.return_value = [1]
        group_regex_perm = MagicMock()
        group_regex_perm.regex = "^team-.*"
        group_regex_perm.priority = 5
        group_regex_perm.permission = "USE"
        mock_store.list_workspace_group_regex_permissions_for_groups_ids.return_value = [group_regex_perm]

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "team-workspace")
            assert result == USE

    def test_respects_custom_source_order(self):
        """Respects PERMISSION_SOURCE_ORDER — if order is ['regex', 'user'], regex is tried before user-direct."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()

        mock_config.PERMISSION_SOURCE_ORDER = ["regex", "user"]

        mock_store = MagicMock()
        # User-direct would return MANAGE
        mock_perm = MagicMock()
        mock_perm.permission = "MANAGE"
        mock_store.get_workspace_permission.return_value = mock_perm
        # But regex is first and matches with READ
        regex_perm = MagicMock()
        regex_perm.regex = "^prod-.*"
        regex_perm.priority = 10
        regex_perm.permission = "READ"
        mock_store.list_workspace_regex_permissions.return_value = [regex_perm]

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "prod-workspace")
            # regex is first in order, so READ wins even though user-direct has MANAGE
            assert result == READ
            # User-direct should NOT have been called because regex matched first
            mock_store.get_workspace_permission.assert_not_called()

    def test_invalid_source_name_skipped(self):
        """Invalid source names are skipped without error."""
        from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

        mock_config = MagicMock()

        mock_config.PERMISSION_SOURCE_ORDER = ["invalid-source", "user"]

        mock_store = MagicMock()
        mock_perm = MagicMock()
        mock_perm.permission = "MANAGE"
        mock_store.get_workspace_permission.return_value = mock_perm

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", mock_config),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            result = _lookup_workspace_permission("user1", "ws1")
            assert result == MANAGE


class TestDenialCache:
    """Denials: separate cache, short TTL, never an error (PR #464 review)."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        wc = importlib.import_module("mlflow_oidc_auth.utils.workspace_cache")

        wc._cache = None
        wc._denial_cache = None
        yield
        wc._cache = None
        wc._denial_cache = None

    @staticmethod
    def _config(workspace_ttl=300, permission_ttl=30):
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True
        mock_config.WORKSPACE_CACHE_MAX_SIZE = 1024
        mock_config.WORKSPACE_CACHE_TTL_SECONDS = workspace_ttl
        mock_config.PERMISSION_CACHE_TTL_SECONDS = permission_ttl
        mock_config.PERMISSION_SOURCE_ORDER = ["user", "group", "regex", "group-regex"]
        return mock_config

    @pytest.mark.parametrize(("workspace_ttl", "permission_ttl", "expected"), [(300, 30, 30), (10, 30, 10), (300, 300, 300)])
    def test_denial_ttl_is_at_most_the_permission_ttl(self, workspace_ttl, permission_ttl, expected):
        """A denial on one replica outlives a grant written via another for at most PERMISSION_CACHE_TTL_SECONDS."""
        from mlflow_oidc_auth.utils.workspace_cache import _get_cache, _get_denial_cache

        with patch("mlflow_oidc_auth.utils.workspace_cache.config", self._config(workspace_ttl, permission_ttl)):
            assert _get_denial_cache()._cache.ttl == expected
            assert _get_cache()._cache.ttl == workspace_ttl, "grant TTL is unchanged"

    def test_denial_expires_after_its_ttl(self):
        """The denial entry really expires on the short TTL, while a grant would not."""
        from mlflow_oidc_auth.utils.workspace_cache import _get_denial_cache, get_workspace_permission_cached

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", self._config(300, 30)),
            _patched_lookup() as mock_lookup,
        ):
            mock_lookup.return_value = None
            assert get_workspace_permission_cached("user1", "ws1") is None
            cache = _get_denial_cache()._cache
            cache.expire(cache.timer() + 31)  # 31 s on: past the denial TTL, inside the grant TTL
            mock_lookup.return_value = READ
            assert get_workspace_permission_cached("user1", "ws1") == READ
            assert mock_lookup.call_count == 2

    def test_lookup_error_is_not_cached_and_denies(self):
        from mlflow_oidc_auth.utils.workspace_cache import _get_cache, _get_denial_cache, get_workspace_permission_cached

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = RuntimeError("db down")
        mock_store.get_user_groups_workspace_permission.return_value = MagicMock(permission="MANAGE")

        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", self._config()),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            assert get_workspace_permission_cached("user1", "ws1") is None, "error must deny, not fall through to the group grant"
            assert _get_cache().get("user1:ws1") is None
            assert _get_denial_cache().get("user1:ws1") is None

            mock_store.get_workspace_permission.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
            assert get_workspace_permission_cached("user1", "ws1") == MANAGE, "nothing stale was cached by the failure"

    def test_unexpected_mlflow_exception_is_an_error(self):
        from mlflow.protos.databricks_pb2 import INTERNAL_ERROR

        from mlflow_oidc_auth.utils.workspace_cache import _resolve_workspace_permission

        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = MlflowException("boom", INTERNAL_ERROR)
        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", self._config()),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            assert _resolve_workspace_permission("user1", "ws1") == (None, True)

    def test_regex_not_found_is_no_grant_not_an_error(self):
        from mlflow_oidc_auth.utils.workspace_cache import _resolve_workspace_permission

        not_found = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)
        mock_store = MagicMock()
        mock_store.get_workspace_permission.side_effect = not_found
        mock_store.get_user_groups_workspace_permission.side_effect = not_found
        mock_store.list_workspace_regex_permissions.side_effect = not_found
        mock_store.get_groups_ids_for_user.side_effect = not_found
        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.config", self._config()),
            patch("mlflow_oidc_auth.store.store", mock_store),
        ):
            assert _resolve_workspace_permission("user1", "ws1") == (None, False)
