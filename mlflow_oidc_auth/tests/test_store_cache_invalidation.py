"""Tests for permission cache invalidation wiring in SqlAlchemyStore.

Verifies that every permission CUD method on SqlAlchemyStore calls
flush_permission_cache() after successful execution, as defined by the
_PERMISSION_CUD_METHODS list in sqlalchemy_store.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore, _PERMISSION_CUD_METHODS

FLUSH_PATCH_PATH = "mlflow_oidc_auth.utils.permissions.flush_permission_cache"


@pytest.fixture
def mock_store():
    """Store with all repositories mocked for isolated testing."""
    store = SqlAlchemyStore()
    store.user_repo = MagicMock()
    store.experiment_repo = MagicMock()
    store.experiment_group_repo = MagicMock()
    store.group_repo = MagicMock()
    store.registered_model_repo = MagicMock()
    store.registered_model_group_repo = MagicMock()
    store.prompt_group_repo = MagicMock()
    store.experiment_regex_repo = MagicMock()
    store.experiment_group_regex_repo = MagicMock()
    store.registered_model_regex_repo = MagicMock()
    store.registered_model_group_regex_repo = MagicMock()
    store.prompt_group_regex_repo = MagicMock()
    store.prompt_regex_repo = MagicMock()
    store.scorer_repo = MagicMock()
    store.scorer_group_repo = MagicMock()
    store.scorer_regex_repo = MagicMock()
    store.scorer_group_regex_repo = MagicMock()
    store.gateway_secret_repo = MagicMock()
    store.gateway_secret_group_repo = MagicMock()
    store.gateway_secret_regex_repo = MagicMock()
    store.gateway_secret_group_regex_repo = MagicMock()
    store.gateway_endpoint_repo = MagicMock()
    store.gateway_endpoint_group_repo = MagicMock()
    store.gateway_endpoint_regex_repo = MagicMock()
    store.gateway_endpoint_group_regex_repo = MagicMock()
    store.gateway_model_definition_repo = MagicMock()
    store.gateway_model_definition_group_repo = MagicMock()
    store.gateway_model_definition_regex_repo = MagicMock()
    store.gateway_model_definition_group_regex_repo = MagicMock()
    store.mcp_server_repo = MagicMock()
    store.mcp_server_group_repo = MagicMock()
    store.workspace_permission_repo = MagicMock()
    store.workspace_group_permission_repo = MagicMock()
    store.workspace_regex_permission_repo = MagicMock()
    store.workspace_group_regex_permission_repo = MagicMock()
    store.ManagedSessionMaker = MagicMock()
    return store


class TestPermissionCUDMethodsList:
    """Verify that _PERMISSION_CUD_METHODS is complete and accurate."""

    def test_all_methods_exist_on_store(self):
        """Every method name in _PERMISSION_CUD_METHODS must exist on SqlAlchemyStore."""
        for method_name in _PERMISSION_CUD_METHODS:
            assert hasattr(SqlAlchemyStore, method_name), f"Method {method_name} not found on SqlAlchemyStore"

    def test_workspace_methods_included(self):
        """Workspace permission methods MUST be in the list (issue #253).

        They were previously excluded on the grounds that workspace_cache had its own
        cache. But that is a *different* cache namespace: when workspaces are enabled,
        workspace permissions feed resolution through the workspace fallback, so
        clearing only the workspace cache left the permission cache serving a revoked
        permission until its TTL expired.
        """
        for method_name in (
            "create_workspace_permission",
            "update_workspace_permission",
            "delete_workspace_permission",
            "create_workspace_group_permission",
            "update_workspace_group_permission",
            "delete_workspace_group_permission",
        ):
            assert method_name in _PERMISSION_CUD_METHODS, f"{method_name} must flush the permission cache"

    def test_no_user_management_methods_included(self):
        """User CRUD methods (create_user, update_user, delete_user) must NOT be in the list."""
        user_mgmt_methods = {"create_user", "update_user", "delete_user"}
        overlap = user_mgmt_methods & set(_PERMISSION_CUD_METHODS)
        assert not overlap, f"User management methods should not be in _PERMISSION_CUD_METHODS: {overlap}"

    def test_group_membership_methods_included(self):
        """Group membership changes affect permission resolution and must be included."""
        assert "set_user_groups" in _PERMISSION_CUD_METHODS
        assert "add_user_to_group" in _PERMISSION_CUD_METHODS
        assert "remove_user_from_group" in _PERMISSION_CUD_METHODS


class TestCacheInvalidationWiring:
    """Verify that CUD methods actually flush the permission cache."""

    @patch(FLUSH_PATCH_PATH)
    def test_create_experiment_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating an experiment permission must flush the cache."""
        mock_store.create_experiment_permission("exp1", "user1", "READ")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_update_experiment_permission_flushes_cache(self, mock_flush, mock_store):
        """Updating an experiment permission must flush the cache."""
        mock_store.update_experiment_permission("exp1", "user1", "MANAGE")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_delete_experiment_permission_flushes_cache(self, mock_flush, mock_store):
        """Deleting an experiment permission must flush the cache."""
        mock_store.delete_experiment_permission("exp1", "user1")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_create_registered_model_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating a registered model permission must flush the cache."""
        mock_store.create_registered_model_permission("model1", "user1", "READ")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_wipe_registered_model_permissions_flushes_cache(self, mock_flush, mock_store):
        """Wiping registered model permissions must flush the cache."""
        mock_store.wipe_registered_model_permissions("model1")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_create_group_experiment_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating a group experiment permission must flush the cache."""
        mock_store.create_group_experiment_permission("group1", "exp1", "READ")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_create_experiment_regex_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating an experiment regex permission must flush the cache."""
        mock_store.create_experiment_regex_permission(".*", 1, "READ", "user1")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_create_scorer_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating a scorer permission must flush the cache."""
        mock_store.create_scorer_permission("exp1", "scorer1", "user1", "READ")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_create_gateway_endpoint_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating a gateway endpoint permission must flush the cache."""
        mock_store.create_gateway_endpoint_permission("gw1", "user1", "READ")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_create_gateway_secret_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating a gateway secret permission must flush the cache."""
        mock_store.create_gateway_secret_permission("secret1", "user1", "READ")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_create_gateway_model_definition_permission_flushes_cache(self, mock_flush, mock_store):
        """Creating a gateway model definition permission must flush the cache."""
        mock_store.create_gateway_model_definition_permission("model1", "user1", "READ")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_set_user_groups_unchanged_does_not_flush_cache(self, mock_flush, mock_store):
        """A sync that changed nothing (every login re-asserting membership) must not flush (issue #456)."""
        from mlflow_oidc_auth.repository.group import MembershipOutcome

        mock_store.group_repo.set_groups_for_user.return_value = MembershipOutcome()
        mock_store.set_user_groups("user1", ["group1", "group2"])
        mock_flush.assert_not_called()

    @pytest.mark.parametrize(
        "outcome_kwargs",
        [
            {"added": [("user1", "group2")]},
            {"removed": [("user1", "group1")]},
            {"added": [("user1", "group2")], "removed": [("user1", "group1")]},
        ],
        ids=["added", "removed", "both"],
    )
    @patch(FLUSH_PATCH_PATH)
    def test_set_user_groups_changed_flushes_cache(self, mock_flush, mock_store, outcome_kwargs):
        """A sync that added or removed a membership must flush the cache."""
        from mlflow_oidc_auth.repository.group import MembershipOutcome

        mock_store.group_repo.set_groups_for_user.return_value = MembershipOutcome(**outcome_kwargs)
        mock_store.set_user_groups("user1", ["group1", "group2"])
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_set_user_groups_unknown_result_flushes_cache(self, mock_flush, mock_store):
        """Anything but a MembershipOutcome reporting no change flushes — fail safe, never stale."""
        mock_store.group_repo.set_groups_for_user.return_value = None
        mock_store.set_user_groups("user1", ["group1"])
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_add_user_to_group_flushes_cache(self, mock_flush, mock_store):
        """Adding a user to a group must flush the cache."""
        mock_store.add_user_to_group("user1", "group1")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_remove_user_from_group_flushes_cache(self, mock_flush, mock_store):
        """Removing a user from a group must flush the cache."""
        mock_store.remove_user_from_group("user1", "group1")
        mock_flush.assert_called_once()

    @patch(FLUSH_PATCH_PATH)
    def test_delete_scorer_permissions_for_scorer_flushes_cache(self, mock_flush, mock_store):
        """Bulk-deleting scorer permissions must flush the cache."""
        mock_store.delete_scorer_permissions_for_scorer("exp1", "scorer1")
        mock_flush.assert_called_once()


class TestCacheNotInvalidatedForReadOps:
    """Verify that read-only methods do NOT flush the permission cache."""

    @patch(FLUSH_PATCH_PATH)
    def test_get_experiment_permission_does_not_flush(self, mock_flush, mock_store):
        """Reading a permission must not flush the cache."""
        mock_store.get_experiment_permission("exp1", "user1")
        mock_flush.assert_not_called()

    @patch(FLUSH_PATCH_PATH)
    def test_list_experiment_permissions_does_not_flush(self, mock_flush, mock_store):
        """Listing permissions must not flush the cache."""
        mock_store.list_experiment_permissions("user1")
        mock_flush.assert_not_called()

    @patch(FLUSH_PATCH_PATH)
    def test_get_user_does_not_flush(self, mock_flush, mock_store):
        """Getting user info must not flush the cache."""
        mock_store.get_user("user1")
        mock_flush.assert_not_called()

    @patch(FLUSH_PATCH_PATH)
    def test_create_user_does_not_flush(self, mock_flush, mock_store):
        """Creating a user must not flush the cache."""
        mock_store.create_user("user1", "pass", "User 1")
        mock_flush.assert_not_called()


class TestCacheFlushOnlyOnSuccess:
    """Verify that cache is NOT flushed when the underlying operation fails."""

    @patch(FLUSH_PATCH_PATH)
    def test_no_flush_on_repo_exception(self, mock_flush, mock_store):
        """When the repo raises an exception, cache must NOT be flushed."""
        mock_store.experiment_repo.grant_permission.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            mock_store.create_experiment_permission("exp1", "user1", "READ")
        mock_flush.assert_not_called()

    @patch(FLUSH_PATCH_PATH)
    def test_no_flush_on_regex_repo_exception(self, mock_flush, mock_store):
        """When a regex repo raises, cache must NOT be flushed."""
        mock_store.experiment_regex_repo.grant.side_effect = ValueError("invalid regex")
        with pytest.raises(ValueError, match="invalid regex"):
            mock_store.create_experiment_regex_permission("(bad", 1, "READ", "user1")
        mock_flush.assert_not_called()


class TestComprehensiveCUDCoverage:
    """Verify that ALL methods in _PERMISSION_CUD_METHODS are wrapped."""

    @patch(FLUSH_PATCH_PATH)
    def test_every_cud_method_is_wrapped(self, mock_flush, mock_store):
        """Call every CUD method and verify flush is called each time."""
        # Build a map of method name -> sample args to call it with
        sample_args = {
            # Experiment
            "create_experiment_permission": ("exp1", "user1", "READ"),
            "update_experiment_permission": ("exp1", "user1", "MANAGE"),
            "delete_experiment_permission": ("exp1", "user1"),
            "create_group_experiment_permission": ("group1", "exp1", "READ"),
            "update_group_experiment_permission": ("group1", "exp1", "MANAGE"),
            "delete_group_experiment_permission": ("group1", "exp1"),
            "create_experiment_regex_permission": (".*", 1, "READ", "user1"),
            "update_experiment_regex_permission": (".*", 1, "READ", "user1", 1),
            "delete_experiment_regex_permission": ("user1", 1),
            "create_group_experiment_regex_permission": ("group1", ".*", 1, "READ"),
            "update_group_experiment_regex_permission": (1, "group1", ".*", 1, "READ"),
            "delete_group_experiment_regex_permission": ("group1", 1),
            # Registered model
            "create_registered_model_permission": ("model1", "user1", "READ"),
            "update_registered_model_permission": ("model1", "user1", "MANAGE"),
            "delete_registered_model_permission": ("model1", "user1"),
            "rename_registered_model_permissions": ("old", "new"),
            "move_registered_model_permissions": ("old", "new"),
            "wipe_registered_model_permissions": ("model1",),
            "create_group_model_permission": ("group1", "model1", "READ"),
            "update_group_model_permission": ("group1", "model1", "MANAGE"),
            "delete_group_model_permission": ("group1", "model1"),
            "rename_group_model_permissions": ("old", "new"),
            "wipe_group_model_permissions": ("model1",),
            "create_registered_model_regex_permission": (".*", 1, "READ", "user1"),
            "update_registered_model_regex_permission": (1, ".*", 1, "READ", "user1"),
            "delete_registered_model_regex_permission": (1, "user1"),
            "create_group_registered_model_regex_permission": (
                "group1",
                ".*",
                1,
                "READ",
            ),
            "update_group_registered_model_regex_permission": (
                1,
                "group1",
                ".*",
                1,
                "READ",
            ),
            "delete_group_registered_model_regex_permission": ("group1", 1),
            # Prompt
            "create_group_prompt_permission": ("group1", "prompt1", "READ"),
            "update_group_prompt_permission": ("group1", "prompt1", "MANAGE"),
            "delete_group_prompt_permission": ("group1", "prompt1"),
            "create_prompt_regex_permission": (".*", 1, "READ", "user1"),
            "update_prompt_regex_permission": (1, ".*", 1, "READ", "user1"),
            "delete_prompt_regex_permission": (1, "user1"),
            "create_group_prompt_regex_permission": (".*", 1, "READ", "group1"),
            "update_group_prompt_regex_permission": (1, ".*", 1, "READ", "group1"),
            "delete_group_prompt_regex_permission": (1, "group1"),
            # Scorer
            "create_scorer_permission": ("exp1", "scorer1", "user1", "READ"),
            "update_scorer_permission": ("exp1", "scorer1", "user1", "MANAGE"),
            "delete_scorer_permission": ("exp1", "scorer1", "user1"),
            "delete_scorer_permissions_for_scorer": ("exp1", "scorer1"),
            "create_group_scorer_permission": ("group1", "exp1", "scorer1", "READ"),
            "update_group_scorer_permission": ("group1", "exp1", "scorer1", "MANAGE"),
            "delete_group_scorer_permission": ("group1", "exp1", "scorer1"),
            "create_scorer_regex_permission": (".*", 1, "READ", "user1"),
            "update_scorer_regex_permission": (1, ".*", 1, "READ", "user1"),
            "delete_scorer_regex_permission": (1, "user1"),
            "create_group_scorer_regex_permission": ("group1", ".*", 1, "READ"),
            "update_group_scorer_regex_permission": (1, "group1", ".*", 1, "READ"),
            "delete_group_scorer_regex_permission": (1, "group1"),
            # Gateway endpoint
            "create_gateway_endpoint_permission": ("gw1", "user1", "READ"),
            "update_gateway_endpoint_permission": ("gw1", "user1", "MANAGE"),
            "delete_gateway_endpoint_permission": ("gw1", "user1"),
            "grant_creator_prompt_permission": ("prompt1", "user1"),
            "grant_creator_gateway_endpoint_permission": ("gw1", "user1"),
            "grant_creator_gateway_secret_permission": ("gw1", "user1"),
            "grant_creator_gateway_model_definition_permission": ("gw1", "user1"),
            "rename_gateway_endpoint_permissions": ("old", "new"),
            "wipe_gateway_endpoint_permissions": ("gw1",),
            "create_group_gateway_endpoint_permission": ("group1", "gw1", "READ"),
            "update_group_gateway_endpoint_permission": ("group1", "gw1", "MANAGE"),
            "delete_group_gateway_endpoint_permission": ("group1", "gw1"),
            "create_gateway_endpoint_regex_permission": (".*", 1, "READ", "user1"),
            "update_gateway_endpoint_regex_permission": (1, ".*", 1, "READ", "user1"),
            "delete_gateway_endpoint_regex_permission": (1, "user1"),
            "create_group_gateway_endpoint_regex_permission": (
                "group1",
                ".*",
                1,
                "READ",
            ),
            "update_group_gateway_endpoint_regex_permission": (
                1,
                "group1",
                ".*",
                1,
                "READ",
            ),
            "delete_group_gateway_endpoint_regex_permission": (1, "group1"),
            # Gateway secret
            "create_gateway_secret_permission": ("secret1", "user1", "READ"),
            "update_gateway_secret_permission": ("secret1", "user1", "MANAGE"),
            "delete_gateway_secret_permission": ("secret1", "user1"),
            "wipe_gateway_secret_permissions": ("secret1",),
            "create_group_gateway_secret_permission": ("group1", "secret1", "READ"),
            "update_group_gateway_secret_permission": ("group1", "secret1", "MANAGE"),
            "delete_group_gateway_secret_permission": ("group1", "secret1"),
            "create_gateway_secret_regex_permission": (".*", 1, "READ", "user1"),
            "update_gateway_secret_regex_permission": (1, ".*", 1, "READ", "user1"),
            "delete_gateway_secret_regex_permission": (1, "user1"),
            "create_group_gateway_secret_regex_permission": ("group1", ".*", 1, "READ"),
            "update_group_gateway_secret_regex_permission": (
                1,
                "group1",
                ".*",
                1,
                "READ",
            ),
            "delete_group_gateway_secret_regex_permission": (1, "group1"),
            # Gateway model definition
            "create_gateway_model_definition_permission": ("model1", "user1", "READ"),
            "update_gateway_model_definition_permission": ("model1", "user1", "MANAGE"),
            "delete_gateway_model_definition_permission": ("model1", "user1"),
            "rename_gateway_model_definition_permissions": ("old", "new"),
            "wipe_gateway_model_definition_permissions": ("model1",),
            # MCP servers
            "create_mcp_server_permission": ("com.example/server", "user1", "READ"),
            "update_mcp_server_permission": ("com.example/server", "user1", "MANAGE"),
            "delete_mcp_server_permission": ("com.example/server", "user1"),
            "wipe_mcp_server_permissions": ("com.example/server",),
            "create_group_mcp_server_permission": ("group1", "com.example/server", "READ"),
            "update_group_mcp_server_permission": ("group1", "com.example/server", "MANAGE"),
            "delete_group_mcp_server_permission": ("group1", "com.example/server"),
            "create_group_gateway_model_definition_permission": (
                "group1",
                "model1",
                "READ",
            ),
            "update_group_gateway_model_definition_permission": (
                "group1",
                "model1",
                "MANAGE",
            ),
            "delete_group_gateway_model_definition_permission": ("group1", "model1"),
            "create_gateway_model_definition_regex_permission": (
                ".*",
                1,
                "READ",
                "user1",
            ),
            "update_gateway_model_definition_regex_permission": (
                1,
                ".*",
                1,
                "READ",
                "user1",
            ),
            "delete_gateway_model_definition_regex_permission": (1, "user1"),
            "create_group_gateway_model_definition_regex_permission": (
                "group1",
                ".*",
                1,
                "READ",
            ),
            "update_group_gateway_model_definition_regex_permission": (
                1,
                "group1",
                ".*",
                1,
                "READ",
            ),
            "delete_group_gateway_model_definition_regex_permission": (1, "group1"),
            # Group membership
            "set_user_groups": ("user1", ["group1"]),
            "add_user_to_group": ("user1", "group1"),
            "remove_user_from_group": ("user1", "group1"),
            # Workspace permissions (issue #253 — these feed the workspace fallback in
            # permission resolution, so they must flush the permission cache too)
            "create_workspace_permission": ("ws1", "user1", "READ"),
            "update_workspace_permission": ("ws1", "user1", "EDIT"),
            "delete_workspace_permission": ("ws1", "user1"),
            "create_workspace_group_permission": ("ws1", "group1", "READ"),
            "update_workspace_group_permission": ("ws1", "group1", "EDIT"),
            "delete_workspace_group_permission": ("ws1", "group1"),
            "create_workspace_regex_permission": (".*", 1, "READ", "user1"),
            "update_workspace_regex_permission": (".*", 1, "EDIT", "user1", 1),
            "delete_workspace_regex_permission": ("user1", 1),
            "create_workspace_group_regex_permission": ("group1", ".*", 1, "READ"),
            "update_workspace_group_regex_permission": (1, "group1", ".*", 1, "EDIT"),
            "delete_workspace_group_regex_permission": ("group1", 1),
            "wipe_workspace_permissions": ("ws1",),
        }

        # Verify every method in _PERMISSION_CUD_METHODS has sample args
        missing = set(_PERMISSION_CUD_METHODS) - set(sample_args.keys())
        assert not missing, f"Missing sample args for methods: {missing}"

        # Call each method and verify flush was called
        for method_name in _PERMISSION_CUD_METHODS:
            mock_flush.reset_mock()
            method = getattr(mock_store, method_name)
            args = sample_args[method_name]
            method(*args)
            assert mock_flush.called, f"flush_permission_cache() not called after {method_name}"


class TestWorkspaceCacheInvalidationRegressions:
    """Regression tests for the three fail-open holes found while investigating #253.

    All three left REVOKED authorization working until the workspace cache TTL (300s)
    expired. They are asserted at the store layer because that is where the guarantee
    now lives — putting invalidation only in the router made it bypassable by any
    other caller.
    """

    def test_group_workspace_cud_invalidates_group_members(self, mock_store):
        """BUG 1: group-scoped workspace CUD used to invalidate nothing (decision D-15)."""
        with patch("mlflow_oidc_auth.utils.workspace_cache.invalidate_group_workspace_permission") as inv:
            mock_store.delete_workspace_group_permission("ws-prod", "team-a")
            inv.assert_called_once_with(group_name="team-a", workspace="ws-prod")

    def test_membership_change_invalidates_that_users_workspace_entries(self, mock_store):
        """BUG 2: membership mutations flushed the permission cache but not the workspace cache."""
        with patch("mlflow_oidc_auth.utils.workspace_cache.invalidate_user_workspace_entries") as inv:
            mock_store.set_user_groups("alice", [])
            inv.assert_called_once_with("alice")

    def test_membership_invalidation_is_targeted_not_a_full_flush(self, mock_store):
        """Must NOT full-flush: OIDC login re-syncs membership on every sign-in."""
        with (
            patch("mlflow_oidc_auth.utils.workspace_cache.invalidate_user_workspace_entries"),
            patch("mlflow_oidc_auth.utils.workspace_cache.flush_workspace_cache") as flush,
        ):
            mock_store.set_user_groups("alice", ["g1"])
            flush.assert_not_called()

    def test_user_workspace_cud_invalidates_at_store_layer(self, mock_store):
        """BUG 3: user workspace CUD invalidated only in the router, so direct store calls leaked."""
        with patch("mlflow_oidc_auth.utils.workspace_cache.invalidate_workspace_permission") as inv:
            mock_store.delete_workspace_permission("ws-prod", "bob")
            inv.assert_called_once_with("bob", "ws-prod")

    def test_workspace_cud_also_flushes_the_permission_cache(self, mock_store):
        """BUG 3 (other half): the workspace cache and permission cache are separate namespaces."""
        with patch(FLUSH_PATCH_PATH) as mock_flush:
            mock_store.delete_workspace_permission("ws-prod", "bob")
            mock_flush.assert_called_once()

    def test_invalidation_failure_never_masks_a_successful_mutation(self, mock_store):
        """A cache problem must not turn a successful permission change into an error."""
        with patch(
            "mlflow_oidc_auth.utils.workspace_cache.invalidate_user_workspace_entries",
            side_effect=RuntimeError("cache down"),
        ):
            mock_store.set_user_groups("alice", ["g1"])  # must not raise


class TestSetUserGroupsRealStore:
    """End to end with a real store and the real permission cache: no mocks of the flush path.

    Uses registered models because experiment regex resolution reads experiment names from
    MLflow's tracking store, which these tests do not stand up.
    """

    @pytest.fixture
    def real_store(self, tmp_path, monkeypatch):
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.utils import permissions as perms

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["user", "group", "regex", "group-regex"])
        store = SqlAlchemyStore()
        store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        monkeypatch.setattr(perms, "store", store)
        # The grant context (issue #460) reads the store singleton itself.
        import mlflow_oidc_auth.store as store_module

        monkeypatch.setattr(store_module, "store", store)
        perms.flush_permission_cache()
        yield store
        perms.flush_permission_cache()

    def test_set_user_groups_removed_member_loses_access_immediately(self, real_store):
        """Negative test: removing a user from the granting group must not leave a cached READ behind."""
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS, READ
        from mlflow_oidc_auth.utils import permissions as perms

        real_store.create_user("nina@example.com", "Nina")
        real_store.populate_groups(["readers", "others"])
        real_store.set_user_groups("nina@example.com", ["readers", "others"])
        real_store.create_group_model_permission("readers", "model-1", "READ")

        warm = perms.effective_registered_model_permission("model-1", "nina@example.com")
        assert warm.permission == READ and warm.kind == "group", "precondition: READ cached through the group"

        real_store.set_user_groups("nina@example.com", ["others"])

        after = perms.effective_registered_model_permission("model-1", "nina@example.com")
        assert after.permission == NO_PERMISSIONS, "removed member still served the cached group READ"

    def test_set_user_groups_unchanged_keeps_cached_entries(self, real_store):
        """Re-asserting the same membership (a login) leaves other users' cached decisions in place."""
        from mlflow_oidc_auth.utils import permissions as perms

        for name in ("olga@example.com", "paul@example.com"):
            real_store.create_user(name, name)
        real_store.populate_groups(["readers"])
        real_store.set_user_groups("olga@example.com", ["readers"])
        real_store.set_user_groups("paul@example.com", ["readers"])
        real_store.create_group_model_permission("readers", "model-1", "READ")
        perms.effective_registered_model_permission("model-1", "paul@example.com")
        key = perms._make_cache_key("registered_model", "model-1", "paul@example.com", perms._get_cache_workspace())
        assert perms._get_permission_cache().get(key) is not None, "precondition: entry cached"

        real_store.set_user_groups("olga@example.com", ["readers"])

        assert perms._get_permission_cache().get(key) is not None, "an unchanged login sync flushed the cache"


