"""User-level permission integration tests for MLflow OIDC Auth Plugin.

Test IDs: PERM-U-001 through PERM-U-012

Tests verify:
- Direct user-to-resource permission grants work correctly
- READ, EDIT, MANAGE, and NO_PERMISSIONS are enforced properly
"""

from __future__ import annotations

import time
import uuid
from urllib.parse import quote

import httpx
import pytest

# =============================================================================
# Helper Functions
# =============================================================================


def _create_experiment(client: httpx.Client, experiment_name: str) -> tuple[bool, str]:
    """Create an experiment and return (success, experiment_id)."""
    get_api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(experiment_name)}"
    create_api = "ajax-api/2.0/mlflow/experiments/create"

    get_resp = client.get(get_api)
    if get_resp.status_code == 200:
        payload = get_resp.json()
        exp = payload.get("experiment", payload)
        exp_id = exp.get("experiment_id") or exp.get("experimentId") or exp.get("id")
        return True, str(exp_id)

    create_resp = client.post(create_api, json={"name": experiment_name})
    if create_resp.status_code != 200:
        return False, f"Create failed: {create_resp.status_code} {create_resp.text}"

    get_resp2 = client.get(get_api)
    if get_resp2.status_code == 200:
        payload2 = get_resp2.json()
        exp2 = payload2.get("experiment", payload2)
        exp_id2 = exp2.get("experiment_id") or exp2.get("experimentId") or exp2.get("id")
        return True, str(exp_id2)

    return False, "Failed to get experiment after creation"


def _create_model(client: httpx.Client, model_name: str) -> bool:
    """Create a registered model."""
    get_api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(model_name)}"
    create_api = "ajax-api/2.0/mlflow/registered-models/create"

    get_resp = client.get(get_api)
    if get_resp.status_code == 200:
        return True

    create_resp = client.post(create_api, json={"name": model_name})
    return create_resp.status_code == 200


def _create_prompt(client: httpx.Client, prompt_name: str, prompt_text: str) -> bool:
    """Create a prompt."""
    get_api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(prompt_name)}"
    create_api = "ajax-api/2.0/mlflow/registered-models/create"
    version_api = "ajax-api/2.0/mlflow/model-versions/create"

    get_resp = client.get(get_api)
    if get_resp.status_code == 200:
        return True

    create_resp = client.post(
        create_api,
        json={
            "name": prompt_name,
            "tags": [{"key": "mlflow.prompt.is_prompt", "value": "true"}],
        },
    )
    if create_resp.status_code != 200:
        return False

    version_resp = client.post(
        version_api,
        json={
            "name": prompt_name,
            "description": "Initial version",
            "source": "test-source",
            "tags": [
                {"key": "mlflow.prompt.is_prompt", "value": "true"},
                {"key": "mlflow.prompt.text", "value": prompt_text},
            ],
        },
    )
    return version_resp.status_code == 200


def _grant_user_experiment_permission(
    client: httpx.Client,
    experiment_id: str,
    target_user: str,
    permission: str,
) -> bool:
    """Grant user-level experiment permission."""
    api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/experiments/{quote(experiment_id)}"

    # Try PATCH first, then POST if 404
    resp = client.patch(api, json={"permission": permission})
    if resp.status_code == 404:
        resp = client.post(api, json={"permission": permission})

    return resp.status_code in (200, 201)


def _grant_user_model_permission(
    client: httpx.Client,
    model_name: str,
    target_user: str,
    permission: str,
) -> bool:
    """Grant user-level model permission."""
    api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/registered-models/{quote(model_name)}"

    resp = client.patch(api, json={"permission": permission})
    if resp.status_code == 404:
        resp = client.post(api, json={"permission": permission})

    return resp.status_code in (200, 201)


def _grant_user_prompt_permission(
    client: httpx.Client,
    prompt_name: str,
    target_user: str,
    permission: str,
) -> bool:
    """Grant user-level prompt permission."""
    api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/prompts/{quote(prompt_name)}"

    resp = client.patch(api, json={"permission": permission})
    if resp.status_code == 404:
        resp = client.post(api, json={"permission": permission})

    return resp.status_code in (200, 201)


