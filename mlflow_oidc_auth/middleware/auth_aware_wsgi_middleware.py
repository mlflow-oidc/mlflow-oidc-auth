"""
Auth Passing WSGI Middleware

This middleware passes FastAPI authentication information to Flask via WSGI environ.
It acts as a bridge between FastAPI's authentication middleware and Flask's WSGI application.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

from asgiref.sync import sync_to_async
from asgiref.wsgi import WsgiToAsgi, WsgiToAsgiInstance

from starlette.types import Receive, Scope, Send
import asyncio
from types import TracebackType

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: asgiref's own ``run_wsgi_app``, without its ``@sync_to_async`` (see ``_ThreadPoolWsgiToAsgiInstance``).
_RUN_WSGI_APP = WsgiToAsgiInstance.__dict__["run_wsgi_app"].func

#: How long admin demo generation waits for the other Flask requests in flight to finish before it is
#: refused with 503. New Flask requests wait meanwhile, so this bounds how long they can be held.
RUN_ALONE_WAIT_SECONDS = 10.0

#: Paths whose Flask request runs alone, with no other Flask request of the process in flight. MLflow's
#: demo generation sets the process-wide ``MLFLOW_WORKSPACE`` for its whole run (``mlflow.demo.
#: generate_all_demos`` enters ``WorkspaceContext``), and MLflow serves a header-less request with no
#: workspace of its own from that variable. Running it alone keeps every other request from being decided
#: or served in the workspace of the request that generates (issue #482). It is admin-only
#: (``hooks/before_request.py``), and only an admin's request takes this path, so no other caller can hold
#: the process's Flask requests. ``tests/middleware/test_flask_request_gate.py`` fails when an MLflow
#: upgrade sets the variable anywhere else in the server process.
#:
#: This covers the requests MLflow serves through Flask. MLflow's FastAPI-native routes (OTel ingest,
#: gateway, jobs) do not pass through this bridge, so a header-less request to one of them can still
#: be checked and served on either side of the moment demo generation sets or clears the variable,
#: as before Flask requests ran on a pool.
RUN_ALONE_PATH_SUFFIXES = ("/mlflow/demo/generate",)

#: Flask routes that neither read a workspace nor take long. They skip the gate and run on their own
#: small pool (``_GATE_FREE_EXECUTOR``), so a liveness probe still answers while demo generation runs
#: and the requests waiting for it hold every thread of ``_WSGI_EXECUTOR``. Compared exactly, after the
#: static prefix.
GATE_FREE_PATHS = frozenset({"/health", "/version"})


class _FlaskRequestGate:
    """Lets Flask requests run together, except one that has to run alone.

    A request that runs alone waits until no other request is in flight; requests that arrive while it
    waits or runs wait for it. It gives up after a timeout, so requests that never finish (a client that
    stops reading a response) hold the others for that long at most.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._shared = 0
        self._alone_waiting = 0
        self._alone = False

    @contextmanager
    def shared(self) -> Iterator[None]:
        """Hold a place among the requests that run together."""
        with self._condition:
            self._condition.wait_for(lambda: not self._alone and not self._alone_waiting)
            self._shared += 1
        try:
            yield
        finally:
            with self._condition:
                self._shared -= 1
                self._condition.notify_all()

    def acquire_alone(self, timeout: float) -> bool:
        """Wait until no other request is in flight, then run alone.

        Parameters:
            timeout: Seconds to wait at most.

        Returns:
            True when the caller now runs alone and must call :meth:`release_alone`, False after the timeout.
        """
        deadline = time.monotonic() + timeout
        with self._condition:
            self._alone_waiting += 1
            try:
                acquired = self._condition.wait_for(lambda: not self._alone and not self._shared, max(0.0, deadline - time.monotonic()))
                if acquired:
                    self._alone = True
                return acquired
            finally:
                self._alone_waiting -= 1
                self._condition.notify_all()

    def release_alone(self) -> None:
        """Let the other requests run again."""
        with self._condition:
            self._alone = False
            self._condition.notify_all()


_FLASK_REQUEST_GATE = _FlaskRequestGate()


