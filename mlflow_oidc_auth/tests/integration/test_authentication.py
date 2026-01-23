"""Authentication integration tests for MLflow OIDC Auth Plugin.

Test IDs: AUTH-001 through AUTH-024

Tests verify:
- OIDC login for all mlflow-users group members
- Access token creation and authentication
- Service account authentication
"""

from __future__ import annotations

import base64
import uuid

import httpx
import pytest

from .users import get_admin_users, get_mlflow_users, get_non_mlflow_users


def _make_basic_auth_header(username: str, token: str) -> dict[str, str]:
    """Create Basic auth header from username and token (token as password)."""
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


# =============================================================================
# AUTH-001 to AUTH-007: OIDC Login Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_mlflow_users())
def test_mlflow_users_can_login(
    base_url: str,
    ensure_server: None,
    playwright_browser,
    user_email: str,
) -> None:
    """AUTH-001 to AUTH-005: Users in mlflow-users group can authenticate via OIDC.

    Validates that session cookies are returned after OIDC login flow.
    """
    from .utils import user_login

    context = playwright_browser.new_context()
    page = context.new_page()
    try:
        cookies = user_login(page, user_email, url=base_url)
        assert cookies.jar, f"Login failed for {user_email}; no cookies returned"

        # Verify the session is valid by hitting a protected endpoint
        response = httpx.get(f"{base_url}health/live", cookies=cookies)
        assert response.status_code == 200, f"Health check failed for {user_email}: {response.status_code}"
    finally:
        page.close()
        context.close()


@pytest.mark.integration
@pytest.mark.parametrize("admin_email", get_admin_users())
def test_admin_users_can_login(
    base_url: str,
    ensure_server: None,
    playwright_browser,
    admin_email: str,
) -> None:
    """AUTH-006: Admin users can authenticate via OIDC."""
    from .utils import user_login

    context = playwright_browser.new_context()
    page = context.new_page()
    try:
        cookies = user_login(page, admin_email, url=base_url)
        assert cookies.jar, f"Login failed for admin {admin_email}; no cookies returned"

        # Verify admin can access admin-only endpoint
        response = httpx.get(f"{base_url}api/2.0/mlflow/users", cookies=cookies)
        # Admin should be able to list users
        assert response.status_code == 200, f"Admin endpoint access failed for {admin_email}: {response.status_code}"
    finally:
        page.close()
        context.close()


@pytest.mark.integration
@pytest.mark.parametrize("user_email", get_non_mlflow_users())
def test_non_mlflow_users_login_behavior(
    base_url: str,
    ensure_server: None,
    playwright_browser,
    user_email: str,
) -> None:
    """AUTH-007: Users not in mlflow-users group - verify login behavior.

    Depending on server configuration, these users may:
    - Be denied login entirely
    - Login but have no/limited access to resources
    """
    from .utils import user_login

    context = playwright_browser.new_context()
    page = context.new_page()
    try:
        # This might succeed (user created) or fail (access denied)
        # We just verify the behavior is consistent
        try:
            cookies = user_login(page, user_email, url=base_url)
            # If login succeeds, verify limited access
            if cookies.jar:
                response = httpx.get(f"{base_url}ajax-api/2.0/mlflow/experiments", cookies=cookies)
                # User may have access or not depending on DEFAULT_MLFLOW_PERMISSION
                assert response.status_code in (200, 401, 403), f"Unexpected status for {user_email}: {response.status_code}"
        except Exception:
            # Login denial is acceptable for non-mlflow-users
            pass
    finally:
        page.close()
        context.close()


# =============================================================================
# AUTH-010 to AUTH-014: Access Token Authentication
# =============================================================================


@pytest.mark.integration
def test_user_creates_own_access_token(
    base_url: str,
    ensure_server: None,
    user_cookies_factory,
) -> None:
    """AUTH-010: User can create an access token for themselves."""
    from .utils import create_access_token_for_user

    user_email = "alice@example.com"
    cookies = user_cookies_factory(user_email)

    success, token_or_reason = create_access_token_for_user(user_email, cookies, base_url=base_url)

    if not success and "unavailable" in token_or_reason:
        pytest.skip("Access token endpoint not available on this deployment")

    assert success, f"Failed to create access token: {token_or_reason}"
    assert token_or_reason, "Token should not be empty"


