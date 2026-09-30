"""Pagination never widens what a non-admin sees: real store, real permission resolution.

A non-admin holds MANAGE on a subset of experiments, registered models, prompts and AI Gateway
endpoints, secrets and model definitions — every list endpoint that filters per user. Paging and
search run after ``filter_manageable_*``, so ``X-Total-Count`` equals the visible count and no
page — at any offset, with any search — ever contains a hidden resource.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.routers._prefix import (
    EXPERIMENT_PERMISSIONS_ROUTER_PREFIX,
    GATEWAY_PERMISSIONS_ROUTER_PREFIX,
    PROMPT_PERMISSIONS_ROUTER_PREFIX,
    REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX,
)
from mlflow_oidc_auth.routers.experiment_permissions import experiment_permissions_router
from mlflow_oidc_auth.routers.gateway_endpoint_permissions import gateway_endpoint_permissions_router
from mlflow_oidc_auth.routers.gateway_model_definition_permissions import gateway_model_definition_permissions_router
from mlflow_oidc_auth.routers.gateway_secret_permissions import gateway_secret_permissions_router
from mlflow_oidc_auth.routers.prompt_permissions import prompt_permissions_router
from mlflow_oidc_auth.routers.registered_model_permissions import registered_model_permissions_router
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.pagination import TOTAL_COUNT_HEADER
from mlflow_oidc_auth.utils.permissions import flush_permission_cache

ALICE = "alice@example.com"
EXPERIMENTS = {str(i): f"exp-{i:02d}" for i in range(1, 13)}
VISIBLE_EXPERIMENTS = {"2", "5", "9"}
MODELS = [f"model-{c}" for c in "abcdefghij"]
VISIBLE_MODELS = {"model-c", "model-h"}
PROMPTS = [f"prompt-{i}" for i in range(1, 9)]
VISIBLE_PROMPTS = {"prompt-3", "prompt-6"}
GATEWAY_NAMES = [f"gw-{c}" for c in "pqrstuv"]
VISIBLE_GATEWAY = {"gw-q", "gw-u"}

# (router prefix, row key, grant function name) for each AI Gateway list.
GATEWAY_LISTS = {
    "endpoints": (f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/endpoints", "name", "create_gateway_endpoint_permission"),
    "secrets": (f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/secrets", "key", "create_gateway_secret_permission"),
    "model-definitions": (f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/model-definitions", "name", "create_gateway_model_definition_permission"),
}


@pytest.fixture
def real_store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ALICE, "Alice")
    for experiment_id in VISIBLE_EXPERIMENTS:
        s.create_experiment_permission(experiment_id, ALICE, "MANAGE")
    for name in VISIBLE_MODELS:
        s.create_registered_model_permission(name, ALICE, "MANAGE")
    # A lower grant must not make a resource listable either.
    s.create_experiment_permission("1", ALICE, "READ")
    s.create_registered_model_permission("model-a", ALICE, "EDIT")
    # Prompts are registered models under the hood and share their permission table.
    for name in VISIBLE_PROMPTS:
        s.create_registered_model_permission(name, ALICE, "MANAGE")
    s.create_registered_model_permission("prompt-1", ALICE, "READ")
    for _, _, grant in GATEWAY_LISTS.values():
        for name in VISIBLE_GATEWAY:
            getattr(s, grant)(name, ALICE, "MANAGE")
        getattr(s, grant)("gw-p", ALICE, "USE")

    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    flush_permission_cache()
    yield s
    flush_permission_cache()
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture
def client(real_store):
    app = FastAPI()
    app.include_router(experiment_permissions_router)
    app.include_router(registered_model_permissions_router)
    app.include_router(prompt_permissions_router)
    app.include_router(gateway_endpoint_permissions_router)
    app.include_router(gateway_secret_permissions_router)
    app.include_router(gateway_model_definition_permissions_router)
    app.dependency_overrides[get_username] = lambda: ALICE
    app.dependency_overrides[get_is_admin] = lambda: False

    tracking = MagicMock()
    tracking.search_experiments.return_value = [SimpleNamespace(name=name, experiment_id=eid, tags={}) for eid, name in EXPERIMENTS.items()]
    models = [SimpleNamespace(name=name, tags={}, description="", aliases={}) for name in MODELS]
    prompts = [SimpleNamespace(name=name, tags={}, description="", aliases={}) for name in PROMPTS]
    endpoints = [{"name": name} for name in GATEWAY_NAMES]
    secrets = [{"secret_name": name} for name in GATEWAY_NAMES]
    definitions = [{"name": name} for name in GATEWAY_NAMES]
    with (
        patch("mlflow_oidc_auth.routers.experiment_permissions._get_tracking_store", return_value=tracking),
        patch("mlflow_oidc_auth.routers.registered_model_permissions.fetch_all_registered_models", return_value=models),
        patch("mlflow_oidc_auth.routers.prompt_permissions.fetch_all_prompts", return_value=prompts),
        patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints", return_value=endpoints),
        patch("mlflow_oidc_auth.routers.gateway_secret_permissions.fetch_all_gateway_secrets", return_value=secrets),
        patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.fetch_all_gateway_model_definitions", return_value=definitions),
        patch("mlflow_oidc_auth.config.config.DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
    ):
        yield TestClient(app)


def _walk(client, url, key="name", **params):
    """Every page at limit=1, and the totals each page reported."""
    names, totals, offset = [], set(), 0
    while offset < 50:
        resp = client.get(url, params={"limit": 1, "offset": offset, **params})
        assert resp.status_code == 200, resp.text
        totals.add(resp.headers[TOTAL_COUNT_HEADER])
        page = [row[key] for row in resp.json()]
        if not page:
            break
        names.extend(page)
        offset += 1
    return names, totals


def test_unpaged_list_is_the_visible_subset(client):
    resp = client.get(EXPERIMENT_PERMISSIONS_ROUTER_PREFIX)
    assert {row["id"] for row in resp.json()} == VISIBLE_EXPERIMENTS


def test_experiment_total_counts_only_visible(client):
    visible_names = sorted(EXPERIMENTS[e] for e in VISIBLE_EXPERIMENTS)
    resp = client.get(EXPERIMENT_PERMISSIONS_ROUTER_PREFIX, params={"limit": 500})
    assert resp.headers[TOTAL_COUNT_HEADER] == str(len(VISIBLE_EXPERIMENTS))
    assert [row["name"] for row in resp.json()] == visible_names

    names, totals = _walk(client, EXPERIMENT_PERMISSIONS_ROUTER_PREFIX)
    assert names == visible_names
    assert totals == {str(len(VISIBLE_EXPERIMENTS))}


def test_experiment_search_never_reveals_hidden(client):
    # "exp-" matches all twelve experiments; only the three visible may be counted.
    resp = client.get(EXPERIMENT_PERMISSIONS_ROUTER_PREFIX, params={"search": "EXP-", "limit": 500})
    assert resp.headers[TOTAL_COUNT_HEADER] == str(len(VISIBLE_EXPERIMENTS))
    assert {row["id"] for row in resp.json()} == VISIBLE_EXPERIMENTS

    # Searching for a hidden experiment by exact name finds nothing and counts nothing.
    hidden = client.get(EXPERIMENT_PERMISSIONS_ROUTER_PREFIX, params={"search": EXPERIMENTS["1"], "limit": 10})
    assert hidden.json() == []
    assert hidden.headers[TOTAL_COUNT_HEADER] == "0"


def test_model_total_counts_only_visible(client):
    names, totals = _walk(client, REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX)
    assert names == sorted(VISIBLE_MODELS)
    assert totals == {str(len(VISIBLE_MODELS))}

    hidden = client.get(REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX, params={"search": "model-a", "limit": 10})
    assert hidden.json() == []
    assert hidden.headers[TOTAL_COUNT_HEADER] == "0"


def test_prompt_total_counts_only_visible(client):
    names, totals = _walk(client, PROMPT_PERMISSIONS_ROUTER_PREFIX)
    assert names == sorted(VISIBLE_PROMPTS)
    assert totals == {str(len(VISIBLE_PROMPTS))}

    hidden = client.get(PROMPT_PERMISSIONS_ROUTER_PREFIX, params={"search": "prompt-1", "limit": 10})
    assert hidden.json() == []
    assert hidden.headers[TOTAL_COUNT_HEADER] == "0"


@pytest.mark.parametrize("kind", sorted(GATEWAY_LISTS))
def test_gateway_total_counts_only_visible(client, kind):
    url, key, _ = GATEWAY_LISTS[kind]
    names, totals = _walk(client, url, key=key)
    assert names == sorted(VISIBLE_GATEWAY)
    assert totals == {str(len(VISIBLE_GATEWAY))}

    # A lower grant (USE on gw-p) does not make the resource listable, and searching it counts nothing.
    hidden = client.get(url, params={"search": "gw-p", "limit": 10})
    assert hidden.json() == []
    assert hidden.headers[TOTAL_COUNT_HEADER] == "0"