WS_INVALIDATE_PATH = "mlflow_oidc_auth.utils.workspace_cache.invalidate_user_workspace_entries"


class TestMembershipWrapperWorkspaceInvalidation:
    """One membership wrapper; the sync skips BOTH invalidations when nothing changed (PR #464 review)."""

    @patch(WS_INVALIDATE_PATH)
    @patch(FLUSH_PATCH_PATH)
    def test_set_user_groups_unchanged_skips_workspace_invalidation(self, mock_flush, mock_ws, mock_store):
        from mlflow_oidc_auth.repository.group import MembershipOutcome

        mock_store.group_repo.set_groups_for_user.return_value = MembershipOutcome()
        mock_store.set_user_groups("user1", ["group1"])
        mock_flush.assert_not_called()
        mock_ws.assert_not_called()

    @patch(WS_INVALIDATE_PATH)
    @patch(FLUSH_PATCH_PATH)
    def test_set_user_groups_changed_invalidates_both_once(self, mock_flush, mock_ws, mock_store):
        from mlflow_oidc_auth.repository.group import MembershipOutcome

        mock_store.group_repo.set_groups_for_user.return_value = MembershipOutcome(removed=[("user1", "group1")])
        mock_store.set_user_groups("user1", [])
        mock_flush.assert_called_once()
        mock_ws.assert_called_once_with("user1")

    @pytest.mark.parametrize("method, args", [("add_user_to_group", ("user1", "group1")), ("remove_user_from_group", ("user1", "group1"))])
    @patch(WS_INVALIDATE_PATH)
    @patch(FLUSH_PATCH_PATH)
    def test_other_membership_methods_always_invalidate(self, mock_flush, mock_ws, mock_store, method, args):
        getattr(mock_store, method)(*args)
        mock_flush.assert_called_once()
        mock_ws.assert_called_once_with("user1")

    def test_membership_methods_are_wrapped_once(self):
        """The flush wrapper and the membership wrapper used to stack; now there is one layer."""
        from mlflow_oidc_auth.sqlalchemy_store import _MEMBERSHIP_CUD_METHODS

        for name in _MEMBERSHIP_CUD_METHODS:
            wrapped = getattr(SqlAlchemyStore, name)
            assert hasattr(wrapped, "__wrapped__")
            assert not hasattr(wrapped.__wrapped__, "__wrapped__"), f"{name} is wrapped more than once"


