"""The grant-context cache follows the workspace cache's rules (issue #460).

Separate namespace, percent-encoded keys, the shared generation guard against invalidations racing
a read, and failed reads never cached — a store error must fail closed, never grant. Names are
matched in memory only where the auth database's ``=`` is exact; single checks never read a
user's whole grant set; and a decision is never cached past the grants it was built from.
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils import grant_context
from mlflow_oidc_auth.utils.grant_context import load_grant_context, resolve


def _missing(*_args):
    raise MlflowException("no grant", RESOURCE_DOES_NOT_EXIST)


@pytest.fixture
def store():
    """A store on an exact-``=`` database whose only grant is alice's MANAGE on experiment 1."""
    store = MagicMock()
    store.engine.dialect.name = "sqlite"
    store.get_groups_ids_for_user.return_value = []
    store.list_experiment_permissions.return_value = [SimpleNamespace(experiment_id="1", permission="MANAGE")]
    store.list_user_groups_grants.return_value = []
    store.list_experiment_regex_permissions.return_value = []
    # The bulk read of direct grants (store.list_user_grants), by grant table.
    store.list_user_grants.side_effect = lambda table, username: {
        "experiment": store.list_experiment_permissions,
        "registered_model": store.list_registered_model_permissions,
    }[table](username)
    store.get_experiment_permission.side_effect = lambda r, u: SimpleNamespace(permission="MANAGE") if r == "1" else _missing()
    store.get_user_groups_experiment_permission.side_effect = _missing
    with (
        patch("mlflow_oidc_auth.utils.grant_context._store", return_value=store),
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
    ):
        yield store


def _decide(experiment_id="1", username="alice", bulk=True):
    return resolve(load_grant_context(username, bulk=bulk), "experiment", experiment_id, name="e")


def _cached_keys():
    return list(grant_context._get_section_cache()._cache.keys())


def test_direct_grants_are_read_once_and_reused_across_bulk_contexts(store):
    assert _decide().permission.can_manage
    assert _decide().permission.can_manage
    assert _decide("2").kind == "fallback"
    store.list_experiment_permissions.assert_called_once_with("alice")
    store.get_experiment_permission.assert_not_called()


def test_a_single_check_never_reads_the_whole_grant_set(store):
    """A single check looks its direct grants up one by one; it never lists them."""
    assert _decide(bulk=False).permission.can_manage
    assert _decide("2", bulk=False).kind == "fallback"
    store.list_experiment_permissions.assert_not_called()
    store.list_user_groups_grants.assert_not_called()
    assert store.get_experiment_permission.call_count == 2


def test_a_failed_load_raises_and_is_not_cached(store):
    store.list_experiment_permissions.side_effect = RuntimeError("database down")
    with pytest.raises(RuntimeError):
        _decide()
    assert _cached_keys() == []

    store.list_experiment_permissions.side_effect = None
    assert _decide().permission.can_manage, "the next request reads again"


def test_a_failed_group_read_never_falls_through_to_a_grant(store):
    """An error in a lower source is not 'no grant': the decision fails, it does not fall back."""
    store.list_experiment_permissions.return_value = []
    store.list_user_groups_grants.side_effect = RuntimeError("database down")
    with patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"), pytest.raises(RuntimeError):
        _decide()
    store.get_experiment_permission.side_effect = _missing
    store.get_user_groups_experiment_permission.side_effect = RuntimeError("database down")
    with patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"), pytest.raises(RuntimeError):
        _decide(bulk=False)


def test_load_racing_an_invalidation_is_not_cached(store):
    """A flush between the read and the write leaves nothing cached (generation guard)."""
    original = store.list_experiment_permissions.return_value

    def racing(username):
        grant_context.flush_grant_contexts()
        return original

    store.list_experiment_permissions.side_effect = racing
    assert _decide().permission.can_manage, "the racing request is still answered"
    assert not any(key.endswith(":direct") for key in _cached_keys())


def test_keys_are_percent_encoded():
    """User ``a:b`` in scope ``c`` and user ``a`` in scope ``b:c`` never share an entry."""
    assert grant_context._section_key("a:b", "c", "experiment", "direct") != grant_context._section_key("a", "b:c", "experiment", "direct")
    assert grant_context._section_key("a:b", "c", "experiment", "direct").count(":") == 3


def test_namespace_is_separate_from_the_permission_cache():
    from mlflow_oidc_auth.utils import permissions

    assert grant_context._get_section_cache() is not permissions._get_permission_cache()
    with patch("mlflow_oidc_auth.utils.grant_context.get_cache_backend") as backend:
        grant_context._section_cache = None
        grant_context._get_section_cache()
    assert backend.call_args.args[0] == "grant_context_v2"


def test_flush_permission_cache_flushes_the_grant_reads(store):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache, invalidate_permission_cache

    _decide()
    flush_permission_cache()
    _decide()
    assert store.list_experiment_permissions.call_count == 2
    invalidate_permission_cache("experiment", "1", "alice", None)
    _decide()
    assert store.list_experiment_permissions.call_count == 3


