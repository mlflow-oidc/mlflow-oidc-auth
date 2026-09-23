"""Fixtures for the end-to-end identity suite: a real Keycloak and the real app as a server.

Nothing here is mocked. Keycloak runs the ``mlflow-e2e`` realm from
``scripts/e2e/keycloak/realm-mlflow-e2e.json``; the plugin runs as ``mlflow server --app-name
oidc-auth`` in a subprocess on a free loopback port, configured through the same environment
variables an operator would set. See "End-to-end identity tests" in ``docs/development.md``.

Environment:

``MLFLOW_OIDC_E2E_KEYCLOAK_URL``
    Keycloak over http, used for OIDC and the admin API. Default ``http://localhost:8080``.
``MLFLOW_OIDC_E2E_KEYCLOAK_HTTPS_URL``
    Keycloak over https, used for SAML: the plugin refuses a non-https IdP SSO/SLO URL. Default
    ``https://localhost:8443``. Its certificate is the runtime-generated one Keycloak was started
    with; pass it as ``MLFLOW_OIDC_E2E_KEYCLOAK_CA`` to verify it, otherwise verification is off
    for this loopback IdP only.
``MLFLOW_OIDC_E2E_REQUIRE``
    ``1`` (CI) makes an unreachable Keycloak a failure. Unset, the suite skips.
``MLFLOW_OIDC_E2E_DB_URI``
    A PostgreSQL URI with CREATEDB rights. A fresh database is created in it per run (and dropped
    after), so the refresh guard's row lock is exercised for real. Unset: a temp SQLite file.
``MLFLOW_OIDC_E2E_WORKERS``
    uvicorn workers. Default 1 on SQLite (whose refresh guard is process-wide only, by design)
    and 4 on PostgreSQL, so concurrent refreshes race across processes.
``MLFLOW_OIDC_E2E_LOG_DIR``
    Where the app server log is written; CI uploads it on failure. Default: a pytest temp dir.
"""

from __future__ import annotations

import os
import secrets
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Iterator, List

import httpx
import pytest

from mlflow_oidc_auth.tests.e2e.harness import (
    DEFAULT_KEYCLOAK_HTTPS_URL,
    DEFAULT_KEYCLOAK_URL,
    REALM,
    AppServer,
    AuthDatabase,
    Keycloak,
    free_port,
    server_env,
    truthy,
    keycloak_verify,
)


def _unavailable(message: str) -> None:
    """Fail under ``MLFLOW_OIDC_E2E_REQUIRE`` (CI), skip otherwise."""
    if truthy(os.environ.get("MLFLOW_OIDC_E2E_REQUIRE")):
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


@pytest.fixture(scope="session")
def keycloak() -> Iterator[Keycloak]:
    url = os.environ.get("MLFLOW_OIDC_E2E_KEYCLOAK_URL", DEFAULT_KEYCLOAK_URL)
    https_url = os.environ.get("MLFLOW_OIDC_E2E_KEYCLOAK_HTTPS_URL", DEFAULT_KEYCLOAK_HTTPS_URL)
    try:
        response = httpx.get(f"{url.rstrip('/')}/realms/{REALM}", timeout=5.0)
        response.raise_for_status()
        httpx.get(f"{https_url.rstrip('/')}/realms/{REALM}", timeout=5.0, verify=keycloak_verify()).raise_for_status()
    except Exception as exc:
        _unavailable(
            f"Keycloak realm '{REALM}' is not reachable at {url} / {https_url} ({type(exc).__name__}: {exc}). "
            "Start Keycloak with scripts/e2e/keycloak/realm-mlflow-e2e.json imported — see docs/development.md, "
            '"End-to-end identity tests".'
        )
    kc = Keycloak(
        url,
        https_url,
        os.environ.get("MLFLOW_OIDC_E2E_KEYCLOAK_ADMIN", "admin"),
        os.environ.get("MLFLOW_OIDC_E2E_KEYCLOAK_ADMIN_PASSWORD", "admin"),
    )
    yield kc
    kc._http.close()


