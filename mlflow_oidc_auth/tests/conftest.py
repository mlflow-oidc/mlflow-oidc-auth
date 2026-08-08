"""Shared pytest configuration for the mlflow-oidc-auth test suite."""

import os

import dotenv

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
