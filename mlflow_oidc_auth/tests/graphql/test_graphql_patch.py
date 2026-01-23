from __future__ import annotations

from typing import Any

from mlflow_oidc_auth.graphql.patch import (
    install_mlflow_graphql_authorization_middleware,
    uninstall_mlflow_graphql_authorization_middleware,
)


def test_patch_installs_into_mlflow_handlers() -> None:
    """Ensure install patches MLflow's handler hook used by /graphql."""

    import mlflow.server.handlers as mlflow_handlers

    # The application factory may install the patch at import time.
    # Normalize to a clean baseline for this test.
    uninstall_mlflow_graphql_authorization_middleware()

    original = getattr(mlflow_handlers, "_get_graphql_auth_middleware")
    try:
        install_mlflow_graphql_authorization_middleware()
        middleware = mlflow_handlers._get_graphql_auth_middleware()  # type: ignore[attr-defined]
        assert isinstance(middleware, list)
        assert len(middleware) == 1
        # Don't assert exact type path too strictly; just ensure it's callable middleware.
        assert hasattr(middleware[0], "resolve")
    finally:
        uninstall_mlflow_graphql_authorization_middleware()
        assert getattr(mlflow_handlers, "_get_graphql_auth_middleware") is original
