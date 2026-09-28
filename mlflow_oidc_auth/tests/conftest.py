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
import mlflow_oidc_auth
import mlflow_oidc_auth.config as _config_module
import mlflow_oidc_auth.oauth as _oauth_module

from mlflow_oidc_auth.tests import _sharding


# Opt-in CI sharding (``--shard-count``/``--shard-index``); a no-op without those options.
def pytest_addoption(parser: pytest.Parser) -> None:
    _sharding.add_shard_options(parser)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list) -> None:
    # trylast: select after marker deselection (-m) has already run.
    _sharding.select_shard(session, config, items)


@pytest.fixture(autouse=True)
def _config_module_guard():
    """Fail the test that leaves a second ``mlflow_oidc_auth.config``/``oauth`` in the process.

    A couple of tests delete ``mlflow_oidc_auth.config`` (and, in ``test_oauth.py``,
    ``mlflow_oidc_auth.oauth``) from ``sys.modules`` to force a fresh read of an env-driven
    setting, then restore the original module object on teardown (via
    ``monkeypatch.delitem(..., raising=False)`` or an equivalent ``addCleanup``). If a future
    test does the deletion without restoring it, every import of the module from that point on
    resolves to a second, orphaned instance, and which copy a given test sees becomes
    dependent on run order under pytest-randomly — see #353.

    Restoring the ``sys.modules`` entry alone is not sufficient: reimporting a deleted
    submodule also makes the import system ``setattr`` the parent package (e.g.
    ``mlflow_oidc_auth.config = <new module>``), so code that reaches the module via the
    package attribute (``from mlflow_oidc_auth import oauth as oauth_mod``) would still see
    the duplicate even after ``sys.modules`` was put back. Check both. This is four identity
    comparisons, so it adds no meaningful overhead to the suite.
    """
    yield
    assert sys.modules.get("mlflow_oidc_auth.config") is _config_module, (
        "mlflow_oidc_auth.config was replaced in sys.modules and not restored — use "
        "monkeypatch.delitem(sys.modules, 'mlflow_oidc_auth.config', raising=False), or "
        "restore the original module object explicitly, instead of a bare `del`/`pop`"
    )
    assert mlflow_oidc_auth.config is _config_module, (
        "mlflow_oidc_auth.config (the package attribute) was left pointing at a duplicate "
        "module — restoring sys.modules is not enough; also restore the attribute the import "
        "system sets on the parent package (e.g. monkeypatch.setattr(mlflow_oidc_auth, "
        "'config', <original>))"
    )
    assert (
        sys.modules.get("mlflow_oidc_auth.oauth") is _oauth_module
    ), "mlflow_oidc_auth.oauth was replaced in sys.modules and not restored — restore the original module object instead of a bare `del`/`pop`"
    assert mlflow_oidc_auth.oauth is _oauth_module, (
        "mlflow_oidc_auth.oauth (the package attribute) was left pointing at a duplicate "
        "module — restoring sys.modules is not enough; also restore the attribute the import "
        "system sets on the parent package"
    )
