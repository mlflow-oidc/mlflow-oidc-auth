"""The grant-context section cache follows the workspace cache's rules (issue #460).

Separate namespace, percent-encoded keys, a generation guard against invalidations racing a
load, and failed loads never cached — a store error must fail closed, never grant.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils import grant_context
from mlflow_oidc_auth.utils.grant_context import load_grant_context, resolve


@pytest.fixture
def store():
    store = MagicMock()
    store.get_groups_ids_for_user.return_value = []
    store.list_experiment_permissions.return_value = [SimpleNamespace(experiment_id="1", permission="MANAGE")]
    store.list_user_groups_grants.return_value = []
    store.list_experiment_regex_permissions.return_value = []
    with (
        patch("mlflow_oidc_auth.utils.grant_context._store", return_value=store),
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
    ):
        yield store


def _decide(experiment_id="1", username="alice"):
    return resolve(load_grant_context(username), "experiment", experiment_id, name="e")


def test_section_is_read_once_and_reused_across_contexts(store):
    assert _decide().permission.can_manage
    assert _decide().permission.can_manage
    assert _decide("2").kind == "fallback"
    store.list_experiment_permissions.assert_called_once_with("alice")


def test_a_failed_load_raises_and_is_not_cached(store):
    store.list_experiment_permissions.side_effect = RuntimeError("database down")
    with pytest.raises(RuntimeError):
        _decide()
    assert list(grant_context._get_section_cache()._cache.keys()) == []

    store.list_experiment_permissions.side_effect = None
    assert _decide().permission.can_manage, "the next request reads again"


def test_a_failed_group_read_never_falls_through_to_a_grant(store):
    """An error in a lower source is not 'no grant': the decision fails, it does not fall back."""
    store.list_experiment_permissions.return_value = []
    store.list_user_groups_grants.side_effect = RuntimeError("database down")
    with patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"), pytest.raises(RuntimeError):
        _decide()


def test_load_racing_an_invalidation_is_not_cached(store):
    """A flush between the read and the write leaves nothing cached (generation guard)."""
    original = store.list_experiment_permissions.return_value

    def racing(username):
        grant_context.flush_grant_contexts()
        return original

    store.list_experiment_permissions.side_effect = racing
    assert _decide().permission.can_manage, "the racing request is still answered"
    assert list(grant_context._get_section_cache()._cache.keys()) == []


def test_keys_are_percent_encoded():
    """User ``a:b`` in scope ``c`` and user ``a`` in scope ``b:c`` never share an entry."""
    assert grant_context._section_key("a:b", "c", "experiment") != grant_context._section_key("a", "b:c", "experiment")
    assert grant_context._section_key("a:b", "c", "experiment").count(":") == 2


def test_namespace_is_separate_from_the_permission_cache():
    from mlflow_oidc_auth.utils import permissions

    assert grant_context._get_section_cache() is not permissions._get_permission_cache()
    with patch("mlflow_oidc_auth.utils.grant_context.get_cache_backend") as backend:
        grant_context._section_cache = None
        grant_context._get_section_cache()
    assert backend.call_args.args[0] == "grant_context_v1"


def test_flush_permission_cache_flushes_the_sections(store):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache, invalidate_permission_cache

    _decide()
    flush_permission_cache()
    _decide()
    assert store.list_experiment_permissions.call_count == 2
    invalidate_permission_cache("experiment", "1", "alice", None)
    _decide()
    assert store.list_experiment_permissions.call_count == 3


def test_sections_are_per_grant_scope(store):
    """Grants read in one workspace never answer for another."""
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True):
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-a"):
            _decide()
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-b"):
            _decide()
    assert store.list_experiment_permissions.call_count == 2


@pytest.mark.parametrize("dialect, denied", [("mysql", True), ("mariadb", True), ("sqlite", False), ("postgresql", False)])
def test_name_matching_follows_the_databases_collation(store, dialect, denied):
    """On MySQL ``=`` ignores case, so a deny written as ``CHURN`` still applies to ``churn``."""
    store.engine.dialect.name = dialect
    store.list_registered_model_permissions.return_value = [SimpleNamespace(name="CHURN", permission="NO_PERMISSIONS")]
    store.list_user_groups_grants.return_value = [SimpleNamespace(name="churn", permission="READ")]
    store.list_registered_model_regex_permissions.return_value = []

    result = resolve(load_grant_context("alice"), "registered_model", "churn")

    assert (result.kind == "user" and not result.permission.can_read) is denied
    if not denied:
        assert result.kind == "group"


def test_a_grant_scope_change_after_build_is_refused(store):
    """Grants are never cached under a scope other than the one they were read in."""
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True):
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-a"):
            ctx = load_grant_context("alice")
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-b"), pytest.raises(RuntimeError):
            resolve(ctx, "experiment", "1", name="e")
    assert list(grant_context._get_section_cache()._cache.keys()) == []
