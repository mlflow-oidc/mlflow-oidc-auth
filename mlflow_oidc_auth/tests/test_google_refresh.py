from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import mlflow_oidc_auth.oauth as oauth_mod
import mlflow_oidc_auth.routers.auth as auth_mod
from mlflow_oidc_auth.tests.test_provider_login import DummyRequest

GOOGLE_DISCOVERY = "https://accounts.google.com/.well-known/openid-configuration"


@pytest.fixture
def configure_google(monkeypatch):
    def configure(provider_id="default", discovery=GOOGLE_DISCOVERY, refresh=True, source="env", registered=True, provider_type="oidc"):
        provider = SimpleNamespace(id=provider_id, type=provider_type, discovery_url=discovery)
        registry = SimpleNamespace(source=source, by_id=lambda pid: provider if registered and pid == provider_id else None)
        monkeypatch.setattr(oauth_mod.config, "AUTH_PROVIDERS", registry)
        monkeypatch.setattr(oauth_mod.config, "OIDC_DISCOVERY_URL", GOOGLE_DISCOVERY)
        monkeypatch.setattr(oauth_mod.config, "OIDC_SCOPE", "openid,email,profile")
        monkeypatch.setattr(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", refresh)

    return configure


@pytest.mark.parametrize("provider_id", ["default", "google"])
@pytest.mark.parametrize("suffix", ["", "/"])
def test_google_offline_access_uses_authorization_parameters(configure_google, provider_id, suffix):
    configure_google(provider_id, GOOGLE_DISCOVERY + suffix)
    assert oauth_mod._build_scope(provider_id) == "openid email profile"
    assert oauth_mod.get_authorization_request_kwargs(provider_id) == {"access_type": "offline", "prompt": "consent"}


def test_legacy_google_discovery(configure_google):
    configure_google(source="legacy", registered=False)
    assert oauth_mod._build_scope() == "openid email profile"
    assert oauth_mod.get_authorization_request_kwargs() == {"access_type": "offline", "prompt": "consent"}


@pytest.mark.parametrize("provider_id", ["default", "google"])
def test_refresh_disabled_preserves_authorization_request(configure_google, provider_id):
    configure_google(provider_id, refresh=False)
    assert oauth_mod._build_scope(provider_id) == "openid email profile"
    assert oauth_mod.get_authorization_request_kwargs(provider_id) == {}


@pytest.mark.parametrize(
    "discovery",
    [
        "https://issuer.example/.well-known/openid-configuration",
        "https://accounts.google.com.example/.well-known/openid-configuration",
    ],
)
def test_other_providers_keep_offline_access_scope(configure_google, discovery):
    configure_google(discovery=discovery)
    assert oauth_mod._build_scope() == "openid email profile offline_access"
    assert oauth_mod.get_authorization_request_kwargs() == {}


@pytest.mark.parametrize("provider_type", ["saml", "k8s"])
def test_non_oidc_provider_does_not_get_google_parameters(configure_google, provider_type):
    configure_google(provider_type=provider_type)
    assert oauth_mod.get_authorization_request_kwargs() == {}


def test_registry_omission_does_not_fall_back_to_legacy_google(configure_google):
    configure_google(registered=False)
    assert oauth_mod.get_authorization_request_kwargs() == {}


def test_explicit_scopes_are_preserved(configure_google, monkeypatch):
    configure_google()
    monkeypatch.setattr(oauth_mod.config, "OIDC_SCOPE", "openid offline_access,email,email")
    assert oauth_mod._build_scope() == "openid offline_access email"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_id", ["default", "google"])
async def test_google_login_keeps_provider_state_and_pkce(configure_google, monkeypatch, provider_id):
    configure_google(provider_id)
    redirect = AsyncMock(return_value=SimpleNamespace(status_code=302))
    client = SimpleNamespace(authorize_redirect=redirect)
    state = Mock(return_value="test-state")
    pkce = AsyncMock()
    monkeypatch.setattr(auth_mod.store, "create_auth_state", state)
    monkeypatch.setattr(auth_mod, "is_oidc_configured", lambda pid: True)
    monkeypatch.setattr(auth_mod, "assert_pkce_supported", pkce)
    monkeypatch.setattr(auth_mod, "get_client", lambda pid: client)
    monkeypatch.setattr(auth_mod, "get_configured_or_dynamic_redirect_uri", lambda *args, **kwargs: "https://tracking.example/callback")
    request = DummyRequest()
    response = await auth_mod._begin_login(request, provider_id)
    assert response.status_code == 302
    assert state.call_args.args == (provider_id,)
    pkce.assert_awaited_once_with(client, provider_id)
    redirect.assert_awaited_once_with(request, redirect_uri="https://tracking.example/callback", state="test-state", access_type="offline", prompt="consent")


def test_named_google_registration_uses_its_own_scope(configure_google, monkeypatch):
    configure_google("google")
    settings = Mock(return_value={"client_id": "test-client", "server_metadata_url": GOOGLE_DISCOVERY})
    register = Mock()
    monkeypatch.setattr(oauth_mod, "_registered", {})
    monkeypatch.setattr(oauth_mod, "_client_settings", settings)
    monkeypatch.setattr(oauth_mod.oauth, "register", register)
    assert oauth_mod.ensure_client_registered("google")
    settings.assert_called_once_with("google")
    register.assert_called_once()
    assert register.call_args.kwargs["client_kwargs"]["scope"] == "openid email profile"
