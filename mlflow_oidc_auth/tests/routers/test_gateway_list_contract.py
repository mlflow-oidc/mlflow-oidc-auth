"""The gateway list routes send exactly what their response models declare (#470).

The handlers return a ``JSONResponse``, so FastAPI does not validate the body against ``response_model``; these
tests feed MLflow-shaped dictionaries (the fields of the entity dataclasses, which have no ``to_dict``), including
``None`` values, through each handler and validate the bytes against the model.
"""

import json
from unittest.mock import patch

import pytest

from mlflow_oidc_auth.models.gateway import GatewayEndpointListItem, GatewayModelDefinitionListItem, GatewaySecretListItem
from mlflow_oidc_auth.routers import gateway_endpoint_permissions, gateway_model_definition_permissions, gateway_secret_permissions
from mlflow_oidc_auth.utils.pagination import NO_PAGE

ENDPOINT = {"endpoint_id": "e-1", "name": "chat", "model_mappings": [], "tags": [], "created_by": None, "routing_strategy": None, "workspace": "default"}
MODEL_DEFINITION = {"model_definition_id": "m-1", "name": "gpt", "secret_name": None, "provider": "openai", "model_name": "gpt-4o", "workspace": "default"}
SECRET = {"secret_id": "s-1", "secret_name": "openai-key", "masked_values": {}, "provider": None, "auth_config": None, "workspace": "default"}


async def _list(module, handler, fetch, filt, rows):
    with patch.object(module, fetch, return_value=rows), patch.object(module, filt, side_effect=lambda user, items: items):
        response = await getattr(module, handler)(username="u", is_admin=False, page=NO_PAGE)
    return response, json.loads(response.body)


@pytest.mark.asyncio
async def test_gateway_endpoint_list_matches_model():
    rows = [ENDPOINT, {**ENDPOINT, "name": None, "endpoint_type": None, "description": None, "route_type": None, "auth_type": None}]
    response, body = await _list(
        gateway_endpoint_permissions, "list_gateway_endpoints", "fetch_all_gateway_endpoints", "filter_manageable_gateway_endpoints", rows
    )
    for item in body:
        GatewayEndpointListItem.model_validate(item)
    assert body[0] == {"name": "chat", "type": "", "description": "", "route_type": "", "auth_type": ""}
    assert body[1]["name"] == ""
    assert all(isinstance(value, str) for item in body for value in item.values())


@pytest.mark.asyncio
async def test_gateway_model_definition_list_matches_model():
    rows = [MODEL_DEFINITION, {**MODEL_DEFINITION, "name": "other", "source": None, "provider": None}, {**MODEL_DEFINITION, "name": "src", "source": "s3://m"}]
    _, body = await _list(
        gateway_model_definition_permissions,
        "list_gateway_model_definitions",
        "fetch_all_gateway_model_definitions",
        "filter_manageable_gateway_model_definitions",
        rows,
    )
    for item in body:
        GatewayModelDefinitionListItem.model_validate(item)
    assert body == [{"name": "gpt", "source": "openai"}, {"name": "other", "source": ""}, {"name": "src", "source": "s3://m"}]


@pytest.mark.asyncio
async def test_gateway_secret_list_matches_model():
    rows = [SECRET, {**SECRET, "secret_name": None, "name": None, "key": None}]
    _, body = await _list(gateway_secret_permissions, "list_gateway_secrets", "fetch_all_gateway_secrets", "filter_manageable_gateway_secrets", rows)
    for item in body:
        GatewaySecretListItem.model_validate(item)
    assert body == [{"key": "openai-key"}, {"key": ""}]


@pytest.mark.asyncio
async def test_gateway_list_keeps_pagination_headers():
    from mlflow_oidc_auth.utils.pagination import PageParams

    rows = [{**SECRET, "secret_name": f"k{i}"} for i in range(3)]
    with patch.object(gateway_secret_permissions, "fetch_all_gateway_secrets", return_value=rows):
        response = await gateway_secret_permissions.list_gateway_secrets(username="u", is_admin=True, page=PageParams(limit=2, offset=0, search=None))
    assert response.headers["x-total-count"] == "3"
    assert json.loads(response.body) == [{"key": "k0"}, {"key": "k1"}]
