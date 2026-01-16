from __future__ import annotations

import uuid

import pytest

from .users import get_mlflow_users
from .utils import create_experiment, create_model, create_prompt


@pytest.mark.integration
def test_populate_users_can_create_resources(
    base_url: str,
    ensure_server: None,
    user_cookies_factory,
) -> None:
    """Verify each user can authenticate via OIDC UI and create personal resources."""
    run_id = uuid.uuid4().hex[:8]

    for email in get_mlflow_users():
        cookies = user_cookies_factory(email)
        assert cookies, f"Failed to get cookies for {email}"

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