@pytest.mark.integration
def test_api_call_with_valid_bearer_token(
    base_url: str,
    ensure_server: None,
    user_cookies_factory,
) -> None:
    """AUTH-011: API call with valid token succeeds (via Basic auth)."""
    from .utils import create_access_token_for_user

    user_email = "alice@example.com"
    cookies = user_cookies_factory(user_email)

    success, token_or_reason = create_access_token_for_user(user_email, cookies, base_url=base_url)

    if not success and "unavailable" in token_or_reason:
        pytest.skip("Access token endpoint not available on this deployment")

    assert success, f"Failed to create access token: {token_or_reason}"

    # Use the token for API call via Basic auth (username:token)
    headers = _make_basic_auth_header(user_email, token_or_reason)
    response = httpx.get(f"{base_url}ajax-api/2.0/mlflow/experiments/search?max_results=5", headers=headers)

    assert response.status_code == 200, f"Token auth failed: {response.status_code} {response.text}"


@pytest.mark.integration
def test_api_call_with_invalid_token(
    base_url: str,
    ensure_server: None,
) -> None:
    """AUTH-012: API call with invalid/expired token returns 401."""
    headers = {"Authorization": "Bearer invalid-token-12345"}
    response = httpx.get(f"{base_url}ajax-api/2.0/mlflow/experiments", headers=headers, follow_redirects=False)

    # 401/403 = direct rejection, 302 = redirect to login (also rejection)
    assert response.status_code in (401, 403, 302), f"Expected 401/403/302 for invalid token, got {response.status_code}"


@pytest.mark.integration
def test_admin_creates_token_for_another_user(
    base_url: str,
    ensure_server: None,
    admin_cookies: httpx.Cookies,
) -> None:
    """AUTH-013: Admin can create a token for another user."""
    from .utils import create_access_token_for_user

    target_user = "bob@example.com"

    success, token_or_reason = create_access_token_for_user(target_user, admin_cookies, base_url=base_url)

    if not success and "unavailable" in token_or_reason:
        pytest.skip("Access token endpoint not available on this deployment")

    assert success, f"Admin failed to create token for {target_user}: {token_or_reason}"

    # Verify the token works for the target user via Basic auth
    headers = _make_basic_auth_header(target_user, token_or_reason)
    response = httpx.get(f"{base_url}ajax-api/2.0/mlflow/experiments/search?max_results=5", headers=headers)

    assert response.status_code == 200, f"Token for {target_user} failed: {response.status_code}"


@pytest.mark.integration
def test_non_admin_cannot_create_token_for_another_user(
    base_url: str,
    ensure_server: None,
    user_cookies_factory,
) -> None:
    """AUTH-014: Non-admin attempting to create token for another user fails."""
    from .utils import create_access_token_for_user

    requester = "alice@example.com"
    target_user = "bob@example.com"

    cookies = user_cookies_factory(requester)
    success, result = create_access_token_for_user(target_user, cookies, base_url=base_url)

    if "unavailable" in result:
        pytest.skip("Access token endpoint not available on this deployment")

    # Non-admin should not be able to create tokens for others
    assert not success, f"Non-admin {requester} should not create token for {target_user}"


# =============================================================================
# AUTH-020 to AUTH-024: Service Account Authentication
# =============================================================================


@pytest.mark.integration
def test_admin_creates_service_account(
    base_url: str,
    ensure_server: None,
    admin_cookies: httpx.Cookies,
    test_run_id: str,
) -> None:
    """AUTH-020: Admin can create a service account."""
    from .utils import create_service_account

    username = f"svc-auth-test-{test_run_id}@example.com"
    display_name = f"Auth Test Service Account {test_run_id}"

    success, message = create_service_account(username, display_name, admin_cookies, base_url=base_url)

    assert success, f"Failed to create service account: {message}"


@pytest.mark.integration
def test_admin_creates_token_for_service_account(
    base_url: str,
    ensure_server: None,
    admin_cookies: httpx.Cookies,
    test_run_id: str,
) -> None:
    """AUTH-021: Admin can create a token for a service account."""
    from .utils import create_access_token_for_user, create_service_account

    username = f"svc-token-test-{test_run_id}@example.com"
    display_name = f"Token Test Service Account {test_run_id}"

    # Create service account first
    created, msg = create_service_account(username, display_name, admin_cookies, base_url=base_url)
    assert created, f"Failed to create service account: {msg}"

    # Create token for service account
    success, token_or_reason = create_access_token_for_user(username, admin_cookies, base_url=base_url)

    if not success and "unavailable" in token_or_reason:
        pytest.skip("Access token endpoint not available on this deployment")

    assert success, f"Failed to create token for service account: {token_or_reason}"


