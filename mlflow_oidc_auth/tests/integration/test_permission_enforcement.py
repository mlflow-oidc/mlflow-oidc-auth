"""Permission enforcement integration tests for MLflow OIDC Auth Plugin.

Test IDs: ENF-R-001 through ENF-N-008

Tests verify:
- READ permission: can only view
- EDIT permission: can view and modify, but not delete or manage permissions
- MANAGE permission: full control
- NO_PERMISSIONS: no access, resources hidden from lists
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
        return False, f"Create failed: {create_resp.status_code}"

    get_resp2 = client.get(get_api)
    if get_resp2.status_code == 200:
        payload2 = get_resp2.json()
        exp2 = payload2.get("experiment", payload2)
        exp_id2 = exp2.get("experiment_id") or exp2.get("experimentId") or exp2.get("id")
        return True, str(exp_id2)

    return False, "Failed to get experiment after creation"


def _create_model(client: httpx.Client, model_name: str) -> bool:
    """Create a registered model."""
    create_api = "ajax-api/2.0/mlflow/registered-models/create"
    create_resp = client.post(create_api, json={"name": model_name})
    return create_resp.status_code in (200, 409)  # 409 if already exists


def _grant_user_permission(
    client: httpx.Client,
    resource_type: str,
    resource_id: str,
    target_user: str,
    permission: str,
) -> bool:
    """Grant user-level permission for a resource."""
    if resource_type == "experiment":
        api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/experiments/{quote(resource_id)}"
    elif resource_type == "model":
        api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/registered-models/{quote(resource_id)}"
    else:
        return False

    resp = client.patch(api, json={"permission": permission})
    if resp.status_code == 404:
        resp = client.post(api, json={"permission": permission})

    return resp.status_code in (200, 201)


def _is_denied(status_code: int) -> bool:
    """Check if response indicates access denied.

    Includes 405 Method Not Allowed as some endpoints respond with this when
    the HTTP method is not supported for the user's permission level.
    """
    return status_code in (401, 403, 404, 405)


def _is_ok(status_code: int) -> bool:
    """Check if response indicates success."""
    return status_code == 200


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def enforcement_test_resources(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
):
    """Create resources for permission enforcement testing.

    Owner: alice@example.com
    - Bob: READ
    - Charlie: EDIT
    - Eve: MANAGE
    - Dave: NO_PERMISSIONS
    """
    owner = "alice@example.com"

    experiment_name = f"enforcement-exp-{test_run_id}"
    model_name = f"enforcement-model-{test_run_id}"

    with http_client_factory(owner) as client:
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

        assert _create_model(client, model_name), f"Failed to create model"

        # Grant permissions
        for user, perm in [
            ("bob@example.com", "READ"),
            ("charlie@example.com", "EDIT"),
            ("eve@example.com", "MANAGE"),
            ("dave@example.com", "NO_PERMISSIONS"),
        ]:
            assert _grant_user_permission(client, "experiment", experiment_id, user, perm)
            assert _grant_user_permission(client, "model", model_name, user, perm)

    return {
        "owner": owner,
        "experiment_name": experiment_name,
        "experiment_id": experiment_id,
        "model_name": model_name,
    }


# =============================================================================
# ENF-R-001 to ENF-R-009: READ Permission Enforcement
# =============================================================================


@pytest.mark.integration
def test_read_user_get_experiment(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-001: READ user can GET experiment."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(resources['experiment_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"READ should GET experiment: {resp.status_code}"


@pytest.mark.integration
def test_read_user_get_runs(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-002: READ user can GET experiment runs."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/runs/search"
        resp = client.post(api, json={"experiment_ids": [resources["experiment_id"]]})
        assert _is_ok(resp.status_code), f"READ should search runs: {resp.status_code}"


@pytest.mark.integration
def test_read_user_cannot_create_run(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-003: READ user cannot POST create run."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/runs/create"
        payload = {
            "experiment_id": resources["experiment_id"],
            "start_time": int(time.time() * 1000),
        }
        resp = client.post(api, json=payload)
        assert _is_denied(resp.status_code), f"READ should NOT create run: {resp.status_code}"


@pytest.mark.integration
def test_read_user_cannot_update_experiment(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-004: READ user cannot PATCH update experiment."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/experiments/update"
        resp = client.patch(
            api,
            json={
                "experiment_id": resources["experiment_id"],
                "new_name": f"should-not-rename-{uuid.uuid4().hex[:6]}",
            },
        )
        assert _is_denied(resp.status_code), f"READ should NOT update experiment: {resp.status_code}"


@pytest.mark.integration
def test_read_user_cannot_delete_experiment(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-005: READ user cannot DELETE experiment."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/experiments/delete"
        resp = client.post(api, json={"experiment_id": resources["experiment_id"]})
        assert _is_denied(resp.status_code), f"READ should NOT delete experiment: {resp.status_code}"


@pytest.mark.integration
def test_read_user_cannot_manage_permissions(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-006: READ user cannot POST/PATCH permission endpoint."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = f"api/2.0/mlflow/permissions/users/{quote('newuser@example.com')}/experiments/{quote(resources['experiment_id'])}"
        resp = client.post(api, json={"permission": "READ"})
        assert _is_denied(resp.status_code), f"READ should NOT manage permissions: {resp.status_code}"


@pytest.mark.integration
def test_read_user_get_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-007: READ user can GET model."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(resources['model_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"READ should GET model: {resp.status_code}"


@pytest.mark.integration
def test_read_user_cannot_update_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-008: READ user cannot PATCH update model."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/registered-models/update"
        resp = client.patch(
            api,
            json={"name": resources["model_name"], "description": "should not update"},
        )
        assert _is_denied(resp.status_code), f"READ should NOT update model: {resp.status_code}"


@pytest.mark.integration
def test_read_user_cannot_delete_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-R-009: READ user cannot DELETE model."""
    resources = enforcement_test_resources
    user = "bob@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/registered-models/delete"
        resp = client.request("DELETE", api, json={"name": resources["model_name"]})
        assert _is_denied(resp.status_code), f"READ should NOT delete model: {resp.status_code}"


