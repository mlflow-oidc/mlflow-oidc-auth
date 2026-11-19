"""Admin demo generation runs alone among the Flask requests of a process (issue #482).

MLflow's demo generation sets the process-wide ``MLFLOW_WORKSPACE`` while it runs, and MLflow serves a
header-less request with no workspace of its own from that variable. With Flask requests on several
threads, no other request may be decided or served while it is set.
"""

import ast
import asyncio
import pathlib
import re
import threading
import time

import pytest

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.middleware import auth_aware_wsgi_middleware as bridge
from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware, _FlaskRequestGate

DEMO = "/ajax-api/3.0/mlflow/demo/generate"
OTHER = "/api/2.0/mlflow/experiments/search"
ADMIN = AuthContext(username="admin@example.com", is_admin=True)
USER = AuthContext(username="bob@example.com", is_admin=False)


def _scope(path, auth_context):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
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
    """Wait for ``condition`` instead of sleeping a guessed time."""
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.005)


async def _until_async(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not reached"
        await asyncio.sleep(0.005)


async def _call(middleware, path, auth_context=USER):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await middleware(_scope(path, auth_context), receive, send)
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


class _RecordingApp:
    """A WSGI app that records how many requests were in flight while the demo request ran."""

    def __init__(self, hold=None):
        self.lock = threading.Lock()
        self.in_flight = 0
        self.seen_by_demo = []
        self.hold = hold

    def __call__(self, environ, start_response):
        with self.lock:
            self.in_flight += 1
        try:
            if environ["PATH_INFO"].endswith("/mlflow/demo/generate"):
                for _ in range(5):
                    with self.lock:
                        self.seen_by_demo.append(self.in_flight)
                    time.sleep(0.02)
            elif self.hold is not None:
                assert self.hold.wait(10)
            else:
                time.sleep(0.05)
        finally:
            with self.lock:
                self.in_flight -= 1
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]


@pytest.mark.asyncio
async def test_admin_demo_generation_runs_alone():
    app = _RecordingApp()
    middleware = AuthAwareWSGIMiddleware(app)
    calls = [_call(middleware, OTHER) for _ in range(3)] + [_call(middleware, DEMO, ADMIN)] + [_call(middleware, OTHER) for _ in range(3)]
    statuses = await asyncio.gather(*calls)
    assert statuses == [200] * 7
    assert app.seen_by_demo and set(app.seen_by_demo) == {1}


@pytest.mark.asyncio
async def test_a_non_admin_demo_request_does_not_hold_the_others():
    """Only an admin's request runs alone; anyone else's runs with the others (and the hooks refuse it)."""
    hold = threading.Event()
    app = _RecordingApp(hold=hold)
    middleware = AuthAwareWSGIMiddleware(app)
    long_request = asyncio.ensure_future(_call(middleware, OTHER))
    await _until_async(lambda: app.in_flight == 1)
    try:
        demo = asyncio.ensure_future(_call(middleware, DEMO, USER))
        done, _ = await asyncio.wait({demo}, timeout=2)
        assert demo in done, "a non-admin's demo request waited for the other requests"
        assert demo.result() == 200
        assert set(app.seen_by_demo) == {2}
    finally:
        # Let every request finish before the loop closes: a pool thread left sending to a closed
        # loop would block the process at exit.
        hold.set()
        await asyncio.gather(long_request, *([demo] if "demo" in locals() else []), return_exceptions=True)
    assert long_request.result() == 200


@pytest.mark.asyncio
async def test_demo_generation_is_refused_when_other_requests_do_not_finish(monkeypatch):
    monkeypatch.setattr(bridge, "RUN_ALONE_WAIT_SECONDS", 0.2)
    hold = threading.Event()
    app = _RecordingApp(hold=hold)
    middleware = AuthAwareWSGIMiddleware(app)
    stuck = asyncio.ensure_future(_call(middleware, OTHER))
    await _until_async(lambda: app.in_flight == 1)
    demo = asyncio.ensure_future(_call(middleware, DEMO, ADMIN))
    try:
        done, _ = await asyncio.wait({demo}, timeout=2)
        assert demo in done, "demo generation was not refused while another request held the gate"
        assert demo.result() == 503
        assert app.seen_by_demo == []
    finally:
        hold.set()
        await asyncio.gather(stuck, demo, return_exceptions=True)
    assert stuck.result() == 200
    # The gate is free again: requests run, and demo generation now runs alone.
    app.hold = None
    assert await asyncio.wait_for(asyncio.gather(_call(middleware, OTHER), _call(middleware, DEMO, ADMIN)), 5) == [200, 200]
    assert set(app.seen_by_demo) == {1}


