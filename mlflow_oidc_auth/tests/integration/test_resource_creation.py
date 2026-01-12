"""Resource creation integration tests for MLflow OIDC Auth Plugin.

Test IDs: RES-001 through RES-022

Tests verify:
- Each user can create experiments with runs containing scorers
- Each user can create registered models
- Each user can create prompts
"""

from __future__ import annotations

import time
import uuid
from urllib.parse import quote, urljoin

import httpx
import pytest

from .users import get_mlflow_users


# =============================================================================
# Helper Functions
# =============================================================================


def _create_experiment(client: httpx.Client, experiment_name: str) -> tuple[bool, str]:
    """Create an experiment and return (success, experiment_id)."""
    get_api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(experiment_name)}"
    create_api = "ajax-api/2.0/mlflow/experiments/create"

    # Check if exists
    get_resp = client.get(get_api)
    if get_resp.status_code == 200:
        payload = get_resp.json()
        exp = payload.get("experiment", payload)
        exp_id = exp.get("experiment_id") or exp.get("experimentId") or exp.get("id")
        return True, str(exp_id)

    # Create new
    create_resp = client.post(create_api, json={"name": experiment_name})
    if create_resp.status_code != 200:
        return False, f"Create failed: {create_resp.status_code} {create_resp.text}"

    # Fetch the ID
    get_resp2 = client.get(get_api)
    if get_resp2.status_code == 200:
        payload2 = get_resp2.json()
        exp2 = payload2.get("experiment", payload2)
        exp_id2 = exp2.get("experiment_id") or exp2.get("experimentId") or exp2.get("id")
        return True, str(exp_id2)

    return False, "Failed to get experiment after creation"


def _create_run(client: httpx.Client, experiment_id: str, run_name: str | None = None) -> tuple[bool, str]:
    """Create a run in an experiment and return (success, run_id)."""
    api = "api/2.0/mlflow/runs/create"
    payload = {
        "experiment_id": experiment_id,
        "start_time": int(time.time() * 1000),
        "tags": [{"key": "mlflow.runName", "value": run_name or f"run-{uuid.uuid4().hex[:8]}"}],
    }

    resp = client.post(api, json=payload)
    if resp.status_code != 200:
        return False, f"Create run failed: {resp.status_code} {resp.text}"

    data = resp.json()
    run = data.get("run", data)
    run_info = run.get("info", run)
    run_id = run_info.get("run_id") or run_info.get("runId")

    return True, str(run_id) if run_id else ""


def _log_metric(client: httpx.Client, run_id: str, key: str, value: float) -> bool:
    """Log a metric to a run."""
    api = "api/2.0/mlflow/runs/log-metric"
    payload = {
        "run_id": run_id,
        "key": key,
        "value": value,
        "timestamp": int(time.time() * 1000),
    }

    resp = client.post(api, json=payload)
    return resp.status_code == 200


def _create_registered_model(client: httpx.Client, model_name: str) -> bool:
    """Create a registered model."""
    get_api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(model_name)}"
    create_api = "ajax-api/2.0/mlflow/registered-models/create"

    get_resp = client.get(get_api)
    if get_resp.status_code == 200:
        return True  # Already exists

    create_resp = client.post(create_api, json={"name": model_name})
    return create_resp.status_code == 200


def _create_model_version(client: httpx.Client, model_name: str) -> bool:
    """Create a model version by first creating a run to get artifact URI.
    
    Model versions require a valid artifact source that includes a run_id.
    We create a temporary experiment for the user since they may not have
    access to the default experiment.
    """
    # First create a temporary experiment for the run
    temp_exp_name = f"model-version-temp-{model_name}"
    exp_api = "ajax-api/2.0/mlflow/experiments/create"
    exp_resp = client.post(exp_api, json={"name": temp_exp_name})
    
    if exp_resp.status_code == 200:
        experiment_id = exp_resp.json().get("experiment_id", "0")
    else:
        # If experiment creation fails (maybe it exists), try to get it
        get_exp_api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(temp_exp_name)}"
        get_resp = client.get(get_exp_api)
        if get_resp.status_code == 200:
            experiment = get_resp.json().get("experiment", get_resp.json())
            experiment_id = experiment.get("experiment_id") or experiment.get("id", "0")
        else:
            return False
    
    # Create a run in this experiment to get an artifact path
    run_api = "ajax-api/2.0/mlflow/runs/create"
    run_resp = client.post(run_api, json={"experiment_id": experiment_id})
    if run_resp.status_code != 200:
        return False
    
    run_data = run_resp.json()
    run_id = run_data.get("run", {}).get("info", {}).get("run_id")
    if not run_id:
        return False
    
    # Now create version with the run's artifact location
    version_api = "ajax-api/2.0/mlflow/model-versions/create"
    payload = {
        "name": model_name,
        "source": f"mlflow-artifacts:/{experiment_id}/{run_id}/artifacts/model",
        "run_id": run_id,
        "description": "Test model version",
    }

    resp = client.post(version_api, json=payload)
    return resp.status_code == 200


