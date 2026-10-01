"""Opt-in ``limit`` / ``offset`` / ``search`` on every list endpoint that supports it.

Each endpoint is driven through a minimal FastAPI app with the auth dependencies overridden and
its data source patched. For every endpoint the same contract is checked:

* no parameters — the body is exactly what it was, in its original order, with no header;
* ``limit=2&offset=0`` — two items in display-key order, ``X-Total-Count`` is the full count;
* ``offset`` past the end — an empty page with the right total;
* ``search`` — case-insensitive substring filter, with or without ``limit``;
* out-of-range values — 422, never a 500.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from mlflow.store.entities.paged_list import PagedList
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.repository.scim_token import ScimTokenRecord
from mlflow_oidc_auth.repository.user_token import UserTokenRecord
from mlflow_oidc_auth.routers import webhook as webhook_module
from mlflow_oidc_auth.routers._prefix import (
    EXPERIMENT_PERMISSIONS_ROUTER_PREFIX,
    GATEWAY_PERMISSIONS_ROUTER_PREFIX,
    GROUP_PERMISSIONS_ROUTER_PREFIX,
    PROMPT_PERMISSIONS_ROUTER_PREFIX,
    REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX,
    SCIM_TOKENS_ROUTER_PREFIX,
    TRASH_ROUTER_PREFIX,
    USERS_ROUTER_PREFIX,
    WEBHOOK_ROUTER_PREFIX,
)
from mlflow_oidc_auth.routers.experiment_permissions import experiment_permissions_router
from mlflow_oidc_auth.routers.gateway_endpoint_permissions import gateway_endpoint_permissions_router
from mlflow_oidc_auth.routers.gateway_model_definition_permissions import gateway_model_definition_permissions_router
from mlflow_oidc_auth.routers.gateway_secret_permissions import gateway_secret_permissions_router
from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
from mlflow_oidc_auth.routers.prompt_permissions import prompt_permissions_router
from mlflow_oidc_auth.routers.registered_model_permissions import registered_model_permissions_router
from mlflow_oidc_auth.routers.scim import scim_tokens_router
from mlflow_oidc_auth.routers.trash import trash_router
from mlflow_oidc_auth.routers.users import users_router
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.pagination import MAX_PAGE_SIZE, TOTAL_COUNT_HEADER

# Deliberately unsorted, mixed case: sorted case-insensitively they read Alpha, alpha2, bravo,
# charlie, delta.
NAMES = ["delta", "Alpha", "charlie", "bravo", "alpha2"]
SORTED = ["Alpha", "alpha2", "bravo", "charlie", "delta"]

ADMIN = "admin@example.com"


def _naive_now() -> datetime:
    # The token repository stores naive UTC timestamps.
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def client():
    app = FastAPI()
    for router in (
        experiment_permissions_router,
        registered_model_permissions_router,
        prompt_permissions_router,
        gateway_endpoint_permissions_router,
        gateway_secret_permissions_router,
        gateway_model_definition_permissions_router,
        group_permissions_router,
        users_router,
        trash_router,
        scim_tokens_router,
        webhook_module.webhook_router,
    ):
        app.include_router(router)
    app.dependency_overrides[get_username] = lambda: ADMIN
    app.dependency_overrides[get_is_admin] = lambda: True
    app.dependency_overrides[check_admin_permission] = lambda: ADMIN
    return TestClient(app)


# --- data sources, one per endpoint -------------------------------------------------------------


def _experiments(stack, mock_store):
    tracking = MagicMock()
    tracking.search_experiments.return_value = [SimpleNamespace(name=n, experiment_id=str(i + 1), tags={}) for i, n in enumerate(NAMES)]
    stack.append(patch("mlflow_oidc_auth.routers.experiment_permissions._get_tracking_store", return_value=tracking))


def _models(stack, mock_store):
    rows = [SimpleNamespace(name=n, tags={}, description="", aliases={}) for n in NAMES]
    stack.append(patch("mlflow_oidc_auth.routers.registered_model_permissions.fetch_all_registered_models", return_value=rows))


def _prompts(stack, mock_store):
    rows = [SimpleNamespace(name=n, tags={}, description="", aliases={}) for n in NAMES]
    stack.append(patch("mlflow_oidc_auth.routers.prompt_permissions.fetch_all_prompts", return_value=rows))


def _gateway_endpoints(stack, mock_store):
    stack.append(patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints", return_value=[{"name": n} for n in NAMES]))


def _gateway_secrets(stack, mock_store):
    stack.append(patch("mlflow_oidc_auth.routers.gateway_secret_permissions.fetch_all_gateway_secrets", return_value=[{"secret_name": n} for n in NAMES]))


def _gateway_model_definitions(stack, mock_store):
    stack.append(
        patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.fetch_all_gateway_model_definitions", return_value=[{"name": n} for n in NAMES])
    )


def _groups(stack, mock_store):
    mock_store.get_groups.return_value = list(NAMES)


def _group_details(stack, mock_store):
    mock_store.list_group_details.return_value = [{"group_name": n, "external_id": None, "member_count": 0} for n in NAMES]


def _users(stack, mock_store):
    mock_store.list_usernames.return_value = list(NAMES)


def _user_details(stack, mock_store):
    rows = [
        {
            "username": n,
            "display_name": n,
            "is_admin": False,
            "is_service_account": False,
            "active": True,
            "managed_by": "manual",
            "service_account_source": None,
            "id": i,
        }
        for i, n in enumerate(NAMES)
    ]
    mock_store.list_user_details.return_value = (len(rows), rows)


def _user_tokens(stack, mock_store):
    now = _naive_now()
    mock_store.list_user_tokens.return_value = [
        UserTokenRecord(id=i + 1, name=n, token_prefix="mlf_x", created_at=now, created_by=ADMIN, expires_at=now + timedelta(days=1), last_used_at=None)
        for i, n in enumerate(NAMES)
    ]


def _deleted_experiments(stack, mock_store):
    rows = [
        SimpleNamespace(experiment_id=str(i + 1), name=n, lifecycle_stage="deleted", artifact_location="/tmp", tags={}, creation_time=0, last_update_time=0)
        for i, n in enumerate(NAMES)
    ]
    stack.append(patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments", return_value=rows))


def _deleted_runs(stack, mock_store):
    runs = {
        f"r{i}": SimpleNamespace(
            info=SimpleNamespace(run_id=f"r{i}", experiment_id="1", run_name=n, status="FINISHED", start_time=0, end_time=0, lifecycle_stage="deleted")
        )
        for i, n in enumerate(NAMES)
    }
    backend = MagicMock()
    backend._get_deleted_runs.return_value = list(runs)
    backend.get_run.side_effect = lambda run_id: runs[run_id]
    stack.append(patch("mlflow_oidc_auth.routers.trash._get_store", return_value=backend))


def _scim_tokens(stack, mock_store):
    records = [
        ScimTokenRecord(id=i + 1, name=n, token_prefix="scim_x", created_at=None, created_by=ADMIN, last_used_at=None, expires_at=None, revoked_at=None)
        for i, n in enumerate(NAMES)
    ]
    scim_store = MagicMock()
    scim_store.list_scim_tokens.return_value = records
    stack.append(patch("mlflow_oidc_auth.routers.scim.store", scim_store))


def _webhook(i: int, name: str):
    return SimpleNamespace(
        webhook_id=f"w{i}",
        name=name,
        url="https://example.com/hook",
        events=[webhook_module.WebhookEvent.from_str("registered_model.created")],
        description=None,
        status=webhook_module.WebhookStatus.ACTIVE,
        creation_timestamp=1,
        last_updated_timestamp=1,
    )


def _webhooks(stack, mock_store):
    hooks = [_webhook(i, n) for i, n in enumerate(NAMES)]

    # MLflow's default page holds all five; the scan (which asks for an explicit page size) gets
    # two pages, so the paged path has to follow the token.
    def list_webhooks(max_results=None, page_token=None):
        if max_results is None:
            return PagedList(hooks, token=None)
        if page_token is None:
            return PagedList(hooks[:3], token="next")
        return PagedList(hooks[3:], token=None)

    stack.append(patch.object(webhook_module, "_get_model_registry_store", return_value=SimpleNamespace(list_webhooks=list_webhooks)))


def _bare(key: str) -> Callable[[Any], List[str]]:
    return lambda body: [row[key] for row in body]


CASES: Dict[str, Dict[str, Any]] = {
    "experiments": dict(url=EXPERIMENT_PERMISSIONS_ROUTER_PREFIX, setup=_experiments, names=_bare("name")),
    "models": dict(url=REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX, setup=_models, names=_bare("name")),
    "prompts": dict(url=PROMPT_PERMISSIONS_ROUTER_PREFIX, setup=_prompts, names=_bare("name")),
    "gateway-endpoints": dict(url=f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/endpoints", setup=_gateway_endpoints, names=_bare("name")),
    "gateway-secrets": dict(url=f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/secrets", setup=_gateway_secrets, names=_bare("key")),
    "gateway-model-definitions": dict(url=f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/model-definitions", setup=_gateway_model_definitions, names=_bare("name")),
    "groups": dict(url=GROUP_PERMISSIONS_ROUTER_PREFIX, setup=_groups, names=list),
    "group-details": dict(url=f"{GROUP_PERMISSIONS_ROUTER_PREFIX}/details", setup=_group_details, names=_bare("group_name")),
    "users": dict(url=USERS_ROUTER_PREFIX, setup=_users, names=list),
    "service-accounts": dict(url=f"{USERS_ROUTER_PREFIX}?service=true", setup=_users, names=list),
    "user-details": dict(url=f"{USERS_ROUTER_PREFIX}/details", setup=_user_details, names=_bare("username")),
    "my-tokens": dict(url=f"{USERS_ROUTER_PREFIX}/current/tokens", setup=_user_tokens, names=lambda body: [t["name"] for t in body["tokens"]]),
    "user-tokens": dict(url=f"{USERS_ROUTER_PREFIX}/{ADMIN}/tokens", setup=_user_tokens, names=lambda body: [t["name"] for t in body["tokens"]]),
    "deleted-experiments": dict(
        url=f"{TRASH_ROUTER_PREFIX}/experiments", setup=_deleted_experiments, names=lambda body: [e["name"] for e in body["deleted_experiments"]]
    ),
    "deleted-runs": dict(url=f"{TRASH_ROUTER_PREFIX}/runs", setup=_deleted_runs, names=lambda body: [r["run_name"] for r in body["deleted_runs"]]),
    "scim-tokens": dict(url=SCIM_TOKENS_ROUTER_PREFIX, setup=_scim_tokens, names=_bare("name")),
    "webhooks": dict(url=WEBHOOK_ROUTER_PREFIX, setup=_webhooks, names=lambda body: [w["name"] for w in body["webhooks"]]),
}


@pytest.fixture(params=sorted(CASES))
def case(request, mock_store):
    spec = CASES[request.param]
    patches: list = []
    spec["setup"](patches, mock_store)
    for p in patches:
        p.start()
    yield spec
    for p in reversed(patches):
        p.stop()


def _get(client, url: str, **params):
    return client.get(url, params=params)


def test_no_params_is_unchanged(client, case):
    resp = _get(client, case["url"])
    assert resp.status_code == 200, resp.text
    # Full list, original (store) order, no total header.
    assert case["names"](resp.json()) == NAMES
    assert TOTAL_COUNT_HEADER.lower() not in {k.lower() for k in resp.headers}


def test_first_page(client, case):
    resp = _get(client, case["url"], limit=2, offset=0)
    assert resp.status_code == 200, resp.text
    assert case["names"](resp.json()) == SORTED[:2]
    assert resp.headers[TOTAL_COUNT_HEADER] == str(len(NAMES))


def test_second_page(client, case):
    resp = _get(client, case["url"], limit=2, offset=2)
    assert case["names"](resp.json()) == SORTED[2:4]
    assert resp.headers[TOTAL_COUNT_HEADER] == str(len(NAMES))


def test_offset_past_end_is_empty(client, case):
    resp = _get(client, case["url"], limit=2, offset=50)
    assert resp.status_code == 200, resp.text
    assert case["names"](resp.json()) == []
    assert resp.headers[TOTAL_COUNT_HEADER] == str(len(NAMES))


def test_search_with_limit(client, case):
    resp = _get(client, case["url"], limit=1, search="ALP")
    assert case["names"](resp.json()) == ["Alpha"]
    assert resp.headers[TOTAL_COUNT_HEADER] == "2"


def test_search_without_limit(client, case):
    resp = _get(client, case["url"], search="ha")
    assert case["names"](resp.json()) == ["Alpha", "alpha2", "charlie"]
    assert resp.headers[TOTAL_COUNT_HEADER] == "3"


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": MAX_PAGE_SIZE + 1}, {"limit": 2, "offset": -1}, {"limit": "abc"}])
def test_out_of_range_is_rejected(client, case, params):
    resp = _get(client, case["url"], **params)
    assert resp.status_code == 422, resp.text


def test_body_shape_is_kept_when_paged(client, case):
    unpaged = _get(client, case["url"]).json()
    paged = _get(client, case["url"], limit=2).json()
    assert type(unpaged) is type(paged)
    if isinstance(unpaged, dict):
        assert set(unpaged) == set(paged)


# --- endpoint specifics ---------------------------------------------------------------------------


def test_webhooks_legacy_paging_still_forwarded(client):
    seen = {}

    def list_webhooks(max_results=None, page_token=None):
        seen.update(max_results=max_results, page_token=page_token)
        return PagedList([_webhook(0, "only")], token="t2")

    with patch.object(webhook_module, "_get_model_registry_store", return_value=SimpleNamespace(list_webhooks=list_webhooks)):
        resp = client.get(WEBHOOK_ROUTER_PREFIX, params={"max_results": 1, "page_token": "t1"})
    assert resp.status_code == 200
    assert seen == {"max_results": 1, "page_token": "t1"}
    assert resp.json()["next_page_token"] == "t2"
    assert TOTAL_COUNT_HEADER not in resp.headers


def test_webhooks_limit_wins_over_mlflow_paging(client, mock_store):
    patches: list = []
    _webhooks(patches, mock_store)
    with patches[0]:
        resp = client.get(WEBHOOK_ROUTER_PREFIX, params={"max_results": 1, "page_token": "ignored", "limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert [w["name"] for w in body["webhooks"]] == SORTED
    assert body["next_page_token"] is None
    assert resp.headers[TOTAL_COUNT_HEADER] == str(len(NAMES))


def test_webhooks_scan_is_bounded(client):
    calls = []

    def list_webhooks(max_results=None, page_token=None):
        calls.append(page_token)
        return PagedList([_webhook(len(calls), f"h{len(calls)}")], token="more")

    with patch.object(webhook_module, "_get_model_registry_store", return_value=SimpleNamespace(list_webhooks=list_webhooks)):
        resp = client.get(WEBHOOK_ROUTER_PREFIX, params={"limit": 5})
    assert resp.status_code == 200
    assert len(calls) == webhook_module.WEBHOOK_SCAN_MAX_PAGES


def test_tokens_keep_no_store_when_paged(client, mock_store):
    _user_tokens([], mock_store)
    resp = client.get(f"{USERS_ROUTER_PREFIX}/current/tokens", params={"limit": 2})
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers[TOTAL_COUNT_HEADER] == str(len(NAMES))


def test_ties_are_ordered_by_id(client, mock_store):
    now = _naive_now()
    mock_store.list_user_tokens.return_value = [
        UserTokenRecord(id=i, name="same", token_prefix="mlf_x", created_at=now, created_by=ADMIN, expires_at=now + timedelta(days=1), last_used_at=None)
        for i in (10, 2, 7)
    ]
    resp = client.get(f"{USERS_ROUTER_PREFIX}/current/tokens", params={"limit": 3})
    assert [t["id"] for t in resp.json()["tokens"]] == [2, 7, 10]


def test_non_admin_is_paged_after_the_permission_filter(client, mock_store):
    """The router must filter first: a hidden experiment never lands in a page or in the total."""
    app = client.app
    app.dependency_overrides[get_username] = lambda: "user@example.com"
    app.dependency_overrides[get_is_admin] = lambda: False
    tracking = MagicMock()
    tracking.search_experiments.return_value = [SimpleNamespace(name=n, experiment_id=str(i + 1), tags={}) for i, n in enumerate(NAMES)]
    visible = {"Alpha", "charlie"}
    with (
        patch("mlflow_oidc_auth.routers.experiment_permissions._get_tracking_store", return_value=tracking),
        patch(
            "mlflow_oidc_auth.routers.experiment_permissions.filter_manageable_experiments",
            side_effect=lambda username, experiments: [e for e in experiments if e.name in visible],
        ),
    ):
        first = client.get(EXPERIMENT_PERMISSIONS_ROUTER_PREFIX, params={"limit": 1})
        rest = client.get(EXPERIMENT_PERMISSIONS_ROUTER_PREFIX, params={"limit": 5, "offset": 1})
        searched = client.get(EXPERIMENT_PERMISSIONS_ROUTER_PREFIX, params={"limit": 5, "search": "a"})
    assert first.headers[TOTAL_COUNT_HEADER] == "2"
    assert [e["name"] for e in first.json()] == ["Alpha"]
    assert [e["name"] for e in rest.json()] == ["charlie"]
    # "a" matches every name; only the two visible ones may be counted or returned.
    assert searched.headers[TOTAL_COUNT_HEADER] == "2"
    assert {e["name"] for e in searched.json()} == visible