@pytest.fixture(scope="session")
def auth_db(tmp_path_factory) -> Iterator[AuthDatabase]:
    base = os.environ.get("MLFLOW_OIDC_E2E_DB_URI")
    if not base:
        path = tmp_path_factory.mktemp("authdb") / "auth.db"
        yield AuthDatabase(uri=f"sqlite:///{path}", dialect="sqlite")
        return

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(base)
    assert url.get_backend_name() == "postgresql", "MLFLOW_OIDC_E2E_DB_URI must be a PostgreSQL URI"
    name = f"mlflow_oidc_e2e_{uuid.uuid4().hex[:10]}"
    server = create_engine(url, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))

    def drop() -> None:
        with server.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        server.dispose()

    database = AuthDatabase(uri=url.set(database=name).render_as_string(hide_password=False), dialect="postgresql", _drop=drop)
    try:
        yield database
    finally:
        drop()


def _run(cmd: List[str], env: Dict[str, str], cwd: Path) -> None:
    result = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        pytest.fail(f"{' '.join(cmd[:4])} failed ({result.returncode}):\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}", pytrace=False)


@pytest.fixture(scope="session")
def app_server(keycloak: Keycloak, auth_db: AuthDatabase, tmp_path_factory) -> Iterator[AppServer]:
    workdir = tmp_path_factory.mktemp("app")
    log_dir = Path(os.environ.get("MLFLOW_OIDC_E2E_LOG_DIR") or workdir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app-server.log"

    port = free_port()
    app_url = f"http://127.0.0.1:{port}"
    keycloak.point_clients_at(app_url)

    secret_key = secrets.token_hex(32)
    env = server_env(app_url=app_url, secret_key=secret_key, db_uri=auth_db.uri, keycloak=keycloak)
    default_workers = "1" if auth_db.dialect == "sqlite" else "4"
    workers = int(os.environ.get("MLFLOW_OIDC_E2E_WORKERS") or default_workers)

    # Migrate once, up front. Every worker migrates lazily on its first request otherwise, and
    # several racing to create the same tables on a fresh PostgreSQL database is a startup flake
    # this suite is not about.
    _run(
        [
            sys.executable,
            "-c",
            "import sys; from sqlalchemy import create_engine; from mlflow_oidc_auth.db.utils import migrate_if_needed; "
            + "migrate_if_needed(create_engine(sys.argv[1]), 'head')",
            auth_db.uri,
        ],
        env,
        workdir,
    )

    cmd = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--app-name",
        "oidc-auth",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workers",
        str(workers),
        "--backend-store-uri",
        f"sqlite:///{workdir / 'mlflow.db'}",
        "--default-artifact-root",
        str(workdir / "artifacts"),
    ]
    log_file = open(log_path, "wb")
    process = subprocess.Popen(cmd, env=env, cwd=workdir, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
    server = AppServer(url=app_url, log_path=log_path, secret_key=secret_key, db=auth_db, workers=workers, process=process)

    try:
        deadline = time.monotonic() + 120
        while True:
            if process.poll() is not None:
                pytest.fail(f"app server exited with {process.returncode} during startup; log tail:\n{server.tail()}", pytrace=False)
            try:
                if httpx.get(f"{app_url}/health", timeout=2.0).status_code == 200:
                    break
            except httpx.HTTPError:
                pass  # not up yet: keep polling until the deadline below
            if time.monotonic() > deadline:
                pytest.fail(f"app server did not answer /health within 120 s; log tail:\n{server.tail()}", pytrace=False)
            time.sleep(0.5)
        yield server
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        log_file.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach the app server's log tail to every failing e2e test."""
    outcome = yield
    report = outcome.get_result()
    if report.failed and "app_server" in getattr(item, "fixturenames", ()):
        server = item.funcargs.get("app_server") if hasattr(item, "funcargs") else None
        if isinstance(server, AppServer):
            report.sections.append(("app server log (tail)", server.tail()))