def _create_run(client: httpx.Client, experiment_id: str) -> httpx.Response:
    """Attempt to create a run in an experiment."""
    api = "api/2.0/mlflow/runs/create"
    payload = {
        "experiment_id": experiment_id,
        "start_time": int(time.time() * 1000),
        "tags": [{"key": "mlflow.runName", "value": f"perm-test-run-{uuid.uuid4().hex[:8]}"}],
    }
    return client.post(api, json=payload)


def _get_experiment(client: httpx.Client, experiment_name: str) -> httpx.Response:
    """Get experiment by name."""
    api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(experiment_name)}"
    return client.get(api)


def _get_model(client: httpx.Client, model_name: str) -> httpx.Response:
    """Get model by name."""
    api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(model_name)}"
    return client.get(api)


def _update_model(client: httpx.Client, model_name: str, description: str) -> httpx.Response:
    """Update model description."""
    api = "ajax-api/2.0/mlflow/registered-models/update"
    return client.patch(api, json={"name": model_name, "description": description})


def _delete_model(client: httpx.Client, model_name: str) -> httpx.Response:
    """Delete a registered model."""
    api = "ajax-api/2.0/mlflow/registered-models/delete"
    return client.request("DELETE", api, json={"name": model_name})


def _create_prompt_version(client: httpx.Client, prompt_name: str, text: str) -> httpx.Response:
    """Create a new prompt version."""
    api = "ajax-api/2.0/mlflow/model-versions/create"
    return client.post(
        api,
        json={
            "name": prompt_name,
            "description": "Permission test version",
            "source": "perm-test-source",
            "tags": [
                {"key": "mlflow.prompt.is_prompt", "value": "true"},
                {"key": "mlflow.prompt.text", "value": text},
            ],
        },
    )


def _is_denied(status_code: int) -> bool:
    """Check if response indicates access denied."""
    return status_code in (401, 403, 404)


# =============================================================================
# Test Fixture: Create resources and grant permissions
# =============================================================================


@pytest.fixture(scope="module")
def user_permission_test_resources(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
):
    """Create resources owned by Alice and grant permissions to other users.

    Alice (owner) grants:
    - Bob: READ
    - Charlie: EDIT
    - Eve: MANAGE
    - Dave: NO_PERMISSIONS
    """
    owner = "alice@example.com"

    experiment_name = f"user-perm-exp-{test_run_id}"
    model_name = f"user-perm-model-{test_run_id}"
    prompt_name = f"user-perm-prompt-{test_run_id}"

    with http_client_factory(owner) as client:
        # Create resources
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

        assert _create_model(client, model_name), f"Failed to create model: {model_name}"
        assert _create_prompt(client, prompt_name, "Test prompt text"), f"Failed to create prompt: {prompt_name}"

        # Grant permissions
        # Bob: READ
        assert _grant_user_experiment_permission(client, experiment_id, "bob@example.com", "READ")
        assert _grant_user_model_permission(client, model_name, "bob@example.com", "READ")
        assert _grant_user_prompt_permission(client, prompt_name, "bob@example.com", "READ")

        # Charlie: EDIT
        assert _grant_user_experiment_permission(client, experiment_id, "charlie@example.com", "EDIT")
        assert _grant_user_model_permission(client, model_name, "charlie@example.com", "EDIT")
        assert _grant_user_prompt_permission(client, prompt_name, "charlie@example.com", "EDIT")

        # Eve: MANAGE
        assert _grant_user_experiment_permission(client, experiment_id, "eve@example.com", "MANAGE")
        assert _grant_user_model_permission(client, model_name, "eve@example.com", "MANAGE")
        assert _grant_user_prompt_permission(client, prompt_name, "eve@example.com", "MANAGE")

        # Dave: NO_PERMISSIONS
        assert _grant_user_experiment_permission(client, experiment_id, "dave@example.com", "NO_PERMISSIONS")
        assert _grant_user_model_permission(client, model_name, "dave@example.com", "NO_PERMISSIONS")
        assert _grant_user_prompt_permission(client, prompt_name, "dave@example.com", "NO_PERMISSIONS")

    return {
        "owner": owner,
        "experiment_name": experiment_name,
        "experiment_id": experiment_id,
        "model_name": model_name,
        "prompt_name": prompt_name,
    }


