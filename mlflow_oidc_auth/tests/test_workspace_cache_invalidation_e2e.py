"""End-to-end tests for workspace cache invalidation (issue #253).

These use a REAL SqlAlchemyStore on a temporary SQLite database and the REAL local
cache backend — no mocks of the invalidation path. That is deliberate: the mock-based
tests in test_store_cache_invalidation.py assert that a helper was *called*, so
neutering the helpers themselves (delete_prefix, invalidate_user_workspace_entries,
invalidate_group_workspace_permission) leaves them green. These tests fail instead.

Every case asserts the REVOKED direction. All three bugs fixed here were fail-open —
denials are never cached, so only a stale *grant* can be served.
"""

import pytest

from mlflow_oidc_auth.config import config


@pytest.fixture
def ws_store(tmp_path, monkeypatch):
    """Real store + real cache with workspaces enabled."""
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils import workspace_cache

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    db_uri = f"sqlite:///{tmp_path / 'auth.db'}"
    store = SqlAlchemyStore()
    store.init_db(db_uri)

    # The store facade is a module-level singleton; point it at this instance so the
    # invalidation helpers (which import it lazily) see the same data.
    monkeypatch.setattr("mlflow_oidc_auth.store.store", store, raising=False)
    workspace_cache.flush_workspace_cache()
    yield store
    workspace_cache.flush_workspace_cache()


def _cached(username, workspace):
    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    return get_workspace_permission_cached(username, workspace)


class TestGroupScopedWorkspaceRevocation:
    """BUG 1: group-scoped workspace CUD used to invalidate nothing (decision D-15)."""

    def test_revoking_group_permission_is_visible_immediately(self, ws_store):
        ws_store.create_user("alice@example.com", "pw", "Alice")
        ws_store.populate_groups(["team-a"])
        ws_store.set_user_groups("alice@example.com", ["team-a"])
        ws_store.create_workspace_group_permission("ws-prod", "team-a", "EDIT")

        assert _cached("alice@example.com", "ws-prod").name == "EDIT", "precondition: cache warm"

        ws_store.delete_workspace_group_permission("ws-prod", "team-a")

        assert _cached("alice@example.com", "ws-prod") is None, "revoked group access still served (fail-open)"

    def test_downgrading_group_permission_is_visible_immediately(self, ws_store):
        ws_store.create_user("bob@example.com", "pw", "Bob")
        ws_store.populate_groups(["team-b"])
        ws_store.set_user_groups("bob@example.com", ["team-b"])
        ws_store.create_workspace_group_permission("ws-prod", "team-b", "MANAGE")
        assert _cached("bob@example.com", "ws-prod").name == "MANAGE"

        ws_store.update_workspace_group_permission("ws-prod", "team-b", "READ")

        assert _cached("bob@example.com", "ws-prod").name == "READ", "downgrade not reflected (fail-open)"


class TestMembershipRevocation:
    """BUG 2: membership mutations flushed the permission cache but not the workspace cache."""

    def test_removing_user_from_group_revokes_group_derived_access(self, ws_store):
        ws_store.create_user("carol@example.com", "pw", "Carol")
        ws_store.populate_groups(["team-c"])
        ws_store.set_user_groups("carol@example.com", ["team-c"])
        ws_store.create_workspace_group_permission("ws-prod", "team-c", "EDIT")
        assert _cached("carol@example.com", "ws-prod").name == "EDIT"

        ws_store.set_user_groups("carol@example.com", [])

        assert _cached("carol@example.com", "ws-prod") is None, "user in no groups still has group-derived access"

    def test_invalidation_is_targeted_to_the_mutated_user(self, ws_store):
        """Other users' entries must survive — OIDC re-syncs membership on every login."""
        for name in ("dave@example.com", "erin@example.com"):
            ws_store.create_user(name, "pw", name)
        ws_store.populate_groups(["team-d"])
        ws_store.set_user_groups("dave@example.com", ["team-d"])
        ws_store.set_user_groups("erin@example.com", ["team-d"])
        ws_store.create_workspace_group_permission("ws-prod", "team-d", "EDIT")

        assert _cached("dave@example.com", "ws-prod").name == "EDIT"
        assert _cached("erin@example.com", "ws-prod").name == "EDIT"

        # Re-assert dave's existing membership (what a login does).
        ws_store.set_user_groups("dave@example.com", ["team-d"])

        # Erin's entry must still be served from cache — a full flush would drop it.
        from mlflow_oidc_auth.utils.workspace_cache import _get_cache, _make_cache_key

        assert _get_cache().get(_make_cache_key("erin@example.com", "ws-prod")) is not None, "invalidation was not targeted"


