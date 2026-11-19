"""An admin's demo generation runs alone among the requests of a process (issue #482).

MLflow's demo generation sets the process-wide ``MLFLOW_WORKSPACE`` while it runs, and MLflow serves a
header-less request with no workspace of its own from that variable. No other request, Flask or
FastAPI-native, may be decided or served while it is set.
"""

import ast
import asyncio
import pathlib
import threading
import time

import pytest

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.middleware import auth_aware_wsgi_middleware as bridge
from mlflow_oidc_auth.middleware import request_gate
from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware
from mlflow_oidc_auth.middleware.request_gate import RequestGate, RequestGateMiddleware

DEMO = "/ajax-api/3.0/mlflow/demo/generate"
OTHER = "/api/2.0/mlflow/experiments/search"
NATIVE = "/v1/traces"
ADMIN = AuthContext(username="admin@example.com", is_admin=True)
USER = AuthContext(username="bob@example.com", is_admin=False)


@pytest.fixture(autouse=True)
def _workspaces_enabled(monkeypatch):
    """The gate only acts with workspaces on; tests that need it off say so."""
    from mlflow_oidc_auth.config import config

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)


def _scope(path, auth_context, method="POST"):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        AUTH_CONTEXT_KEY: auth_context,
    }


def _until(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.005)


async def _until_async(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not reached"
        await asyncio.sleep(0.005)


async def _call(app, path, auth_context=USER):
    sent = []
    body_read = []

    async def receive():
        # As a server does: the body once, then nothing until the client goes away (it does not here).
        if not body_read:
            body_read.append(True)
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()

    async def send(message):
        sent.append(message)

    await app(_scope(path, auth_context), receive, send)
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


class _Server:
    """The gate in front of a Flask app (through the bridge) and a FastAPI-native streaming route.

    Both record how many requests are in flight; the demo request records what it sees while it runs.
    """

    def __init__(self, hold_flask=None):
        self.lock = threading.Lock()
        self.in_flight = 0
        self.seen_by_demo = []
        self.hold_flask = hold_flask
        self.native_release = asyncio.Event()
        self.native_chunks_sent = 0
        self.flask = AuthAwareWSGIMiddleware(self._flask_app)
        self.app = RequestGateMiddleware(self._dispatch)

    def _enter(self):
        with self.lock:
            self.in_flight += 1

    def _leave(self):
        with self.lock:
            self.in_flight -= 1

    def _flask_app(self, environ, start_response):
        self._enter()
        try:
            if environ["PATH_INFO"].endswith("/mlflow/demo/generate"):
                for _ in range(5):
                    with self.lock:
                        self.seen_by_demo.append(self.in_flight)
                    time.sleep(0.02)
            elif self.hold_flask is not None:
                assert self.hold_flask.wait(10)
            else:
                time.sleep(0.05)
        finally:
            self._leave()
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]

    async def _native(self, scope, receive, send):
        """A streamed FastAPI-native response: it is in flight until its last chunk."""
        self._enter()
        try:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"first", "more_body": True})
            self.native_chunks_sent = 1
            await self.native_release.wait()
            await send({"type": "http.response.body", "body": b"last", "more_body": False})
        finally:
            self._leave()

    async def _dispatch(self, scope, receive, send):
        if scope["path"].startswith(NATIVE):
            await self._native(scope, receive, send)
        else:
            await self.flask(scope, receive, send)


@pytest.mark.asyncio
async def test_admin_demo_generation_runs_alone_among_flask_requests():
    server = _Server()
    calls = [_call(server.app, OTHER) for _ in range(3)] + [_call(server.app, DEMO, ADMIN)] + [_call(server.app, OTHER) for _ in range(3)]
    assert await asyncio.gather(*calls) == [200] * 7
    assert server.seen_by_demo and set(server.seen_by_demo) == {1}


