from __future__ import annotations

import uuid
from urllib.parse import urljoin

import httpx
import pytest

pytest.importorskip("playwright.sync_api")

from .utils import create_experiment, get_experiment_id, user_login


@pytest.mark.integration
def test_list_scorers_for_experiment(base_url: str, ensure_server: None) -> None:
    """Ensure scorer listing endpoint is reachable and returns a list for a known experiment."""

    playwright_sync = pytest.importorskip("playwright.sync_api")

    with playwright_sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            cookies = user_login(page, "frank@example.com", url=base_url)
            assert cookies.jar, "Login failed for frank@example.com; no cookies returned"

            run_id = uuid.uuid4().hex[:8]
            experiment_name = f"scorers-exp-{run_id}"
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
        finally:
            context.close()
            browser.close()
