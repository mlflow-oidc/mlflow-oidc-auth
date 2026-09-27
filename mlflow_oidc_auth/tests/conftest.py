"""Shared pytest configuration for the mlflow-oidc-auth test suite."""

import os
import sys

import dotenv
import pytest

# ``mlflow_oidc_auth.config`` calls ``load_dotenv()`` at import time, which walks up
# from the package directory and picks up whatever ".env" a developer keeps at the
# repository root - including inside a git worktree, where the search reaches the
# parent checkout. Those values then leak into the suite: a local
# ``MLFLOW_ENABLE_WORKSPACES=True``, for instance, makes MLflow's workspace-aware
# store reject every query that has no workspace context, failing a dozen router
# tests that pass in CI (where no ".env" exists). Neutralise the load so the suite
# always sees the CI environment.
#
# This runs at conftest import time, before any test module imports the config, so
# the ``from dotenv import load_dotenv`` there binds to the no-op. Tests that need
# specific configuration set it explicitly (``patch.dict(os.environ, ...)``).
dotenv.load_dotenv = lambda *args, **kwargs: False

# MLflow 3.14 put the filesystem tracking/registry backends into maintenance mode and
# raises unless callers opt in explicitly. Several router tests exercise real endpoints
# that fall back to the default './mlruns' store; they are testing our authorization
# layer, not MLflow's storage policy, so opt in for the suite.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

# Imported once, here, before any test runs — the reference identity `_config_module_guard`
# below checks every test against (#353).
import mlflow_oidc_auth.config as _config_module


@pytest.fixture(autouse=True)
def _config_module_guard():
    """Fail the test that leaves a second ``mlflow_oidc_auth.config`` in the process.

    A couple of tests delete ``mlflow_oidc_auth.config`` from ``sys.modules`` to force a
    fresh read of an env-driven setting, then restore the original module object on
    teardown (via ``monkeypatch.delitem(..., raising=False)`` or an equivalent
    ``addCleanup``). If a future test does the deletion without restoring it, every import
    of ``mlflow_oidc_auth.config`` from that point on resolves to a second, orphaned
    ``AppConfig`` instance, and which copy a given test sees becomes dependent on run order
    under pytest-randomly — see #353. This check is a single identity comparison, so it adds
    no meaningful overhead to the suite.
    """
    yield
    current = sys.modules.get("mlflow_oidc_auth.config")
    assert current is _config_module, (
        "mlflow_oidc_auth.config was replaced in sys.modules and not restored — use "
        "monkeypatch.delitem(sys.modules, 'mlflow_oidc_auth.config', raising=False), or "
        "restore the original module object explicitly, instead of a bare `del`/`pop`"
    )
