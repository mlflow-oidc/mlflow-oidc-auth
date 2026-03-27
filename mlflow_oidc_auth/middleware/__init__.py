"""
Middleware package for MLflow OIDC Auth.

This package contains middleware components for handling authentication,
authorization, session management, and proxy headers in the FastAPI application.
"""

from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import (
    AuthAwareWSGIMiddleware,
)
from mlflow_oidc_auth.middleware.fastapi_permission_middleware import (
    add_fastapi_permission_middleware,
)
from mlflow_oidc_auth.middleware.proxy_headers_middleware import ProxyHeadersMiddleware
from mlflow_oidc_auth.middleware.workspace_context_middleware import (
    WorkspaceContextMiddleware,
)

__all__ = [
    "AuthMiddleware",
    "AuthAwareWSGIMiddleware",
    "ProxyHeadersMiddleware",
    "WorkspaceContextMiddleware",
    "add_fastapi_permission_middleware",
]