def _runs_alone(scope: Scope) -> bool:
    """Whether the request is an admin's to one of :data:`RUN_ALONE_PATH_SUFFIXES`.

    Matched on the path's end, so a static or forwarded prefix does not matter; a non-admin's request
    runs with the others and is refused by the Flask hooks.
    """
    auth_context = scope.get(AUTH_CONTEXT_KEY)
    if not isinstance(auth_context, AuthContext) or not auth_context.is_admin:
        return False
    path = str(scope.get("path") or "").rstrip("/")
    return path.endswith(RUN_ALONE_PATH_SUFFIXES)


def _bypasses_gate(scope: Scope) -> bool:
    """Whether the request is to one of :data:`GATE_FREE_PATHS`."""
    from mlflow_oidc_auth.hooks.route_policy import strip_static_prefix
    from mlflow_oidc_auth.middleware.route_path import routed_path

    return strip_static_prefix(routed_path(scope)).rstrip("/") in GATE_FREE_PATHS


def _send_busy(instance: WsgiToAsgiInstance) -> None:
    """Answer 503 in MLflow's error format, from the pool thread."""
    body = json.dumps({"error_code": "TEMPORARILY_UNAVAILABLE", "message": "Other requests are still running; retry demo generation."}).encode()
    instance.sync_send(
        {
            "type": "http.response.start",
            "status": 503,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"retry-after", b"5")],
        }
    )
    instance.sync_send({"type": "http.response.body", "body": body})


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

    Each request runs under :data:`_FLASK_REQUEST_GATE`, which runs admin demo generation alone
    (see :data:`RUN_ALONE_PATH_SUFFIXES`).
    """

    def _run_wsgi_app_gated(self, body: bytes) -> None:
        """Run the request under :data:`_FLASK_REQUEST_GATE`: alone for admin demo generation, else shared."""
        if not _runs_alone(self.scope):
            with _FLASK_REQUEST_GATE.shared():
                return _RUN_WSGI_APP(self, body)
        if not _FLASK_REQUEST_GATE.acquire_alone(RUN_ALONE_WAIT_SECONDS):
            logger.warning("Refusing demo generation: other Flask requests still ran after %ss", RUN_ALONE_WAIT_SECONDS)
            _send_busy(self)
            return None
        try:
            return _RUN_WSGI_APP(self, body)
        finally:
            _FLASK_REQUEST_GATE.release_alone()

    run_wsgi_app = sync_to_async(_run_wsgi_app_gated, thread_sensitive=False, executor=_WSGI_EXECUTOR)


#: Runs the requests to :data:`GATE_FREE_PATHS`.
_GATE_FREE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mlflow-oidc-wsgi-probe")


class _GateFreeWsgiToAsgiInstance(WsgiToAsgiInstance):
    """asgiref's per-request WSGI adapter for :data:`GATE_FREE_PATHS`: no gate, its own pool."""

    run_wsgi_app = sync_to_async(_RUN_WSGI_APP, thread_sensitive=False, executor=_GATE_FREE_EXECUTOR)


class WSGIMiddleware(WsgiToAsgi):
    """``asgiref.wsgi.WsgiToAsgi`` that runs the WSGI application on a thread pool.

    See ``_ThreadPoolWsgiToAsgiInstance`` for why the stock adapter is not used.
    """

    async def __call__(self, scope, receive, send):
        instance = _GateFreeWsgiToAsgiInstance if scope.get("type") == "http" and _bypasses_gate(scope) else _ThreadPoolWsgiToAsgiInstance
        await instance(self.wsgi_application, self.duplicate_header_limit)(scope, receive, send)


#: A non-HEAD ``200`` response declaring more than this many bytes is sent without ``Content-Length``,
#: so Uvicorn sends it chunked. Proxies that cap non-streamed responses then stream it through
#: instead of failing it (Cloud Run refuses non-streamed HTTP/1 responses over 32 MiB). MLflow pages
#: its reads by item count, not size, so any read can get there: a run search page, a whole trace, an
#: artifact. Smaller responses, the bulk of the traffic, keep their exact length.
STREAMED_RESPONSE_THRESHOLD_BYTES = 16 << 20


def _declared_length(value: str) -> int:
    """The byte count a ``Content-Length`` value declares.

    Parameters:
        value: The header value. Only ASCII digits are a length (RFC 9110), so ``+1``, ``1_000`` or ``1e9`` are not.

    Returns:
        The declared length, or -1 when ``value`` is not one.
    """
    value = value.strip()
    return int(value) if value.isascii() and value.isdigit() else -1


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