@pytest.mark.asyncio
async def test_demo_generation_waits_for_a_streamed_fastapi_native_response():
    """A FastAPI-native request, decided and served without Flask, still counts until its last byte."""
    server = _Server()
    stream = asyncio.ensure_future(_call(server.app, NATIVE))
    await _until_async(lambda: server.native_chunks_sent == 1)
    demo = asyncio.ensure_future(_call(server.app, DEMO, ADMIN))
    try:
        await asyncio.sleep(0.2)
        assert not demo.done()
        assert server.seen_by_demo == []
    finally:
        server.native_release.set()
        await asyncio.gather(stream, demo, return_exceptions=True)
    assert demo.result() == 200
    assert set(server.seen_by_demo) == {1}


@pytest.mark.asyncio
async def test_fastapi_native_requests_wait_while_demo_generation_runs():
    hold = threading.Event()
    server = _Server()
    entered = threading.Event()

    def slow_demo(environ, start_response):
        entered.set()
        assert hold.wait(10)
        start_response("200 OK", [])
        return [b"ok"]

    server.flask = AuthAwareWSGIMiddleware(slow_demo)
    demo = asyncio.ensure_future(_call(server.app, DEMO, ADMIN))
    native = None
    try:
        await _until_async(entered.is_set)
        server.native_release.set()
        native = asyncio.ensure_future(_call(server.app, NATIVE))
        await asyncio.sleep(0.2)
        assert not native.done()
        assert server.in_flight == 0
    finally:
        hold.set()
        await asyncio.gather(demo, *([native] if native else []), return_exceptions=True)
    assert native.result() == 200


@pytest.mark.asyncio
async def test_requests_waiting_for_demo_generation_hold_no_pool_thread():
    """Waiting happens on the event loop: the pool has room, so a probe and the demo's own work proceed."""
    hold = threading.Event()
    entered = threading.Event()

    def app(environ, start_response):
        if environ["PATH_INFO"].endswith("/mlflow/demo/generate"):
            entered.set()
            assert hold.wait(10)
        start_response("200 OK", [])
        return [b"ok"]

    gated = RequestGateMiddleware(AuthAwareWSGIMiddleware(app))
    demo = asyncio.ensure_future(_call(gated, DEMO, ADMIN))
    waiting = []
    try:
        await _until_async(entered.is_set)
        waiting = [asyncio.ensure_future(_call(gated, OTHER)) for _ in range(bridge._WSGI_EXECUTOR._max_workers * 3)]
        await asyncio.sleep(0.1)
        assert not any(task.done() for task in waiting)
        assert bridge._WSGI_EXECUTOR._work_queue.qsize() == 0
        probe = asyncio.ensure_future(_call(gated, "/version"))
        done, _ = await asyncio.wait({probe}, timeout=2)
        assert probe in done and probe.result() == 200
    finally:
        hold.set()
        await asyncio.gather(demo, *waiting, return_exceptions=True)
    assert all(task.result() == 200 for task in waiting)


@pytest.mark.asyncio
async def test_a_non_admin_demo_request_does_not_hold_the_others():
    hold = threading.Event()
    server = _Server(hold_flask=hold)
    long_request = asyncio.ensure_future(_call(server.app, OTHER))
    await _until_async(lambda: server.in_flight == 1)
    demo = None
    try:
        demo = asyncio.ensure_future(_call(server.app, DEMO, USER))
        done, _ = await asyncio.wait({demo}, timeout=2)
        assert demo in done, "a non-admin's demo request waited for the other requests"
        assert set(server.seen_by_demo) == {2}
    finally:
        hold.set()
        await asyncio.gather(long_request, *([demo] if demo else []), return_exceptions=True)


@pytest.mark.asyncio
async def test_demo_generation_is_refused_when_other_requests_do_not_finish(monkeypatch):
    monkeypatch.setattr(request_gate, "RUN_ALONE_WAIT_SECONDS", 0.2)
    server = _Server()
    stream = asyncio.ensure_future(_call(server.app, NATIVE))
    await _until_async(lambda: server.native_chunks_sent == 1)
    demo = asyncio.ensure_future(_call(server.app, DEMO, ADMIN))
    try:
        done, _ = await asyncio.wait({demo}, timeout=2)
        assert demo in done, "demo generation was not refused while another request held the gate"
        assert demo.result() == 503
        assert server.seen_by_demo == []
    finally:
        server.native_release.set()
        await asyncio.gather(stream, demo, return_exceptions=True)
    assert stream.result() == 200
    # The gate is free again.
    assert await asyncio.wait_for(asyncio.gather(_call(server.app, OTHER), _call(server.app, DEMO, ADMIN)), 5) == [200, 200]
    assert set(server.seen_by_demo) == {1}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/health/ready", "/health/live", "/version", "/health/"])