class TestSetUserGroupsWorkspaceRealStore:
    """Real store, real workspace cache."""

    @pytest.fixture
    def ws_store(self, tmp_path, monkeypatch):
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.utils import workspace_cache

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["user", "group", "regex", "group-regex"])
        store = SqlAlchemyStore()
        store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        monkeypatch.setattr("mlflow_oidc_auth.store.store", store, raising=False)
        workspace_cache.flush_workspace_cache()
        yield store
        workspace_cache.flush_workspace_cache()

    def test_set_user_groups_removed_member_loses_workspace_access_immediately(self, ws_store):
        """Negative test: a cached group-derived workspace grant must not survive removal from the group."""
        from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

        ws_store.create_user("wendy@example.com", "Wendy")
        ws_store.populate_groups(["ws-readers", "others"])
        ws_store.set_user_groups("wendy@example.com", ["ws-readers", "others"])
        ws_store.create_workspace_group_permission("ws-prod", "ws-readers", "READ")
        assert get_workspace_permission_cached("wendy@example.com", "ws-prod").name == "READ", "precondition: grant cached"

        ws_store.set_user_groups("wendy@example.com", ["others"])

        assert get_workspace_permission_cached("wendy@example.com", "ws-prod") is None, "removed member still served the cached workspace grant"
