"""Shared pytest configuration for the mlflow-oidc-auth test suite."""

import os

# MLflow 3.14 put the filesystem tracking/registry backends into maintenance mode and
# raises unless callers opt in explicitly. Several router tests exercise real endpoints
# that fall back to the default './mlruns' store; they are testing our authorization
# layer, not MLflow's storage policy, so opt in for the suite.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
