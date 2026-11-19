"""Caches created on first use are created once, even when first uses overlap (WSGI_THREADS)."""

import threading
import time

import pytest

from mlflow_oidc_auth.cache import generation
from mlflow_oidc_auth.utils import bearer_identity_cache, grant_context, permissions, workspace_cache


def _race(get, monkeypatch, module):
    made = []

    def slow_backend(*args, **kwargs):
        time.sleep(0.02)
        backend = object()
        made.append(backend)
        return backend

    monkeypatch.setattr(module, "get_cache_backend", slow_backend)
    barrier = threading.Barrier(8)
    seen = []

    def first_use():
        barrier.wait()
        seen.append(get())

    threads = [threading.Thread(target=first_use) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert len(made) == 1
    assert seen == made * 8


@pytest.mark.parametrize(
    "module, attribute, getter",
    [
        (permissions, "_permission_cache", "_get_permission_cache"),
        (grant_context, "_section_cache", "_get_section_cache"),
        (workspace_cache, "_cache", "_get_cache"),
        (workspace_cache, "_denial_cache", "_get_denial_cache"),
        (bearer_identity_cache, "_cache", "bearer_identity_cache"),
    ],
)
def test_module_cache_is_created_once(monkeypatch, module, attribute, getter):
    monkeypatch.setattr(module, attribute, None)
    _race(getattr(module, getter), monkeypatch, module)


def test_generation_guard_backend_is_created_once(monkeypatch):
    guard = generation.GenerationGuard("test_generation", lambda: 30)
    _race(guard._backend, monkeypatch, generation)
