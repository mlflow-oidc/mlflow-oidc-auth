"""
Cache backend protocol definition.

The CacheBackend protocol defines the interface that all cache implementations
must satisfy. Values are stored as arbitrary Python objects — serialization is
handled internally by each backend (e.g. pickle for Redis, identity for local).
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Protocol for pluggable cache backends.

    All cache backends must implement this interface. Keys are strings;
    values are arbitrary Python objects.

    Thread-safety is the responsibility of each implementation.
    """

    def get(self, key: str) -> Any | None:
        """Retrieve a value by key.

        Returns:
            The cached value, or None if the key is missing or expired.
        """
        ...

    def set(self, key: str, value: Any) -> None:
        """Store a value under the given key.

        The value will expire according to the TTL configured at
        construction time.
        """
        ...

    def delete(self, key: str) -> None:
        """Remove a single key from the cache.

        No-op if the key does not exist.
        """
        ...

    def clear(self) -> None:
        """Remove all entries from this cache namespace."""
        ...
