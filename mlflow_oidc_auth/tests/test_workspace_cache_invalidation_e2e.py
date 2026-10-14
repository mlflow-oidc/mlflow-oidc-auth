"""End-to-end tests for workspace cache invalidation (issue #253).

These use a REAL SqlAlchemyStore on a temporary SQLite database and the REAL local
cache backend — no mocks of the invalidation path. That is deliberate: the mock-based
tests in test_store_cache_invalidation.py assert that a helper was *called*, so
neutering the helpers themselves (delete_prefix, invalidate_user_workspace_entries,
invalidate_group_workspace_permission) leaves them green. These tests fail instead.

Most cases assert the REVOKED direction: all three bugs fixed here were fail-open.
Denials are cached too since issue #456, so TestCachedDenialIsCleared asserts the
GRANTED direction through the same invalidation paths — a stale denial fails closed, but
it must not outlive the grant that lifts it.
"""

import json
from types import SimpleNamespace

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
        ws_store.create_user("alice@example.com", "Alice")
        ws_store.populate_groups(["team-a"])
        ws_store.set_user_groups("alice@example.com", ["team-a"])
        ws_store.create_workspace_group_permission("ws-prod", "team-a", "EDIT")

        assert _cached("alice@example.com", "ws-prod").name == "EDIT", "precondition: cache warm"

        ws_store.delete_workspace_group_permission("ws-prod", "team-a")

        assert _cached("alice@example.com", "ws-prod") is None, "revoked group access still served (fail-open)"

    def test_downgrading_group_permission_is_visible_immediately(self, ws_store):
        ws_store.create_user("bob@example.com", "Bob")
        ws_store.populate_groups(["team-b"])
        ws_store.set_user_groups("bob@example.com", ["team-b"])
        ws_store.create_workspace_group_permission("ws-prod", "team-b", "MANAGE")
        assert _cached("bob@example.com", "ws-prod").name == "MANAGE"

        ws_store.update_workspace_group_permission("ws-prod", "team-b", "READ")

        assert _cached("bob@example.com", "ws-prod").name == "READ", "downgrade not reflected (fail-open)"


class TestMembershipRevocation:
    """BUG 2: membership mutations flushed the permission cache but not the workspace cache."""

    def test_removing_user_from_group_revokes_group_derived_access(self, ws_store):
        ws_store.create_user("carol@example.com", "Carol")
        ws_store.populate_groups(["team-c"])
        ws_store.set_user_groups("carol@example.com", ["team-c"])
        ws_store.create_workspace_group_permission("ws-prod", "team-c", "EDIT")
        assert _cached("carol@example.com", "ws-prod").name == "EDIT"

        ws_store.set_user_groups("carol@example.com", [])

        assert _cached("carol@example.com", "ws-prod") is None, "user in no groups still has group-derived access"

    def test_invalidation_is_targeted_to_the_mutated_user(self, ws_store):
        """Other users' entries must survive — OIDC re-syncs membership on every login."""
        for name in ("dave@example.com", "erin@example.com"):
            ws_store.create_user(name, name)
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
        ws_store.create_user("frank@example.com", "Frank")
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

        ws_store.create_user("grace@example.com", "Grace")
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

        ws_store.create_user("hank@example.com", "Hank")
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
            ws_store.create_user(name, name)
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


