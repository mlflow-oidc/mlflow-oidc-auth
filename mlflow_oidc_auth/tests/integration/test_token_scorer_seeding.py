from __future__ import annotations

import uuid

import pytest

from .utils import (
    create_access_token_for_user,
    create_service_account,
    seed_scorers_with_tracking_token,
)


@pytest.mark.integration
def test_service_account_token_can_seed_scorers(
    base_url: str,
    ensure_server: None,
    admin_cookies,
) -> None:
    """Service account token allows MLflow runs to log scorer metrics."""
    run_suffix = uuid.uuid4().hex[:8]

    username = f"svc-scorer-{run_suffix}@example.com"
    display_name = f"Svc Scorer {run_suffix}"
    experiment_name = f"token-scorer-exp-{run_suffix}"

    created, message = create_service_account(username, display_name, admin_cookies, base_url=base_url)
    assert created, f"Failed to create service account {username}: {message}"

    token_ok, token_or_reason = create_access_token_for_user(username, admin_cookies, base_url=base_url)
    if not token_ok and "unavailable" in token_or_reason:
        pytest.skip("Access token endpoint not available on this deployment")
    assert token_ok, f"Failed to create access token for {username}: {token_or_reason}"
    token = token_or_reason

    run_id, metrics = seed_scorers_with_tracking_token(experiment_name, token, base_url=base_url, username=username)
    assert run_id, "MLflow run id missing after scorer seeding"
    assert metrics, "No metrics logged during scorer seeding"

    for scorer_key in ("scorer.response_length", "scorer.contains_hello"):
        assert scorer_key in metrics, f"Missing scorer metric {scorer_key}"
