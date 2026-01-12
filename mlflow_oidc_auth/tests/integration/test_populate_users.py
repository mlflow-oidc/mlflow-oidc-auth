from __future__ import annotations

import uuid

import pytest

pytest.importorskip("playwright.sync_api")

from .users import list_users
from .utils import create_experiment, create_model, create_prompt, user_login


@pytest.mark.integration
def test_populate_users_can_create_resources(base_url: str, ensure_server: None) -> None:
    """Verify each user can authenticate via OIDC UI and create personal resources."""

    playwright_sync = pytest.importorskip("playwright.sync_api")
    run_id = uuid.uuid4().hex[:8]

    with playwright_sync.sync_playwright() as playwright:
        for email in list_users():
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                cookies = user_login(page, email, url=base_url)
                assert cookies.jar, f"Login failed for {email}; no cookies returned"

                experiment_name = f"{email}-personal-experiment-{run_id}"
                model_name = f"{email}-personal-model-{run_id}"
                prompt_name = f"{email}-personal-prompt-{run_id}"

                assert create_experiment(experiment_name, cookies, url=base_url), f"Failed to create {experiment_name}"
                assert create_model(model_name, cookies, url=base_url), f"Failed to create {model_name}"
                assert create_prompt(
                    prompt_name,
                    f"Integration prompt for {email} {run_id}",
                    cookies,
                    url=base_url,
                    commit_message="integration prompt creation",
                    source="integration-test",
                ), f"Failed to create {prompt_name}"
            finally:
                context.close()
                browser.close()