async def test_probes_answer_while_demo_generation_runs(path):
    hold = threading.Event()
    entered = threading.Event()

    def app(environ, start_response):
        if environ["PATH_INFO"].endswith("/mlflow/demo/generate"):
            entered.set()
            assert hold.wait(10)
        start_response("200 OK", [])
        return [b"ok"]

    gated = RequestGateMiddleware(AuthAwareWSGIMiddleware(app))
    demo = asyncio.ensure_future(_call(gated, DEMO, ADMIN))
    probe = None
    try:
        await _until_async(entered.is_set)
        probe = asyncio.ensure_future(_call(gated, path))
        done, _ = await asyncio.wait({probe}, timeout=2)
        assert probe in done, f"{path} waited for demo generation"
    finally:
        hold.set()
        await asyncio.gather(demo, *([probe] if probe else []), return_exceptions=True)


@pytest.mark.asyncio
async def test_non_http_scopes_pass_through():
    seen = []

    async def app(scope, receive, send):
        seen.append(scope["type"])

    await RequestGateMiddleware(app)({"type": "lifespan"}, None, None)
    assert seen == ["lifespan"]


def test_the_gate_wraps_the_permission_decision():
    """Inside Auth (it needs the admin flag), outside the permission middleware (it must cover the decision)."""
    from fastapi import FastAPI
    from starlette.middleware.base import BaseHTTPMiddleware

    from mlflow_oidc_auth.app import add_middleware_stack
    from mlflow_oidc_auth.middleware import AuthMiddleware

    app = FastAPI()
    add_middleware_stack(app)
    order = [m.cls for m in app.user_middleware]  # outermost first
    gate = order.index(RequestGateMiddleware)
    assert order[gate - 1] is AuthMiddleware
    assert order[gate + 1] is BaseHTTPMiddleware
    assert gate + 1 == len(order) - 1


@pytest.mark.parametrize("path", ["/prefix" + DEMO, DEMO + "/", "/api/3.0/mlflow/demo/generate"])
def test_run_alone_matches_any_prefix(path):
    assert request_gate.runs_alone(_scope(path, ADMIN))


@pytest.mark.parametrize("auth_context", [USER, None, "admin"])
def test_only_an_admin_runs_alone(auth_context):
    assert not request_gate.runs_alone(_scope(DEMO, auth_context))


def test_other_paths_do_not_run_alone():
    assert not request_gate.runs_alone(_scope("/ajax-api/3.0/mlflow/demo/delete", ADMIN))
    assert not request_gate.runs_alone(_scope(OTHER, ADMIN))


@pytest.mark.parametrize("method", ["GET", "OPTIONS", "HEAD"])
def test_only_a_post_runs_alone(method):
    """MLflow serves demo generation on POST only; anything else is refused without generating."""
    assert not request_gate.runs_alone(_scope(DEMO, ADMIN, method=method))


@pytest.mark.asyncio
async def test_with_workspaces_disabled_nothing_waits(monkeypatch):
    """A default deployment is unaffected: MLflow serves every request from the default workspace then."""
    from mlflow_oidc_auth.config import config

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    hold = threading.Event()
    server = _Server(hold_flask=hold)
    long_request = asyncio.ensure_future(_call(server.app, OTHER))
    await _until_async(lambda: server.in_flight == 1)
    demo = None
    try:
        demo = asyncio.ensure_future(_call(server.app, DEMO, ADMIN))
        done, _ = await asyncio.wait({demo}, timeout=2)
        assert demo in done, "demo generation waited although workspaces are disabled"
        assert set(server.seen_by_demo) == {2}
    finally:
        hold.set()
        await asyncio.gather(long_request, *([demo] if demo else []), return_exceptions=True)


