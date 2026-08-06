"""
Lazy-initialized singleton for the auth database store.

The ``store`` object is a transparent proxy that defers ``SqlAlchemyStore``
creation and ``init_db()`` (engine creation, Alembic migrations) until the
first attribute access.  This avoids triggering database I/O at module import
time, which is problematic for tests, type-checkers, and CLI tools that import
the module without needing a live database.
"""

from __future__ import annotations

import threading


class _LazyStore:
    """Thread-safe lazy proxy around :class:`SqlAlchemyStore`.

    On first attribute access the real store is created and ``init_db`` is
    called.  Subsequent accesses go directly to the underlying instance.
    """

    def __init__(self) -> None:
        object.__setattr__(self, "_instance", None)
        object.__setattr__(self, "_lock", threading.Lock())

    def _init(self):
        """Instantiate and initialise the real store (called once)."""
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        instance = SqlAlchemyStore()
        instance.init_db(config.OIDC_USERS_DB_URI)
        object.__setattr__(self, "_instance", instance)

    def _get_instance(self):
        instance = object.__getattribute__(self, "_instance")
        if instance is None:
            lock = object.__getattribute__(self, "_lock")
            with lock:
                # Double-check after acquiring lock
                instance = object.__getattribute__(self, "_instance")
                if instance is None:
                    object.__getattribute__(self, "_init")()
                    instance = object.__getattribute__(self, "_instance")
        return instance

    def __getattr__(self, name: str):
        return getattr(self._get_instance(), name)

    def __setattr__(self, name: str, value):
        setattr(self._get_instance(), name, value)

    def __repr__(self) -> str:
        instance = object.__getattribute__(self, "_instance")
        if instance is None:
            return "<_LazyStore (not yet initialised)>"
        return repr(instance)


store = _LazyStore()
