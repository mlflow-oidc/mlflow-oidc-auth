"""Pytest fixtures for MLflow OIDC Auth integration tests.

These fixtures provide session-scoped resources for E2E testing against a running
mlflow-oidc-auth server with OIDC mock provider at https://oidc-mock.technicaldomain.xyz/
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Generator
from urllib.parse import urljoin

import httpx
import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page, BrowserContext

from .users import get_admin_users, get_mlflow_users


def _should_require_server() -> bool:
    """Return True when the test run should fail instead of skip if the server is unreachable."""

    return os.environ.get("MLFLOW_OIDC_E2E_REQUIRE", "0").lower() in {"1", "true", "t", "yes", "y"}


@pytest.fixture(scope="session")
def base_url() -> str:
    """Normalized base URL for the running mlflow-oidc-auth server."""

    url = os.environ.get("MLFLOW_OIDC_E2E_BASE_URL", "http://localhost:8080/")
    return url if url.endswith("/") else f"{url}/"


@pytest.fixture(scope="session")
def ensure_server(base_url: str) -> None:
    """Skip (or fail) the session if the target server health check is not reachable."""

    require = _should_require_server()
    try:
        response = httpx.get(urljoin(base_url, "health/live"), timeout=5.0)
    except Exception as exc:  # pragma: no cover - network dependent
        message = f"E2E server not reachable at {base_url}: {exc}"
        if require:
            pytest.fail(message)
        pytest.skip(message)

    if response.status_code != 200:
        message = f"E2E server health check failed: {response.status_code} {response.text}"
        if require:
            pytest.fail(message)
        pytest.skip(message)


@pytest.fixture(scope="session")
def test_run_id() -> str:
    """Unique identifier for this test run to avoid resource name collisions."""

    return uuid.uuid4().hex[:10]


@pytest.fixture(scope="session")
def admin_email() -> str:
    """Email of the admin user for tests."""

    admins = get_admin_users()
    assert admins, "No admin users configured in users.py"
    return admins[0]  # frank@example.com


@pytest.fixture(scope="session")
def playwright_browser(ensure_server: None) -> Generator:
    """Session-scoped Playwright browser instance."""

    playwright_sync = pytest.importorskip("playwright.sync_api")

    with playwright_sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def browser_context(playwright_browser) -> Generator["BrowserContext", None, None]:
    """Function-scoped browser context for isolated test sessions."""

    context = playwright_browser.new_context()
    yield context
    context.close()


@pytest.fixture(scope="function")
def browser_page(browser_context: "BrowserContext") -> Generator["Page", None, None]:
    """Function-scoped browser page."""

    page = browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="session")
def admin_cookies(playwright_browser, base_url: str, admin_email: str) -> httpx.Cookies:
    """Session-scoped admin cookies for API calls requiring admin privileges."""

    from .utils import user_login

    context = playwright_browser.new_context()
    page = context.new_page()
    try:
        cookies = user_login(page, admin_email, url=base_url)
        assert cookies.jar, f"Login failed for admin {admin_email}; no cookies returned"
        return cookies
    finally:
        page.close()
        context.close()


@pytest.fixture(scope="session")
def user_cookies_factory(playwright_browser, base_url: str):
    """Factory fixture to get cookies for any user by email."""

    from .utils import user_login

    _cache: dict[str, httpx.Cookies] = {}

    def _get_cookies(email: str) -> httpx.Cookies:
        if email not in _cache:
            context = playwright_browser.new_context()
            page = context.new_page()
            try:
                cookies = user_login(page, email, url=base_url)
                _cache[email] = cookies
            finally:
                page.close()
                context.close()
        return _cache[email]

    return _get_cookies


@pytest.fixture(scope="session")
def http_client_factory(user_cookies_factory, base_url: str):
    """Factory fixture to create httpx.Client with user authentication."""

    def _create_client(email: str) -> httpx.Client:
        cookies = user_cookies_factory(email)
        return httpx.Client(cookies=cookies, base_url=base_url, timeout=30.0, follow_redirects=True)

    return _create_client
