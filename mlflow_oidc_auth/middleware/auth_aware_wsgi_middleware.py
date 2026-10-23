"""
Auth Passing WSGI Middleware

This middleware passes FastAPI authentication information to Flask via WSGI environ.
It acts as a bridge between FastAPI's authentication middleware and Flask's WSGI application.
"""

from concurrent.futures import ThreadPoolExecutor

from asgiref.sync import sync_to_async
from asgiref.wsgi import WsgiToAsgi, WsgiToAsgiInstance

from starlette.types import Receive, Scope, Send
import asyncio

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: Runs the Flask requests of this process: ``WSGI_THREADS`` threads (default 4). Its threads start
#: on first use, so a server that forks its workers after importing the app still gets one pool each.
_WSGI_EXECUTOR = ThreadPoolExecutor(max_workers=config.WSGI_THREADS, thread_name_prefix="mlflow-oidc-wsgi")


class _ThreadPoolWsgiToAsgiInstance(WsgiToAsgiInstance):
    """asgiref's per-request WSGI adapter, with the WSGI call on a bounded thread pool.

    asgiref decorates ``WsgiToAsgiInstance.run_wsgi_app`` with a bare ``@sync_to_async``, which is
    ``thread_sensitive=True``. Outside Django nothing sets a thread-sensitive context, so every call
    in the process runs on ``SyncToAsync.single_thread_executor``: one thread for all Flask requests
    of a uvicorn worker. A long request then delays every other request of that worker, for its
    whole run and for as long as its response takes to drain to a slow client.

    ``thread_sensitive=False`` runs each request on ``_WSGI_EXECUTOR`` instead. Not on the event
    loop's default executor, which has ``min(32, CPUs + 4)`` threads: every request in flight holds
    its response in memory, and CPU-bound requests do not finish sooner in parallel under the GIL.
    With 8 large searches at once, the default executor doubled a worker's memory and made the
    slowest search 2.5 times longer, for no more searches served; 4 threads kept writes passing the
    searches and bounded both (issue #482).
    """

    run_wsgi_app = sync_to_async(WsgiToAsgiInstance.__dict__["run_wsgi_app"].func, thread_sensitive=False, executor=_WSGI_EXECUTOR)


class WSGIMiddleware(WsgiToAsgi):
    """``asgiref.wsgi.WsgiToAsgi`` that runs the WSGI application on a thread pool.

    See ``_ThreadPoolWsgiToAsgiInstance`` for why the stock adapter is not used.
    """

    async def __call__(self, scope, receive, send):
        await _ThreadPoolWsgiToAsgiInstance(self.wsgi_application, self.duplicate_header_limit)(scope, receive, send)


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

            # asgiref's WsgiToAsgi adapter (on a thread pool, see WSGIMiddleware) handles the
            # ASGI-to-WSGI conversion. This avoids depending on Starlette's deprecated WSGI adapter.
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
