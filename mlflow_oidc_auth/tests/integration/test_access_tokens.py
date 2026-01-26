"""Access token integration tests for MLflow OIDC Auth Plugin.

Test IDs: TOK-001 through TOK-012

Tests verify:
- Token creation and validation
- Admin creating tokens for other users
- Token-based authentication for API access
- Token revocation
"""

from __future__ import annotations

import base64
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


def _make_basic_auth_header(username: str, token: str) -> dict[str, str]:
    """Create Basic auth header from username and token (token as password)."""
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


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
def token_test_resources(
    base_url: str,
    ensure_server: None,
    http_client_factory,
    test_run_id: str,
):
    """Create resources and tokens for testing."""
    admin = "frank@example.com"
    user = "alice@example.com"

    experiment_name = f"token-test-exp-{test_run_id}"

    with http_client_factory(admin) as client:
        # Create experiment for permission testing
        exp_success, experiment_id = _create_experiment(client, experiment_name)
        assert exp_success, f"Failed to create experiment: {experiment_id}"

    return {
        "admin": admin,
        "user": user,
        "experiment_name": experiment_name,
        "experiment_id": experiment_id,
        "base_url": base_url,
    }


# =============================================================================
# TOK-001 to TOK-004: Token Creation
# =============================================================================


@pytest.mark.integration
def test_user_creates_own_token(
    http_client_factory,
    token_test_resources,
) -> None:
    """TOK-001: User creates their own access token."""
    user = token_test_resources["user"]

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/users/access-token"
        resp = client.patch(api, json={"username": user})

        if resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        assert resp.status_code in (200, 201), f"User should create own token: {resp.status_code}"

        data = resp.json()
        assert "token" in data, "Response should contain token"
        assert len(data["token"]) > 10, "Token should be non-trivial"


@pytest.mark.integration
def test_admin_creates_token_for_user(
    http_client_factory,
    token_test_resources,
) -> None:
    """TOK-002: Admin creates token for another user."""
    admin = token_test_resources["admin"]
    target_user = "bob@example.com"

    with http_client_factory(admin) as client:
        api = "api/2.0/mlflow/users/access-token"
        resp = client.patch(api, json={"username": target_user})

        if resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        assert resp.status_code in (200, 201), f"Admin should create token for user: {resp.status_code}"


@pytest.mark.integration
def test_user_cannot_create_token_for_other(
    http_client_factory,
    token_test_resources,
) -> None:
    """TOK-003: Non-admin user cannot create token for another user."""
    user = token_test_resources["user"]
    target_user = "bob@example.com"

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/users/access-token"
        resp = client.patch(api, json={"username": target_user})

        if resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        assert resp.status_code in (403, 401), f"Non-admin should not create token for other: {resp.status_code}"


