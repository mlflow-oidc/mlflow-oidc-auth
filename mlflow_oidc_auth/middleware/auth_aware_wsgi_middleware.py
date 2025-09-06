"""
Auth Passing WSGI Middleware

This middleware passes FastAPI authentication information to Flask via WSGI environ.
It acts as a bridge between FastAPI's authentication middleware and Flask's WSGI application.
"""

from starlette.middleware.wsgi import WSGIMiddleware
from starlette.types import Receive, Scope, Send

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


class AuthInjectingWSGIApp:
    """
    WSGI app wrapper that injects FastAPI authentication info into environ.

    This wrapper sits between WSGIMiddleware and the Flask app to inject
    authentication information from the ASGI scope into the WSGI environ.
    """

    def __init__(self, flask_app, scope: Scope):
        self.flask_app = flask_app
        self.scope = scope

    def __call__(self, environ, start_response):
        """WSGI app callable that injects auth info before calling Flask app."""

        # Extract auth info from ASGI scope (set by AuthMiddleware)
        auth_info = self.scope.get("mlflow_oidc_auth", {})
        username = auth_info.get("username")
        is_admin = auth_info.get("is_admin", False)

        if username:
            logger.debug(f"Injecting auth info into WSGI environ: username={username}, is_admin={is_admin}")
            # Inject auth info into WSGI environ
            environ["mlflow_oidc_auth.username"] = username
            environ["mlflow_oidc_auth.is_admin"] = is_admin

        # Call the Flask app with enhanced environ
        return self.flask_app(environ, start_response)


class AuthAwareWSGIMiddleware:
    """
    Custom WSGI Middleware that passes FastAPI authentication information to Flask.

    This middleware:
    1. Extracts the ASGI scope
    2. Creates an auth-injecting wrapper around the Flask app
    3. Uses WSGIMiddleware to handle the ASGI-to-WSGI conversion
    """

    def __init__(self, flask_app):
        self.flask_app = flask_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            # Create auth-injecting wrapper for this request
            auth_injecting_app = AuthInjectingWSGIApp(self.flask_app, scope)

            # Use WSGIMiddleware to handle the actual ASGI-to-WSGI conversion
            wsgi_middleware = WSGIMiddleware(auth_injecting_app)
            await wsgi_middleware(scope, receive, send)
        else:
            # For non-HTTP requests, just pass through
            await self.flask_app(scope, receive, send)
