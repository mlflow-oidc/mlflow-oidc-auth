"""GraphQL authorization integration for MLflow.

MLflow serves `/graphql` from `mlflow.server.handlers._graphql()`.
That handler supports a Graphene/GraphQL middleware chain via
`schema.execute(..., middleware=[...])`.

The MLflow basic-auth plugin provides a middleware that enforces per-field
authorization. This package implements an equivalent middleware for the
OIDC auth plugin and installs it into MLflow at runtime.
"""

from mlflow_oidc_auth.graphql.middleware import GraphQLAuthorizationMiddleware
from mlflow_oidc_auth.graphql.patch import install_mlflow_graphql_authorization_middleware

__all__ = [
    "GraphQLAuthorizationMiddleware",
    "install_mlflow_graphql_authorization_middleware",
]
