"""Tests for the batch permissions module.

These tests verify the batch permission resolution functions work correctly
by mocking the store methods and verifying the permission resolution logic.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.utils.batch_permissions import (
    UserPermissionContext,
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
    _find_regex_permission,
    _resolve_permission_from_context,
)


class TestFindRegexPermission:
    """Tests for the _find_regex_permission helper function."""

    def test_finds_matching_regex(self):
        """Should return permission when regex matches."""
        regex_perm = MagicMock()
        regex_perm.regex = "^model-.*"
        regex_perm.permission = "READ"

        result = _find_regex_permission([regex_perm], "model-test")
        assert result == "READ"

    def test_returns_none_when_no_match(self):
        """Should return None when no regex matches."""
        regex_perm = MagicMock()
        regex_perm.regex = "^other-.*"
        regex_perm.permission = "READ"

        result = _find_regex_permission([regex_perm], "model-test")
        assert result is None

    def test_returns_first_matching_regex(self):
        """Should return the first matching regex permission."""
        regex_perm1 = MagicMock()
        regex_perm1.regex = ".*"
        regex_perm1.permission = "READ"

        regex_perm2 = MagicMock()
        regex_perm2.regex = "^model-.*"
        regex_perm2.permission = "MANAGE"

        result = _find_regex_permission([regex_perm1, regex_perm2], "model-test")
        assert result == "READ"

    def test_empty_list_returns_none(self):
        """Should return None for empty regex list."""
        result = _find_regex_permission([], "model-test")
        assert result is None

    def test_partial_match_with_anchored_regex(self):
        """Should only match if regex pattern matches."""
        regex_perm = MagicMock()
        regex_perm.regex = "^exact$"
        regex_perm.permission = "MANAGE"

        assert _find_regex_permission([regex_perm], "exact") == "MANAGE"
        assert _find_regex_permission([regex_perm], "exact-extra") is None
        assert _find_regex_permission([regex_perm], "not-exact") is None


class TestResolvePermissionFromContext:
    """Tests for the _resolve_permission_from_context helper function."""

    def test_returns_user_permission_first(self):
        """Should return user permission when it's first in source order."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = _resolve_permission_from_context(
                mock_config.PERMISSION_SOURCE_ORDER,
                user_direct="MANAGE",
                group_direct="READ",
                user_regex_match="EDIT",
                group_regex_match="READ",
            )

            assert result.permission.name == "MANAGE"
            assert result.kind == "user"

    def test_returns_group_permission_when_no_user(self):
        """Should return group permission when user permission is None."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = _resolve_permission_from_context(
                mock_config.PERMISSION_SOURCE_ORDER,
                user_direct=None,
                group_direct="READ",
                user_regex_match="EDIT",
                group_regex_match=None,
            )

            assert result.permission.name == "READ"
            assert result.kind == "group"

    def test_returns_regex_permission_when_no_direct(self):
        """Should return regex permission when no direct permissions."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = _resolve_permission_from_context(
                mock_config.PERMISSION_SOURCE_ORDER,
                user_direct=None,
                group_direct=None,
                user_regex_match="EDIT",
                group_regex_match="READ",
            )

            assert result.permission.name == "EDIT"
            assert result.kind == "regex"

    def test_returns_group_regex_permission_when_no_user_regex(self):
        """Should return group-regex permission when no user regex."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = _resolve_permission_from_context(
                mock_config.PERMISSION_SOURCE_ORDER,
                user_direct=None,
                group_direct=None,
                user_regex_match=None,
                group_regex_match="MANAGE",
            )

            assert result.permission.name == "MANAGE"
            assert result.kind == "group-regex"

    def test_returns_default_permission_when_no_match(self):
        """Should return default permission when no sources match."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "READ"

            result = _resolve_permission_from_context(
                mock_config.PERMISSION_SOURCE_ORDER,
                user_direct=None,
                group_direct=None,
                user_regex_match=None,
                group_regex_match=None,
            )

            assert result.permission.name == "READ"
            assert result.kind == "fallback"

    def test_respects_custom_source_order(self):
        """Should respect custom source order configuration."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            # Group first
            mock_config.PERMISSION_SOURCE_ORDER = [
                "group",
                "user",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = _resolve_permission_from_context(
                mock_config.PERMISSION_SOURCE_ORDER,
                user_direct="MANAGE",
                group_direct="READ",
                user_regex_match=None,
                group_regex_match=None,
            )

            assert result.permission.name == "READ"
            assert result.kind == "group"


class TestUserPermissionContext:
    """Tests for the UserPermissionContext dataclass."""

    def test_dataclass_creation(self):
        """Should create dataclass with all fields."""
        ctx = UserPermissionContext(
            username="testuser",
            group_ids=[1, 2, 3],
            user_experiment_permissions={"exp-1": "READ"},
            group_experiment_permissions={"exp-2": "MANAGE"},
            experiment_regex_permissions=[],
            group_experiment_regex_permissions=[],
            user_model_permissions={"model-a": "EDIT"},
            group_model_permissions={},
            model_regex_permissions=[],
            group_model_regex_permissions=[],
            prompt_regex_permissions=[],
            group_prompt_regex_permissions=[],
        )

        assert ctx.username == "testuser"
        assert ctx.group_ids == [1, 2, 3]
        assert ctx.user_experiment_permissions == {"exp-1": "READ"}
        assert ctx.group_experiment_permissions == {"exp-2": "MANAGE"}
        assert ctx.user_model_permissions == {"model-a": "EDIT"}


class TestBuildUserPermissionContext:
    """Tests for the build_user_permission_context function."""

    @patch("mlflow_oidc_auth.utils.batch_permissions.store")
    def test_builds_context_with_group_ids(self, mock_store):
        """Should build context fetching all permission data when user has groups."""
        # Setup mocks
        mock_store.get_groups_ids_for_user.return_value = [1, 2]

        exp_perm = MagicMock()
        exp_perm.experiment_id = "exp-1"
        exp_perm.permission = "READ"
        mock_store.list_experiment_permissions.return_value = [exp_perm]

        group_exp_perm = MagicMock()
        group_exp_perm.experiment_id = "exp-2"
        group_exp_perm.permission = "MANAGE"
        mock_store.list_user_groups_experiment_permissions.return_value = [group_exp_perm]

        mock_store.list_experiment_regex_permissions.return_value = []
        mock_store.list_group_experiment_regex_permissions_for_groups_ids.return_value = []

        model_perm = MagicMock()
        model_perm.name = "model-a"
        model_perm.permission = "EDIT"
        mock_store.list_registered_model_permissions.return_value = [model_perm]

        mock_store.list_user_groups_registered_model_permissions.return_value = []
        mock_store.list_registered_model_regex_permissions.return_value = []
        mock_store.list_group_registered_model_regex_permissions_for_groups_ids.return_value = []
        mock_store.list_prompt_regex_permissions.return_value = []
        mock_store.list_group_prompt_regex_permissions_for_groups_ids.return_value = []

        ctx = build_user_permission_context("testuser")

        assert ctx.username == "testuser"
        assert ctx.group_ids == [1, 2]
        assert ctx.user_experiment_permissions == {"exp-1": "READ"}
        assert ctx.group_experiment_permissions == {"exp-2": "MANAGE"}
        assert ctx.user_model_permissions == {"model-a": "EDIT"}

        # Verify store calls
        mock_store.get_groups_ids_for_user.assert_called_once_with("testuser")
        mock_store.list_experiment_permissions.assert_called_once_with("testuser")
        mock_store.list_group_experiment_regex_permissions_for_groups_ids.assert_called_once_with([1, 2])

    @patch("mlflow_oidc_auth.utils.batch_permissions.store")
    def test_builds_context_without_groups(self, mock_store):
        """Should skip group regex queries when user has no groups."""
        mock_store.get_groups_ids_for_user.return_value = []
        mock_store.list_experiment_permissions.return_value = []
        mock_store.list_user_groups_experiment_permissions.return_value = []
        mock_store.list_experiment_regex_permissions.return_value = []
        mock_store.list_registered_model_permissions.return_value = []
        mock_store.list_user_groups_registered_model_permissions.return_value = []
        mock_store.list_registered_model_regex_permissions.return_value = []
        mock_store.list_prompt_regex_permissions.return_value = []

        ctx = build_user_permission_context("testuser")

        assert ctx.group_ids == []
        assert ctx.group_experiment_regex_permissions == []
        assert ctx.group_model_regex_permissions == []
        assert ctx.group_prompt_regex_permissions == []

        # Should NOT call group regex methods when no groups
        mock_store.list_group_experiment_regex_permissions_for_groups_ids.assert_not_called()
        mock_store.list_group_registered_model_regex_permissions_for_groups_ids.assert_not_called()
        mock_store.list_group_prompt_regex_permissions_for_groups_ids.assert_not_called()


class TestResolveExperimentPermissionFromContext:
    """Tests for resolving experiment permissions from context."""

    @pytest.fixture
    def context_with_experiment_permissions(self):
        """Create context with experiment permissions."""
        exp_regex = MagicMock()
        exp_regex.regex = "^test-.*"
        exp_regex.permission = "EDIT"

        group_regex = MagicMock()
        group_regex.regex = "^prod-.*"
        group_regex.permission = "READ"

        return UserPermissionContext(
            username="testuser",
            group_ids=[1],
            user_experiment_permissions={"exp-1": "MANAGE"},
            group_experiment_permissions={"exp-2": "READ"},
            experiment_regex_permissions=[exp_regex],
            group_experiment_regex_permissions=[group_regex],
            user_model_permissions={},
            group_model_permissions={},
            model_regex_permissions=[],
            group_model_regex_permissions=[],
            prompt_regex_permissions=[],
            group_prompt_regex_permissions=[],
        )

    def test_resolves_user_experiment_permission(self, context_with_experiment_permissions):
        """Should resolve user direct experiment permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_experiment_permission_from_context(context_with_experiment_permissions, "exp-1", "experiment-name")

            assert result.permission.name == "MANAGE"
            assert result.kind == "user"

    def test_resolves_group_experiment_permission(self, context_with_experiment_permissions):
        """Should resolve group experiment permission when no user permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_experiment_permission_from_context(context_with_experiment_permissions, "exp-2", "experiment-name")

            assert result.permission.name == "READ"
            assert result.kind == "group"

    def test_resolves_regex_experiment_permission(self, context_with_experiment_permissions):
        """Should resolve regex experiment permission by experiment name."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_experiment_permission_from_context(context_with_experiment_permissions, "exp-unknown", "test-experiment")

            assert result.permission.name == "EDIT"
            assert result.kind == "regex"

    def test_resolves_group_regex_experiment_permission(self, context_with_experiment_permissions):
        """Should resolve group regex experiment permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_experiment_permission_from_context(context_with_experiment_permissions, "exp-unknown", "prod-experiment")

            assert result.permission.name == "READ"
            assert result.kind == "group-regex"

    @patch("mlflow_oidc_auth.utils.batch_permissions._get_tracking_store")
    def test_fetches_experiment_name_when_not_provided(self, mock_get_store, context_with_experiment_permissions):
        """Should fetch experiment name from tracking store when not provided."""
        mock_experiment = MagicMock()
        mock_experiment.name = "test-fetched-experiment"
        mock_get_store.return_value.get_experiment.return_value = mock_experiment

        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_experiment_permission_from_context(context_with_experiment_permissions, "exp-unknown", None)

            mock_get_store.return_value.get_experiment.assert_called_once_with("exp-unknown")
            # Should match the regex "^test-.*"
            assert result.permission.name == "EDIT"


class TestResolveModelPermissionFromContext:
    """Tests for resolving model permissions from context."""

    @pytest.fixture
    def context_with_model_permissions(self):
        """Create context with model permissions."""
        model_regex = MagicMock()
        model_regex.regex = "^ml-.*"
        model_regex.permission = "EDIT"

        group_model_regex = MagicMock()
        group_model_regex.regex = "^shared-.*"
        group_model_regex.permission = "READ"

        return UserPermissionContext(
            username="testuser",
            group_ids=[1],
            user_experiment_permissions={},
            group_experiment_permissions={},
            experiment_regex_permissions=[],
            group_experiment_regex_permissions=[],
            user_model_permissions={"my-model": "MANAGE"},
            group_model_permissions={"team-model": "EDIT"},
            model_regex_permissions=[model_regex],
            group_model_regex_permissions=[group_model_regex],
            prompt_regex_permissions=[],
            group_prompt_regex_permissions=[],
        )

    def test_resolves_user_model_permission(self, context_with_model_permissions):
        """Should resolve user direct model permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_model_permission_from_context(context_with_model_permissions, "my-model")

            assert result.permission.name == "MANAGE"
            assert result.kind == "user"

    def test_resolves_group_model_permission(self, context_with_model_permissions):
        """Should resolve group model permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_model_permission_from_context(context_with_model_permissions, "team-model")

            assert result.permission.name == "EDIT"
            assert result.kind == "group"

    def test_resolves_regex_model_permission(self, context_with_model_permissions):
        """Should resolve regex model permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_model_permission_from_context(context_with_model_permissions, "ml-classifier")

            assert result.permission.name == "EDIT"
            assert result.kind == "regex"

    def test_resolves_group_regex_model_permission(self, context_with_model_permissions):
        """Should resolve group regex model permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_model_permission_from_context(context_with_model_permissions, "shared-model")

            assert result.permission.name == "READ"
            assert result.kind == "group-regex"


class TestResolvePromptPermissionFromContext:
    """Tests for resolving prompt permissions from context."""

    @pytest.fixture
    def context_with_prompt_permissions(self):
        """Create context with prompt permissions (using model permissions + prompt regex)."""
        prompt_regex = MagicMock()
        prompt_regex.regex = "^prompt-.*"
        prompt_regex.permission = "EDIT"

        group_prompt_regex = MagicMock()
        group_prompt_regex.regex = "^team-prompt-.*"
        group_prompt_regex.permission = "READ"

        return UserPermissionContext(
            username="testuser",
            group_ids=[1],
            user_experiment_permissions={},
            group_experiment_permissions={},
            experiment_regex_permissions=[],
            group_experiment_regex_permissions=[],
            user_model_permissions={"my-prompt": "MANAGE"},  # Prompts share model permissions
            group_model_permissions={"shared-prompt": "EDIT"},
            model_regex_permissions=[],
            group_model_regex_permissions=[],
            prompt_regex_permissions=[prompt_regex],
            group_prompt_regex_permissions=[group_prompt_regex],
        )

    def test_resolves_user_prompt_permission_from_model_permissions(self, context_with_prompt_permissions):
        """Should resolve user prompt permission from model permissions."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_prompt_permission_from_context(context_with_prompt_permissions, "my-prompt")

            assert result.permission.name == "MANAGE"
            assert result.kind == "user"

    def test_resolves_group_prompt_permission(self, context_with_prompt_permissions):
        """Should resolve group prompt permission from model permissions."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_prompt_permission_from_context(context_with_prompt_permissions, "shared-prompt")

            assert result.permission.name == "EDIT"
            assert result.kind == "group"

    def test_resolves_prompt_regex_permission(self, context_with_prompt_permissions):
        """Should resolve prompt-specific regex permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_prompt_permission_from_context(context_with_prompt_permissions, "prompt-test")

            assert result.permission.name == "EDIT"
            assert result.kind == "regex"

    def test_resolves_group_prompt_regex_permission(self, context_with_prompt_permissions):
        """Should resolve group prompt-specific regex permission."""
        with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
            mock_config.PERMISSION_SOURCE_ORDER = [
                "user",
                "group",
                "regex",
                "group-regex",
            ]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "NO_PERMISSIONS"

            result = resolve_prompt_permission_from_context(context_with_prompt_permissions, "team-prompt-1")

            assert result.permission.name == "READ"
            assert result.kind == "group-regex"


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
