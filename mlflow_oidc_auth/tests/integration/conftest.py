from __future__ import annotations

import os
from urllib.parse import urljoin

import httpx
import pytest


def _should_require_server() -> bool:
    """Return True when the test run should fail instead of skip if the server is unreachable."""

    return os.environ.get("MLFLOW_OIDC_E2E_REQUIRE", "0").lower() in {"1", "true", "t", "yes", "y"}


@pytest.fixture(scope="session")
def base_url() -> str:
    """Normalized base URL for the running mlflow-oidc-auth server."""

    url = os.environ.get("MLFLOW_OIDC_E2E_BASE_URL", "http://localhost:8080/")
    return url if url.endswith("/") else f"{url}/"


@pytest.fixture(scope="session")
def ensure_server(base_url: str) -> None:
    """Skip (or fail) the session if the target server health check is not reachable."""

    require = _should_require_server()
    try:
        response = httpx.get(urljoin(base_url, "health/live"), timeout=5.0)
    except Exception as exc:  # pragma: no cover - network dependent
        message = f"E2E server not reachable at {base_url}: {exc}"
        if require:
            pytest.fail(message)
        pytest.skip(message)

    if response.status_code != 200:
        message = f"E2E server health check failed: {response.status_code} {response.text}"
        if require:
            pytest.fail(message)
        pytest.skip(message)
