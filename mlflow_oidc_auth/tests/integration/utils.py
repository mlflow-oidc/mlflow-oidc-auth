import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
import mlflow
from mlflow.entities import Feedback
from mlflow.genai.scorers import scorer as scorer_decorator
from mlflow.tracking import MlflowClient
from playwright.sync_api import Cookie

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from playwright.sync_api import sync_playwright, Page
from urllib.parse import quote


def bake_cookies(cookies: List[Cookie]) -> httpx.Cookies:
    ready_cookies = httpx.Cookies()
    for cookie in cookies:
        if "value" in cookie:
            name = cookie.get("name")
            if name is not None:
                value = cookie.get("value")
                if value is not None:
                    ready_cookies.set(name, value)
    return ready_cookies


def create_experiment(
    experiment_name: str,
    cookies,
    url: str = "http://localhost:8080/",
    create_api: str = "ajax-api/2.0/mlflow/experiments/create",
    get_api: str = "ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name=",
) -> bool:
    respone = httpx.get(url=urljoin(url, get_api) + quote(experiment_name), cookies=cookies)
    if respone.status_code == 200:
        print(f"Experiment {experiment_name} already exists")
        return True
    if respone.status_code == 404:
        respone = httpx.post(
            url=urljoin(url, create_api),
            json={"name": experiment_name},
            cookies=cookies,
        )
        if respone.status_code == 200:
            print(f"Experiment {experiment_name} created")
            return True
        else:
            print(f"Experiment {experiment_name} not created")
            return False
    return False


def _build_seed_scorers() -> list[Any]:
    """Return a small set of demo scorers used when seeding test data."""

    @scorer_decorator
    def response_length(outputs: dict[str, Any] | None = None) -> Feedback:
        text = (outputs or {}).get("response", "")
        length = len(text)
        return Feedback(
            value=length,
            rationale=f"Response length = {length}",
            metadata={"chars": length},
        )

    @scorer_decorator
    def contains_hello(outputs: dict[str, Any] | None = None) -> Feedback:
        text = (outputs or {}).get("response", "").lower()
        found = "hello" in text
        return Feedback(value=found, rationale=f"'hello' present: {found}", metadata={})

    return [response_length, contains_hello]


def create_model(
    model_name: str,
    cookies,
    url: str = "http://localhost:8080/",
    create_api: str = "ajax-api/2.0/mlflow/registered-models/create",
    get_api: str = "ajax-api/2.0/mlflow/registered-models/get?name=",
) -> bool:
    respone = httpx.get(url=urljoin(url, get_api) + quote(model_name), cookies=cookies)
    print(respone.status_code)
    if respone.status_code == 404:
        respone = httpx.post(url=urljoin(url, create_api), json={"name": model_name}, cookies=cookies)
        if respone.status_code == 200:
            print(f"Model {model_name} created")
            return True
        else:
            print(f"Model {model_name} not created")
            return False
    print(f"Model {model_name} already exists")
    return True


def create_prompt(
    prompt_name: str,
    prompt_text: str,
    cookies,
    url: str = "http://localhost:8080/",
    create_api: str = "ajax-api/2.0/mlflow/registered-models/create",
    create_version_api: str = "ajax-api/2.0/mlflow/model-versions/create",
    get_api: str = "ajax-api/2.0/mlflow/registered-models/get?name=",
    commit_message: str = "commit message here",
    source: str = "dummy-source",
) -> bool:
    respone = httpx.get(url=urljoin(url, get_api) + prompt_name, cookies=cookies)
    print(respone.status_code)
    if respone.status_code == 404:
        respone = httpx.post(
            url=urljoin(url, create_api),
            json={
                "name": prompt_name,
                "tags": [{"key": "mlflow.prompt.is_prompt", "value": "true"}],
            },
            cookies=cookies,
        )
        if respone.status_code == 200:
            print(f"Prompt {prompt_name} created")
            # Now create the version with the prompt text
            respone = httpx.post(
                url=urljoin(url, create_version_api),
                json={
                    "name": prompt_name,
                    "description": commit_message,
                    "source": source,
                    "tags": [
                        {"key": "mlflow.prompt.is_prompt", "value": "true"},
                        {"key": "mlflow.prompt.text", "value": prompt_text},
                    ],
                },
                cookies=cookies,
            )
            if respone.status_code == 200:
                print(f"Prompt version for {prompt_name} created")
                return True
            else:
                print(f"Prompt version for {prompt_name} not created")
                return False
        else:
            print(f"Prompt {prompt_name} not created")
            return False
    print(f"Prompt {prompt_name} already exists")
    return True