@pytest.mark.parametrize(
    "path, gate_free",
    [
        ("/static-files/static/js/main.abc123.js", True),
        ("/oidc/ui/", True),
        ("/oidc/ui/assets/index.js", True),
        ("/docs", True),
        ("/docs/oauth2-redirect", True),
        ("/openapi.json", True),
        ("/static-filesx/a.js", False),
        ("/docsx", False),
        ("/oidc/uix", False),
        ("/api/2.0/mlflow/static-files/a.js", False),
    ],
)
def test_static_asset_trees_skip_the_gate(path, gate_free):
    """Large unauthenticated downloads must not hold a place: a client that stops reading one would make every demo wait."""
    assert request_gate.bypasses_gate(_scope(path, None, method="GET")) is gate_free


def test_asset_trees_do_not_run_on_the_probe_pool():
    """Only the probes get the small pool of their own; a slow asset download must not take it."""
    assert request_gate.is_probe(_scope("/health", None, method="GET"))
    assert not request_gate.is_probe(_scope("/static-files/static/js/main.js", None, method="GET"))


@pytest.mark.asyncio
async def test_real_starlette_layers_hold_the_place_to_the_last_byte():
    """The gate between two ``BaseHTTPMiddleware`` layers, as in ``app.py``, around a streamed FastAPI route and Flask."""
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    release = asyncio.Event()
    first_chunk = asyncio.Event()
    seen_by_demo = []
    streams_open = [0]

    def flask_app(environ, start_response):
        seen_by_demo.append(streams_open[0])
        start_response("200 OK", [])
        return [b"ok"]

    app = FastAPI()

    @app.middleware("http")
    async def permission(request, call_next):  # stands in for the permission middleware
        return await call_next(request)

    @app.post(NATIVE)
    async def stream():
        async def body():
            streams_open[0] += 1
            try:
                yield b"first"
                first_chunk.set()
                await release.wait()
                yield b"last"
            finally:
                streams_open[0] -= 1

        return StreamingResponse(body())

    class Auth(BaseHTTPMiddleware):  # stands in for AuthMiddleware: puts the caller in the scope
        async def dispatch(self, request, call_next):
            return await call_next(request)

    app.add_middleware(RequestGateMiddleware)
    app.add_middleware(Auth)
    app.mount("/", AuthAwareWSGIMiddleware(flask_app))

    streaming = asyncio.ensure_future(_call(app, NATIVE, USER))
    await asyncio.wait_for(first_chunk.wait(), 5)
    demo = asyncio.ensure_future(_call(app, DEMO, ADMIN))
    try:
        await asyncio.sleep(0.2)
        assert not demo.done(), "demo generation ran while a streamed response was still being sent"
    finally:
        release.set()
        await asyncio.gather(streaming, demo, return_exceptions=True)
    assert streaming.result() == 200 and demo.result() == 200
    assert seen_by_demo == [0]


def test_gate_free_paths_are_exact():
    assert request_gate.bypasses_gate(_scope("/health", USER))
    assert not request_gate.bypasses_gate(_scope("/api/2.0/mlflow/experiments/health", USER))
    assert not request_gate.bypasses_gate(_scope("/healthz", USER))
    assert not request_gate.bypasses_gate(_scope("/health/anything", USER))


@pytest.mark.parametrize(
    "static_prefix, root_path, path, gate_free",
    [
        ("/sp", "", "/sp/health", True),
        ("/sp/", "", "/sp/version", True),
        ("", "/fwd", "/fwd/health/ready", True),
        ("/sp", "/fwd", "/fwd/sp/health", True),
        ("/sp", "", "/sp/api/2.0/mlflow/experiments/search", False),
        ("/sp", "", "/sp//health", False),
        ("/health", "", "/health/api/2.0/mlflow/experiments/search", False),
        ("", "/fwd", "/fwd/api/2.0/mlflow/health", False),
    ],
)
def test_gate_free_paths_under_a_static_or_forwarded_prefix(monkeypatch, static_prefix, root_path, path, gate_free):
    from mlflow_oidc_auth.hooks.route_policy import STATIC_PREFIX_ENV_VAR

    monkeypatch.setenv(STATIC_PREFIX_ENV_VAR, static_prefix)
    scope = _scope(path, USER)
    scope["root_path"] = root_path
    assert request_gate.bypasses_gate(scope) is gate_free


