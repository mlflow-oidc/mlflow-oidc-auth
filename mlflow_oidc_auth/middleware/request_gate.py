"""Runs an admin's demo data generation alone among the requests of a process (issue #482).

MLflow's demo generation sets the process-wide ``MLFLOW_WORKSPACE`` for its whole run
(``mlflow.demo.generate_all_demos`` enters ``WorkspaceContext``), and MLflow serves a request that names
no workspace, on a workspace provider without a default one, from that variable. The plugin decides such
a request in the workspace MLflow serves it from (``bridge.user.get_authorization_workspace``), so the
decision and the serving must not straddle the moment the variable is set or cleared.
:class:`RequestGateMiddleware` runs every other request either before demo generation starts or after it
ends, from the permission decision to the last byte of the response: Flask requests and MLflow's
FastAPI-native routes (OTel ingest, gateway, jobs, assistant, MCP and skill registries) alike.

Requests wait on the event loop, not on a thread, so waiting for demo generation holds no thread of the
WSGI pool. ``tests/middleware/test_request_gate.py`` fails when an MLflow upgrade sets the variable anywhere
else that can run while the server process serves requests.
"""

import asyncio
import json
import threading
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: How long demo generation waits for the requests in flight to finish before it is refused with 503.
#: New requests wait meanwhile, so this bounds how long they can be held up by a request that does not
#: finish (a client that stops reading, a long streamed response).
RUN_ALONE_WAIT_SECONDS = 10.0

#: Paths whose request runs alone. Admin-only (``hooks/before_request.py``), and only an admin's request
#: takes this path, so no other caller can hold the process's requests. Matched on the path's end, so a
#: static or forwarded prefix does not matter.
RUN_ALONE_PATH_SUFFIXES = ("/mlflow/demo/generate",)

#: Routes that neither read a workspace nor take long. They skip the gate, so liveness and readiness
#: probes answer while demo generation runs. Compared exactly, after the forwarded and static prefixes.
GATE_FREE_PATHS = frozenset({"/health", "/health/ready", "/health/live", "/health/startup", "/version"})

#: Trees of static assets: MLflow's React bundle, this plugin's admin UI and its API docs. They never read
#: a workspace, and they are large and served without authentication, so a client that downloads one and
#: stops reading would otherwise hold its place in the gate and make every demo generation wait it out.
GATE_FREE_TREES = ("/static-files/", "/oidc/ui/", "/docs", "/redoc", "/openapi.json")


class RequestGate:
    """Lets requests run together, except one that has to run alone.

    A request that runs alone waits until no other request is in flight; requests that arrive while it
    waits or runs wait for it. It gives up after a timeout. A waiting request sleeps on a future of its own
    event loop, woken when the gate changes, so waiting costs nothing and the gate is not bound to one loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._shared = 0
        self._alone_waiting = 0
        self._alone = False
        self._waiters: list[tuple[asyncio.AbstractEventLoop, asyncio.Future[None]]] = []

    def _wait_for_change_locked(self) -> "asyncio.Future[None]":
        """A future resolved at the next change of the gate. Called with the lock held, so no change is missed."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        entry = (loop, future)
        self._waiters.append(entry)
        # A waiter that is cancelled or times out leaves the list at once, not at the next change.
        future.add_done_callback(lambda _: self._forget(entry))
        return future

    def _forget(self, entry: "tuple[asyncio.AbstractEventLoop, asyncio.Future[None]]") -> None:
        with self._lock:
            try:
                self._waiters.remove(entry)
            except ValueError:
                pass

    def _wake_locked(self) -> None:
        """Wake every waiting request to look again. Called with the lock held."""
        waiters, self._waiters = self._waiters, []
        for loop, future in waiters:
            if future.done():
                continue
            try:
                loop.call_soon_threadsafe(_resolve, future)
            except RuntimeError:
                # Its loop has closed: nobody is left to wake there, and the others must still be woken.
                continue

    async def enter_shared(self) -> None:
        """Wait for a place among the requests that run together; :meth:`leave_shared` gives it back."""
        while True:
            with self._lock:
                if not self._alone and not self._alone_waiting:
                    self._shared += 1
                    return
                change = self._wait_for_change_locked()
            await change

    def leave_shared(self) -> None:
        """Give back the place :meth:`enter_shared` took."""
        with self._lock:
            self._shared -= 1
            if not self._shared:
                self._wake_locked()

    async def acquire_alone(self, timeout: float) -> bool:
        """Wait until no other request is in flight, then run alone.

        Parameters:
            timeout: Seconds to wait at most.

        Returns:
            True when the caller now runs alone and must call :meth:`release_alone`, False after the timeout.
        """
        deadline = time.monotonic() + timeout
        with self._lock:
            self._alone_waiting += 1
        try:
            while True:
                with self._lock:
                    if not self._alone and not self._shared:
                        self._alone = True
                        return True
                    change = self._wait_for_change_locked()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                try:
                    await asyncio.wait_for(change, remaining)
                except TimeoutError:
                    return False
        finally:
            with self._lock:
                self._alone_waiting -= 1
                self._wake_locked()

    def release_alone(self) -> None:
        """Let the other requests run again."""
        with self._lock:
            self._alone = False
            self._wake_locked()


