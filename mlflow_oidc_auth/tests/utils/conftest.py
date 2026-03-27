"""Pytest configuration and fixtures for utils tests."""

import pytest

import mlflow_oidc_auth.utils.permissions as _permissions_mod


@pytest.fixture(autouse=True)
def _flush_permission_cache():
    """Flush the permission cache before each test to prevent cross-test leakage."""
    _permissions_mod._permission_cache = None
    yield
    _permissions_mod._permission_cache = None
