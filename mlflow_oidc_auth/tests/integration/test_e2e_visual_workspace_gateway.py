"""Visual E2E smoke tests for workspace and gateway authorization behavior.

These tests run against a live dev server and use Playwright for UI validation.
They also verify that direct workspace URL access does not grant unauthorized
Gateway create rights.
"""

from __future__ import annotations

import httpx
import pytest


def _assert_workspace_menu_stable(page) -> None:
    """Validate injected menu links remain visible while toggling workspace selection."""

    page.goto("#/")
    page.wait_for_load_state("networkidle")

    # No workspace selected: custom entries should still be visible.
    assert page.get_by_role("link", name="Permissions").count() == 1
    assert page.get_by_role("link", name="Logout").count() == 1

    # Select default workspace from table and verify Settings appears.
    page.get_by_role("link", name="default").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    assert "workspace=default" in page.url
    assert page.get_by_role("link", name="Settings").count() >= 1
    assert page.get_by_role("link", name="Permissions").count() == 1
    assert page.get_by_role("link", name="Logout").count() == 1

    # Return to no-workspace state and ensure UI is not stuck.
    clear_button = page.get_by_role("button", name="Clear selection")
    if clear_button.count() > 0:
        clear_button.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

    assert page.get_by_role("combobox", name="Workspace, no option selected").count() == 1
    assert page.get_by_role("link", name="Permissions").count() == 1
    assert page.get_by_role("link", name="Logout").count() == 1


def _assert_gateway_create_denied_for_workspace(base_url: str, cookies: httpx.Cookies) -> None:
    """Verify gateway create APIs are denied for users without workspace MANAGE."""

    headers = {"X-MLFLOW-WORKSPACE": "new-ws"}
    payload = {}
    create_paths = (
        "api/3.0/mlflow/gateway/endpoints/create",
        "api/3.0/mlflow/gateway/secrets/create",
        "api/3.0/mlflow/gateway/model-definitions/create",
    )

    with httpx.Client(base_url=base_url, cookies=cookies, timeout=15.0, follow_redirects=True) as client:
        for api_path in create_paths:
            response = client.post(api_path, headers=headers, json=payload)
            assert response.status_code == 403, f"Expected 403 for {api_path}, got {response.status_code}: {response.text}"


@pytest.mark.integration
def test_visual_workspace_navigation_and_gateway_creation_guard(
    base_url: str,
    ensure_server: None,
    playwright_browser,
) -> None:
    """Smoke-test key UI navigation and workspace-gated gateway create behavior."""

    user_login = pytest.importorskip("mlflow_oidc_auth.tests.integration.utils").user_login

    context = playwright_browser.new_context()
    page = context.new_page()
    try:
        eve_cookies = user_login(page, "eve@example.com", url=base_url)

        # Visual checks for workspace toggle behavior and injected menu stability.
        _assert_workspace_menu_stable(page)

        # Direct-link into a workspace should not grant create permissions.
        page.goto("#/?workspace=new-ws")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        _assert_gateway_create_denied_for_workspace(base_url, eve_cookies)
    finally:
        page.close()
        context.close()
