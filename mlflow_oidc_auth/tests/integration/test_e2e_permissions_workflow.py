"""End-to-end integration test for mlflow-oidc-auth permissions.

This test exercises a full workflow against a *running* mlflow-oidc-auth server:
- Authenticate 5 users (via the built-in OIDC UI flow)
- Each user creates their own prompt, registered model, and experiment
- User1 grants user-level permissions on *their* resources to users 2..5
- Verify access controls:
  - READ: can view, cannot modify, cannot manage permissions
  - EDIT: can modify data, cannot delete, cannot manage permissions
  - MANAGE: can manage permissions
  - NO_PERMISSIONS: cannot see or modify

How to run (server must be running separately):
    pytest -q mlflow_oidc_auth/tests/integration/test_e2e_permissions_workflow.py

Environment variables:
  MLFLOW_OIDC_E2E_BASE_URL: base URL for the running server (default: http://localhost:8080/)

Dependencies:
  - playwright (Python package)
  - Playwright browsers installed (e.g. `playwright install chromium`)

Notes:
    - These integration tests live under `mlflow_oidc_auth/tests/integration`.
    - Denials may surface as 401/403/404 depending on MLflow handler behavior.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote, urljoin

import httpx
import pytest


@dataclass(frozen=True)
class User:
    """Test user identity."""

    email: str


@dataclass(frozen=True)
class Resources:
    """Per-user resources created during the test."""

    experiment_name: str
    model_name: str
    prompt_name: str


def _base_url() -> str:
    url = os.environ.get("MLFLOW_OIDC_E2E_BASE_URL", "http://localhost:8080/")
    if not url.endswith("/"):
        url += "/"
    return url


def _require_server(base_url: str) -> None:
    """Skip the test if the server is not reachable."""

    require = os.environ.get("MLFLOW_OIDC_E2E_REQUIRE", "0").lower() in {"1", "true", "t", "yes", "y"}

    try:
        # Prefer FastAPI-native health endpoint to avoid falling through to the
        # mounted MLflow WSGI app (older deployments may not serve `/health`).
        response = httpx.get(urljoin(base_url, "health/live"), timeout=5.0)
    except Exception as exc:  # pragma: no cover
        message = f"E2E server not reachable at {base_url}: {exc}"
        if require:
            raise AssertionError(message)
        pytest.skip(message)

    if response.status_code != 200:
        message = f"E2E server health check failed: {response.status_code} {response.text}"
        if require:
            raise AssertionError(message)
        pytest.skip(message)


def _deny_expected(status_code: int) -> bool:
    """Return True when a denied access code is observed."""

    return status_code in (401, 403, 404)


def _assert_denied(response: httpx.Response, context: str) -> None:
    assert _deny_expected(response.status_code), f"Expected denial for {context}, got {response.status_code}: {response.text}"


def _assert_ok(response: httpx.Response, context: str) -> None:
    assert response.status_code == 200, f"Expected 200 for {context}, got {response.status_code}: {response.text}"


def _create_experiment(client: httpx.Client, base_url: str, experiment_name: str) -> str:
    """Create an MLflow experiment and return experiment_id."""

    get_api = "ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name="
    create_api = "ajax-api/2.0/mlflow/experiments/create"

    get_resp = client.get(urljoin(base_url, get_api) + quote(experiment_name))
    if get_resp.status_code == 200:
        payload = get_resp.json()
        exp = payload.get("experiment", payload)
        experiment_id = exp.get("experiment_id") or exp.get("experimentId") or exp.get("id")
        assert experiment_id, f"Could not parse experiment_id from: {payload}"
        return str(experiment_id)

    if get_resp.status_code != 404:
        raise AssertionError(f"Unexpected get-by-name status {get_resp.status_code}: {get_resp.text}")

    create_resp = client.post(urljoin(base_url, create_api), json={"name": experiment_name})
    _assert_ok(create_resp, f"create experiment {experiment_name}")

    # Re-fetch to obtain id consistently.
    get_resp2 = client.get(urljoin(base_url, get_api) + quote(experiment_name))
    _assert_ok(get_resp2, f"get experiment {experiment_name}")
    payload2 = get_resp2.json()
    exp2 = payload2.get("experiment", payload2)
    experiment_id2 = exp2.get("experiment_id") or exp2.get("experimentId") or exp2.get("id")
    assert experiment_id2, f"Could not parse experiment_id from: {payload2}"
    return str(experiment_id2)


def _create_registered_model(client: httpx.Client, base_url: str, model_name: str) -> None:
    """Create an MLflow registered model."""

    get_api = "ajax-api/2.0/mlflow/registered-models/get?name="
    create_api = "ajax-api/2.0/mlflow/registered-models/create"

    get_resp = client.get(urljoin(base_url, get_api) + quote(model_name))
    if get_resp.status_code == 200:
        return
    if get_resp.status_code != 404:
        raise AssertionError(f"Unexpected model get status {get_resp.status_code}: {get_resp.text}")

    create_resp = client.post(urljoin(base_url, create_api), json={"name": model_name})
    _assert_ok(create_resp, f"create model {model_name}")


def _create_prompt(client: httpx.Client, base_url: str, prompt_name: str, prompt_text: str) -> None:
    """Create an MLflow Prompt (implemented as a registered model + version tags)."""

    get_api = "ajax-api/2.0/mlflow/registered-models/get?name="
    create_api = "ajax-api/2.0/mlflow/registered-models/create"
    create_version_api = "ajax-api/2.0/mlflow/model-versions/create"

    get_resp = client.get(urljoin(base_url, get_api) + quote(prompt_name))
    if get_resp.status_code != 404:
        # If already exists, we don't try to mutate it here (avoid bleeding state).
        if get_resp.status_code == 200:
            return
        raise AssertionError(f"Unexpected prompt get status {get_resp.status_code}: {get_resp.text}")

    create_resp = client.post(
        urljoin(base_url, create_api),
        json={"name": prompt_name, "tags": [{"key": "mlflow.prompt.is_prompt", "value": "true"}]},
    )
    _assert_ok(create_resp, f"create prompt {prompt_name}")

    version_resp = client.post(
        urljoin(base_url, create_version_api),
        json={
            "name": prompt_name,
            "description": "e2e commit",
            "source": "e2e-source",
            "tags": [
                {"key": "mlflow.prompt.is_prompt", "value": "true"},
                {"key": "mlflow.prompt.text", "value": prompt_text},
            ],
        },
    )
    _assert_ok(version_resp, f"create prompt version {prompt_name}")


def _create_run(client: httpx.Client, base_url: str, experiment_id: str) -> httpx.Response:
    """Attempt to create a run in an experiment."""

    api = "api/2.0/mlflow/runs/create"
    payload: dict[str, Any] = {
        "experiment_id": experiment_id,
        "start_time": int(time.time() * 1000),
        "tags": [{"key": "mlflow.runName", "value": f"e2e-run-{uuid.uuid4().hex[:8]}"}],
    }
    return client.post(urljoin(base_url, api), json=payload)


def _update_registered_model_description(client: httpx.Client, base_url: str, model_name: str, description: str) -> httpx.Response:
    api = "ajax-api/2.0/mlflow/registered-models/update"
    return client.patch(urljoin(base_url, api), json={"name": model_name, "description": description})


def _delete_registered_model(client: httpx.Client, base_url: str, model_name: str) -> httpx.Response:
    api = "ajax-api/2.0/mlflow/registered-models/delete"
    # NOTE: Some httpx versions don't accept `json=` on convenience .delete().
    return client.request("DELETE", urljoin(base_url, api), json={"name": model_name})


def _create_prompt_version(client: httpx.Client, base_url: str, prompt_name: str, prompt_text: str) -> httpx.Response:
    api = "ajax-api/2.0/mlflow/model-versions/create"
    return client.post(
        urljoin(base_url, api),
        json={
            "name": prompt_name,
            "description": "e2e edit",
            "source": "e2e-source-edit",
            "tags": [
                {"key": "mlflow.prompt.is_prompt", "value": "true"},
                {"key": "mlflow.prompt.text", "value": prompt_text},
            ],
        },
    )


def _grant_experiment_permission(client: httpx.Client, base_url: str, experiment_id: str, target_user: str, permission: str) -> None:
    api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/experiments/{quote(experiment_id)}"
    resp = client.patch(urljoin(base_url, api), json={"permission": permission})
    if resp.status_code == 404:
        resp = client.post(urljoin(base_url, api), json={"permission": permission})
    assert resp.status_code in (200, 201), f"Failed to grant experiment {permission} to {target_user}: {resp.status_code} {resp.text}"


def _grant_registered_model_permission(client: httpx.Client, base_url: str, model_name: str, target_user: str, permission: str) -> None:
    api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/registered-models/{quote(model_name)}"
    resp = client.patch(urljoin(base_url, api), json={"permission": permission})
    if resp.status_code == 404:
        resp = client.post(urljoin(base_url, api), json={"permission": permission})
    assert resp.status_code in (200, 201), f"Failed to grant model {permission} to {target_user}: {resp.status_code} {resp.text}"


def _grant_prompt_permission(client: httpx.Client, base_url: str, prompt_name: str, target_user: str, permission: str) -> None:
    api = f"api/2.0/mlflow/permissions/users/{quote(target_user)}/prompts/{quote(prompt_name)}"
    resp = client.patch(urljoin(base_url, api), json={"permission": permission})
    if resp.status_code == 404:
        resp = client.post(urljoin(base_url, api), json={"permission": permission})
    assert resp.status_code in (200, 201), f"Failed to grant prompt {permission} to {target_user}: {resp.status_code} {resp.text}"


def _get_registered_model(client: httpx.Client, base_url: str, model_name: str) -> httpx.Response:
    api = "ajax-api/2.0/mlflow/registered-models/get?name="
    return client.get(urljoin(base_url, api) + quote(model_name))


def _get_experiment_by_name(client: httpx.Client, base_url: str, experiment_name: str) -> httpx.Response:
    api = "ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name="
    return client.get(urljoin(base_url, api) + quote(experiment_name))


def _login_via_playwright(user_email: str, base_url: str) -> httpx.Cookies:
    """Perform UI login using Playwright and return httpx cookies.

    We import Playwright lazily so the test suite can skip if it isn't installed.
    """

    playwright_sync = pytest.importorskip("playwright.sync_api")
    sync_playwright = playwright_sync.sync_playwright

    # Reuse the existing integration login logic as closely as possible.
    # The exact HTML is controlled by the running server.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(base_url)
            page.wait_for_load_state("networkidle")

            # Find and click "Login" if present.
            login_buttons = page.locator("button").filter(has_text="Login")
            if login_buttons.count() > 0:
                login_buttons.first.click()
                page.wait_for_load_state("networkidle")

            # Enter the user identity into the provider UI.
            username_field = page.locator("input[name='sub']").or_(page.locator("input[type='text']")).first
            assert username_field.is_visible(), f"Login page did not expose a username field for {user_email}"
            username_field.fill(user_email)

            # Click Authorize/Submit.
            auth_buttons = page.locator("button").filter(has_text="Authorize").or_(page.locator("button[type='submit']"))
            assert auth_buttons.count() > 0, f"Login page did not expose an authorize button for {user_email}"
            auth_buttons.first.click()
            page.wait_for_load_state("networkidle")

            cookies = context.cookies()
            httpx_cookies = httpx.Cookies()
            for cookie in cookies:
                name = cookie.get("name")
                value = cookie.get("value")
                if name and value:
                    httpx_cookies.set(name, value)
            assert len(httpx_cookies.jar) > 0, f"No cookies returned after login for {user_email}"
            return httpx_cookies
        finally:
            context.close()
            browser.close()


@pytest.mark.integration
def test_e2e_permissions_workflow() -> None:
    """Full 5-user workflow with user-level permissions and access assertions."""

    base_url = _base_url()
    _require_server(base_url)

    # Users 1..5 are "regular" users in the example data.
    user1 = User("alice@example.com")
    user2 = User("bob@example.com")
    user3 = User("charlie@example.com")
    user4 = User("dave@example.com")
    user5 = User("eve@example.com")

    run_id = uuid.uuid4().hex[:10]

    # Authenticate each user and create per-user resources.
    cookies: dict[str, httpx.Cookies] = {}
    resources: dict[str, Resources] = {}

    for user in (user1, user2, user3, user4, user5):
        cookies[user.email] = _login_via_playwright(user.email, base_url)
        with httpx.Client(cookies=cookies[user.email], timeout=30.0, follow_redirects=True) as client:
            r = Resources(
                experiment_name=f"{user.email}-exp-{run_id}",
                model_name=f"{user.email}-model-{run_id}",
                prompt_name=f"{user.email}-prompt-{run_id}",
            )

            experiment_id = _create_experiment(client, base_url, r.experiment_name)
            _create_registered_model(client, base_url, r.model_name)
            _create_prompt(client, base_url, r.prompt_name, prompt_text=f"prompt text for {user.email} {run_id}")

            resources[user.email] = r
            # Sanity: creator should be able to create a run in their own experiment.
            run_resp = _create_run(client, base_url, experiment_id)
            assert run_resp.status_code == 200, f"Owner could not create run: {run_resp.status_code} {run_resp.text}"

    # Resolve user1 experiment_id for subsequent permission grants.
    with httpx.Client(cookies=cookies[user1.email], timeout=30.0, follow_redirects=True) as client1:
        user1_exp_resp = _get_experiment_by_name(client1, base_url, resources[user1.email].experiment_name)
        _assert_ok(user1_exp_resp, "user1 get experiment by name")
        user1_payload = user1_exp_resp.json()
        user1_exp = user1_payload.get("experiment", user1_payload)
        user1_experiment_id = str(user1_exp.get("experiment_id") or user1_exp.get("experimentId") or user1_exp.get("id"))
        assert user1_experiment_id and user1_experiment_id != "None", f"Could not parse user1 experiment_id: {user1_payload}"

        # Grant user-level permissions for ALL user1 resources.
        _grant_experiment_permission(client1, base_url, user1_experiment_id, user2.email, "READ")
        _grant_experiment_permission(client1, base_url, user1_experiment_id, user3.email, "EDIT")
        _grant_experiment_permission(client1, base_url, user1_experiment_id, user4.email, "MANAGE")
        _grant_experiment_permission(client1, base_url, user1_experiment_id, user5.email, "NO_PERMISSIONS")

        _grant_registered_model_permission(client1, base_url, resources[user1.email].model_name, user2.email, "READ")
        _grant_registered_model_permission(client1, base_url, resources[user1.email].model_name, user3.email, "EDIT")
        _grant_registered_model_permission(client1, base_url, resources[user1.email].model_name, user4.email, "MANAGE")
        _grant_registered_model_permission(client1, base_url, resources[user1.email].model_name, user5.email, "NO_PERMISSIONS")

        _grant_prompt_permission(client1, base_url, resources[user1.email].prompt_name, user2.email, "READ")
        _grant_prompt_permission(client1, base_url, resources[user1.email].prompt_name, user3.email, "EDIT")
        _grant_prompt_permission(client1, base_url, resources[user1.email].prompt_name, user4.email, "MANAGE")
        _grant_prompt_permission(client1, base_url, resources[user1.email].prompt_name, user5.email, "NO_PERMISSIONS")

    # --- Validate user2 (READ) ---
    with httpx.Client(cookies=cookies[user2.email], timeout=30.0, follow_redirects=True) as client2:
        # Can view
        _assert_ok(_get_experiment_by_name(client2, base_url, resources[user1.email].experiment_name), "user2 read experiment")
        _assert_ok(_get_registered_model(client2, base_url, resources[user1.email].model_name), "user2 read model")
        _assert_ok(_get_registered_model(client2, base_url, resources[user1.email].prompt_name), "user2 read prompt")

        # Cannot modify data
        _assert_denied(_create_run(client2, base_url, user1_experiment_id), "user2 create run")
        _assert_denied(
            _update_registered_model_description(client2, base_url, resources[user1.email].model_name, "user2 should not update"),
            "user2 update model description",
        )
        _assert_denied(
            _create_prompt_version(client2, base_url, resources[user1.email].prompt_name, "user2 should not update"),
            "user2 create prompt version",
        )

        # Cannot manage permissions (attempt: upgrade themselves)
        resp = client2.patch(
            urljoin(
                base_url,
                f"api/2.0/mlflow/permissions/users/{quote(user2.email)}/registered-models/{quote(resources[user1.email].model_name)}",
            ),
            json={"permission": "MANAGE"},
        )
        _assert_denied(resp, "user2 self-upgrade permissions")

    # --- Validate user3 (EDIT) ---
    with httpx.Client(cookies=cookies[user3.email], timeout=30.0, follow_redirects=True) as client3:
        # Can view
        _assert_ok(_get_experiment_by_name(client3, base_url, resources[user1.email].experiment_name), "user3 view experiment")

        # Can modify data
        run_resp = _create_run(client3, base_url, user1_experiment_id)
        _assert_ok(run_resp, "user3 create run")

        update_resp = _update_registered_model_description(client3, base_url, resources[user1.email].model_name, "user3 edit")
        _assert_ok(update_resp, "user3 update model")

        prompt_ver_resp = _create_prompt_version(client3, base_url, resources[user1.email].prompt_name, "user3 edited prompt")
        _assert_ok(prompt_ver_resp, "user3 update prompt")

        # Cannot delete
        _assert_denied(_delete_registered_model(client3, base_url, resources[user1.email].model_name), "user3 delete model")

        # Cannot manage permissions
        resp = client3.patch(
            urljoin(
                base_url,
                f"api/2.0/mlflow/permissions/users/{quote(user5.email)}/experiments/{quote(user1_experiment_id)}",
            ),
            json={"permission": "READ"},
        )
        _assert_denied(resp, "user3 manage permissions")

    # --- Validate user4 (MANAGE) ---
    with httpx.Client(cookies=cookies[user4.email], timeout=30.0, follow_redirects=True) as client4:
        # Can view
        _assert_ok(_get_experiment_by_name(client4, base_url, resources[user1.email].experiment_name), "user4 view experiment")

        # Can manage permissions: grant user5 READ (was NO_PERMISSIONS)
        resp = client4.patch(
            urljoin(
                base_url,
                f"api/2.0/mlflow/permissions/users/{quote(user5.email)}/registered-models/{quote(resources[user1.email].model_name)}",
            ),
            json={"permission": "READ"},
        )
        assert resp.status_code in (200, 201), f"Expected user4 to manage permissions, got {resp.status_code}: {resp.text}"

    # --- Validate user5 (NO_PERMISSIONS initially) ---
    with httpx.Client(cookies=cookies[user5.email], timeout=30.0, follow_redirects=True) as client5:
        # The exact denial code may vary (401/403/404). We accept any denial.
        _assert_denied(_get_experiment_by_name(client5, base_url, resources[user1.email].experiment_name), "user5 view experiment")
        _assert_denied(_get_registered_model(client5, base_url, resources[user1.email].prompt_name), "user5 view prompt")

        # NOTE: after user4 granted user5 READ to the *model*, user5 should now be able to see the model.
        model_get = _get_registered_model(client5, base_url, resources[user1.email].model_name)
        _assert_ok(model_get, "user5 view model after user4 grant")

        # But user5 still should not be able to modify it.
        _assert_denied(
            _update_registered_model_description(client5, base_url, resources[user1.email].model_name, "user5 should not update"),
            "user5 update model",
        )