@pytest.mark.integration
def test_admin_creates_token_for_service_account(
    http_client_factory,
    token_test_resources,
    test_run_id: str,
) -> None:
    """TOK-004: Admin creates token for service account."""
    admin = token_test_resources["admin"]
    svc_username = f"svc-token-test-{test_run_id}@example.com"

    with http_client_factory(admin) as client:
        # Create service account first
        create_api = "api/2.0/mlflow/users"
        create_resp = client.post(
            create_api,
            json={
                "username": svc_username,
                "display_name": f"Token Test Service {test_run_id}",
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

        assert token_resp.status_code in (200, 201), f"Admin should create token for service account: {token_resp.status_code}"


# =============================================================================
# TOK-005 to TOK-008: Token Validation and Usage
# =============================================================================


@pytest.mark.integration
def test_token_authenticates_api_requests(
    http_client_factory,
    token_test_resources,
) -> None:
    """TOK-005: Access token successfully authenticates API requests via Basic auth."""
    user = token_test_resources["user"]
    base_url = token_test_resources["base_url"]

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/users/access-token"
        resp = client.patch(api, json={"username": user})

        if resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        assert resp.status_code in (200, 201), "Failed to create token"
        token = resp.json().get("token")
        assert token, "No token in response"

    # Use token for authentication via Basic auth (username:token)
    with httpx.Client(
        base_url=base_url,
        headers=_make_basic_auth_header(user, token),
        timeout=30,
    ) as token_client:
        list_api = "ajax-api/2.0/mlflow/experiments/search"
        list_resp = token_client.post(list_api, json={"max_results": 5})
        assert _is_ok(list_resp.status_code), f"Token should authenticate: {list_resp.status_code}"


@pytest.mark.integration
def test_invalid_token_rejected(
    token_test_resources,
) -> None:
    """TOK-006: Invalid token is rejected."""
    base_url = token_test_resources["base_url"]

    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": "Bearer invalid-token-12345"},
        timeout=30,
        follow_redirects=False,  # Don't follow redirects to detect 302
    ) as token_client:
        api = "ajax-api/2.0/mlflow/experiments/search"
        resp = token_client.post(api, json={})
        # 401/403 = direct rejection, 302 = redirect to login (also rejection)
        assert resp.status_code in (401, 403, 302), f"Invalid token should be rejected: {resp.status_code}"


@pytest.mark.integration
def test_token_permissions_enforced(
    http_client_factory,
    token_test_resources,
    test_run_id: str,
) -> None:
    """TOK-007: Token-authenticated requests respect permission system."""
    admin = token_test_resources["admin"]
    user = "charlie@example.com"
    base_url = token_test_resources["base_url"]

    experiment_name = f"token-perm-test-{test_run_id}"

    # Create experiment and grant user READ only
    with http_client_factory(admin) as client:
        exp_success, exp_id = _create_experiment(client, experiment_name)
        assert exp_success, "Failed to create experiment"
        _grant_user_permission(client, "experiment", exp_id, user, "READ")

    # Get token for user
    with http_client_factory(user) as client:
        token_api = "api/2.0/mlflow/users/access-token"
        token_resp = client.patch(token_api, json={"username": user})

        if token_resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        token = token_resp.json().get("token")
        assert token, "No token in response"

    # Try to create run with token (should fail, only READ permission)
    with httpx.Client(
        base_url=base_url,
        headers=_make_basic_auth_header(user, token),
        timeout=30,
    ) as token_client:
        run_api = "api/2.0/mlflow/runs/create"
        run_resp = token_client.post(
            run_api,
            json={
                "experiment_id": exp_id,
                "start_time": int(time.time() * 1000),
            },
        )
        # Should be denied (403) since user only has READ
        assert run_resp.status_code in (401, 403), f"Token should respect permissions: {run_resp.status_code}"


@pytest.mark.integration
def test_service_account_token_works(
    http_client_factory,
    token_test_resources,
    test_run_id: str,
) -> None:
    """TOK-008: Service account token can authenticate API requests."""
    admin = token_test_resources["admin"]
    base_url = token_test_resources["base_url"]
    svc_username = f"svc-auth-test-{test_run_id}@example.com"

    with http_client_factory(admin) as client:
        # Create service account
        create_api = "api/2.0/mlflow/users"
        create_resp = client.post(
            create_api,
            json={
                "username": svc_username,
                "display_name": f"Auth Test Service {test_run_id}",
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

        token = token_resp.json().get("token")
        assert token, "No token in response"

    # Use service account token via Basic auth
    with httpx.Client(
        base_url=base_url,
        headers=_make_basic_auth_header(svc_username, token),
        timeout=30,
    ) as token_client:
        list_api = "ajax-api/2.0/mlflow/experiments/search"
        list_resp = token_client.post(list_api, json={"max_results": 5})
        assert _is_ok(list_resp.status_code), f"Service account token should work: {list_resp.status_code}"


# =============================================================================
# TOK-009 to TOK-012: Token Lifecycle
# =============================================================================


@pytest.mark.integration
def test_token_regeneration(
    http_client_factory,
    token_test_resources,
) -> None:
    """TOK-009: User can regenerate their token."""
    user = token_test_resources["user"]

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/users/access-token"

        # Create first token
        resp1 = client.patch(api, json={"username": user})

        if resp1.status_code == 404:
            pytest.skip("Access token endpoint not available")

        token1 = resp1.json().get("token")

        # Regenerate token
        resp2 = client.patch(api, json={"username": user})
        token2 = resp2.json().get("token")

        # Tokens should be different
        assert token1 != token2, "Regenerated token should be different"


@pytest.mark.integration
def test_old_token_invalid_after_regeneration(
    http_client_factory,
    token_test_resources,
) -> None:
    """TOK-010: Old token is invalid after regeneration."""
    user = "dave@example.com"
    base_url = token_test_resources["base_url"]

    with http_client_factory(user) as client:
        api = "api/2.0/mlflow/users/access-token"

        # Create first token
        resp1 = client.patch(api, json={"username": user})

        if resp1.status_code == 404:
            pytest.skip("Access token endpoint not available")

        old_token = resp1.json().get("token")

        # Regenerate
        client.patch(api, json={"username": user})

    # Try to use old token via Basic auth
    with httpx.Client(
        base_url=base_url,
        headers=_make_basic_auth_header(user, old_token),
        timeout=30,
    ) as token_client:
        list_api = "ajax-api/2.0/mlflow/experiments/search"
        list_resp = token_client.post(list_api, json={"max_results": 5})
        # Old token should be invalid - 302 redirect to login, 401 or 403
        assert list_resp.status_code in (401, 403, 302), f"Old token should be invalid: {list_resp.status_code}"


@pytest.mark.integration
def test_token_works_for_experiment_operations(
    http_client_factory,
    token_test_resources,
    test_run_id: str,
) -> None:
    """TOK-011: Token can be used for full experiment workflow."""
    admin = token_test_resources["admin"]
    base_url = token_test_resources["base_url"]

    # Get admin token
    with http_client_factory(admin) as client:
        api = "api/2.0/mlflow/users/access-token"
        resp = client.patch(api, json={"username": admin})

        if resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        token = resp.json().get("token")

    experiment_name = f"token-workflow-{test_run_id}"

    with httpx.Client(
        base_url=base_url,
        headers=_make_basic_auth_header(admin, token),
        timeout=30,
    ) as token_client:
        # Create experiment
        create_resp = token_client.post(
            "ajax-api/2.0/mlflow/experiments/create",
            json={"name": experiment_name},
        )
        assert create_resp.status_code in (200, 409), "Failed to create experiment"

        # Get experiment
        get_resp = token_client.get(f"ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(experiment_name)}")
        assert _is_ok(get_resp.status_code), "Failed to get experiment"

        exp_id = get_resp.json()["experiment"]["experiment_id"]

        # Create run
        run_resp = token_client.post(
            "api/2.0/mlflow/runs/create",
            json={
                "experiment_id": exp_id,
                "start_time": int(time.time() * 1000),
            },
        )
        assert _is_ok(run_resp.status_code), "Failed to create run"


@pytest.mark.integration
def test_token_works_for_model_operations(
    http_client_factory,
    token_test_resources,
    test_run_id: str,
) -> None:
    """TOK-012: Token can be used for model operations."""
    admin = token_test_resources["admin"]
    base_url = token_test_resources["base_url"]

    # Get admin token
    with http_client_factory(admin) as client:
        api = "api/2.0/mlflow/users/access-token"
        resp = client.patch(api, json={"username": admin})

        if resp.status_code == 404:
            pytest.skip("Access token endpoint not available")

        token = resp.json().get("token")

    model_name = f"token-model-{test_run_id}"

    with httpx.Client(
        base_url=base_url,
        headers=_make_basic_auth_header(admin, token),
        timeout=30,
    ) as token_client:
        # Create model
        create_resp = token_client.post(
            "ajax-api/2.0/mlflow/registered-models/create",
            json={"name": model_name},
        )
        assert create_resp.status_code in (200, 409), "Failed to create model"

        # Get model
        get_resp = token_client.get(f"ajax-api/2.0/mlflow/registered-models/get?name={quote(model_name)}")
        assert _is_ok(get_resp.status_code), "Failed to get model"
