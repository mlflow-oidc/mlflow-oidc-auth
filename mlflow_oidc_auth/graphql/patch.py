from __future__ import annotations

from typing import Any, Callable, Optional

from mlflow_oidc_auth.graphql.middleware import GraphQLAuthorizationMiddleware
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


_INSTALLED = False
_ORIGINAL_AUTH_HOOK: Optional[Callable[[], list[Any]]] = None
_ORIGINAL_HANDLERS_HOOK: Optional[Callable[[], list[Any]]] = None
_INSTALLED_TARGET: Optional[str] = None


def install_mlflow_graphql_authorization_middleware() -> None:
    """Install OIDC GraphQL authorization middleware into MLflow.

    MLflow's `/graphql` handler (`mlflow.server.handlers._graphql`) calls
    `mlflow.server.handlers._get_graphql_auth_middleware()`, which *by default*
    tries to import `mlflow.server.auth.get_graphql_authorization_middleware`.

    This project does not use MLflow's basic-auth plugin, so MLflow's default
    implementation typically returns an empty list. To achieve the same *style*
    of authorization (Graphene middleware that enforces per-field access), we
    In some MLflow distributions, `mlflow.server.auth` is absent. To work
    reliably, we patch `mlflow.server.handlers._get_graphql_auth_middleware`
    directly to return our middleware.

    Notes:
        - The returned middleware list is evaluated per-request.
    """

    global _INSTALLED, _ORIGINAL_AUTH_HOOK, _ORIGINAL_HANDLERS_HOOK, _INSTALLED_TARGET
    if _INSTALLED:
        return

    def _middleware_list() -> list[Any]:
        return [GraphQLAuthorizationMiddleware()]

    # Prefer patching MLflow handlers directly (works even if mlflow.server.auth is missing).
    try:
        import mlflow.server.handlers as mlflow_handlers

        _ORIGINAL_HANDLERS_HOOK = getattr(mlflow_handlers, "_get_graphql_auth_middleware", None)

        def _get_graphql_auth_middleware() -> list[Any]:
            return _middleware_list()

        mlflow_handlers._get_graphql_auth_middleware = _get_graphql_auth_middleware  # type: ignore[attr-defined]
        _INSTALLED = True
        _INSTALLED_TARGET = "mlflow.server.handlers._get_graphql_auth_middleware"
        logger.info("Installed OIDC GraphQL authorization middleware (patched MLflow handlers)")
        return
    except Exception:
        pass

    # Fallback: patch mlflow.server.auth if available.
    try:
        import mlflow.server.auth as mlflow_auth

        _ORIGINAL_AUTH_HOOK = getattr(mlflow_auth, "get_graphql_authorization_middleware", None)

        def _get_graphql_authorization_middleware() -> list[Any]:
            return _middleware_list()

        mlflow_auth.get_graphql_authorization_middleware = _get_graphql_authorization_middleware  # type: ignore[attr-defined]
        _INSTALLED = True
        _INSTALLED_TARGET = "mlflow.server.auth.get_graphql_authorization_middleware"
        logger.info("Installed OIDC GraphQL authorization middleware (patched MLflow auth hook)")
    except Exception:
        logger.warning("Failed to install OIDC GraphQL authorization middleware", exc_info=True)


def uninstall_mlflow_graphql_authorization_middleware() -> None:
    """Restore the original MLflow GraphQL middleware hook (used in tests)."""

    global _INSTALLED, _ORIGINAL_AUTH_HOOK, _ORIGINAL_HANDLERS_HOOK, _INSTALLED_TARGET
    if not _INSTALLED:
        return

    try:
        import mlflow.server.handlers as mlflow_handlers

        if _ORIGINAL_HANDLERS_HOOK is not None:
            mlflow_handlers._get_graphql_auth_middleware = _ORIGINAL_HANDLERS_HOOK  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        import mlflow.server.auth as mlflow_auth

        if _ORIGINAL_AUTH_HOOK is not None:
            mlflow_auth.get_graphql_authorization_middleware = _ORIGINAL_AUTH_HOOK  # type: ignore[attr-defined]
    except Exception:
        pass

    _INSTALLED = False
    _ORIGINAL_AUTH_HOOK = None
    _ORIGINAL_HANDLERS_HOOK = None
    _INSTALLED_TARGET = None