class TestCachedDenialIsCleared:
    """A cached denial shares the grant's key, so every grant path must drop it (issue #456)."""

    def _deny_warm(self, ws_store, username, workspace):
        assert _cached(username, workspace) is None, "precondition: no grant"
        from mlflow_oidc_auth.utils.workspace_cache import _get_cache, _get_denial_cache, _make_cache_key

        key = _make_cache_key(username, workspace)
        assert _get_denial_cache().get(key) is not None, "precondition: denial cached"
        assert _get_cache().get(key) is None, "a denial must never sit in the grant cache"

    def test_user_grant_clears_cached_denial(self, ws_store):
        ws_store.create_user("ivy@example.com", "Ivy")
        self._deny_warm(ws_store, "ivy@example.com", "ws-prod")

        ws_store.create_workspace_permission("ws-prod", "ivy@example.com", "READ")

        assert _cached("ivy@example.com", "ws-prod").name == "READ", "cached denial outlived a user grant"

    def test_group_grant_clears_cached_denial(self, ws_store):
        ws_store.create_user("jack@example.com", "Jack")
        ws_store.populate_groups(["team-j"])
        ws_store.set_user_groups("jack@example.com", ["team-j"])
        self._deny_warm(ws_store, "jack@example.com", "ws-prod")

        ws_store.create_workspace_group_permission("ws-prod", "team-j", "EDIT")

        assert _cached("jack@example.com", "ws-prod").name == "EDIT", "cached denial outlived a group grant"

    def test_joining_a_granted_group_clears_cached_denial(self, ws_store):
        ws_store.create_user("kate@example.com", "Kate")
        ws_store.populate_groups(["team-k"])
        ws_store.create_workspace_group_permission("ws-prod", "team-k", "READ")
        self._deny_warm(ws_store, "kate@example.com", "ws-prod")

        ws_store.set_user_groups("kate@example.com", ["team-k"])

        assert _cached("kate@example.com", "ws-prod").name == "READ", "cached denial outlived a membership change"

    def test_denial_is_not_shared_across_users_or_workspaces(self, ws_store):
        ws_store.create_user("liam@example.com", "Liam")
        ws_store.create_user("mia@example.com", "Mia")
        ws_store.create_workspace_permission("ws-prod", "mia@example.com", "READ")
        ws_store.create_workspace_permission("ws-dev", "liam@example.com", "EDIT")
        self._deny_warm(ws_store, "liam@example.com", "ws-prod")

        assert _cached("mia@example.com", "ws-prod").name == "READ"
        assert _cached("liam@example.com", "ws-dev").name == "EDIT"


class TestLookupErrorsAreNotCached:
    """A failed source walk denies the request but caches nothing (PR #464 review)."""

    def test_error_denies_and_is_not_cached(self, ws_store, monkeypatch):
        from mlflow_oidc_auth.utils.workspace_cache import _get_cache, _get_denial_cache, _make_cache_key

        ws_store.create_user("quinn@example.com", "Quinn")
        ws_store.create_workspace_permission("ws-prod", "quinn@example.com", "READ")

        def _db_down(*args, **kwargs):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(ws_store, "get_workspace_permission", _db_down)
        assert _cached("quinn@example.com", "ws-prod") is None, "a failed lookup must deny (fail closed)"

        key = _make_cache_key("quinn@example.com", "ws-prod")
        assert _get_denial_cache().get(key) is None, "an error was cached as a denial"
        assert _get_cache().get(key) is None

        del ws_store.get_workspace_permission  # the store recovers
        assert _cached("quinn@example.com", "ws-prod").name == "READ", "the grant is served once the store recovers"

    def test_error_in_a_higher_source_does_not_fall_through_to_a_lower_grant(self, ws_store, monkeypatch):
        """Fail closed: the failed source might hold a narrower answer than the one below it."""
        from mlflow_oidc_auth.utils.workspace_cache import _get_cache, _get_denial_cache, _make_cache_key

        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["user", "group", "regex", "group-regex"])
        ws_store.create_user("rita@example.com", "Rita")
        ws_store.populate_groups(["team-r"])
        ws_store.set_user_groups("rita@example.com", ["team-r"])
        ws_store.create_workspace_group_permission("ws-prod", "team-r", "MANAGE")

        def _db_down(*args, **kwargs):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(ws_store, "get_workspace_permission", _db_down)
        assert _cached("rita@example.com", "ws-prod") is None
        key = _make_cache_key("rita@example.com", "ws-prod")
        assert _get_cache().get(key) is None and _get_denial_cache().get(key) is None

    def test_list_workspaces_drops_a_workspace_whose_lookup_failed(self, ws_store, monkeypatch):
        from flask import Flask, Response

        from mlflow_oidc_auth.hooks import after_request as ar
        from mlflow_oidc_auth.utils.workspace_cache import _get_denial_cache, _make_cache_key

        ws_store.create_user("sam@example.com", "Sam")
        ws_store.create_workspace_permission("ws-prod", "sam@example.com", "READ")

        def _db_down(*args, **kwargs):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(ws_store, "get_workspace_permission", _db_down)
        context = SimpleNamespace(username="sam@example.com", is_admin=False)
        monkeypatch.setattr(ar, "get_auth_context", lambda: context)

        resp = Response(json.dumps({"workspaces": [{"name": "ws-prod"}]}), mimetype="application/json")
        with Flask(__name__).test_request_context("/"):
            ar._filter_list_workspaces(resp)

        assert json.loads(resp.get_data(as_text=True))["workspaces"] == []
        assert _get_denial_cache().get(_make_cache_key("sam@example.com", "ws-prod")) is None