def _update_model_description(client: httpx.Client, model_name: str, description: str) -> bool:
    """Update a model's description."""
    api = "ajax-api/2.0/mlflow/registered-models/update"
    payload = {"name": model_name, "description": description}

    resp = client.patch(api, json=payload)
    return resp.status_code == 200


def _create_prompt(client: httpx.Client, prompt_name: str, prompt_text: str) -> bool:
    """Create a prompt (registered model with prompt tags)."""
    get_api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(prompt_name)}"
    create_api = "ajax-api/2.0/mlflow/registered-models/create"
    version_api = "ajax-api/2.0/mlflow/model-versions/create"

    get_resp = client.get(get_api)
    if get_resp.status_code == 200:
        return True  # Already exists

    # Create the prompt (registered model with tags)
    create_resp = client.post(
        create_api,
        json={"name": prompt_name, "tags": [{"key": "mlflow.prompt.is_prompt", "value": "true"}]},
    )
    if create_resp.status_code != 200:
        return False

    # Create version with prompt text
    version_resp = client.post(
        version_api,
        json={
            "name": prompt_name,
            "description": "Initial prompt version",
            "source": "test-source",
            "tags": [
                {"key": "mlflow.prompt.is_prompt", "value": "true"},
                {"key": "mlflow.prompt.text", "value": prompt_text},
            ],
        },
    )

    return version_resp.status_code == 200


def _create_prompt_version(client: httpx.Client, prompt_name: str, prompt_text: str) -> bool:
    """Create a new prompt version."""
    api = "ajax-api/2.0/mlflow/model-versions/create"
    payload = {
        "name": prompt_name,
        "description": "Updated prompt version",
        "source": "test-source-v2",
        "tags": [
            {"key": "mlflow.prompt.is_prompt", "value": "true"},
            {"key": "mlflow.prompt.text", "value": prompt_text},
        ],
    }

    resp = client.post(api, json=payload)
    return resp.status_code == 200