def register_sample_scorers(
    experiment_name: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
    register_api: str = "ajax-api/2.0/mlflow/scorers/register",
) -> Tuple[bool, bool]:
    """
    Register a couple of demo scorers for an experiment so E2E tests have scorer data.

    Returns (success, missing_endpoint). missing_endpoint is True when the registration
    endpoint responds with 404, allowing callers to skip when unsupported.
    """

    experiment_id = get_experiment_id(experiment_name, cookies, url=url)
    if not experiment_id:
        logger.warning("Could not resolve experiment id for %s", experiment_name)
        return False, False

    success = True
    missing_endpoint = False
    for scorer_obj in _build_seed_scorers():
        payload = {
            "experiment_id": experiment_id,
            "name": scorer_obj.name,
            "serialized_scorer": scorer_obj.model_dump_json(),
        }
        response = httpx.post(url=urljoin(url, register_api), json=payload, cookies=cookies)
        if response.status_code == 404:
            logger.warning(
                "Scorer registration endpoint missing for %s: %s %s",
                experiment_name,
                response.status_code,
                response.text,
            )
            missing_endpoint = True
            break
        if response.status_code not in (200, 409):
            logger.warning(
                "Failed to register scorer %s for %s: %s %s",
                scorer_obj.name,
                experiment_name,
                response.status_code,
                response.text,
            )
            success = False
    return success, missing_endpoint


def create_service_account(
    username: str,
    display_name: str,
    cookies: httpx.Cookies,
    base_url: str,
    users_api: str = "api/2.0/mlflow/users",
) -> tuple[bool, str]:
    """Create a service account via the admin session cookies."""

    payload = {
        "username": username,
        "display_name": display_name,
        "is_admin": False,
        "is_service_account": True,
    }
    response = httpx.post(url=urljoin(base_url, users_api), json=payload, cookies=cookies, timeout=10.0)
    if response.status_code in (200, 201):
        return True, response.json().get("message", "created") if response.headers.get("content-type", "").startswith("application/json") else "created"

    return False, f"{response.status_code}: {response.text}"


def create_access_token_for_user(
    username: str,
    cookies: httpx.Cookies,
    base_url: str,
    access_token_api: str = "api/2.0/mlflow/users/access-token",
) -> tuple[bool, str]:
    """Request an access token for the target user using admin cookies."""

    response = httpx.patch(
        url=urljoin(base_url, access_token_api),
        json={"username": username},
        cookies=cookies,
        timeout=10.0,
    )
    if response.status_code == 404:
        return False, "access-token endpoint unavailable"

    if response.status_code not in (200, 201):
        return False, f"{response.status_code}: {response.text}"

    try:
        payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"Invalid JSON response: {exc}"

    token = payload.get("token") if isinstance(payload, dict) else None
    if not token:
        return False, f"Token missing in response: {payload}"

    return True, token


def _normalize_metric_value(value: Any) -> float:
    """Normalize feedback values to floats for MLflow metrics."""

    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    return float(len(str(value)))


