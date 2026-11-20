"""The gateway list routes send exactly what their response models declare (#470).

The handlers return the list-item models, so FastAPI validates them against ``response_model`` and serialises
them. These tests feed MLflow-shaped dictionaries (the fields of the entity dataclasses, which have no
``to_dict``), including ``None`` and non-string values, through each route of a small app and check the bytes.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.models.gateway import GatewayEndpointListItem, GatewayModelDefinitionListItem, GatewaySecretListItem
from mlflow_oidc_auth.routers import gateway_endpoint_permissions, gateway_model_definition_permissions, gateway_secret_permissions
from mlflow_oidc_auth.utils import get_is_admin, get_username

ENDPOINT = {"endpoint_id": "e-1", "name": "chat", "model_mappings": [], "tags": [], "created_by": None, "routing_strategy": None, "workspace": "default"}
MODEL_DEFINITION = {"model_definition_id": "m-1", "name": "gpt", "secret_name": None, "provider": "openai", "model_name": "gpt-4o", "workspace": "default"}
SECRET = {"secret_id": "s-1", "secret_name": "openai-key", "masked_values": {}, "provider": None, "auth_config": None, "workspace": "default"}


def _get(module, router, fetch, filt, rows, query="", is_admin=False):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_username] = lambda: "u"
    app.dependency_overrides[get_is_admin] = lambda: is_admin
    with patch.object(module, fetch, return_value=rows), patch.object(module, filt, side_effect=lambda user, items: items):
        response = TestClient(app).get(f"{module_prefix(router)}{query}")
    assert response.status_code == 200, response.text
    return response


def module_prefix(router):
    return router.prefix


def _endpoints(rows, **kw):
    return _get(
        gateway_endpoint_permissions,
        gateway_endpoint_permissions.gateway_endpoint_permissions_router,
        "fetch_all_gateway_endpoints",
        "filter_manageable_gateway_endpoints",
        rows,
        **kw,
    )


def _model_definitions(rows, **kw):
    return _get(
        gateway_model_definition_permissions,
        gateway_model_definition_permissions.gateway_model_definition_permissions_router,
        "fetch_all_gateway_model_definitions",
        "filter_manageable_gateway_model_definitions",
        rows,
        **kw,
    )


def _secrets(rows, **kw):
    return _get(
        gateway_secret_permissions,
        gateway_secret_permissions.gateway_secret_permissions_router,
        "fetch_all_gateway_secrets",
        "filter_manageable_gateway_secrets",
        rows,
        **kw,
    )


def test_gateway_endpoint_list_matches_model():
    rows = [ENDPOINT, {**ENDPOINT, "name": None, "endpoint_type": None, "description": None, "route_type": None, "auth_type": None}]
    response = _endpoints(rows)
    body = response.json()
    for item in body:
        GatewayEndpointListItem.model_validate(item)
    assert (
        response.content
        == b'[{"name":"chat","type":"","description":"","route_type":"","auth_type":""},{"name":"","type":"","description":"","route_type":"","auth_type":""}]'
    )
    assert all(isinstance(value, str) for item in body for value in item.values())
    assert "x-total-count" not in response.headers


def test_gateway_endpoint_list_coerces_a_non_string_value_instead_of_failing():
    """A shape change in MLflow (a number or an enum where a string was) must not turn the list into a 500."""
    response = _endpoints([{**ENDPOINT, "endpoint_type": 3, "route_type": ["a"], "auth_type": {"k": 1}}])
    assert response.json() == [{"name": "chat", "type": "3", "description": "", "route_type": "['a']", "auth_type": "{'k': 1}"}]


def test_gateway_endpoint_deprecated_fields_are_marked_in_the_schema():
    props = GatewayEndpointListItem.model_json_schema(mode="serialization")["properties"]
    assert props["name"].get("deprecated") is not True
    for name in ("type", "description", "route_type", "auth_type"):
        assert props[name]["deprecated"] is True
        assert "no such attribute" in props[name]["description"]


def test_gateway_model_definition_list_matches_model():
    rows = [MODEL_DEFINITION, {**MODEL_DEFINITION, "name": "other", "source": None, "provider": None}, {**MODEL_DEFINITION, "name": "src", "source": "s3://m"}]
    response = _model_definitions(rows)
    for item in response.json():
        GatewayModelDefinitionListItem.model_validate(item)
    assert response.json() == [{"name": "gpt", "source": "openai"}, {"name": "other", "source": ""}, {"name": "src", "source": "s3://m"}]


def test_gateway_secret_list_matches_model():
    rows = [SECRET, {**SECRET, "secret_name": None, "name": None, "key": None}]
    response = _secrets(rows)
    for item in response.json():
        GatewaySecretListItem.model_validate(item)
    assert response.content == b'[{"key":"openai-key"},{"key":""}]'


@pytest.mark.parametrize("which", [_endpoints, _model_definitions, _secrets])
def test_gateway_list_keeps_pagination_headers(which):
    names = ["b", "C", "a"]
    rows = [{**ENDPOINT, **MODEL_DEFINITION, **SECRET, "name": n, "secret_name": n} for n in names]
    response = which(rows, query="?limit=2&offset=0", is_admin=True)
    assert response.headers["x-total-count"] == "3"
    body = response.json()
    assert [next(iter(item.values())) for item in body] == ["a", "b"]
    searched = which(rows, query="?search=C", is_admin=True)
    assert searched.headers["x-total-count"] == "1"
