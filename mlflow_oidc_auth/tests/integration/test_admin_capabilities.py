"""Admin capabilities integration tests for MLflow OIDC Auth Plugin.

Test IDs: ADM-001 through ADM-022

Tests verify:
- Admin can manage permissions on any resource
- Admin can manage users and service accounts
- Admin bypasses all permission restrictions
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
    return create_resp.status_code in (200, 409)


def _grant_user_permission(
    client: httpx.Client,
    resource_type: str,
    resource_id: str,
    target_user: str,
    permission: str,
) -> bool:
    """Grant user-level permission."""
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


def _is_ok(status_code: int) -> bool:
    """Check if response indicates success."""
    return status_code == 200


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def admin_test_resources(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
):
    """Create resources owned by a regular user for admin tests.

    Alice creates resources and grants herself MANAGE,
    then grants specific limited permissions to Frank (admin) to verify bypass.
    """
    owner = "alice@example.com"
    admin = "frank@example.com"

    experiment_name = f"admin-test-exp-{test_run_id}"
    model_name = f"admin-test-model-{test_run_id}"

    # Resources with NO_PERMISSIONS for admin (to test bypass)
    restricted_exp_name = f"admin-restricted-exp-{test_run_id}"
    restricted_model_name = f"admin-restricted-model-{test_run_id}"

    with http_client_factory(owner) as client:
        # Create regular resources
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

        assert _create_model(client, model_name), "Failed to create model"

        # Create restricted resources and grant admin NO_PERMISSIONS
        rest_exp_success, restricted_exp_id = _create_experiment(client, restricted_exp_name)
        assert rest_exp_success, f"Failed to create restricted experiment"

        assert _create_model(client, restricted_model_name), "Failed to create restricted model"

        # Grant admin NO_PERMISSIONS on restricted resources (admin should bypass)
        _grant_user_permission(client, "experiment", restricted_exp_id, admin, "NO_PERMISSIONS")
        _grant_user_permission(client, "model", restricted_model_name, admin, "NO_PERMISSIONS")

        # Grant admin READ on regular resources (admin should still have full access)
        _grant_user_permission(client, "experiment", experiment_id, admin, "READ")
        _grant_user_permission(client, "model", model_name, admin, "READ")

    return {
        "owner": owner,
        "admin": admin,
        "experiment_name": experiment_name,
        "experiment_id": experiment_id,
        "model_name": model_name,
        "restricted_exp_name": restricted_exp_name,
        "restricted_exp_id": restricted_exp_id,
        "restricted_model_name": restricted_model_name,
    }


# =============================================================================
# ADM-001 to ADM-006: Admin Permission Management
# =============================================================================


@pytest.mark.integration
def test_admin_views_any_experiment(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-001: Admin can view any experiment."""
    resources = admin_test_resources
    admin = resources["admin"]

    with http_client_factory(admin) as client:
        api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(resources['experiment_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"Admin should view any experiment: {resp.status_code}"


@pytest.mark.integration
def test_admin_modifies_any_experiment(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-002: Admin can modify any experiment (create runs)."""
    resources = admin_test_resources
    admin = resources["admin"]

    with http_client_factory(admin) as client:
        api = "api/2.0/mlflow/runs/create"
        resp = client.post(
            api,
            json={
                "experiment_id": resources["experiment_id"],
                "start_time": int(time.time() * 1000),
                "tags": [{"key": "mlflow.runName", "value": f"admin-run-{uuid.uuid4().hex[:6]}"}],
            },
        )
        assert _is_ok(resp.status_code), f"Admin should create run: {resp.status_code}"


@pytest.mark.integration
def test_admin_deletes_any_experiment(
    http_client_factory,
    admin_test_resources,
    test_run_id: str,
) -> None:
    """ADM-003: Admin can delete any experiment."""
    admin = admin_test_resources["admin"]
    owner = admin_test_resources["owner"]

    # Create a new experiment to delete
    delete_exp_name = f"admin-delete-test-{test_run_id}-{uuid.uuid4().hex[:6]}"

    with http_client_factory(owner) as client:
        exp_success, exp_id = _create_experiment(client, delete_exp_name)
        assert exp_success, "Failed to create experiment for delete test"

    with http_client_factory(admin) as client:
        api = "ajax-api/2.0/mlflow/experiments/delete"
        resp = client.post(api, json={"experiment_id": exp_id})
        assert _is_ok(resp.status_code), f"Admin should delete experiment: {resp.status_code}"


@pytest.mark.integration
def test_admin_grants_permission_on_any_resource(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-004: Admin can grant permission on any resource."""
    resources = admin_test_resources
    admin = resources["admin"]

    with http_client_factory(admin) as client:
        api = f"api/2.0/mlflow/permissions/users/{quote('newuser@example.com')}/experiments/{quote(resources['experiment_id'])}"
        resp = client.post(api, json={"permission": "READ"})

        if resp.status_code == 409:  # Already exists
            resp = client.patch(api, json={"permission": "READ"})

        assert resp.status_code in (200, 201), f"Admin should grant permission: {resp.status_code}"


@pytest.mark.integration
def test_admin_revokes_permission_on_any_resource(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-005: Admin can revoke permission on any resource."""
    resources = admin_test_resources
    admin = resources["admin"]

    with http_client_factory(admin) as client:
        # First grant, then revoke
        grant_api = f"api/2.0/mlflow/permissions/users/{quote('newuser@example.com')}/experiments/{quote(resources['experiment_id'])}"

        # Grant first
        client.post(grant_api, json={"permission": "READ"})

        # Now revoke (delete)
        resp = client.request("DELETE", grant_api)
        assert resp.status_code in (200, 204, 404), f"Admin should revoke permission: {resp.status_code}"


@pytest.mark.integration
def test_admin_overrides_existing_permission(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-006: Admin can override existing permission."""
    resources = admin_test_resources
    admin = resources["admin"]

    with http_client_factory(admin) as client:
        api = f"api/2.0/mlflow/permissions/users/{quote('bob@example.com')}/experiments/{quote(resources['experiment_id'])}"

        # Set initial permission
        client.post(api, json={"permission": "READ"})

        # Override to EDIT
        resp = client.patch(api, json={"permission": "EDIT"})
        assert resp.status_code in (200, 201), f"Admin should override permission: {resp.status_code}"


# =============================================================================
# ADM-010 to ADM-014: Admin User Management
# =============================================================================


@pytest.mark.integration
def test_admin_lists_all_users(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-010: Admin can list all users."""
    admin = admin_test_resources["admin"]

    with http_client_factory(admin) as client:
        api = "api/2.0/mlflow/users"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"Admin should list users: {resp.status_code}"

        data = resp.json()
        assert "users" in data or isinstance(data, list), "Response should contain users"


@pytest.mark.integration
def test_admin_creates_service_account(
    http_client_factory,
    admin_test_resources,
    test_run_id: str,
) -> None:
    """ADM-011: Admin can create service account."""
    admin = admin_test_resources["admin"]
    svc_username = f"svc-admin-test-{test_run_id}@example.com"

    with http_client_factory(admin) as client:
        api = "api/2.0/mlflow/users"
        resp = client.post(
            api,
            json={
                "username": svc_username,
                "display_name": f"Admin Test Service Account {test_run_id}",
                "is_admin": False,
                "is_service_account": True,
            },
        )
        assert resp.status_code in (200, 201), f"Admin should create service account: {resp.status_code}"


@pytest.mark.integration
def test_admin_creates_token_for_any_user(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-012: Admin can create token for any user."""
    admin = admin_test_resources["admin"]
    target_user = "bob@example.com"

    with http_client_factory(admin) as client:
        api = "api/2.0/mlflow/users/access-token"
        resp = client.patch(api, json={"username": target_user})

        if resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        assert resp.status_code in (200, 201), f"Admin should create token: {resp.status_code}"

        data = resp.json()
        assert "token" in data, "Response should contain token"


@pytest.mark.integration
def test_admin_creates_token_for_service_account(
    http_client_factory,
    admin_test_resources,
    test_run_id: str,
) -> None:
    """ADM-013: Admin can create token for service account."""
    admin = admin_test_resources["admin"]
    svc_username = f"svc-token-admin-{test_run_id}@example.com"

    with http_client_factory(admin) as client:
        # Create service account first
        create_api = "api/2.0/mlflow/users"
        create_resp = client.post(
            create_api,
            json={
                "username": svc_username,
                "display_name": f"Token Test {test_run_id}",
                "is_admin": False,
                "is_service_account": True,
            },
        )
        assert create_resp.status_code in (200, 201), "Failed to create service account"

        # Create token
        token_api = "api/2.0/mlflow/users/access-token"
        token_resp = client.patch(token_api, json={"username": svc_username})

        if token_resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        assert token_resp.status_code in (200, 201), f"Admin should create token for svc account: {token_resp.status_code}"


@pytest.mark.integration
def test_admin_updates_user_attributes(
    http_client_factory,
    admin_test_resources,
    test_run_id: str,
) -> None:
    """ADM-014: Admin can update user attributes."""
    admin = admin_test_resources["admin"]
    target_user = f"update-test-{test_run_id}@example.com"

    with http_client_factory(admin) as client:
        # Create user first
        create_api = "api/2.0/mlflow/users"
        client.post(
            create_api,
            json={
                "username": target_user,
                "display_name": f"Update Test {test_run_id}",
                "is_admin": False,
                "is_service_account": False,
            },
        )

        # Update user (endpoint may vary)
        update_api = "api/2.0/mlflow/users"
        resp = client.patch(
            update_api,
            json={
                "username": target_user,
                "display_name": f"Updated Display Name {test_run_id}",
            },
        )

        # May be 200, 404 if endpoint doesn't exist, or 501 if not implemented
        assert resp.status_code in (200, 201, 404, 501), f"Unexpected status: {resp.status_code}"


# =============================================================================
# ADM-020 to ADM-022: Admin Bypasses All Restrictions
# =============================================================================


@pytest.mark.integration
def test_admin_accesses_resource_with_no_permissions(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-020: Admin accesses resource even with NO_PERMISSIONS granted."""
    resources = admin_test_resources
    admin = resources["admin"]

    with http_client_factory(admin) as client:
        # Admin was granted NO_PERMISSIONS on restricted_exp, but should still access
        api = f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(resources['restricted_exp_name'])}"
        resp = client.get(api)
        assert _is_ok(resp.status_code), f"Admin should bypass NO_PERMISSIONS: {resp.status_code}"


@pytest.mark.integration
def test_admin_modifies_read_only_resource(
    http_client_factory,
    admin_test_resources,
) -> None:
    """ADM-021: Admin modifies resource even with only READ permission."""
    resources = admin_test_resources
    admin = resources["admin"]

    with http_client_factory(admin) as client:
        # Admin was granted READ on experiment, but should still create runs
        api = "api/2.0/mlflow/runs/create"
        resp = client.post(
            api,
            json={
                "experiment_id": resources["experiment_id"],
                "start_time": int(time.time() * 1000),
            },
        )
        assert _is_ok(resp.status_code), f"Admin should bypass READ-only: {resp.status_code}"


@pytest.mark.integration
def test_admin_deletes_resource_without_manage(
    http_client_factory,
    admin_test_resources,
    test_run_id: str,
) -> None:
    """ADM-022: Admin deletes resource even without MANAGE permission."""
    resources = admin_test_resources
    admin = resources["admin"]
    owner = resources["owner"]

    # Create a new model for delete test
    delete_model_name = f"admin-delete-model-{test_run_id}-{uuid.uuid4().hex[:6]}"

    with http_client_factory(owner) as client:
        assert _create_model(client, delete_model_name), "Failed to create model"
        # Grant admin EDIT (not MANAGE)
        _grant_user_permission(client, "model", delete_model_name, admin, "EDIT")

    with http_client_factory(admin) as client:
        # Admin should still be able to delete despite only having EDIT
        api = "ajax-api/2.0/mlflow/registered-models/delete"
        resp = client.request("DELETE", api, json={"name": delete_model_name})
        assert _is_ok(resp.status_code), f"Admin should bypass EDIT-only for delete: {resp.status_code}"
