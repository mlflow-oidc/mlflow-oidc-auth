from __future__ import annotations

from typing import Any
from unittest.mock import patch as mock_patch

from mlflow_oidc_auth.graphql.patch import (
    _HANDLERS_ATTR,
    install_mlflow_graphql_authorization_middleware,
    uninstall_mlflow_graphql_authorization_middleware,
)


def test_patch_installs_into_mlflow_handlers() -> None:
    """Ensure install patches MLflow's handler hook used by /graphql."""

    import mlflow.server.handlers as mlflow_handlers

    # The application factory may install the patch at import time.
    # Normalize to a clean baseline for this test.
    uninstall_mlflow_graphql_authorization_middleware()

    original = getattr(mlflow_handlers, _HANDLERS_ATTR)
    try:
        install_mlflow_graphql_authorization_middleware()
        middleware = getattr(mlflow_handlers, _HANDLERS_ATTR)()
        assert isinstance(middleware, list)
        assert len(middleware) == 1
        # Don't assert exact type path too strictly; just ensure it's callable middleware.
        assert hasattr(middleware[0], "resolve")
    finally:
        uninstall_mlflow_graphql_authorization_middleware()
        assert getattr(mlflow_handlers, _HANDLERS_ATTR) is original


def test_patch_is_idempotent() -> None:
    """Calling install twice should not fail or double-patch."""

    uninstall_mlflow_graphql_authorization_middleware()
    try:
        install_mlflow_graphql_authorization_middleware()
        install_mlflow_graphql_authorization_middleware()  # second call is a no-op

        import mlflow.server.handlers as mlflow_handlers

        middleware = getattr(mlflow_handlers, _HANDLERS_ATTR)()
        assert isinstance(middleware, list)
        assert len(middleware) == 1
    finally:
        uninstall_mlflow_graphql_authorization_middleware()


def test_patch_warns_when_attribute_missing(caplog) -> None:
    """If the target attribute is removed from MLflow, a warning should be logged."""
    import mlflow.server.handlers as mlflow_handlers

    uninstall_mlflow_graphql_authorization_middleware()
    original = getattr(mlflow_handlers, _HANDLERS_ATTR, None)
    try:
        # Temporarily remove the attribute to simulate an incompatible MLflow version
        if hasattr(mlflow_handlers, _HANDLERS_ATTR):
            delattr(mlflow_handlers, _HANDLERS_ATTR)

        # Also prevent fallback to mlflow.server.auth by making it fail
        with mock_patch.dict("sys.modules", {"mlflow.server.auth": None}):
            install_mlflow_graphql_authorization_middleware()

        assert any("does not have attribute" in record.message for record in caplog.records)
    finally:
        # Restore original
        if original is not None:
            setattr(mlflow_handlers, _HANDLERS_ATTR, original)
        uninstall_mlflow_graphql_authorization_middleware()


def test_uninstall_restores_original() -> None:
    """Uninstall should restore the exact original function."""

    import mlflow.server.handlers as mlflow_handlers

    uninstall_mlflow_graphql_authorization_middleware()

    original = getattr(mlflow_handlers, _HANDLERS_ATTR)
    install_mlflow_graphql_authorization_middleware()

    # After install, it should be patched (different from original)
    patched = getattr(mlflow_handlers, _HANDLERS_ATTR)
    assert patched is not original

    uninstall_mlflow_graphql_authorization_middleware()

    # After uninstall, it should be restored
    restored = getattr(mlflow_handlers, _HANDLERS_ATTR)
    assert restored is original