@pytest.mark.parametrize("path", ["/prefix" + DEMO, DEMO + "/", "/api/3.0/mlflow/demo/generate"])
def test_run_alone_matches_any_prefix(path):
    assert bridge._runs_alone(_scope(path, ADMIN))


@pytest.mark.parametrize("auth_context", [USER, None, "admin"])
def test_only_an_admin_runs_alone(auth_context):
    assert not bridge._runs_alone(_scope(DEMO, auth_context))


def test_other_paths_do_not_run_alone():
    assert not bridge._runs_alone(_scope("/ajax-api/3.0/mlflow/demo/delete", ADMIN))
    assert not bridge._runs_alone(_scope(OTHER, ADMIN))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/version", "/health/"])
async def test_health_and_version_answer_while_demo_generation_runs(path):
    gate_held = threading.Event()
    release = threading.Event()

    class SlowDemoApp(_RecordingApp):
        def __call__(self, environ, start_response):
            if environ["PATH_INFO"].endswith("/mlflow/demo/generate"):
                gate_held.set()
                assert release.wait(10)
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

    middleware = AuthAwareWSGIMiddleware(SlowDemoApp())
    demo = asyncio.ensure_future(_call(middleware, DEMO, ADMIN))
    waiting = []
    probe = None
    try:
        await _until_async(gate_held.is_set)
        # Requests waiting for demo generation fill every other thread of the pool.
        waiting = [asyncio.ensure_future(_call(middleware, OTHER)) for _ in range(bridge._WSGI_EXECUTOR._max_workers + 2)]
        await _until_async(lambda: bridge._FLASK_REQUEST_GATE._alone)
        await asyncio.sleep(0.05)
        assert not any(task.done() for task in waiting)
        probe = asyncio.ensure_future(_call(middleware, path))
        done, _ = await asyncio.wait({probe}, timeout=2)
        assert probe in done, f"{path} waited for demo generation"
        assert probe.result() == 200
    finally:
        release.set()
        await asyncio.gather(demo, *waiting, *([probe] if probe else []), return_exceptions=True)
    assert all(task.result() == 200 for task in waiting)


def test_gate_free_paths_are_exact():
    assert bridge._bypasses_gate(_scope("/health", USER))
    assert not bridge._bypasses_gate(_scope("/api/2.0/mlflow/experiments/health", USER))
    assert not bridge._bypasses_gate(_scope("/healthz", USER))


@pytest.mark.parametrize(
    "static_prefix, root_path, path, gate_free",
    [
        ("/sp", "", "/sp/health", True),
        ("/sp/", "", "/sp/version", True),
        ("", "/fwd", "/fwd/health", True),
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
    assert bridge._bypasses_gate(scope) is gate_free


class TestGate:
    def test_alone_waits_for_shared_and_times_out(self):
        gate = _FlaskRequestGate()
        with gate.shared():
            started = time.monotonic()
            assert gate.acquire_alone(0.1) is False
            assert time.monotonic() - started >= 0.1
        assert gate.acquire_alone(0.1) is True
        gate.release_alone()

    def test_shared_waits_while_alone_runs(self):
        gate = _FlaskRequestGate()
        assert gate.acquire_alone(1)
        entered = threading.Event()

        def shared():
            with gate.shared():
                entered.set()

        thread = threading.Thread(target=shared)
        thread.start()
        assert not entered.wait(0.1)
        gate.release_alone()
        assert entered.wait(5)
        thread.join()

    def test_new_shared_waits_while_alone_waits(self):
        """A request that has to run alone is not starved by requests that keep arriving."""
        gate = _FlaskRequestGate()
        first = gate.shared()
        first.__enter__()
        result = {}
        waiter = threading.Thread(target=lambda: result.setdefault("alone", gate.acquire_alone(5)))
        waiter.start()
        _until(lambda: gate._alone_waiting == 1)
        entered = threading.Event()

        def late_request():
            with gate.shared():
                entered.set()

        late = threading.Thread(target=late_request)
        late.start()
        assert not entered.wait(0.1)
        first.__exit__(None, None, None)
        waiter.join(5)
        assert result["alone"] is True
        assert not entered.is_set()
        gate.release_alone()
        assert entered.wait(5)
        late.join()


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
    assert [path for path, _, _ in get_demo_endpoints() if path.rstrip("/").endswith(bridge.RUN_ALONE_PATH_SUFFIXES)]


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