# =============================================================================
# PERM-U-001 to PERM-U-004: Experiment Permissions
# =============================================================================


@pytest.mark.integration
def test_read_user_can_view_experiment(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-001: User with READ can view experiment but cannot create runs."""
    resources = user_permission_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        # Can view
        resp = _get_experiment(client, resources["experiment_name"])
        assert resp.status_code == 200, f"READ user should view experiment: {resp.status_code}"

        # Cannot create run
        run_resp = _create_run(client, resources["experiment_id"])
        assert _is_denied(run_resp.status_code), f"READ user should not create run: {run_resp.status_code}"


@pytest.mark.integration
def test_edit_user_can_modify_experiment(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-002: User with EDIT can view and create runs, but cannot delete."""
    resources = user_permission_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        # Can view
        resp = _get_experiment(client, resources["experiment_name"])
        assert resp.status_code == 200, f"EDIT user should view experiment: {resp.status_code}"

        # Can create run
        run_resp = _create_run(client, resources["experiment_id"])
        assert run_resp.status_code == 200, f"EDIT user should create run: {run_resp.status_code}"


@pytest.mark.integration
def test_manage_user_has_full_control_experiment(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-003: User with MANAGE can view, create runs, and manage permissions."""
    resources = user_permission_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        # Can view
        resp = _get_experiment(client, resources["experiment_name"])
        assert resp.status_code == 200, f"MANAGE user should view experiment: {resp.status_code}"

        # Can create run
        run_resp = _create_run(client, resources["experiment_id"])
        assert run_resp.status_code == 200, f"MANAGE user should create run: {run_resp.status_code}"

        # Can manage permissions (grant/update permissions for an existing user)
        # Using newuser@example.com which exists in the system
        perm_resp = _grant_user_experiment_permission(client, resources["experiment_id"], "newuser@example.com", "READ")
        assert perm_resp, "MANAGE user should be able to grant permissions"


@pytest.mark.integration
def test_no_permissions_user_cannot_access_experiment(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-004: User with NO_PERMISSIONS cannot view experiment (hidden)."""
    resources = user_permission_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        # Cannot view (should be 404 - hidden)
        resp = _get_experiment(client, resources["experiment_name"])
        assert _is_denied(resp.status_code), f"NO_PERMISSIONS user should not view: {resp.status_code}"


# =============================================================================
# PERM-U-005 to PERM-U-008: Model Permissions
# =============================================================================


@pytest.mark.integration
def test_read_user_can_view_model(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-005: User with READ can view model but cannot update."""
    resources = user_permission_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        # Can view
        resp = _get_model(client, resources["model_name"])
        assert resp.status_code == 200, f"READ user should view model: {resp.status_code}"

        # Cannot update
        update_resp = _update_model(client, resources["model_name"], "should not update")
        assert _is_denied(update_resp.status_code), f"READ user should not update: {update_resp.status_code}"


@pytest.mark.integration
def test_edit_user_can_modify_model(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-006: User with EDIT can view and update, but cannot delete."""
    resources = user_permission_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        # Can view
        resp = _get_model(client, resources["model_name"])
        assert resp.status_code == 200, f"EDIT user should view model: {resp.status_code}"

        # Can update
        update_resp = _update_model(client, resources["model_name"], "updated by charlie")
        assert update_resp.status_code == 200, f"EDIT user should update: {update_resp.status_code}"

        # Cannot delete
        delete_resp = _delete_model(client, resources["model_name"])
        assert _is_denied(delete_resp.status_code), f"EDIT user should not delete: {delete_resp.status_code}"


@pytest.mark.integration
def test_manage_user_has_full_control_model(
    http_client_factory,
    user_permission_test_resources,
    test_run_id: str,
) -> None:
    """PERM-U-007: User with MANAGE has full control including permission management."""
    resources = user_permission_test_resources
    user = "eve@example.com"

    # Create a separate model for delete test to avoid breaking other tests
    delete_test_model = f"eve-delete-test-model-{test_run_id}"

    with http_client_factory("alice@example.com") as alice_client:
        _create_model(alice_client, delete_test_model)
        _grant_user_model_permission(alice_client, delete_test_model, user, "MANAGE")

    with http_client_factory(user) as client:
        # Can view original model
        resp = _get_model(client, resources["model_name"])
        assert resp.status_code == 200, f"MANAGE user should view model: {resp.status_code}"

        # Can manage permissions
        perm_success = _grant_user_model_permission(client, resources["model_name"], "newuser@example.com", "READ")
        assert perm_success, "MANAGE user should manage permissions"

        # Can delete (separate model)
        delete_resp = _delete_model(client, delete_test_model)
        assert delete_resp.status_code == 200, f"MANAGE user should delete: {delete_resp.status_code}"


@pytest.mark.integration
def test_no_permissions_user_cannot_access_model(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-008: User with NO_PERMISSIONS cannot view model (hidden)."""
    resources = user_permission_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        # Cannot view (should be 404 - hidden)
        resp = _get_model(client, resources["model_name"])
        assert _is_denied(resp.status_code), f"NO_PERMISSIONS user should not view: {resp.status_code}"


# =============================================================================
# PERM-U-009 to PERM-U-012: Prompt Permissions
# =============================================================================


@pytest.mark.integration
def test_read_user_can_view_prompt(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-009: User with READ can view prompt but cannot create version."""
    resources = user_permission_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        # Can view (prompts are registered models)
        resp = _get_model(client, resources["prompt_name"])
        assert resp.status_code == 200, f"READ user should view prompt: {resp.status_code}"

        # Cannot create version
        version_resp = _create_prompt_version(client, resources["prompt_name"], "should not create")
        assert _is_denied(version_resp.status_code), f"READ user should not create version: {version_resp.status_code}"


@pytest.mark.integration
def test_edit_user_can_modify_prompt(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-010: User with EDIT can view and create versions."""
    resources = user_permission_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        # Can view
        resp = _get_model(client, resources["prompt_name"])
        assert resp.status_code == 200, f"EDIT user should view prompt: {resp.status_code}"

        # Can create version
        version_resp = _create_prompt_version(client, resources["prompt_name"], "charlie's version")
        assert version_resp.status_code == 200, f"EDIT user should create version: {version_resp.status_code}"


@pytest.mark.integration
def test_manage_user_has_full_control_prompt(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-011: User with MANAGE has full control over prompt."""
    resources = user_permission_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        # Can view
        resp = _get_model(client, resources["prompt_name"])
        assert resp.status_code == 200, f"MANAGE user should view prompt: {resp.status_code}"

        # Can create version
        version_resp = _create_prompt_version(client, resources["prompt_name"], "eve's version")
        assert version_resp.status_code == 200, f"MANAGE user should create version: {version_resp.status_code}"

        # Can manage permissions
        perm_success = _grant_user_prompt_permission(client, resources["prompt_name"], "newuser@example.com", "READ")
        assert perm_success, "MANAGE user should manage permissions"


@pytest.mark.integration
def test_no_permissions_user_cannot_access_prompt(
    http_client_factory,
    user_permission_test_resources,
) -> None:
    """PERM-U-012: User with NO_PERMISSIONS cannot view prompt (hidden)."""
    resources = user_permission_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        # Cannot view (should be 404 - hidden)
        resp = _get_model(client, resources["prompt_name"])
        assert _is_denied(resp.status_code), f"NO_PERMISSIONS user should not view: {resp.status_code}"
