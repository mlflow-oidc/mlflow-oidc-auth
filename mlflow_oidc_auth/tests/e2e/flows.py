"""Protocol flows the e2e suite drives: an interactive login, and the calls a signed-in browser makes."""

from __future__ import annotations

import concurrent.futures
import threading
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from mlflow_oidc_auth.tests.e2e.browser import Browser, is_ui_redirect, parse_forms
from mlflow_oidc_auth.tests.e2e.harness import PASSWORDS, AppServer, keycloak_verify

SESSION_COOKIE = "session"
API_HEADERS = {"Accept": "application/json"}
CURRENT_USER = "/api/2.0/mlflow/users/current"


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def new_browser() -> Browser:
    return Browser(verify=keycloak_verify())


def landing_url(response: httpx.Response) -> str:
    """Where ``response`` puts the browser: its ``Location`` if it redirects, else its own URL.

    Flows stop *at* a redirect into the SPA instead of loading it (see ``Browser.follow``), so
    "the user landed on the login page" is this URL, not a rendered page.
    """
    if response.status_code in (301, 302, 303, 307, 308):
        return urljoin(str(response.url), response.headers["location"])
    return str(response.url)


def drive_to_app(browser: Browser, response: httpx.Response, app: AppServer, username: Optional[str] = None) -> httpx.Response:
    """Play the browser's part until it is back on the app.

    Returns the app's non-redirect response, or — when the flow ends in the plugin's SPA — the
    redirect into it, unfollowed (use ``landing_url``). Handles every page Keycloak shows on the
    way: its login form (credentials for ``username``), the SAML HTTP-POST auto-submit form (posted
    to the app with no cookies, as a cross-site POST under ``SameSite=Lax`` is), and its logout
    confirmation.
    """
    for _ in range(12):
        response = browser.follow(response)
        if _origin(str(response.url)) == app.url:
            return response
        if is_ui_redirect(response) and _origin(landing_url(response)) == app.url:
            return response
        forms = parse_forms(response.text)
        login = next((form for form in forms if form.attrs.get("id") == "kc-form-login"), None)
        if login is not None:
            assert username is not None, f"Keycloak asked for credentials at {response.url} but no user was given"
            assert "Invalid username or password" not in response.text, f"Keycloak refused the credentials for {username}"
            response = browser.submit(response, login, {"username": username, "password": PASSWORDS[username]})
            continue
        saml = next((form for form in forms if "SAMLResponse" in form.fields or "SAMLRequest" in form.fields), None)
        if saml is not None:
            to_app = _origin(saml.action) == app.url
            response = browser.submit(response, saml, cookies=not to_app)
            continue
        confirm = next((form for form in forms if "logout" in form.action), None)
        if confirm is not None:
            response = browser.submit(response, confirm)
            continue
        raise AssertionError(f"unexpected page at {response.url} ({response.status_code}):\n{response.text[:3000]}")
    raise AssertionError("the flow did not return to the app")


def login(app: AppServer, username: str, provider: str = "default", browser: Optional[Browser] = None) -> Browser:
    """Log ``username`` in through ``provider``, returning the browser that holds the session."""
    browser = browser or new_browser()
    path = "/login" if provider == "default" else f"/login/{provider}"
    start = browser.get(f"{app.url}{path}")
    assert start.status_code == 302, f"{path} answered {start.status_code}: {start.text[:500]}"
    drive_to_app(browser, start, app, username)
    return browser


def session_cookie(browser: Browser) -> Optional[str]:
    return browser.cookie(SESSION_COOKIE, host="127.0.0.1")


def api_get(app: AppServer, path: str, cookie: Optional[str] = None, **kwargs) -> httpx.Response:
    """One request with exactly the given session cookie (or none), outside any browser jar."""
    headers = dict(API_HEADERS)
    if cookie is not None:
        headers["Cookie"] = f"{SESSION_COOKIE}={cookie}"
    return httpx.get(f"{app.url}{path}", headers=headers, timeout=60.0, **kwargs)


def auth_status(app: AppServer, cookie: Optional[str]) -> dict:
    """``/auth/status`` for ``cookie``. The route sits behind the auth middleware, so a cookie that
    does not authenticate gets a 401 rather than ``authenticated: false``; both mean the same here.
    """
    response = api_get(app, "/auth/status", cookie)
    if response.status_code == 401:
        return {"authenticated": False, "username": None}
    assert response.status_code == 200, response.text
    return response.json()


def concurrent_get(app: AppServer, path: str, cookie: str, count: int) -> List[httpx.Response]:
    """``count`` requests with the same session cookie, released together."""
    barrier = threading.Barrier(count)

    def one(_):
        with httpx.Client(timeout=60.0) as client:
            barrier.wait()
            return client.get(f"{app.url}{path}", headers={**API_HEADERS, "Cookie": f"{SESSION_COOKIE}={cookie}"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(one, range(count)))