# =============================================================================
# ENF-E-001 to ENF-E-010: EDIT Permission Enforcement
# =============================================================================


@pytest.mark.integration
def test_edit_user_get_experiment(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-001: EDIT user can GET experiment."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(resources['experiment_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"EDIT should GET experiment: {resp.status_code}"


@pytest.mark.integration
def test_edit_user_can_create_run(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-002: EDIT user can POST create run."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/runs/create"
        payload = {
            "experiment_id": resources["experiment_id"],
            "start_time": int(time.time() * 1000),
            "tags": [{"key": "mlflow.runName", "value": f"edit-test-{uuid.uuid4().hex[:6]}"}],
        }
        resp = client.post(api, json=payload)
        assert _is_ok(resp.status_code), f"EDIT should create run: {resp.status_code}"


@pytest.mark.integration
def test_edit_user_can_update_run(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-003: EDIT user can PATCH update run (log metrics)."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        # Create a run first
        create_api = "api/2.0/mlflow/runs/create"
        create_resp = client.post(
            create_api,
            json={
                "experiment_id": resources["experiment_id"],
                "start_time": int(time.time() * 1000),
            },
        )
        assert _is_ok(create_resp.status_code), "Failed to create run for update test"

        run_data = create_resp.json()
        run_id = run_data.get("run", {}).get("info", {}).get("run_id")

        # Log metric to the run
        log_api = "api/2.0/mlflow/runs/log-metric"
        log_resp = client.post(
            log_api,
            json={
                "run_id": run_id,
                "key": "test_metric",
                "value": 1.0,
                "timestamp": int(time.time() * 1000),
            },
        )
        assert _is_ok(log_resp.status_code), f"EDIT should log metric: {log_resp.status_code}"


@pytest.mark.integration
def test_edit_user_cannot_delete_experiment(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-004: EDIT user cannot DELETE experiment."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/experiments/delete"
        resp = client.post(api, json={"experiment_id": resources["experiment_id"]})
        assert _is_denied(resp.status_code), f"EDIT should NOT delete experiment: {resp.status_code}"


@pytest.mark.integration
def test_edit_user_cannot_delete_run(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-005: EDIT user cannot DELETE run."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        # Create a run to try deleting
        create_api = "api/2.0/mlflow/runs/create"
        create_resp = client.post(
            create_api,
            json={
                "experiment_id": resources["experiment_id"],
                "start_time": int(time.time() * 1000),
            },
        )

        if _is_ok(create_resp.status_code):
            run_data = create_resp.json()
            run_id = run_data.get("run", {}).get("info", {}).get("run_id")

            delete_api = "api/2.0/mlflow/runs/delete"
            delete_resp = client.post(delete_api, json={"run_id": run_id})
            assert _is_denied(delete_resp.status_code), f"EDIT should NOT delete run: {delete_resp.status_code}"


@pytest.mark.integration
def test_edit_user_cannot_manage_permissions(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-006: EDIT user cannot POST/PATCH permission endpoint."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        api = f"api/2.0/mlflow/permissions/users/{quote('newuser@example.com')}/experiments/{quote(resources['experiment_id'])}"
        resp = client.post(api, json={"permission": "READ"})
        assert _is_denied(resp.status_code), f"EDIT should NOT manage permissions: {resp.status_code}"


@pytest.mark.integration
def test_edit_user_get_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-007: EDIT user can GET model."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(resources['model_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"EDIT should GET model: {resp.status_code}"


@pytest.mark.integration
def test_edit_user_can_update_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-008: EDIT user can PATCH update model description."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/registered-models/update"
        resp = client.patch(
            api,
            json={
                "name": resources["model_name"],
                "description": "updated by edit user",
            },
        )
        assert _is_ok(resp.status_code), f"EDIT should update model: {resp.status_code}"


@pytest.mark.integration
def test_edit_user_cannot_delete_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-009: EDIT user cannot DELETE model."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/registered-models/delete"
        resp = client.request("DELETE", api, json={"name": resources["model_name"]})
        assert _is_denied(resp.status_code), f"EDIT should NOT delete model: {resp.status_code}"


@pytest.mark.integration
def test_edit_user_can_create_model_version(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-E-010: EDIT user can POST create model version."""
    resources = enforcement_test_resources
    user = "charlie@example.com"

    with http_client_factory(user) as client:
        # First create a run to get valid artifact source
        run_resp = client.post(
            "ajax-api/2.0/mlflow/runs/create",
            json={
                "experiment_id": resources["experiment_id"],
                "run_name": f"mv-source-run-{resources['experiment_id'][:6]}",
            },
        )
        assert run_resp.status_code == 200, f"Failed to create run for model version: {run_resp.status_code}"
        run_data = run_resp.json()
        run_id = run_data.get("run", {}).get("info", {}).get("run_id")
        assert run_id, f"No run_id in response: {run_data}"

        # Use the run's artifact URI as source
        source = f"runs:/{run_id}/model"

        api = "ajax-api/2.0/mlflow/model-versions/create"
        resp = client.post(
            api,
            json={
                "name": resources["model_name"],
                "source": source,
                "run_id": run_id,
                "description": "Version by edit user",
            },
        )
        assert _is_ok(resp.status_code), f"EDIT should create model version: {resp.status_code}"


# =============================================================================
# ENF-M-001 to ENF-M-010: MANAGE Permission Enforcement
# =============================================================================


@pytest.mark.integration
def test_manage_user_get_experiment(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-M-001: MANAGE user can GET experiment."""
    resources = enforcement_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(resources['experiment_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"MANAGE should GET experiment: {resp.status_code}"


@pytest.mark.integration
def test_manage_user_can_create_run(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-M-002: MANAGE user can POST create run."""
    resources = enforcement_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/runs/create"
        resp = client.post(
            api,
            json={
                "experiment_id": resources["experiment_id"],
                "start_time": int(time.time() * 1000),
            },
        )
        assert _is_ok(resp.status_code), f"MANAGE should create run: {resp.status_code}"


@pytest.mark.integration
def test_manage_user_can_delete_run(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-M-003: MANAGE user can DELETE run."""
    resources = enforcement_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        # Create a run to delete
        create_resp = client.post(
            "api/2.0/mlflow/runs/create",
            json={
                "experiment_id": resources["experiment_id"],
                "start_time": int(time.time() * 1000),
            },
        )
        assert _is_ok(create_resp.status_code), "Failed to create run for delete test"

        run_data = create_resp.json()
        run_id = run_data.get("run", {}).get("info", {}).get("run_id")

        delete_resp = client.post("api/2.0/mlflow/runs/delete", json={"run_id": run_id})
        assert _is_ok(delete_resp.status_code), f"MANAGE should delete run: {delete_resp.status_code}"


@pytest.mark.integration
def test_manage_user_can_grant_permission(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-M-005: MANAGE user can POST grant permission to another user."""
    resources = enforcement_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        api = f"api/2.0/mlflow/permissions/users/{quote('newuser@example.com')}/experiments/{quote(resources['experiment_id'])}"
        resp = client.post(api, json={"permission": "READ"})

        # May be 200/201 for new grant, or need PATCH for existing
        if resp.status_code == 409:  # Already exists
            resp = client.patch(api, json={"permission": "READ"})

        assert resp.status_code in (200, 201), f"MANAGE should grant permission: {resp.status_code}"


@pytest.mark.integration
def test_manage_user_can_update_permission(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-M-006: MANAGE user can PATCH update permission."""
    resources = enforcement_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        api = f"api/2.0/mlflow/permissions/users/{quote('newuser@example.com')}/experiments/{quote(resources['experiment_id'])}"
        resp = client.patch(api, json={"permission": "EDIT"})

        # If permission doesn't exist, create it first
        if resp.status_code == 404:
            client.post(api, json={"permission": "READ"})
            resp = client.patch(api, json={"permission": "EDIT"})

        assert resp.status_code in (200, 201), f"MANAGE should update permission: {resp.status_code}"


@pytest.mark.integration
def test_manage_user_get_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-M-008: MANAGE user can GET model."""
    resources = enforcement_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(resources['model_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"MANAGE should GET model: {resp.status_code}"


@pytest.mark.integration
def test_manage_user_can_update_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-M-009: MANAGE user can PATCH update model."""
    resources = enforcement_test_resources
    user = "eve@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/registered-models/update"
        resp = client.patch(
            api,
            json={
                "name": resources["model_name"],
                "description": "updated by manage user",
            },
        )
        assert _is_ok(resp.status_code), f"MANAGE should update model: {resp.status_code}"


# =============================================================================
# ENF-N-001 to ENF-N-008: NO_PERMISSIONS Enforcement
# =============================================================================


@pytest.mark.integration
def test_no_perm_user_cannot_get_experiment_by_name(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-N-001: NO_PERMISSIONS user cannot GET experiment by name (hidden)."""
    resources = enforcement_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(resources['experiment_name'])}"
        resp = client.get(api)
        assert _is_denied(resp.status_code), f"NO_PERM should NOT get experiment: {resp.status_code}"


@pytest.mark.integration
def test_no_perm_user_cannot_get_experiment_by_id(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-N-002: NO_PERMISSIONS user cannot GET experiment by ID."""
    resources = enforcement_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/experiments/get?experiment_id={quote(resources['experiment_id'])}"
        resp = client.get(api)
        assert _is_denied(resp.status_code), f"NO_PERM should NOT get experiment by ID: {resp.status_code}"


@pytest.mark.integration
def test_no_perm_user_experiment_not_in_list(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-N-003: NO_PERMISSIONS resource not in user's experiment list."""
    resources = enforcement_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/experiments/search"
        resp = client.post(api, json={})

        if _is_ok(resp.status_code):
            data = resp.json()
            experiments = data.get("experiments", [])
            exp_names = [e.get("name") for e in experiments]
            assert resources["experiment_name"] not in exp_names, "NO_PERM resource should not be in list"


@pytest.mark.integration
def test_no_perm_user_cannot_create_run(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-N-004: NO_PERMISSIONS user cannot POST create run."""
    resources = enforcement_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/runs/create"
        resp = client.post(
            api,
            json={
                "experiment_id": resources["experiment_id"],
                "start_time": int(time.time() * 1000),
            },
        )
        assert _is_denied(resp.status_code), f"NO_PERM should NOT create run: {resp.status_code}"


@pytest.mark.integration
def test_no_perm_user_cannot_get_model(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-N-005: NO_PERMISSIONS user cannot GET model (hidden)."""
    resources = enforcement_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        api = f"ajax-api/2.0/mlflow/registered-models/get?name={quote(resources['model_name'])}"
        resp = client.get(api)
        assert _is_denied(resp.status_code), f"NO_PERM should NOT get model: {resp.status_code}"


@pytest.mark.integration
def test_no_perm_user_model_not_in_list(
    http_client_factory,
    enforcement_test_resources,
) -> None:
    """ENF-N-006: NO_PERMISSIONS model not in user's model list."""
    resources = enforcement_test_resources
    user = "dave@example.com"

    with http_client_factory(user) as client:
        api = "ajax-api/2.0/mlflow/registered-models/search"
        resp = client.post(api, json={})

        if _is_ok(resp.status_code):
            data = resp.json()
            models = data.get("registered_models", [])
            model_names = [m.get("name") for m in models]
            assert resources["model_name"] not in model_names, "NO_PERM model should not be in list"
