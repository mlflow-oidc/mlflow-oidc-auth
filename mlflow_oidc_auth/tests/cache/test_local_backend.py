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
