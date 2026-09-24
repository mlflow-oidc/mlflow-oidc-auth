"""Gateway budget reads and demo-data generation are admin-only.

Budget policies and their spend windows describe every workspace's gateway usage, and
demo generation creates (and hard-deletes) a shared experiment.
Driven through the real hook and permission store (see ``authz_harness``).
"""

import pytest

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    MANAGER,
    PREFIXES,
    BaseFakeTrackingStore,
    allowed,
    denied,
    hook,
    install_permission_store,
)


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    yield install_permission_store(tmp_path, monkeypatch, BaseFakeTrackingStore())
    flush_permission_cache()


ROUTES = [(f"{prefix}/3.0/mlflow/gateway/budgets/{action}", "GET") for prefix in PREFIXES for action in ("get", "list", "windows")] + [
    ("/ajax-api/3.0/mlflow/demo/generate", "POST"),
    ("/ajax-api/3.0/mlflow/demo/delete", "POST"),
]


@pytest.mark.parametrize("path, method", ROUTES)
def test_refused_to_a_non_admin(path, method):
    body = {} if method == "POST" else None
    assert denied(hook(path, method, MANAGER, body=body))


@pytest.mark.parametrize("path, method", ROUTES)
def test_served_to_an_admin(path, method):
    body = {} if method == "POST" else None
    assert allowed(hook(path, method, ADMIN, body=body))
