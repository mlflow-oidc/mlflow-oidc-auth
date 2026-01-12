from __future__ import annotations

import uuid

import pytest

from .users import list_experiments, list_models, list_prompts
from .utils import (
    create_experiment,
    create_model,
    create_prompt,
    register_sample_scorers,
    set_group_experiment_permission,
)


@pytest.mark.integration
def test_admin_can_seed_reference_data(
    base_url: str,
    ensure_server: None,
    admin_cookies,
) -> None:
    """Ensure the admin can authenticate and seed baseline experiments, models, and prompts."""
    run_id = uuid.uuid4().hex[:8]

    experiment_names = [f"{name}-{run_id}" for name in list_experiments()]
    model_names = [f"{name}-{run_id}" for name in list_models()]
    prompt_names = [f"{name}-{run_id}" for name in list_prompts()]

    cookies = admin_cookies
    assert cookies, "Failed to get admin cookies"

    for experiment in experiment_names:
        assert create_experiment(experiment, cookies, url=base_url), f"Failed to create experiment {experiment}"
        registered, missing_endpoint = register_sample_scorers(
            experiment,
            cookies,
            url=base_url,
        )
        if missing_endpoint:
            pytest.skip("Scorer registration endpoint not available on this deployment")
        assert registered, f"Failed to register scorers for {experiment}"

    for model in model_names:
        assert create_model(model, cookies, url=base_url), f"Failed to create model {model}"

    for prompt in prompt_names:
        assert create_prompt(
            prompt,
            f"Integration prompt text for {prompt}",
            cookies,
            url=base_url,
            commit_message="integration prompt creation",
            source="integration-test",
        ), f"Failed to create prompt {prompt}"

    for experiment in experiment_names:
        for group, permission in (
            ("experiments-no-access", "NO_PERMISSIONS"),
            ("experiments-reader", "READ"),
            ("experiments-editor", "EDIT"),
            ("experiments-manager", "MANAGE"),
        ):
            ok, message = set_group_experiment_permission(
                experiment,
                group,
                permission,
                cookies,
                url=base_url,
            )
            if not ok and "404" in message:
                pytest.skip(f"Group permission endpoint not available: {message}")
            assert ok, f"Failed to set {permission} for {experiment}: {message}"