class TestGate:
    @pytest.mark.asyncio
    async def test_alone_waits_for_shared_and_times_out(self):
        gate = RequestGate()
        await gate.enter_shared()
        started = time.monotonic()
        assert await gate.acquire_alone(0.1) is False
        assert time.monotonic() - started >= 0.1
        gate.leave_shared()
        assert await gate.acquire_alone(0.1) is True
        gate.release_alone()

    @pytest.mark.asyncio
    async def test_a_timed_out_alone_registers_no_wait_it_will_not_await(self):
        gate = RequestGate()
        registrations = []
        original = gate._wait_for_change_locked

        def counting():
            registrations.append(1)
            return original()

        gate._wait_for_change_locked = counting
        await gate.enter_shared()
        assert await gate.acquire_alone(0) is False
        assert registrations == []
        assert await gate.acquire_alone(0.05) is False
        await asyncio.sleep(0)
        assert gate._waiters == []
        assert gate._alone_waiting == 0
        gate.leave_shared()

    @pytest.mark.asyncio
    async def test_shared_waits_while_alone_runs(self):
        gate = RequestGate()
        assert await gate.acquire_alone(1)
        shared = asyncio.ensure_future(gate.enter_shared())
        await asyncio.sleep(0.05)
        assert not shared.done()
        gate.release_alone()
        await asyncio.wait_for(shared, 2)
        gate.leave_shared()

    @pytest.mark.asyncio
    async def test_new_shared_waits_while_alone_waits(self):
        """A request that has to run alone is not starved by requests that keep arriving."""
        gate = RequestGate()
        await gate.enter_shared()
        alone = asyncio.ensure_future(gate.acquire_alone(5))
        await _until_async(lambda: gate._alone_waiting == 1)
        late = asyncio.ensure_future(gate.enter_shared())
        await asyncio.sleep(0.05)
        assert not late.done()
        gate.leave_shared()
        assert await asyncio.wait_for(alone, 2) is True
        assert not late.done()
        gate.release_alone()
        await asyncio.wait_for(late, 2)
        gate.leave_shared()

    @pytest.mark.asyncio
    async def test_a_cancelled_alone_waiter_lets_the_others_run(self):
        gate = RequestGate()
        await gate.enter_shared()
        alone = asyncio.ensure_future(gate.acquire_alone(5))
        await _until_async(lambda: gate._alone_waiting == 1)
        alone.cancel()
        with pytest.raises(asyncio.CancelledError):
            await alone
        assert gate._alone_waiting == 0
        await asyncio.wait_for(gate.enter_shared(), 1)

    @pytest.mark.asyncio
    async def test_waiting_does_not_poll(self):
        """Each waiter sleeps until the gate changes: hundreds of them cost no work while demo generation runs."""
        gate = RequestGate()
        registrations = []
        original = gate._wait_for_change_locked

        def counting():
            registrations.append(1)
            return original()

        gate._wait_for_change_locked = counting
        assert await gate.acquire_alone(1)
        waiters = [asyncio.ensure_future(gate.enter_shared()) for _ in range(200)]
        await asyncio.sleep(0.3)
        assert len(registrations) == 200
        gate.release_alone()
        await asyncio.wait_for(asyncio.gather(*waiters), 2)
        assert len(registrations) == 200
        for _ in waiters:
            gate.leave_shared()

    @pytest.mark.asyncio
    async def test_a_release_on_another_loop_wakes_this_one(self):
        gate = RequestGate()
        acquired, release = threading.Event(), threading.Event()

        def other_loop():
            async def hold():
                assert await gate.acquire_alone(1)
                acquired.set()
                while not release.is_set():
                    await asyncio.sleep(0.01)
                gate.release_alone()

            asyncio.run(hold())

        thread = threading.Thread(target=other_loop)
        thread.start()
        try:
            await _until_async(acquired.is_set)
            waiter = asyncio.ensure_future(gate.enter_shared())
            await asyncio.sleep(0.05)
            assert not waiter.done()
            release.set()
            await asyncio.wait_for(waiter, 2)
            gate.leave_shared()
        finally:
            release.set()
            thread.join(5)

    def test_a_closed_loop_does_not_keep_the_others_waiting(self):
        """A waiter left on a loop that has closed is skipped; the waiters on other loops still wake."""
        gate = RequestGate()
        held = asyncio.new_event_loop()
        assert held.run_until_complete(gate.acquire_alone(1))
        closed = asyncio.new_event_loop()

        async def register():
            with gate._lock:
                return gate._wait_for_change_locked()

        closed.run_until_complete(register())  # pending, then its loop goes away
        closed.close()
        live = asyncio.new_event_loop()
        try:

            async def wait_on_live():
                waiter = asyncio.ensure_future(gate.enter_shared())
                await asyncio.sleep(0.05)
                assert not waiter.done()
                gate.release_alone()
                await asyncio.wait_for(waiter, 2)
                gate.leave_shared()

            live.run_until_complete(wait_on_live())
        finally:
            live.close()
            held.close()

    @pytest.mark.asyncio
    async def test_cancelled_waiters_leave_the_list(self):
        gate = RequestGate()
        assert await gate.acquire_alone(1)
        waiters = [asyncio.ensure_future(gate.enter_shared()) for _ in range(50)]
        await asyncio.sleep(0.05)
        assert len(gate._waiters) == 50
        for waiter in waiters:
            waiter.cancel()
        await asyncio.gather(*waiters, return_exceptions=True)
        await asyncio.sleep(0)
        assert gate._waiters == []
        gate.release_alone()

    @pytest.mark.asyncio
    async def test_the_gate_works_on_more_than_one_event_loop(self):
        """Module-global and polled, it is not bound to the loop that first used it."""
        gate = RequestGate()

        def other_loop():
            async def use():
                assert await gate.acquire_alone(1)
                gate.release_alone()

            asyncio.run(use())

        thread = threading.Thread(target=other_loop)
        thread.start()
        thread.join(5)
        await gate.enter_shared()
        gate.leave_shared()


