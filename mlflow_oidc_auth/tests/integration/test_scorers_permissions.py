from __future__ import annotations

import uuid
from urllib.parse import urljoin

import httpx
import pytest


@pytest.mark.integration
def test_list_scorers_for_experiment(base_url: str, ensure_server: None, user_cookies_factory) -> None:
    """Ensure scorer listing endpoint is reachable and returns a list for a known experiment."""
    cookies = user_cookies_factory("frank@example.com")
    assert cookies, "Failed to get cookies for frank@example.com"

    run_id = uuid.uuid4().hex[:8]
    experiment_name = f"scorers-exp-{run_id}"

    from .utils import create_experiment, get_experiment_id

    assert create_experiment(experiment_name, cookies, url=base_url), f"Failed to create {experiment_name}"

    experiment_id = get_experiment_id(experiment_name, cookies, url=base_url)
    assert experiment_id, f"Could not resolve experiment_id for {experiment_name}"

    api = urljoin(base_url, f"api/3.0/mlflow/permissions/scorers/{experiment_id}")
    resp = httpx.get(api, cookies=cookies, timeout=10.0)

    if resp.status_code == 404:
        pytest.skip("Scorer permission endpoints not available on this deployment")

    assert resp.status_code == 200, f"List scorers failed: {resp.status_code} {resp.text}"
    payload = resp.json()
    assert isinstance(payload, list), "List scorers response is not a list"
