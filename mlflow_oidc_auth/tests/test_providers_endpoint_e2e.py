"""``/providers`` through the real middleware, unauthenticated (issues #316, #317).

The login picker in #317 fetches this before anyone has signed in. Everything about it is
tested elsewhere by calling the handler directly — which cannot see the one property that
matters here: whether an anonymous browser is allowed to reach it at all.

It failed silently. ``AuthMiddleware`` refused the request, the page saw a non-OK response,
fell back to the single-provider login it has always had, and sent every visitor to the
*default* provider with nothing shown and nothing logged. A picker that quietly picks for you
is worse than one that is missing, so this is asserted end to end.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.provider_registry import ProviderConfig, RegistryLoadResult
from mlflow_oidc_auth.routers.auth import auth_router


@pytest.fixture
def client(monkeypatch):
    import mlflow_oidc_auth.routers.auth as auth_router_mod

    registry = RegistryLoadResult(
        providers=[
            ProviderConfig(id="entra", type="oidc", display_name="Entra ID", audience="mlflow", issuer="https://login.microsoftonline.test/"),
            ProviderConfig(id="okta", type="oidc", display_name="Okta", audience="mlflow", issuer="https://okta.test/"),
        ],
        errors=[],
    )
    monkeypatch.setattr(auth_router_mod.config, "AUTH_PROVIDERS", registry, raising=False)

    app = FastAPI()
    app.include_router(auth_router)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")

    with TestClient(app) as c:
        yield c


class TestAnAnonymousBrowserCanReadTheProviderList:
    def test_it_is_not_refused(self, client):
        assert client.get("/providers").status_code == 200

    def test_it_lists_the_interactive_providers(self, client):
        listed = client.get("/providers").json()["providers"]

        assert [entry["id"] for entry in listed] == ["entra", "okta"]

    def test_the_login_urls_are_same_origin_paths(self, client):
        listed = client.get("/providers").json()["providers"]

        assert [entry["login_url"] for entry in listed] == ["/login/entra", "/login/okta"]

    def test_a_hostile_forwarded_host_does_not_reach_the_login_urls(self, client):
        listed = client.get("/providers", headers={"X-Forwarded-Host": "evil.example"}).json()["providers"]

        assert all("evil.example" not in entry["login_url"] for entry in listed)

    def test_the_response_is_not_cacheable(self, client):
        assert client.get("/providers").headers["cache-control"] == "no-store"


class TestUnprotectingItDoesNotUnprotectAnythingElse:
    """It is matched exactly. A prefix would carry along every future route beginning with it."""

    def test_a_longer_path_is_still_protected(self):
        middleware = AuthMiddleware(FastAPI())

        assert middleware._is_unprotected_route("/providers") is True
        assert middleware._is_unprotected_route("/providers/secrets") is False
        assert middleware._is_unprotected_route("/providers-admin") is False