class TestUserScopedWorkspaceRevocation:
    """BUG 3: user workspace CUD invalidated only in the router, so direct store calls leaked."""

    def test_revoking_user_permission_via_store_is_visible_immediately(self, ws_store):
        ws_store.create_user("frank@example.com", "pw", "Frank")
        ws_store.create_workspace_permission("ws-prod", "frank@example.com", "EDIT")
        assert _cached("frank@example.com", "ws-prod").name == "EDIT"

        ws_store.delete_workspace_permission("ws-prod", "frank@example.com")

        assert _cached("frank@example.com", "ws-prod") is None, "revoked user access still served (fail-open)"

    def test_workspace_change_also_clears_the_permission_cache(self, ws_store, monkeypatch):
        """The workspace cache and permission cache are separate namespaces.

        A workspace grant reaches resource decisions through the workspace fallback, so
        revoking it must invalidate the resolved-permission entry too.
        """
        from mlflow_oidc_auth.utils import permissions as perms

        monkeypatch.setattr("mlflow_oidc_auth.bridge.user.get_request_workspace", lambda: "ws-prod")
        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["user", "group"])

        ws_store.create_user("grace@example.com", "pw", "Grace")
        ws_store.create_workspace_permission("ws-prod", "grace@example.com", "EDIT")

        warm = perms.resolve_permission("registered_model", "some-model", "grace@example.com")
        assert warm.permission.name == "EDIT" and warm.kind == "workspace"

        ws_store.delete_workspace_permission("ws-prod", "grace@example.com")

        after = perms.resolve_permission("registered_model", "some-model", "grace@example.com")
        assert after.permission.name != "EDIT", "permission cache still serves the revoked workspace grant"


class TestWorkspaceWipe:
    """The DeleteWorkspace cascade calls wipe_workspace_permissions."""

    def test_wipe_clears_the_permission_cache(self, ws_store, monkeypatch):
        """wipe_workspace_permissions was the one workspace mutator missing from the flush list."""
        from mlflow_oidc_auth.utils import permissions as perms

        monkeypatch.setattr("mlflow_oidc_auth.bridge.user.get_request_workspace", lambda: "ws-doomed")
        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["user", "group"])

        ws_store.create_user("hank@example.com", "pw", "Hank")
        ws_store.create_workspace_permission("ws-doomed", "hank@example.com", "MANAGE")

        warm = perms.resolve_permission("registered_model", "prod-model", "hank@example.com")
        assert warm.permission.name == "MANAGE" and warm.kind == "workspace"

        ws_store.wipe_workspace_permissions("ws-doomed")

        after = perms.resolve_permission("registered_model", "prod-model", "hank@example.com")
        assert after.permission.name != "MANAGE", "permission cache still serves a wiped workspace grant"

    def test_wipe_is_wrapped_for_cache_invalidation(self):
        """Structural guard: every workspace mutator must be in the flush list."""
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore, _PERMISSION_CUD_METHODS

        assert "wipe_workspace_permissions" in _PERMISSION_CUD_METHODS
        assert hasattr(SqlAlchemyStore.wipe_workspace_permissions, "__wrapped__")


class TestPrefixInvalidationDoesNotOverDelete:
    """delete_prefix keys on 'username:workspace' — a username must not match a longer one."""

    def test_similar_usernames_are_not_collaterally_invalidated(self, ws_store):
        for name in ("bob", "bob2", "bobby"):
            ws_store.create_user(name, "pw", name)
            ws_store.create_workspace_permission("ws-prod", name, "EDIT")
            assert _cached(name, "ws-prod").name == "EDIT"

        from mlflow_oidc_auth.utils.workspace_cache import (
            _get_cache,
            _make_cache_key,
            invalidate_user_workspace_entries,
        )

        invalidate_user_workspace_entries("bob")

        cache = _get_cache()
        assert cache.get(_make_cache_key("bob", "ws-prod")) is None, "target not invalidated"
        assert cache.get(_make_cache_key("bob2", "ws-prod")) is not None, "over-deleted bob2"
        assert cache.get(_make_cache_key("bobby", "ws-prod")) is not None, "over-deleted bobby"
