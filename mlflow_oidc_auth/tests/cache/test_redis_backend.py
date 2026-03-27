"""Tests for the Redis cache backend (using mocked redis)."""

import pickle
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.cache.backend import CacheBackend


class TestRedisCacheBackend:
    """Tests for RedisCacheBackend with mocked redis-py."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock redis module and client."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        mock_redis_module = MagicMock()
        mock_redis_module.Redis.from_url.return_value = mock_client
        mock_redis_module.ConnectionError = ConnectionError

        return mock_redis_module, mock_client

    @pytest.fixture
    def backend(self, mock_redis):
        """Create a RedisCacheBackend with mocked redis."""
        mock_redis_module, mock_client = mock_redis

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            from mlflow_oidc_auth.cache.redis_backend import RedisCacheBackend

            backend = RedisCacheBackend(
                url="redis://localhost:6379/0",
                prefix="test:",
                ttl=30,
            )
        return backend

    def test_implements_cache_backend_protocol(self, backend):
        """RedisCacheBackend satisfies the CacheBackend protocol."""
        assert isinstance(backend, CacheBackend)

    def test_init_pings_redis(self, mock_redis):
        """Constructor pings Redis to verify connectivity."""
        mock_redis_module, mock_client = mock_redis

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            from mlflow_oidc_auth.cache.redis_backend import RedisCacheBackend

            RedisCacheBackend(url="redis://localhost:6379/0", prefix="t:", ttl=30)
            mock_client.ping.assert_called_once()

    def test_init_raises_on_connection_failure(self, mock_redis):
        """Constructor raises ConnectionError when Redis is unreachable."""
        mock_redis_module, mock_client = mock_redis
        mock_client.ping.side_effect = ConnectionError("Connection refused")

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            from mlflow_oidc_auth.cache.redis_backend import RedisCacheBackend

            with pytest.raises(ConnectionError, match="Cannot connect to Redis"):
                RedisCacheBackend(url="redis://bad:6379/0", prefix="t:", ttl=30)

    def test_init_raises_import_error_without_redis(self):
        """Constructor raises ImportError when redis package is missing."""
        with patch.dict("sys.modules", {"redis": None}):
            # Need to reimport to trigger the ImportError check
            import importlib

            import mlflow_oidc_auth.cache.redis_backend as rb_module

            importlib.reload(rb_module)

            with pytest.raises(ImportError, match="redis"):
                rb_module.RedisCacheBackend(url="redis://localhost:6379/0", prefix="t:", ttl=30)

    def test_get_returns_none_for_missing_key(self, backend, mock_redis):
        """get() returns None when key does not exist in Redis."""
        _, mock_client = mock_redis
        mock_client.get.return_value = None

        result = backend.get("missing")
        assert result is None
        mock_client.get.assert_called_once_with("test:missing")

    def test_get_returns_deserialized_value(self, backend, mock_redis):
        """get() deserializes pickle data from Redis."""
        _, mock_client = mock_redis
        mock_client.get.return_value = pickle.dumps("hello", protocol=pickle.HIGHEST_PROTOCOL)

        result = backend.get("key1")
        assert result == "hello"
        mock_client.get.assert_called_once_with("test:key1")

    def test_set_serializes_and_stores_with_ttl(self, backend, mock_redis):
        """set() pickles the value and stores with TTL via setex."""
        _, mock_client = mock_redis

        backend.set("key1", {"data": 42})
        mock_client.setex.assert_called_once_with(
            "test:key1",
            30,
            pickle.dumps({"data": 42}, protocol=pickle.HIGHEST_PROTOCOL),
        )

    def test_delete_calls_redis_delete(self, backend, mock_redis):
        """delete() calls Redis DELETE on the prefixed key."""
        _, mock_client = mock_redis

        backend.delete("key1")
        mock_client.delete.assert_called_once_with("test:key1")

    def test_clear_uses_scan(self, backend, mock_redis):
        """clear() uses SCAN to find and delete all prefixed keys."""
        _, mock_client = mock_redis

        # Simulate SCAN returning keys in one batch
        mock_client.scan.return_value = (0, [b"test:a", b"test:b"])

        backend.clear()
        mock_client.scan.assert_called_once_with(cursor=0, match="test:*", count=500)
        mock_client.delete.assert_called_once_with(b"test:a", b"test:b")

    def test_clear_handles_multiple_scan_iterations(self, backend, mock_redis):
        """clear() iterates SCAN until cursor returns 0."""
        _, mock_client = mock_redis

        # First iteration returns cursor=42 (not done), second returns cursor=0 (done)
        mock_client.scan.side_effect = [
            (42, [b"test:a"]),
            (0, [b"test:b"]),
        ]

        backend.clear()
        assert mock_client.scan.call_count == 2
        assert mock_client.delete.call_count == 2

    def test_clear_handles_empty_cache(self, backend, mock_redis):
        """clear() handles no keys matching prefix."""
        _, mock_client = mock_redis
        mock_client.scan.return_value = (0, [])

        backend.clear()  # Should not raise
        mock_client.delete.assert_not_called()

    def test_key_prefixing(self, backend, mock_redis):
        """All operations use the configured prefix."""
        _, mock_client = mock_redis
        mock_client.get.return_value = None

        backend.get("foo:bar:baz")
        mock_client.get.assert_called_once_with("test:foo:bar:baz")

        backend.set("foo:bar:baz", "val")
        mock_client.setex.assert_called_once()
        assert mock_client.setex.call_args[0][0] == "test:foo:bar:baz"

        backend.delete("foo:bar:baz")
        mock_client.delete.assert_called_once_with("test:foo:bar:baz")