def _resolve(future: "asyncio.Future[None]") -> None:
    if not future.done():
        future.set_result(None)


REQUEST_GATE = RequestGate()


def runs_alone(scope: Scope) -> bool:
    """Whether the request is an admin's to one of :data:`RUN_ALONE_PATH_SUFFIXES`.

    Parameters:
        scope: The ASGI scope, with the ``AuthContext`` that ``AuthMiddleware`` put there.

    Returns:
        True for an admin's ``POST`` to demo generation (the only method MLflow serves there); a non-admin's
        runs with the others and is refused by the Flask hooks.
    """
    auth_context = scope.get(AUTH_CONTEXT_KEY)
    if not isinstance(auth_context, AuthContext) or not auth_context.is_admin or scope.get("method") != "POST":
        return False
    return str(scope.get("path") or "").rstrip("/").endswith(RUN_ALONE_PATH_SUFFIXES)


def bypasses_gate(scope: Scope) -> bool:
    """Whether the request is to one of :data:`GATE_FREE_PATHS` or below one of :data:`GATE_FREE_TREES`.

    Parameters:
        scope: The ASGI scope.

    Returns:
        True when the routed path, without MLflow's static prefix, is a gate-free path or asset.
    """
    from mlflow_oidc_auth.hooks.route_policy import strip_static_prefix
    from mlflow_oidc_auth.middleware.route_path import routed_path

    if is_probe(scope):
        return True
    path = strip_static_prefix(routed_path(scope))
    return any(path.startswith(tree) if tree.endswith("/") else path == tree or path.startswith(tree + "/") for tree in GATE_FREE_TREES)


def is_probe(scope: Scope) -> bool:
    """Whether the request is exactly one of :data:`GATE_FREE_PATHS` (the probes, not the asset trees).

    Parameters:
        scope: The ASGI scope.

    Returns:
        True for a probe, whatever the forwarded or static prefix.
    """
    from mlflow_oidc_auth.hooks.route_policy import strip_static_prefix
    from mlflow_oidc_auth.middleware.route_path import routed_path

    return strip_static_prefix(routed_path(scope)).rstrip("/") in GATE_FREE_PATHS


def is_gating() -> bool:
    """Whether the gate is needed: only with workspaces on can a request be served from ``MLFLOW_WORKSPACE``."""
    from mlflow_oidc_auth.config import config

    return bool(config.MLFLOW_ENABLE_WORKSPACES)


async def _send_busy(send: Send) -> None:
    """Answer 503 in MLflow's error format."""
    body = json.dumps({"error_code": "TEMPORARILY_UNAVAILABLE", "message": "Other requests are still running; retry demo generation."}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 503,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"retry-after", b"5")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RequestGateMiddleware:
    """Runs each HTTP request under :data:`REQUEST_GATE`: alone for an admin's demo generation, else shared.

    Installed inside ``AuthMiddleware``, which says who the caller is, and outside the permission middleware,
    so the gate covers the permission decision as well as the handler and the whole response body. With
    workspaces disabled (the default) it passes every request straight through: MLflow then serves every
    request from the default workspace whatever ``MLFLOW_WORKSPACE`` holds.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not is_gating() or bypasses_gate(scope):
            await self.app(scope, receive, send)
            return
        if runs_alone(scope):
            if not await REQUEST_GATE.acquire_alone(RUN_ALONE_WAIT_SECONDS):
                logger.warning("Refusing demo generation: other requests still ran after %ss", RUN_ALONE_WAIT_SECONDS)
                await _send_busy(send)
                return
            try:
                await self.app(scope, receive, send)
            finally:
                REQUEST_GATE.release_alone()
            return
        await REQUEST_GATE.enter_shared()
        try:
            await self.app(scope, receive, send)
        finally:
            REQUEST_GATE.leave_shared()