def seed_scorers_with_tracking_token(
    experiment_name: str,
    token: str,
    base_url: str,
    response_text: str = "Hello from integration",
    username: str | None = None,
) -> tuple[str, Dict[str, float]]:
    """Seed scorer metrics by running an MLflow job authenticated via access token.

    Uses Basic auth: username + token as password.
    """
    env_backup = {
        "MLFLOW_TRACKING_USERNAME": os.environ.get("MLFLOW_TRACKING_USERNAME"),
        "MLFLOW_TRACKING_PASSWORD": os.environ.get("MLFLOW_TRACKING_PASSWORD"),
        "MLFLOW_TRACKING_URI": os.environ.get("MLFLOW_TRACKING_URI"),
    }

    if username:
        os.environ["MLFLOW_TRACKING_USERNAME"] = username
        os.environ["MLFLOW_TRACKING_PASSWORD"] = token
    os.environ["MLFLOW_TRACKING_URI"] = base_url.rstrip("/")

    try:
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name=f"seed-scorers-{experiment_name}") as run:
            for scorer_obj in _build_seed_scorers():
                feedback = scorer_obj({"response": response_text})
                value = _normalize_metric_value(feedback.value)
                mlflow.log_metric(f"scorer.{scorer_obj.name}", value)

            run_id = run.info.run_id

        client = MlflowClient()
        metrics = client.get_run(run_id).data.metrics
        return run_id, metrics
    finally:
        if env_backup["MLFLOW_TRACKING_USERNAME"] is not None:
            os.environ["MLFLOW_TRACKING_USERNAME"] = env_backup["MLFLOW_TRACKING_USERNAME"]
        else:
            os.environ.pop("MLFLOW_TRACKING_USERNAME", None)

        if env_backup["MLFLOW_TRACKING_PASSWORD"] is not None:
            os.environ["MLFLOW_TRACKING_PASSWORD"] = env_backup["MLFLOW_TRACKING_PASSWORD"]
        else:
            os.environ.pop("MLFLOW_TRACKING_PASSWORD", None)

        if env_backup["MLFLOW_TRACKING_URI"] is not None:
            os.environ["MLFLOW_TRACKING_URI"] = env_backup["MLFLOW_TRACKING_URI"]
        else:
            os.environ.pop("MLFLOW_TRACKING_URI", None)


