from __future__ import annotations

from typing import Any, Callable, Optional

from mlflow_oidc_auth.graphql.middleware import GraphQLAuthorizationMiddleware
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: The private MLflow attribute we patch. Defined as a constant so tests can
#: reference the same name and detect renames during MLflow upgrades.
_HANDLERS_ATTR = "_get_graphql_auth_middleware"
_AUTH_ATTR = "get_graphql_authorization_middleware"

_INSTALLED = False
_ORIGINAL_AUTH_HOOK: Optional[Callable[[], list[Any]]] = None
_ORIGINAL_HANDLERS_HOOK: Optional[Callable[[], list[Any]]] = None
_INSTALLED_TARGET: Optional[str] = None


def install_mlflow_graphql_authorization_middleware() -> None:
    """Install OIDC GraphQL authorization middleware into MLflow.

    MLflow's ``/graphql`` handler (``mlflow.server.handlers._graphql()``) calls
    ``mlflow.server.handlers._get_graphql_auth_middleware()``, which *by default*
    tries to import ``mlflow.server.auth.get_graphql_authorization_middleware``.

    This project does not use MLflow's basic-auth plugin, so MLflow's default
    implementation typically returns an empty list. To achieve the same *style*
    of authorization (Graphene middleware that enforces per-field access), we
    patch the hook to return our middleware instead.

    In some MLflow distributions, ``mlflow.server.auth`` is absent. To work
    reliably, we patch ``mlflow.server.handlers._get_graphql_auth_middleware``
    directly to return our middleware.

    Notes:
        - The returned middleware list is evaluated per-request.
        - If the target attribute does not exist on MLflow's ``handlers`` module
          (e.g. after an MLflow upgrade that removes/renames the private API),
          a warning is logged and the fallback path is attempted.
    """

    global _INSTALLED, _ORIGINAL_AUTH_HOOK, _ORIGINAL_HANDLERS_HOOK, _INSTALLED_TARGET
    if _INSTALLED:
        return

    def _middleware_list() -> list[Any]:
        return [GraphQLAuthorizationMiddleware()]

    # Prefer patching MLflow handlers directly (works even if mlflow.server.auth is missing).
    try:
        import mlflow.server.handlers as mlflow_handlers

        if not hasattr(mlflow_handlers, _HANDLERS_ATTR):
            logger.warning(
                "MLflow handlers module does not have attribute '%s'; "
                "GraphQL authorization middleware installation will attempt fallback. "
                "This may indicate an incompatible MLflow version.",
                _HANDLERS_ATTR,
            )
        else:
            _ORIGINAL_HANDLERS_HOOK = getattr(mlflow_handlers, _HANDLERS_ATTR, None)

            # Verify the original is callable (signature sanity check)
            if _ORIGINAL_HANDLERS_HOOK is not None and not callable(_ORIGINAL_HANDLERS_HOOK):
                logger.warning(
                    "MLflow's %s is not callable (type=%s); overwriting anyway",
                    _HANDLERS_ATTR,
                    type(_ORIGINAL_HANDLERS_HOOK).__name__,
                )

            def _get_graphql_auth_middleware() -> list[Any]:
                return _middleware_list()

            setattr(mlflow_handlers, _HANDLERS_ATTR, _get_graphql_auth_middleware)
            _INSTALLED = True
            _INSTALLED_TARGET = f"mlflow.server.handlers.{_HANDLERS_ATTR}"
            logger.info("Installed OIDC GraphQL authorization middleware (patched MLflow handlers)")
            return
    except Exception:
        logger.debug("Failed to patch mlflow.server.handlers, trying fallback", exc_info=True)

    # Fallback: patch mlflow.server.auth if available.
    try:
        import mlflow.server.auth as mlflow_auth

        if not hasattr(mlflow_auth, _AUTH_ATTR):
            logger.warning(
                "MLflow auth module does not have attribute '%s'; "
                "GraphQL authorization middleware could not be installed. "
                "This may indicate an incompatible MLflow version.",
                _AUTH_ATTR,
            )
            return

        _ORIGINAL_AUTH_HOOK = getattr(mlflow_auth, _AUTH_ATTR, None)

        def _get_graphql_authorization_middleware() -> list[Any]:
            return _middleware_list()

        setattr(mlflow_auth, _AUTH_ATTR, _get_graphql_authorization_middleware)
        _INSTALLED = True
        _INSTALLED_TARGET = f"mlflow.server.auth.{_AUTH_ATTR}"
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
            setattr(mlflow_handlers, _HANDLERS_ATTR, _ORIGINAL_HANDLERS_HOOK)
    except Exception:
        pass

    try:
        import mlflow.server.auth as mlflow_auth

        if _ORIGINAL_AUTH_HOOK is not None:
            setattr(mlflow_auth, _AUTH_ATTR, _ORIGINAL_AUTH_HOOK)
    except Exception:
        pass

    _INSTALLED = False
    _ORIGINAL_AUTH_HOOK = None
    _ORIGINAL_HANDLERS_HOOK = None
    _INSTALLED_TARGET = None