def test_reads_are_per_grant_scope(store):
    """Grants read in one workspace never answer for another."""
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True):
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-a"):
            _decide()
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-b"):
            _decide()
    assert store.list_experiment_permissions.call_count == 2


def test_a_grant_scope_change_after_build_is_refused(store):
    """Grants are never cached under a scope other than the one they were read in."""
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True):
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-a"):
            ctx = load_grant_context("alice", bulk=True)
        with patch("mlflow_oidc_auth.utils.grant_context.current_grant_workspace", return_value="ws-b"), pytest.raises(RuntimeError):
            resolve(ctx, "experiment", "1", name="e")
    assert _cached_keys() == []


@pytest.mark.parametrize("dialect", ["mysql", "mariadb", "mssql", "oracle", None])
def test_case_insensitive_databases_never_match_names_in_memory(store, dialect):
    """Where the database's ``=`` ignores case (or anything else), it decides: a deny on ``CHURN`` denies ``churn``.

    The SQL lookup is stood in for by the store returning the grant the database's own comparison
    finds; the bulk listing (exact names) must not be consulted for direct grants at all.
    """
    store.engine.dialect.name = dialect
    store.list_registered_model_permissions.return_value = [SimpleNamespace(name="CHURN", permission="NO_PERMISSIONS")]
    store.list_user_groups_grants.return_value = [SimpleNamespace(name="churn", permission="READ")]
    store.list_registered_model_regex_permissions.return_value = []
    store.get_registered_model_permission.side_effect = lambda r, u: SimpleNamespace(permission="NO_PERMISSIONS")  # CHURN = churn there
    store.get_user_groups_registered_model_permission.side_effect = lambda r, u: SimpleNamespace(permission="READ")

    result = resolve(load_grant_context("alice", bulk=True), "registered_model", "churn")

    assert (result.kind, result.permission.can_read) == ("user", False)
    store.get_registered_model_permission.assert_called_once_with("churn", "alice")
    store.list_registered_model_permissions.assert_not_called()


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_exact_databases_match_names_exactly_in_memory(store, dialect):
    """On SQLite and PostgreSQL ``=`` is exact, so ``CHURN``'s deny does not reach ``churn``, as before."""
    store.engine.dialect.name = dialect
    store.list_registered_model_permissions.return_value = [SimpleNamespace(name="CHURN", permission="NO_PERMISSIONS")]
    store.list_user_groups_grants.return_value = [SimpleNamespace(name="churn", permission="READ")]
    store.list_registered_model_regex_permissions.return_value = []

    result = resolve(load_grant_context("alice", bulk=True), "registered_model", "churn")

    assert (result.kind, result.permission.name) == ("group", "READ")
    store.get_registered_model_permission.assert_not_called()


def test_decision_expires_with_the_grants_it_was_built_from(store, monkeypatch):
    """A decision built from a 20 s-old pattern read is cached for 10 s, not 30 (one TTL in total)."""
    from mlflow_oidc_auth.utils import permissions

    store.get_experiment_permission.side_effect = _missing
    store.list_experiment_regex_permissions.return_value = [SimpleNamespace(id=1, regex=".*", priority=1, permission="READ", workspace="*")]
    monkeypatch.setattr(config, "PERMISSION_CACHE_TTL_SECONDS", 30)
    tracking = MagicMock()
    tracking.get_experiment.return_value = SimpleNamespace(name="e")
    monkeypatch.setattr(permissions, "_get_tracking_store", lambda: tracking)
    now = [1_000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])

    load_grant_context("alice").patterns("experiment")  # read (and cached) at t=1000
    now[0] = 1_020.0
    assert permissions.resolve_permission("experiment", "1", "alice").kind == "regex"
    key = permissions._make_cache_key("experiment", "1", "alice", permissions._get_cache_workspace())
    assert permissions._get_permission_cache().get(key).expires_at == 1_030.0

    # Past the read's expiry the decision is not served, even though its own entry is still there.
    store.list_experiment_regex_permissions.return_value = []
    grant_context._get_section_cache().clear()  # the read's own expiry, which the local TTL cache applies on its clock
    now[0] = 1_031.0
    assert permissions.resolve_permission("experiment", "1", "alice").kind == "fallback"


def test_a_decision_from_an_expired_read_is_not_cached(store, monkeypatch):
    from mlflow_oidc_auth.utils import permissions

    store.get_experiment_permission.side_effect = _missing
    monkeypatch.setattr(config, "PERMISSION_CACHE_TTL_SECONDS", 30)
    now = [1_000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    load_grant_context("alice").patterns("experiment")
    now[0] = 1_040.0
    permissions.resolve_permission("experiment", "1", "alice")
    key = permissions._make_cache_key("experiment", "1", "alice", permissions._get_cache_workspace())
    assert permissions._get_permission_cache().get(key) is None
