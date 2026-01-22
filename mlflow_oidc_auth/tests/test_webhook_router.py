from types import SimpleNamespace

import pytest
from cryptography.fernet import InvalidToken
from fastapi.testclient import TestClient

import mlflow_oidc_auth.routers.webhook as webhook_module
from mlflow_oidc_auth.app import create_app


@pytest.fixture
def client():
    # Create a minimal FastAPI app exposing only the webhook router to isolate tests
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(webhook_module.webhook_router)

    # Bypass admin permission dependency
    app.dependency_overrides[webhook_module.check_admin_permission] = lambda: "admin"
    return TestClient(app)


class FakePage(list):
    def __init__(self, items, token=None):
        super().__init__(items)
        self.token = token


def make_webhook_stub(webhook_id="w1"):
    # Minimal stub with attributes used by router
    return SimpleNamespace(
        webhook_id=webhook_id,
        name="name",
        url="https://example.com/hook",
        events=[webhook_module.WebhookEvent.from_str("registered_model.created")],
        description="desc",
        status=webhook_module.WebhookStatus.ACTIVE,
        creation_timestamp=100,
        last_updated_timestamp=200,
    )


def test_list_webhooks_success(client, monkeypatch):
    stub_page = FakePage([make_webhook_stub()], token="token123")

    store = SimpleNamespace(list_webhooks=lambda max_results=None, page_token=None: stub_page)

    monkeypatch.setattr(webhook_module, "_get_model_registry_store", lambda: store)

    resp = client.get("/oidc/webhook")
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_page_token"] == "token123"
    assert len(body["webhooks"]) == 1
    assert body["webhooks"][0]["name"] == "name"


def test_list_webhooks_invalid_token_cause(client, monkeypatch):
    def raise_with_cause(*args, **kwargs):
        raise Exception("db failure") from InvalidToken()

    store = SimpleNamespace(list_webhooks=raise_with_cause)
    monkeypatch.setattr(webhook_module, "_get_model_registry_store", lambda: store)

    resp = client.get("/oidc/webhook")
    assert resp.status_code == 503
    assert "MLFLOW_WEBHOOK_SECRET_ENCRYPTION_KEY" in resp.json()["detail"]


def test_list_webhooks_signature_message(client, monkeypatch):
    def raise_with_msg(*args, **kwargs):
        raise Exception("Signature did not match digest")

    store = SimpleNamespace(list_webhooks=raise_with_msg)
    monkeypatch.setattr(webhook_module, "_get_model_registry_store", lambda: store)

    resp = client.get("/oidc/webhook")
    assert resp.status_code == 503
    assert "MLFLOW_WEBHOOK_SECRET_ENCRYPTION_KEY" in resp.json()["detail"]


def test_list_webhooks_generic_error(client, monkeypatch):
    def raise_generic(*args, **kwargs):
        raise Exception("boom")

    store = SimpleNamespace(list_webhooks=raise_generic)
    monkeypatch.setattr(webhook_module, "_get_model_registry_store", lambda: store)

    resp = client.get("/oidc/webhook")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Webhook service temporarily unavailable."


def test_create_get_update_delete_test_flow(client, monkeypatch):
    # prepare stub webhook and store with callbacks
    created = make_webhook_stub("created-id")

    def create_webhook(name, url, events, description, secret, status):
        return created

    def get_webhook(webhook_id):
        return created

    def update_webhook(webhook_id, name, description, url, events, secret, status):
        # return an updated stub
        return SimpleNamespace(
            webhook_id=webhook_id,
            name=name or "updated",
            url=url or "https://example.com/updated",
            events=[webhook_module.WebhookEvent.from_str("registered_model.created")],
            description=description or "d",
            status=webhook_module.WebhookStatus.ACTIVE,
            creation_timestamp=111,
            last_updated_timestamp=222,
        )

    def delete_webhook(webhook_id):
        return None

    store = SimpleNamespace(
        create_webhook=create_webhook,
        get_webhook=get_webhook,
        update_webhook=update_webhook,
        delete_webhook=delete_webhook,
    )

    monkeypatch.setattr(webhook_module, "_get_model_registry_store", lambda: store)

    # Create
    resp = client.post(
        "/oidc/webhook",
        json={
            "name": "test",
            "url": "https://example.com/hook",
            "events": ["registered_model.created"],
            "description": "desc",
            "secret": "s",
            "status": "ACTIVE",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["webhook_id"] == "created-id"

    # Get
    resp = client.get("/oidc/webhook/created-id")
    assert resp.status_code == 200
    assert resp.json()["webhook_id"] == "created-id"

    # Update
    resp = client.put(
        "/oidc/webhook/created-id",
        json={
            "name": "updated-name",
            "url": "https://example.com/updated",
            "events": ["registered_model.created"],
            "description": "d",
            "secret": "s2",
            "status": "ACTIVE",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated-name"

    # Delete
    resp = client.delete("/oidc/webhook/created-id")
    assert resp.status_code == 200

    # Test webhook
    # patch the delivery test function
    monkeypatch.setattr(
        webhook_module, "test_webhook", lambda webhook, event=None: SimpleNamespace(success=True, response_status=200, response_body="ok", error_message=None)
    )
    resp = client.post("/oidc/webhook/created-id/test")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_create_webhook_invalid_event_returns_400(client, monkeypatch):
    # events validation happens in pydantic model; use invalid event
    store = SimpleNamespace(create_webhook=lambda **kw: None)
    monkeypatch.setattr(webhook_module, "_get_model_registry_store", lambda: store)

    resp = client.post(
        "/oidc/webhook",
        json={
            "name": "test",
            "url": "https://example.com/hook",
            "events": ["invalid.event"],
        },
    )
    assert resp.status_code == 422 or resp.status_code == 400


def test_update_webhook_invalid_event_returns_400(client, monkeypatch):
    store = SimpleNamespace(update_webhook=lambda **kw: None)
    monkeypatch.setattr(webhook_module, "_get_model_registry_store", lambda: store)

    resp = client.put(
        "/oidc/webhook/any-id",
        json={
            "events": ["invalid.event"],
        },
    )
    assert resp.status_code == 422 or resp.status_code == 400