def set_experiment_permission(
    experiment_id: str,
    user_email: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set user-level permission for an experiment.

    Returns (success, message). Uses PATCH to update or POST to create.
    """
    api = f"api/2.0/mlflow/permissions/users/{quote(user_email)}/experiments/{quote(experiment_id)}"
    full_url = urljoin(url, api)

    # Try PATCH first (update existing)
    resp = httpx.patch(url=full_url, json={"permission": permission}, cookies=cookies, timeout=10.0)
    if resp.status_code == 200:
        return True, "updated"

    # Try POST (create new)
    if resp.status_code == 404:
        resp = httpx.post(url=full_url, json={"permission": permission}, cookies=cookies, timeout=10.0)
        if resp.status_code in (200, 201):
            return True, "created"

    return False, f"{resp.status_code}: {resp.text}"


def set_model_permission(
    model_name: str,
    user_email: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set user-level permission for a registered model.

    Returns (success, message). Uses PATCH to update or POST to create.
    """
    api = f"api/2.0/mlflow/permissions/users/{quote(user_email)}/registered-models/{quote(model_name)}"
    full_url = urljoin(url, api)

    # Try PATCH first (update existing)
    resp = httpx.patch(url=full_url, json={"permission": permission}, cookies=cookies, timeout=10.0)
    if resp.status_code == 200:
        return True, "updated"

    # Try POST (create new)
    if resp.status_code == 404:
        resp = httpx.post(url=full_url, json={"permission": permission}, cookies=cookies, timeout=10.0)
        if resp.status_code in (200, 201):
            return True, "created"

    return False, f"{resp.status_code}: {resp.text}"


def set_prompt_permission(
    prompt_name: str,
    user_email: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set user-level permission for a prompt.

    Returns (success, message). Prompts use the same registered-models endpoint.
    """
    return set_model_permission(prompt_name, user_email, permission, cookies, url)


def get_experiment_id(
    experiment_name: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
    api: str = "api/2.0/mlflow/experiments",
) -> str:
    """Resolve experiment_id using the get-by-name API (more reliable across deployments)."""

    get_by_name_api = "ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name="
    response = httpx.get(url=urljoin(url, get_by_name_api) + quote(experiment_name), cookies=cookies)
    if response.status_code != 200:
        return ""

    payload = response.json()
    experiment = payload.get("experiment", payload)
    return str(experiment.get("experiment_id") or experiment.get("experimentId") or experiment.get("id") or "")


def set_group_experiment_permission(
    experiment_name: str,
    group_name: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set group-level permission for an experiment.

    Returns (success, message). Success is False when the experiment is not found or the
    endpoint is unavailable; callers can choose to skip on 404s.

    Uses the new RESTful API:
    - POST api/2.0/mlflow/permissions/groups/{group_name}/experiments/{experiment_id} to create
    - DELETE api/2.0/mlflow/permissions/groups/{group_name}/experiments/{experiment_id} to delete
    """

    experiment_id = get_experiment_id(experiment_name, cookies, url=url)
    if not experiment_id:
        return False, f"Experiment {experiment_name} not found"

    # New RESTful API path
    api_url = urljoin(
        url,
        f"api/2.0/mlflow/permissions/groups/{quote(group_name)}/experiments/{quote(experiment_id)}",
    )

    # Delete existing permission first (ignore errors - permission may not exist)
    # Note: Server returns 500 when permission doesn't exist, not 404
    httpx.request(
        method="DELETE",
        url=api_url,
        cookies=cookies,
        timeout=10.0,
    )

    # Create new permission with POST
    set_response = httpx.post(
        url=api_url,
        json={"permission": permission},
        cookies=cookies,
        timeout=10.0,
    )
    if set_response.status_code in (200, 201):
        return True, "ok"

    return False, f"Set failed ({set_response.status_code}): {set_response.text}"
    # http://localhost:8080/api/2.0/mlflow/groups/mlflow-admin/experiments/delete
    # {"experiment_id":"537270198867596775"}
    # set new permissions
    # http://localhost:8080/api/2.0/mlflow/groups/mlflow-admin/experiments/create
    # POST
    # {"experiment_id":"537270198867596775","permission":"READ"}
    # get all experiments
    # http://localhost:8080/api/2.0/mlflow/experiments
    # [
    #     {
    #         "id": "0",
    #         "name": "Default",
    #         "tags": {}
    #     }
    # ]
    # pass


def set_group_model_permission(
    model_name: str,
    group_name: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set group-level permission for a registered model.

    Returns (success, message).

    Uses the new RESTful API:
    - POST api/2.0/mlflow/permissions/groups/{group_name}/registered-models/{name} to create
    - DELETE api/2.0/mlflow/permissions/groups/{group_name}/registered-models/{name} to delete
    """
    # New RESTful API path
    api_url = urljoin(
        url,
        f"api/2.0/mlflow/permissions/groups/{quote(group_name)}/registered-models/{quote(model_name)}",
    )

    # Delete existing permission first (ignore errors - permission may not exist)
    # Note: Server returns 500 when permission doesn't exist, not 404
    httpx.request(
        method="DELETE",
        url=api_url,
        cookies=cookies,
        timeout=10.0,
    )

    # Create new permission with POST
    set_response = httpx.post(
        url=api_url,
        json={"permission": permission},
        cookies=cookies,
        timeout=10.0,
    )
    if set_response.status_code in (200, 201):
        return True, "ok"

    return False, f"Set failed ({set_response.status_code}): {set_response.text}"


def set_group_prompt_permission(
    prompt_name: str,
    group_name: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set group-level permission for a prompt.

    Returns (success, message). Prompts use registered-models endpoint.
    """
    return set_group_model_permission(prompt_name, group_name, permission, cookies, url)


def set_regexp_experiment_permission(
    pattern: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
    api: str = "api/2.0/mlflow/permissions/experiments/regex",
) -> tuple[bool, str]:
    """Set regex-based permission for experiments.

    Returns (success, message).
    """
    full_url = urljoin(url, api)
    resp = httpx.post(
        url=full_url,
        json={"regex": pattern, "permission": permission},
        cookies=cookies,
        timeout=10.0,
    )
    if resp.status_code in (200, 201):
        return True, "created"
    if resp.status_code == 409:
        return True, "already exists"
    return False, f"{resp.status_code}: {resp.text}"


def set_regexp_model_permission(
    pattern: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
    api: str = "api/2.0/mlflow/permissions/registered-models/regex",
) -> tuple[bool, str]:
    """Set regex-based permission for registered models.

    Returns (success, message).
    """
    full_url = urljoin(url, api)
    resp = httpx.post(
        url=full_url,
        json={"regex": pattern, "permission": permission},
        cookies=cookies,
        timeout=10.0,
    )
    if resp.status_code in (200, 201):
        return True, "created"
    if resp.status_code == 409:
        return True, "already exists"
    return False, f"{resp.status_code}: {resp.text}"


def set_regexp_prompt_permission(
    pattern: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set regex-based permission for prompts.

    Returns (success, message). Uses registered-models regex endpoint.
    """
    return set_regexp_model_permission(pattern, permission, cookies, url)


def set_regexp_group_experiment_permission(
    pattern: str,
    group_name: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
    api: str = "api/2.0/mlflow/permissions/groups/{group_name}/experiments/regex",
) -> tuple[bool, str]:
    """Set group-regex permission for experiments.

    Returns (success, message).
    """
    full_url = urljoin(url, api.format(group_name=quote(group_name)))
    resp = httpx.post(
        url=full_url,
        json={"regex": pattern, "permission": permission},
        cookies=cookies,
        timeout=10.0,
    )
    if resp.status_code in (200, 201):
        return True, "created"
    if resp.status_code == 409:
        return True, "already exists"
    return False, f"{resp.status_code}: {resp.text}"


def set_regexp_group_model_permission(
    pattern: str,
    group_name: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
    api: str = "api/2.0/mlflow/permissions/groups/{group_name}/registered-models/regex",
) -> tuple[bool, str]:
    """Set group-regex permission for registered models.

    Returns (success, message).
    """
    full_url = urljoin(url, api.format(group_name=quote(group_name)))
    resp = httpx.post(
        url=full_url,
        json={"regex": pattern, "permission": permission},
        cookies=cookies,
        timeout=10.0,
    )
    if resp.status_code in (200, 201):
        return True, "created"
    if resp.status_code == 409:
        return True, "already exists"
    return False, f"{resp.status_code}: {resp.text}"


def set_regexp_group_prompt_permission(
    pattern: str,
    group_name: str,
    permission: str,
    cookies: httpx.Cookies,
    url: str = "http://localhost:8080/",
) -> tuple[bool, str]:
    """Set group-regex permission for prompts.

    Returns (success, message). Uses registered-models regex endpoint.
    """
    return set_regexp_group_model_permission(pattern, group_name, permission, cookies, url)


def user_login(page: Page, username: str, url: str = "http://localhost:8080/") -> httpx.Cookies:
    """Login user using Playwright and httpx cookies.
    This function navigates to the login page, fills in the username, and returns the cookies."""
    try:
        print(f"🔍 Navigating to {url}")
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # print(f"📸 Taking screenshot of initial page")
        # page.screenshot(path=f"debug-initial-{username}.png")

        print(f"🔍 Looking for login button...")
        # Look for any button containing "login" or "Login"
        login_buttons = page.locator("button").filter(has_text="Login")
        if login_buttons.count() == 0:
            print("❌ No login button found, checking page content...")
            print(f"Page title: {page.title()}")
            print(f"Page URL: {page.url}")

            # Check if we're already on a login page
            if "login" in page.url.lower() or "oauth" in page.url.lower():
                print("✅ Already on login/oauth page")
            else:
                print("❌ Not on login page and no login button found")
                raise Exception("No login button found and not on login page")
        else:
            print(f"✅ Found {login_buttons.count()} login button(s)")
            # Click the first login button
            login_buttons.first.click()
            page.wait_for_load_state("networkidle")
            # print(f"📸 Taking screenshot after login button click")
            # page.screenshot(path=f"debug-after-login-click-{username}.png")

        print(f"🔍 Looking for username field...")
        # Look for username/sub field
        username_field = page.locator("input[name='sub']").or_(page.locator("input[type='text']")).first
        if username_field.is_visible():
            print(f"✅ Found username field, filling with '{username}'")
            username_field.fill(username)
        else:
            print("❌ Username field not found")
            raise Exception("Username field not found")

        # print(f"📸 Taking screenshot after filling username")
        # page.screenshot(path=f"debug-after-username-{username}.png")

        print(f"🔍 Looking for authorize/submit button...")
        # Look for authorize button
        auth_buttons = page.locator("button").filter(has_text="Authorize").or_(page.locator("button[type='submit']"))
        if auth_buttons.count() > 0:
            print(f"✅ Found authorize button, clicking...")
            auth_buttons.first.click()
            page.wait_for_load_state("networkidle")
        else:
            print("❌ Authorize button not found")
            raise Exception("Authorize button not found")

        # print(f"📸 Taking screenshot after authorize")
        # page.screenshot(path=f"debug-after-authorize-{username}.png")

        print(f"✅ Login flow completed for {username}")
        print(f"Final URL: {page.url}")

        cookies = page.context.cookies()
        print(f"🍪 Got {len(cookies)} cookies")
        for cookie in cookies:
            print(f"  - {cookie['name']}: {cookie['value'][:20]}...")  # type: ignore

        return bake_cookies(cookies)

    except Exception as e:
        logger.error(f"Failed to login user {username}: {e}")
        page.screenshot(path=f"debug-error-{username}.png")
        raise
