"""Fixtures for the SCIM suite: a real SQLite store, the real ``AuthMiddleware``, and the routers
under test mounted the way ``app.py`` mounts them.

No mocks on the authentication path. The point of these tests is that the carve-out, the token
dependency and the ``active`` enforcement compose correctly — which a mocked store cannot show.
"""

import base64
import json
import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth import audit
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.dependencies import scim_auth_failure_audit, scim_auth_failure_limiter, scim_rate_limiter
from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.ownership import Enforcement

ADMIN = "root-admin@example.com"
ADMIN_PASSWORD = "scim-suite-admin"  # not a credential: only ever seeded into a tmp_path database
USER_PASSWORD = "scim-suite-user"  # likewise
PROTECTED = "/scim-suite/protected"
LOGIN = "/login/scim-suite"  # under the unprotected /login prefix, like the real callback


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield s
    s.engine.dispose()


@pytest.fixture
def bound_store(store):
    """Point the lazy singleton at the test store; routers and middleware import it directly."""
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)
    yield store
    object.__setattr__(store_module.store, "_instance", previous)


@pytest.fixture(autouse=True)
def scim_config(monkeypatch):
    """Deterministic settings, and a fresh rate limiter per test."""
    monkeypatch.setattr(config, "SCIM_RATE_LIMIT_PER_MINUTE", 600, raising=False)
    monkeypatch.setattr(config, "SCIM_TOKEN_ROTATION_OVERLAP_SECONDS", 3600, raising=False)
    monkeypatch.setattr(config, "ORPHAN_FALLBACK_PRINCIPAL", None, raising=False)
    monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.REPORT)
    monkeypatch.setattr(config, "SCIM_AUTH_FAILURE_LIMIT_PER_MINUTE", 60, raising=False)
    for state in (scim_rate_limiter, scim_auth_failure_limiter, scim_auth_failure_audit):
        state.reset()
    from mlflow_oidc_auth.routers.scim import _sweep_state, anonymous_activity_limiter

    _sweep_state["last"] = None
    anonymous_activity_limiter.reset()
    yield
    for state in (scim_rate_limiter, scim_auth_failure_limiter, scim_auth_failure_audit):
        state.reset()


@pytest.fixture
def audit_events():
    """Every audit event emitted during the test, parsed."""
    records = []

    class _Collector(logging.Handler):
        def emit(self, record):
            records.append(json.loads(record.getMessage()))

    logger = audit._get_audit_logger()
    handler = _Collector(level=logging.DEBUG)
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)


@pytest.fixture
def app(bound_store):
    from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
    from mlflow_oidc_auth.routers.scim import scim_admin_router, scim_router, scim_tokens_router
    from mlflow_oidc_auth.routers.users import users_router

    application = FastAPI()

    @application.get(PROTECTED)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @application.get(LOGIN)
    async def login(request: Request, username: str):
        # Mirrors the OIDC callback: the cookie holds only an opaque, revocable session id.
        request.session["session_id"] = store_module.store.create_auth_session(username, expires_at=datetime.now(timezone.utc) + timedelta(hours=8))
        return {"ok": True}

    application.include_router(scim_router)
    application.include_router(scim_tokens_router)
    application.include_router(scim_admin_router)
    application.include_router(users_router)
    application.include_router(group_permissions_router)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def basic(username: str, password: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()}


@pytest.fixture
def admin(bound_store):
    bound_store.create_user(ADMIN, ADMIN_PASSWORD, "Root Admin", is_admin=True)
    return basic(ADMIN, ADMIN_PASSWORD)


@pytest.fixture
def scim_token(bound_store):
    """A live SCIM token's plaintext."""
    _, plaintext = bound_store.create_scim_token("entra", created_by=ADMIN)
    return plaintext


@pytest.fixture
def scim(scim_token):
    return {"Authorization": f"Bearer {scim_token}", "Content-Type": "application/scim+json"}


def user_body(user_name: str, external_id: str = None, active: bool = True, display_name: str = None) -> dict:
    body = {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "userName": user_name, "active": active}
    if external_id is not None:
        body["externalId"] = external_id
    if display_name is not None:
        body["displayName"] = display_name
    return body


def patch_body(*operations) -> dict:
    return {"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"], "Operations": list(operations)}
