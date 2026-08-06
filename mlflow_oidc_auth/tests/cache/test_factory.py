"""Tests for the cache backend factory."""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.cache.local_backend import LocalTTLCacheBackend


class TestGetCacheBackend:
    """Tests for get_cache_backend() factory function."""

    def test_returns_local_backend_by_default(self):
        """Default CACHE_BACKEND='local' returns LocalTTLCacheBackend."""
        mock_config = MagicMock()
        mock_config.CACHE_BACKEND = "local"

        with patch("mlflow_oidc_auth.config.config", mock_config):
            from mlflow_oidc_auth.cache.factory import get_cache_backend

            backend = get_cache_backend("test", maxsize=100, ttl=30)
            assert isinstance(backend, LocalTTLCacheBackend)

    def test_returns_local_backend_when_config_missing(self):
        """Falls back to 'local' when CACHE_BACKEND is not set."""
        mock_config = MagicMock(spec=[])  # No attributes — getattr returns "local"

        with patch("mlflow_oidc_auth.config.config", mock_config):
            from mlflow_oidc_auth.cache.factory import get_cache_backend

            backend = get_cache_backend("test", maxsize=100, ttl=30)
            assert isinstance(backend, LocalTTLCacheBackend)

    def test_redis_backend_raises_without_url(self):
        """Selecting 'redis' without CACHE_REDIS_URL raises ValueError."""
        mock_config = MagicMock()
        mock_config.CACHE_BACKEND = "redis"
        mock_config.CACHE_REDIS_URL = None

        with patch("mlflow_oidc_auth.config.config", mock_config):
            from mlflow_oidc_auth.cache.factory import get_cache_backend

            with pytest.raises(ValueError, match="CACHE_REDIS_URL is not configured"):
                get_cache_backend("test", maxsize=100, ttl=30)

    def test_redis_backend_with_url(self):
        """Selecting 'redis' with valid URL returns RedisCacheBackend."""
        mock_config = MagicMock()
        mock_config.CACHE_BACKEND = "redis"
        mock_config.CACHE_REDIS_URL = "redis://localhost:6379/0"
        mock_config.CACHE_KEY_PREFIX = "mlflow_oidc_auth:"

        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True

        mock_redis_module = MagicMock()
        mock_redis_module.Redis.from_url.return_value = mock_redis_client
        mock_redis_module.ConnectionError = ConnectionError

        with (
            patch("mlflow_oidc_auth.config.config", mock_config),
            patch.dict("sys.modules", {"redis": mock_redis_module}),
        ):
            from mlflow_oidc_auth.cache.factory import get_cache_backend

            backend = get_cache_backend("permissions", maxsize=100, ttl=30)
            # Check it's a RedisCacheBackend by verifying its attributes
            assert hasattr(backend, "_client")
            assert hasattr(backend, "_prefix")
            assert backend._prefix == "mlflow_oidc_auth:permissions:"

    def test_redis_backend_uses_default_prefix(self):
        """Redis backend uses default prefix when CACHE_KEY_PREFIX is not set."""
        mock_config = MagicMock(spec=[])
        mock_config.CACHE_BACKEND = "redis"
        mock_config.CACHE_REDIS_URL = "redis://localhost:6379/0"
        # CACHE_KEY_PREFIX not set — getattr fallback to "mlflow_oidc_auth:"

        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True

        mock_redis_module = MagicMock()
        mock_redis_module.Redis.from_url.return_value = mock_redis_client
        mock_redis_module.ConnectionError = ConnectionError

        with (
            patch("mlflow_oidc_auth.config.config", mock_config),
            patch.dict("sys.modules", {"redis": mock_redis_module}),
        ):
            from mlflow_oidc_auth.cache.factory import get_cache_backend

            backend = get_cache_backend("ws", maxsize=100, ttl=30)
            assert backend._prefix == "mlflow_oidc_auth:ws:"

    def test_unknown_backend_raises_value_error(self):
        """Unknown CACHE_BACKEND value raises ValueError."""
        mock_config = MagicMock()
        mock_config.CACHE_BACKEND = "memcached"

        with patch("mlflow_oidc_auth.config.config", mock_config):
            from mlflow_oidc_auth.cache.factory import get_cache_backend

            with pytest.raises(ValueError, match="Unknown CACHE_BACKEND: 'memcached'"):
                get_cache_backend("test", maxsize=100, ttl=30)
