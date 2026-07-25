"""Tests for the local TTL cache backend."""

import time

import pytest

from mlflow_oidc_auth.cache.backend import CacheBackend
from mlflow_oidc_auth.cache.local_backend import LocalTTLCacheBackend


class TestLocalTTLCacheBackend:
    """Tests for LocalTTLCacheBackend."""

    def test_implements_cache_backend_protocol(self):
        """LocalTTLCacheBackend satisfies the CacheBackend protocol."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        assert isinstance(backend, CacheBackend)

    def test_get_returns_none_for_missing_key(self):
        """get() returns None when key does not exist."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        assert backend.get("nonexistent") is None

    def test_set_and_get(self):
        """set() stores a value and get() retrieves it."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        backend.set("key1", "value1")
        assert backend.get("key1") == "value1"

    def test_set_overwrites_existing(self):
        """set() overwrites an existing value for the same key."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        backend.set("key1", "old")
        backend.set("key1", "new")
        assert backend.get("key1") == "new"

    def test_stores_arbitrary_types(self):
        """Cache can store dicts, lists, custom objects."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        backend.set("dict", {"a": 1})
        backend.set("list", [1, 2, 3])
        backend.set("none_val", None)
        assert backend.get("dict") == {"a": 1}
        assert backend.get("list") == [1, 2, 3]
        # Note: None values are stored but get() returns None for missing keys too
        # This is a known semantic — callers should not cache None values
        assert backend.get("none_val") is None

    def test_delete_removes_key(self):
        """delete() removes an existing key."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        backend.set("key1", "value1")
        backend.delete("key1")
        assert backend.get("key1") is None

    def test_delete_noop_for_missing_key(self):
        """delete() is a no-op when the key does not exist."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        backend.delete("nonexistent")  # Should not raise

    def test_clear_removes_all_entries(self):
        """clear() removes all entries from the cache."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        backend.set("a", 1)
        backend.set("b", 2)
        backend.set("c", 3)
        backend.clear()
        assert backend.get("a") is None
        assert backend.get("b") is None
        assert backend.get("c") is None

    def test_clear_on_empty_cache(self):
        """clear() succeeds on an empty cache."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=60)
        backend.clear()  # Should not raise

    def test_ttl_expiry(self):
        """Entries expire after TTL seconds."""
        backend = LocalTTLCacheBackend(maxsize=10, ttl=1)
        backend.set("key1", "value1")
        assert backend.get("key1") == "value1"
        time.sleep(1.1)
        assert backend.get("key1") is None

    def test_maxsize_eviction(self):
        """When maxsize is exceeded, oldest entries are evicted."""
        backend = LocalTTLCacheBackend(maxsize=3, ttl=60)
        backend.set("a", 1)
        backend.set("b", 2)
        backend.set("c", 3)
        backend.set("d", 4)  # Should evict "a"
        assert backend.get("a") is None
        assert backend.get("d") == 4


class TestDeletePrefix:
    """delete_prefix backs targeted workspace-cache invalidation (issue #253).

    Keys are "username:workspace", so an over-delete costs other users their warm
    entries (perf) and an under-delete leaves a revoked grant live (fail-open).
    """

    def test_deletes_only_matching_keys(self):
        backend = LocalTTLCacheBackend(maxsize=100, ttl=60)
        backend.set("bob:ws1", "a")
        backend.set("bob:ws2", "b")
        backend.set("alice:ws1", "c")

        backend.delete_prefix("bob:")

        assert backend.get("bob:ws1") is None
        assert backend.get("bob:ws2") is None
        assert backend.get("alice:ws1") == "c"

    def test_does_not_over_delete_usernames_sharing_a_prefix(self):
        """'bob' must not invalidate 'bob2' or 'bobby' — the colon is the boundary."""
        backend = LocalTTLCacheBackend(maxsize=100, ttl=60)
        for key in ("bob:ws1", "bob2:ws1", "bobby:ws1", "bob@example.com:ws1"):
            backend.set(key, key)

        backend.delete_prefix("bob:")

        assert backend.get("bob:ws1") is None
        assert backend.get("bob2:ws1") == "bob2:ws1"
        assert backend.get("bobby:ws1") == "bobby:ws1"
        assert backend.get("bob@example.com:ws1") == "bob@example.com:ws1"

    def test_no_match_is_a_noop(self):
        backend = LocalTTLCacheBackend(maxsize=100, ttl=60)
        backend.set("alice:ws1", "a")
        backend.delete_prefix("nobody:")
        assert backend.get("alice:ws1") == "a"

    def test_safe_when_deleting_many_entries(self):
        """Deleting while walking the TTLCache must not raise (keys are materialized first)."""
        backend = LocalTTLCacheBackend(maxsize=500, ttl=60)
        for i in range(200):
            backend.set(f"bob:ws{i}", i)
            backend.set(f"eve:ws{i}", i)

        backend.delete_prefix("bob:")

        assert all(backend.get(f"bob:ws{i}") is None for i in range(200))
        assert all(backend.get(f"eve:ws{i}") == i for i in range(200))