class TestDenialsCannotEvictGrants:
    """Denials live in their own bounded cache (PR #464 review)."""

    def test_listing_many_workspaces_cannot_evict_another_users_grant(self, ws_store, monkeypatch):
        from flask import Flask, Response

        from mlflow_oidc_auth.hooks import after_request as ar
        from mlflow_oidc_auth.utils import workspace_cache as wsc

        # A tiny cache, built fresh at that size.
        monkeypatch.setattr(config, "WORKSPACE_CACHE_MAX_SIZE", 4)
        monkeypatch.setattr(wsc, "_cache", None)
        monkeypatch.setattr(wsc, "_denial_cache", None)

        ws_store.create_user("tess@example.com", "Tess")
        ws_store.create_user("ugo@example.com", "Ugo")
        ws_store.create_workspace_permission("ws-prod", "tess@example.com", "READ")
        assert _cached("tess@example.com", "ws-prod").name == "READ"

        # Ugo lists 50 workspaces he cannot read: 50 denials.
        context = SimpleNamespace(username="ugo@example.com", is_admin=False)
        monkeypatch.setattr(ar, "get_auth_context", lambda: context)
        names = [{"name": f"ws-{i}"} for i in range(50)]
        resp = Response(json.dumps({"workspaces": names}), mimetype="application/json")
        with Flask(__name__).test_request_context("/"):
            ar._filter_list_workspaces(resp)
        assert json.loads(resp.get_data(as_text=True))["workspaces"] == []

        assert wsc._get_cache().get(wsc._make_cache_key("tess@example.com", "ws-prod")) is not None, "a denial flood evicted a grant"
        # The denial cache stayed within its bound.
        assert len(wsc._get_denial_cache()._cache) <= 4

    def test_made_up_workspace_names_never_enter_the_grant_cache(self, ws_store):
        from mlflow_oidc_auth.utils import workspace_cache as wsc

        ws_store.create_user("vera@example.com", "Vera")
        for i in range(20):
            assert _cached("vera@example.com", f"no-such-ws-{i}") is None
        assert len(wsc._get_cache()._cache) == 0


class TestInvalidationDuringLookup:
    """A lookup racing an invalidation must not cache what it read (PR #464 review)."""

    def test_grant_written_mid_lookup_leaves_no_stale_denial(self, ws_store, monkeypatch):
        from mlflow_oidc_auth.utils import workspace_cache as wsc

        ws_store.create_user("xena@example.com", "Xena")
        original = wsc._resolve_workspace_permission

        def racing(username, workspace):
            result = original(username, workspace)  # reads "no grant"
            ws_store.create_workspace_permission(workspace, username, "READ")  # commits + invalidates
            return result

        monkeypatch.setattr(wsc, "_resolve_workspace_permission", racing)
        assert _cached("xena@example.com", "ws-prod") is None, "this request answers with what it read"
        key = wsc._make_cache_key("xena@example.com", "ws-prod")
        assert wsc._get_denial_cache().get(key) is None, "a stale denial was cached after the grant's invalidation"

        monkeypatch.setattr(wsc, "_resolve_workspace_permission", original)
        assert _cached("xena@example.com", "ws-prod").name == "READ", "the next check sees the grant"

    def test_revoke_mid_lookup_leaves_no_stale_grant(self, ws_store, monkeypatch):
        from mlflow_oidc_auth.utils import workspace_cache as wsc

        ws_store.create_user("yuri@example.com", "Yuri")
        ws_store.create_workspace_permission("ws-prod", "yuri@example.com", "EDIT")
        original = wsc._resolve_workspace_permission

        def racing(username, workspace):
            result = original(username, workspace)  # reads EDIT
            ws_store.delete_workspace_permission(workspace, username)
            return result

        monkeypatch.setattr(wsc, "_resolve_workspace_permission", racing)
        _cached("yuri@example.com", "ws-prod")
        assert wsc._get_cache().get(wsc._make_cache_key("yuri@example.com", "ws-prod")) is None, "a revoked grant was cached"

        monkeypatch.setattr(wsc, "_resolve_workspace_permission", original)
        assert _cached("yuri@example.com", "ws-prod") is None

    def test_unrelated_lookup_without_invalidation_is_cached(self, ws_store):
        """The guard must not disable caching when nothing was invalidated."""
        from mlflow_oidc_auth.utils import workspace_cache as wsc

        ws_store.create_user("zoe@example.com", "Zoe")
        assert _cached("zoe@example.com", "ws-prod") is None
        assert wsc._get_denial_cache().get(wsc._make_cache_key("zoe@example.com", "ws-prod")) is not None


