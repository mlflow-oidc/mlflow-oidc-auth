from __future__ import annotations

import uuid

import pytest

pytest.importorskip("playwright.sync_api")

from .utils import (
    create_access_token_for_user,
    create_service_account,
    seed_scorers_with_tracking_token,
    user_login,
)


@pytest.mark.integration
def test_service_account_token_can_seed_scorers(base_url: str, ensure_server: None) -> None:
    """Service account token allows MLflow runs to log scorer metrics."""

    playwright_sync = pytest.importorskip("playwright.sync_api")
    run_suffix = uuid.uuid4().hex[:8]

    username = f"svc-scorer-{run_suffix}@example.com"
    display_name = f"Svc Scorer {run_suffix}"
    experiment_name = f"token-scorer-exp-{run_suffix}"

    token: str

    with playwright_sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            cookies = user_login(page, "frank@example.com", url=base_url)
            assert cookies.jar, "Login failed for frank@example.com; no cookies returned"

            created, message = create_service_account(username, display_name, cookies, base_url=base_url)
            assert created, f"Failed to create service account {username}: {message}"

            token_ok, token_or_reason = create_access_token_for_user(username, cookies, base_url=base_url)
            if not token_ok and "unavailable" in token_or_reason:
                pytest.skip("Access token endpoint not available on this deployment")
            assert token_ok, f"Failed to create access token for {username}: {token_or_reason}"
            token = token_or_reason  # type: ignore[assignment]
        finally:
            context.close()
            browser.close()

    run_id, metrics = seed_scorers_with_tracking_token(experiment_name, token, base_url=base_url)
    assert run_id, "MLflow run id missing after scorer seeding"
    assert metrics, "No metrics logged during scorer seeding"

    for scorer_key in ("scorer.response_length", "scorer.contains_hello"):
        assert scorer_key in metrics, f"Missing scorer metric {scorer_key}"