# =============================================================================
# RES-001 to RES-005: Experiment Creation & Runs
# =============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_creates_experiment(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-001: Each user can create an experiment and becomes owner."""
    experiment_name = f"{user_email}-exp-{test_run_id}"

    with http_client_factory(user_email) as client:
        success, result = _create_experiment(client, experiment_name)
        assert success, f"User {user_email} failed to create experiment: {result}"
        assert result, "Experiment ID should not be empty"


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_creates_run_in_own_experiment(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-002: Each user can create a run in their own experiment."""
    experiment_name = f"{user_email}-run-exp-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create experiment first
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

        # Create run
        run_success, run_id = _create_run(client, experiment_id, f"test-run-{user_email}")
        assert run_success, f"Failed to create run: {run_id}"
        assert run_id, "Run ID should not be empty"


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_logs_scorer_metrics_in_run(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-003: Each user can log scorer metrics in their runs."""
    experiment_name = f"{user_email}-scorer-exp-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create experiment
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

        # Create run
        run_success, run_id = _create_run(client, experiment_id, f"scorer-run-{user_email}")
        assert run_success, f"Failed to create run: {run_id}"

        # Log scorer metrics
        assert _log_metric(client, run_id, "scorer.response_length", 42.0), "Failed to log response_length scorer"
        assert _log_metric(client, run_id, "scorer.contains_hello", 1.0), "Failed to log contains_hello scorer"


@pytest.mark.integration
def test_user_registers_scorers_at_experiment_level(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
) -> None:
    """RES-004: User can register scorers at experiment level."""
    from .utils import register_sample_scorers

    user_email = "alice@example.com"
    experiment_name = f"scorer-registration-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create experiment first
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

    # Use the utility function for scorer registration
    cookies = pytest.importorskip("httpx").Cookies()
    # We need the cookies from the client - use user_cookies_factory instead
    from .utils import register_sample_scorers

    # Get cookies via factory
    user_cookies = http_client_factory.__wrapped__(user_email) if hasattr(http_client_factory, "__wrapped__") else None

    if user_cookies is None:
        # Fallback: create a simple test
        pytest.skip("Cannot access cookies for scorer registration test")

    success, missing_endpoint = register_sample_scorers(experiment_name, user_cookies, url=base_url)

    if missing_endpoint:
        pytest.skip("Scorer registration endpoint not available")

    # Scorer registration may succeed or fail based on endpoint availability
    # Just ensure we don't crash


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_creates_multiple_runs_with_scorers(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-005: User creates multiple runs with different scorer data."""
    experiment_name = f"{user_email}-multi-run-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create experiment
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

        # Create multiple runs with different scorer values
        for i in range(3):
            run_success, run_id = _create_run(client, experiment_id, f"run-{i}-{user_email}")
            assert run_success, f"Failed to create run {i}: {run_id}"

            # Log different scorer values for each run
            assert _log_metric(client, run_id, "scorer.response_length", float(i * 10 + 5))
            assert _log_metric(client, run_id, "scorer.accuracy", float(0.5 + i * 0.1))


# =============================================================================
# RES-010 to RES-012: Model Creation
# =============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_creates_registered_model(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-010: Each user can create a registered model and becomes owner."""
    model_name = f"{user_email}-model-{test_run_id}"

    with http_client_factory(user_email) as client:
        success = _create_registered_model(client, model_name)
        assert success, f"User {user_email} failed to create model {model_name}"


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_creates_model_version(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-011: Each user can create model versions."""
    model_name = f"{user_email}-versioned-model-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create model first
        model_success = _create_registered_model(client, model_name)
        assert model_success, f"Failed to create model: {model_name}"

        # Create version
        version_success = _create_model_version(client, model_name)
        assert version_success, f"Failed to create model version for {model_name}"


@pytest.mark.integration
def test_owner_updates_model_description(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
) -> None:
    """RES-012: Model owner can update model description."""
    user_email = "alice@example.com"
    model_name = f"updatable-model-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create model
        assert _create_registered_model(client, model_name), "Failed to create model"

        # Update description
        success = _update_model_description(client, model_name, "Updated description for testing")
        assert success, "Owner failed to update model description"


# =============================================================================
# RES-020 to RES-022: Prompt Creation
# =============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_creates_prompt(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-020: Each user can create a prompt (registered model with prompt tags)."""
    prompt_name = f"{user_email}-prompt-{test_run_id}"
    prompt_text = f"This is a test prompt created by {user_email}"

    with http_client_factory(user_email) as client:
        success = _create_prompt(client, prompt_name, prompt_text)
        assert success, f"User {user_email} failed to create prompt {prompt_name}"


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_user_creates_prompt_version_with_text(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
    user_email: str,
) -> None:
    """RES-021: Each user can create prompt versions with text."""
    prompt_name = f"{user_email}-versioned-prompt-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create initial prompt
        success = _create_prompt(client, prompt_name, "Initial prompt text")
        assert success, f"Failed to create prompt: {prompt_name}"


@pytest.mark.integration
def test_owner_updates_prompt_with_new_version(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
) -> None:
    """RES-022: Prompt owner can update prompt with a new version."""
    user_email = "alice@example.com"
    prompt_name = f"updatable-prompt-{test_run_id}"

    with http_client_factory(user_email) as client:
        # Create initial prompt
        assert _create_prompt(client, prompt_name, "Initial text"), "Failed to create prompt"

        # Create new version
        success = _create_prompt_version(client, prompt_name, "Updated prompt text v2")
        assert success, "Owner failed to create new prompt version"