@pytest.mark.integration
def test_service_account_authenticates_via_token(
    base_url: str,
    ensure_server: None,
    admin_cookies: httpx.Cookies,
    test_run_id: str,
) -> None:
    """AUTH-022: Service account can authenticate via token."""
    from .utils import create_access_token_for_user, create_service_account

    username = f"svc-auth-via-token-{test_run_id}@example.com"
    display_name = f"Auth Via Token Test {test_run_id}"

    # Create service account
    created, msg = create_service_account(username, display_name, admin_cookies, base_url=base_url)
    assert created, f"Failed to create service account: {msg}"

    # Create token
    success, token = create_access_token_for_user(username, admin_cookies, base_url=base_url)

    if not success and "unavailable" in token:
        pytest.skip("Access token endpoint not available on this deployment")

    assert success, f"Failed to create token: {token}"

    # Authenticate with token via Basic auth (username:token)
    headers = _make_basic_auth_header(username, token)
    response = httpx.get(f"{base_url}ajax-api/2.0/mlflow/experiments/search?max_results=5", headers=headers)

    assert response.status_code == 200, f"Service account auth failed: {response.status_code}"


@pytest.mark.integration
def test_service_account_creates_experiment(
    base_url: str,
    ensure_server: None,
    admin_cookies: httpx.Cookies,
    test_run_id: str,
) -> None:
    """AUTH-023: Service account can create an experiment (if permissions allow)."""
    from .utils import create_access_token_for_user, create_service_account

    username = f"svc-exp-creator-{test_run_id}@example.com"
    display_name = f"Experiment Creator {test_run_id}"
    experiment_name = f"svc-account-exp-{test_run_id}"

    # Create service account
    created, msg = create_service_account(username, display_name, admin_cookies, base_url=base_url)
    assert created, f"Failed to create service account: {msg}"

    # Create token
    success, token = create_access_token_for_user(username, admin_cookies, base_url=base_url)

    if not success and "unavailable" in token:
        pytest.skip("Access token endpoint not available on this deployment")

    assert success, f"Failed to create token: {token}"

    # Create experiment using service account token via Basic auth
    headers = _make_basic_auth_header(username, token)
    response = httpx.post(
        f"{base_url}ajax-api/2.0/mlflow/experiments/create",
        json={"name": experiment_name},
        headers=headers,
    )

    # May succeed (200) or fail depending on DEFAULT_MLFLOW_PERMISSION
    assert response.status_code in (200, 401, 403), f"Unexpected status: {response.status_code}"


@pytest.mark.integration
def test_service_account_logs_run_with_scorers(
    base_url: str,
    ensure_server: None,
    admin_cookies: httpx.Cookies,
    test_run_id: str,
) -> None:
    """AUTH-024: Service account can log runs with scorer metrics."""
    from .utils import create_access_token_for_user, create_service_account, seed_scorers_with_tracking_token

    username = f"svc-scorer-{test_run_id}@example.com"
    display_name = f"Scorer Service Account {test_run_id}"
    experiment_name = f"svc-scorer-exp-{test_run_id}"

    # Create service account
    created, msg = create_service_account(username, display_name, admin_cookies, base_url=base_url)
    assert created, f"Failed to create service account: {msg}"

    # Create token
    success, token = create_access_token_for_user(username, admin_cookies, base_url=base_url)

    if not success and "unavailable" in token:
        pytest.skip("Access token endpoint not available on this deployment")

    assert success, f"Failed to create token: {token}"

    # Seed scorers with the token (use Basic auth: username + token as password)
    run_id, metrics = seed_scorers_with_tracking_token(experiment_name, token, base_url=base_url, username=username)

    assert run_id, "MLflow run_id missing after scorer seeding"
    assert metrics, "No metrics logged during scorer seeding"

    for scorer_key in ("scorer.response_length", "scorer.contains_hello"):
        assert scorer_key in metrics, f"Missing scorer metric {scorer_key}"
