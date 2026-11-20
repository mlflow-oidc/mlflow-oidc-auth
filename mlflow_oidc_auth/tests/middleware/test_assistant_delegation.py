import asyncio
import builtins
import secrets
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Response
from starlette.requests import Request
from fastapi.testclient import TestClient
from flask import Flask

from mlflow_oidc_auth.dependencies import require_interactive_login
from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_DELEGATION
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware, _auth_method
from mlflow_oidc_auth.middleware.fastapi_permission_middleware import _strip_client_credentials


@pytest.fixture
def signing_key(monkeypatch):
    from mlflow.server.assistant.delegation import mint_delegation_credential

    monkeypatch.setenv("_MLFLOW_ASSISTANT_DELEGATION_SIGNING_KEY", secrets.token_hex(32))
    return mint_delegation_credential


@pytest.mark.parametrize("kind", ["valid", "expired", "tampered", "no-key"])
def test_assistant_delegation_authentication(signing_key, monkeypatch, kind):
    credential = signing_key("alice", ttl_seconds=-1 if kind == "expired" else 300)
    if kind == "tampered":
        credential = credential.replace("alice", "bob")
    if kind == "no-key":
        monkeypatch.delenv("_MLFLOW_ASSISTANT_DELEGATION_SIGNING_KEY")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/3.0/mlflow/traces/test",
            "headers": [(b"x-mlflow-assistant-delegation", credential.encode())],
        }
    )
    middleware = AuthMiddleware(FastAPI())
    with patch.object(middleware, "_authenticate_session", new_callable=AsyncMock) as session:
        result = asyncio.run(middleware._authenticate_user(request))
    assert result[0] is (kind == "valid")
    assert result[1] == ("alice" if kind == "valid" else None)
    session.assert_not_called()


@pytest.mark.parametrize("authorization", [None, "Basic ignored", "Bearer ignored"])
def test_delegation_is_not_interactive(authorization):
    headers = [(b"x-mlflow-assistant-delegation", b"credential")]
    if authorization:
        headers.append((b"authorization", authorization.encode()))
    request = Request({"type": "http", "headers": headers})
    request.state.auth_method = _auth_method(request)
    assert request.state.auth_method == AUTH_METHOD_DELEGATION
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_interactive_login(request))
    assert error.value.status_code == 403


@pytest.mark.parametrize("kind", ["active", "inactive", "deleted", "lookup-error", "internal", "external", "kubernetes"])
def test_delegation_dispatch_checks_account(signing_key, kind):
    credential = signing_key("alice")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/3.0/mlflow/traces/test",
            "headers": [(b"x-mlflow-assistant-delegation", credential.encode()), (b"authorization", b"Basic ignored")],
        }
    )
    profile = SimpleNamespace(
        active=kind != "inactive", is_admin=False, is_service_account=kind in {"internal", "external", "kubernetes"}, service_account_source=kind
    )
    mocked_store = MagicMock()
    mocked_store.get_user_profile.return_value = None if kind == "deleted" else profile
    if kind == "lookup-error":
        mocked_store.get_user_profile.side_effect = RuntimeError("unavailable")
    next_handler = AsyncMock(return_value=Response(status_code=204))
    with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mocked_store), patch("mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event"):
        response = asyncio.run(AuthMiddleware(FastAPI()).dispatch(request, next_handler))
    assert response.status_code == (204 if kind == "active" else 401)
    if kind == "active":
        assert request.state.username == "alice"
        assert request.state.auth_method == AUTH_METHOD_DELEGATION
        next_handler.assert_awaited_once()
    else:
        next_handler.assert_not_called()


@pytest.mark.parametrize("path", ["/gateway/test/mlflow/invocations", "/gateway/openai/v1/chat/completions", "/gateway/proxy/test/v1/responses"])
def test_gateway_strips_delegation(path):
    request = Request({"type": "http", "headers": [(b"X-MLflow-Assistant-Delegation", b"credential"), (b"x-other", b"kept")]})
    _strip_client_credentials(request, path)
    assert request.scope["headers"] == [(b"x-other", b"kept")]


def test_empty_delegation_does_not_fall_back_to_session():
    request = Request({"type": "http", "headers": [(b"x-mlflow-assistant-delegation", b"")]})
    middleware = AuthMiddleware(FastAPI())
    with patch.object(middleware, "_authenticate_session", new_callable=AsyncMock) as session:
        assert asyncio.run(middleware._authenticate_user(request))[0] is False
    session.assert_not_called()


def test_delegation_unavailable_in_core(monkeypatch):
    original_import = builtins.__import__

    def import_without_delegation(name, *args, **kwargs):
        if name == "mlflow.server.assistant.delegation":
            raise ImportError("unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_delegation)
    request = Request({"type": "http", "headers": [(b"x-mlflow-assistant-delegation", b"credential")]})
    assert asyncio.run(AuthMiddleware(FastAPI())._authenticate_user(request)) == (False, None, "Assistant delegation is unavailable")


@pytest.mark.parametrize("username,workspace,expected", [("alice", "team-a", 200), ("bob", "team-a", 403), ("alice", "team-b", 403)])
def test_delegation_preserves_trace_authorization(signing_key, monkeypatch, username, workspace, expected):
    from mlflow_oidc_auth.bridge.user import get_auth_context
    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.middleware import AuthAwareWSGIMiddleware
    from mlflow_oidc_auth.validators.trace import validate_can_read_trace

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    flask_app = Flask(__name__)

    @flask_app.get("/api/3.0/mlflow/traces/<trace_id>")
    def trace(trace_id):
        ctx = get_auth_context()
        if not validate_can_read_trace(ctx.username):
            return {"detail": "Permission denied"}, 403
        return {"trace_id": trace_id, "username": ctx.username, "workspace": ctx.workspace}

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.mount("/", AuthAwareWSGIMiddleware(flask_app))
    mocked_store = MagicMock()
    mocked_store.get_user_profile.return_value = SimpleNamespace(active=True, is_admin=False, is_service_account=False)

    def permission(experiment_id, caller):
        ctx = get_auth_context()
        allowed = (caller, ctx.workspace, experiment_id) == ("alice", "team-a", "experiment-a")
        return SimpleNamespace(permission=SimpleNamespace(can_read=allowed))

    with (
        patch("mlflow_oidc_auth.middleware.auth_middleware.store", mocked_store),
        patch("mlflow_oidc_auth.validators.trace._get_tracking_store") as tracking,
        patch("mlflow_oidc_auth.validators.trace.effective_experiment_permission", side_effect=permission),
        TestClient(app) as client,
    ):
        tracking.return_value.get_trace_info.return_value = SimpleNamespace(experiment_id="experiment-a")
        response = client.get(
            "/api/3.0/mlflow/traces/trace-a", headers={"X-MLflow-Assistant-Delegation": signing_key(username), "X-MLFLOW-WORKSPACE": workspace}
        )
    assert response.status_code == expected
    if expected == 200:
        assert response.json() == {"trace_id": "trace-a", "username": "alice", "workspace": "team-a"}