class TestCacheKeysDoNotCollide:
    """``username:workspace`` keys are percent-encoded, so ``:`` cannot shift the boundary."""

    def test_denial_for_a_on_b_colon_c_does_not_lock_out_a_colon_b_on_c(self, ws_store):
        ws_store.create_user("a", "A")
        ws_store.create_user("a:b", "A:B")
        ws_store.create_workspace_permission("c", "a:b", "READ")

        assert _cached("a", "b:c") is None  # caches a denial for user "a", workspace "b:c"
        assert _cached("a:b", "c") is not None and _cached("a:b", "c").name == "READ", "user a:b locked out by a's denial"

    def test_invalidating_a_does_not_drop_a_colon_b_entries(self, ws_store):
        from mlflow_oidc_auth.utils import workspace_cache as wsc

        ws_store.create_user("a", "A")
        ws_store.create_user("a:b", "A:B")
        ws_store.create_workspace_permission("c", "a:b", "READ")
        ws_store.create_workspace_permission("c", "a", "EDIT")
        assert _cached("a:b", "c").name == "READ"
        assert _cached("a", "c").name == "EDIT"

        wsc.invalidate_user_workspace_entries("a")

        assert wsc._get_cache().get(wsc._make_cache_key("a", "c")) is None, "target not invalidated"
        assert wsc._get_cache().get(wsc._make_cache_key("a:b", "c")) is not None, "invalidating a dropped a:b"

    def test_keys_are_distinct(self):
        from mlflow_oidc_auth.utils.workspace_cache import _make_cache_key, _user_key_prefix

        assert _make_cache_key("a", "b:c") != _make_cache_key("a:b", "c")
        assert _make_cache_key("a%3Ab", "c") != _make_cache_key("a:b", "c")
        assert not _make_cache_key("a:b", "c").startswith(_user_key_prefix("a"))


class TestGenerationGuardInterleavings:
    """Run an invalidation at each point of a lookup's generation reads (security review of 633cb1c5).

    A lookup reads the generation (1) before resolving, (2) before writing, and (3) after
    writing. These tests run a real revoke right after read N returns, so the revoke lands
    exactly between that read and the lookup's next step, and check the revoked grant is not
    left in the cache.
    """

    def _revoke_after_read(self, ws_store, monkeypatch, read_number):
        from mlflow_oidc_auth.utils import workspace_cache as wsc

        ws_store.create_user("ines@example.com", "Ines")
        ws_store.create_workspace_permission("ws-prod", "ines@example.com", "EDIT")
        real = wsc._current_generation
        reads = {"n": 0}

        def interleaved():
            value = real()
            reads["n"] += 1
            if reads["n"] == read_number:
                ws_store.delete_workspace_permission("ws-prod", "ines@example.com")
            return value

        monkeypatch.setattr(wsc, "_current_generation", interleaved)
        served = _cached("ines@example.com", "ws-prod")
        monkeypatch.setattr(wsc, "_current_generation", real)
        return wsc, served, reads["n"]

    @pytest.mark.parametrize("read_number", [1, 2, 3])
    def test_revoked_grant_does_not_survive(self, ws_store, monkeypatch, read_number):
        wsc, served, reads = self._revoke_after_read(ws_store, monkeypatch, read_number)

        key = wsc._make_cache_key("ines@example.com", "ws-prod")
        assert wsc._get_cache().get(key) is None, f"revoked grant cached (revoke after read {read_number})"
        assert _cached("ines@example.com", "ws-prod") is None, "next check must resolve fresh and see the revoke"

    def test_second_read_then_write_interleaving(self, ws_store, monkeypatch):
        """The reviewer's case: read gen, second read, invalidation, write — the entry must not survive."""
        wsc, served, reads = self._revoke_after_read(ws_store, monkeypatch, 2)

        assert reads == 3, "the lookup must re-read the generation after writing"
        assert served is not None and served.name == "EDIT", "this request answers with what it read"
        assert wsc._get_cache().get(wsc._make_cache_key("ines@example.com", "ws-prod")) is None
        assert _cached("ines@example.com", "ws-prod") is None