#: Every place MLflow (3.16 to 3.18) sets ``MLFLOW_WORKSPACE``, with why it cannot race a request.
KNOWN_WORKSPACE_VARIABLE_WRITERS = {
    ("demo/__init__.py", "generate_all_demos"): "runs alone, see RUN_ALONE_PATH_SUFFIXES",
    ("server/jobs/_job_subproc_entry.py", "_main"): "a job's own process",
    ("server/jobs/utils.py", "_exec_job"): "3.16/3.17: Huey task body, in the Huey consumer process",
    ("server/jobs/utils.py", "_workspace_contexts_for_recovery"): "3.16/3.17: job runner processes",
    ("genai/scorers/job.py", "_get_online_scoring_workspace_contexts"): "3.16/3.17: Huey periodic task, consumer process",
    ("store/tracking/sqlalchemy_workspace_store.py", "WorkspaceAwareSqlAlchemyStore._create_default_experiment"): (
        "only with a default workspace, where every request resolves its own and the variable is not read"
    ),
    ("utils/workspace_context.py", "WorkspaceContext.__enter__"): "the setter itself",
    ("utils/workspace_context.py", "WorkspaceContext.__exit__"): "the setter itself",
    ("utils/workspace_context.py", "set_workspace"): "the setter itself",
    ("tracking/request_auth/kubernetes_request_auth_provider.py", "KubernetesAuth.__call__"): "client side",
    ("cli/__init__.py", "gc"): "CLI",
}


def _names_variable(node):
    """Whether ``node`` spells the variable's name: ``"MLFLOW_WORKSPACE"`` or ``MLFLOW_WORKSPACE.name``."""
    return ast.unparse(node).strip("'\"") in ("MLFLOW_WORKSPACE", "MLFLOW_WORKSPACE.name")


