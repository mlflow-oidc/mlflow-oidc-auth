"""
Auth Passing WSGI Middleware

This middleware passes FastAPI authentication information to Flask via WSGI environ.
It acts as a bridge between FastAPI's authentication middleware and Flask's WSGI application.
"""

from asgiref.wsgi import WsgiToAsgi as WSGIMiddleware

from starlette.types import Receive, Scope, Send
import asyncio
from types import TracebackType

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: A non-HEAD ``200`` response declaring more than this many bytes is sent without ``Content-Length``,
#: so Uvicorn sends it chunked. Proxies that cap non-streamed responses then stream it through
#: instead of failing it (Cloud Run refuses non-streamed HTTP/1 responses over 32 MiB). MLflow pages
#: its reads by item count, not size, so any read can get there: a run search page, a whole trace, an
#: artifact. Smaller responses, the bulk of the traffic, keep their exact length.
STREAMED_RESPONSE_THRESHOLD_BYTES = 16 << 20


def _declared_length(value: str) -> int:
    """The byte count a ``Content-Length`` value declares, or -1 if it is not a number."""
    try:
        return int(value)
    except ValueError:
        return -1


def _without_large_content_length(method: str, status: str, headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """``headers`` with ``Content-Length`` removed when it declares a large ``200`` body.

    HEAD keeps its length: it reports the size of the GET body, which a client may rely on. Any other
    status (a ``206`` range reply above all) keeps its framing, as does a length that is not a number.

    Parameters:
        method: The request method (WSGI ``REQUEST_METHOD``).
        status: The WSGI status line, e.g. ``"200 OK"``.
        headers: The response headers as Flask passes them to ``start_response``.

    Returns:
        The headers to send, a new list when one is removed.
    """
    if method == "HEAD" or status.split(" ", 1)[0] != "200":
        return headers
    if not any(name.lower() == "content-length" and _declared_length(value) > STREAMED_RESPONSE_THRESHOLD_BYTES for name, value in headers):
        return headers
    return [(name, value) for name, value in headers if name.lower() != "content-length"]


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

        # Extract AuthContext from ASGI scope (set by AuthMiddleware)
        auth_context = self.scope.get(AUTH_CONTEXT_KEY)
        if isinstance(auth_context, AuthContext):
            logger.debug(
                f"Injecting AuthContext into WSGI environ: username={auth_context.username}, is_admin={auth_context.is_admin}, workspace={auth_context.workspace}"
            )
            # Inject AuthContext as a single object — bridge functions read from this
            environ[AUTH_CONTEXT_KEY] = auth_context

        def start_response_with_framing(
            status: str,
            headers: list[tuple[str, str]],
            exc_info: tuple[type[BaseException], BaseException, TracebackType | None] | None = None,
        ) -> object:
            # Flask's response hooks have run, so this is the final length of the filtered body.
            headers = _without_large_content_length(environ.get("REQUEST_METHOD", ""), status, headers)
            return start_response(status, headers, exc_info)

        return self.flask_app(environ, start_response_with_framing)


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

            # Use asgiref's WsgiToAsgi adapter to handle ASGI-to-WSGI conversion.
            # This avoids depending on Starlette's deprecated WSGI adapter.
            wsgi_adapter = WSGIMiddleware(auth_injecting_app)
            await wsgi_adapter(scope, receive, send)
        else:
            # For non-HTTP requests (websocket/lifespan) try calling the
            # provided Flask app directly. If it is a callable that returns
            # an awaitable (e.g. AsyncMock or an ASGI-wrapped app), await it.
            # Otherwise, fall back to WSGI->ASGI adaptation which will likely
            # raise for unsupported scope types (mirroring asgiref behaviour).
            if callable(self.flask_app):
                result = self.flask_app(scope, receive, send)
                # If the call returned an awaitable, await it.
                if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                    await result
                    return

            # Fall back to WSGI->ASGI adaptation for non-callable or sync WSGI apps
            adapter = WSGIMiddleware(self.flask_app)
            await adapter(scope, receive, send)