def _is_environ(node):
    """Whether ``node`` is the process environment (``os.environ``, ``environ``), not a copy built for a subprocess."""
    return ast.unparse(node) in ("os.environ", "environ")


def _workspace_variable_writers(root):
    """(file, function) of each call in MLflow that sets ``MLFLOW_WORKSPACE``, in any spelling."""
    found = set()
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if "/tests/" in relative:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        scope = []

        class Visitor(ast.NodeVisitor):
            def _scoped(self, node):
                scope.append(node.name)
                self.generic_visit(node)
                scope.pop()

            visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scoped

            def _hit(self):
                found.add((relative, ".".join(scope) or "<module>"))

            def visit_Call(self, node):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                if name in ("WorkspaceContext", "putenv") or (name == "set_workspace" and (node.args or node.keywords)):
                    self._hit()
                if isinstance(func, ast.Attribute) and func.attr in ("set", "update", "setdefault"):
                    target = func.value
                    if getattr(target, "id", None) == "MLFLOW_WORKSPACE" or getattr(target, "attr", None) == "MLFLOW_WORKSPACE":
                        self._hit()
                    if _is_environ(target) and (
                        any(k.arg == "MLFLOW_WORKSPACE" for k in node.keywords)
                        or any(isinstance(a, ast.Dict) and any(_names_variable(k) for k in a.keys if k is not None) for a in node.args)
                        or (func.attr == "setdefault" and node.args and _names_variable(node.args[0]))
                    ):
                        self._hit()
                self.generic_visit(node)

            def visit_Assign(self, node):
                if any(isinstance(t, ast.Subscript) and _is_environ(t.value) and _names_variable(t.slice) for t in node.targets):
                    self._hit()
                self.generic_visit(node)

        Visitor().visit(tree)
    return found


def test_demo_generation_is_mlflow_s_only_request_time_writer_of_the_workspace_variable():
    """Fails when an MLflow upgrade sets ``MLFLOW_WORKSPACE`` in a new place.

    A new writer that runs while the server process serves requests has to run alone too (add its
    path to ``RUN_ALONE_PATH_SUFFIXES``), or the race of issue #482 is back; one that runs elsewhere
    goes into ``KNOWN_WORKSPACE_VARIABLE_WRITERS`` with the reason.
    """
    import mlflow
    from mlflow.server.handlers import get_demo_endpoints

    writers = _workspace_variable_writers(pathlib.Path(mlflow.__file__).parent)
    assert writers - KNOWN_WORKSPACE_VARIABLE_WRITERS.keys() == set()
    assert ("demo/__init__.py", "generate_all_demos") in writers
    assert [path for path, _, _ in get_demo_endpoints() if path.rstrip("/").endswith(request_gate.RUN_ALONE_PATH_SUFFIXES)]


def test_the_scan_sees_every_spelling(tmp_path):
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "writers.py").write_text(
        "import os\n"
        "from mlflow.utils import workspace_context\n"
        "def qualified():\n    with workspace_context.WorkspaceContext('w'):\n        pass\n"
        "def env_item():\n    os.environ['MLFLOW_WORKSPACE'] = 'w'\n"
        "def env_update():\n    os.environ.update({'MLFLOW_WORKSPACE': 'w'})\n"
        "def variable():\n    MLFLOW_WORKSPACE.set('w')\n"
        "def client():\n    mlflow.set_workspace('w')\n"
        "def env_name():\n    os.environ[MLFLOW_WORKSPACE.name] = 'w'\n"
        "def message():\n    raise ValueError('call mlflow.set_workspace() first')\n"
        "def subprocess_env():\n    env = {**os.environ}\n    env[MLFLOW_WORKSPACE.name] = 'w'\n"
        "def other_variable():\n    os.environ[MLFLOW_WORKSPACE_STORE_URI.name] = 'uri'\n"
    )
    found = {function for _, function in _workspace_variable_writers(tmp_path)}
    assert found == {"qualified", "env_item", "env_update", "variable", "client", "env_name"}
