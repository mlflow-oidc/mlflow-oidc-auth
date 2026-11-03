"""Google gets offline access through authorization parameters, never the ``offline_access`` scope."""

from unittest.mock import Mock

import pytest

import mlflow_oidc_auth.oauth as oauth_mod

GOOGLE_DISCOVERY = "https://accounts.google.com/.well-known/openid-configuration"
OFFLINE_PARAMS = {"access_type": "offline", "prompt": "consent"}


@pytest.fixture
def configure(monkeypatch):
    def configure(refresh=True, scope="openid,email,profile"):
        monkeypatch.setattr(oauth_mod.config, "OIDC_SCOPE", scope)
        monkeypatch.setattr(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", refresh)

    return configure


@pytest.fixture
def register(monkeypatch):
    """Register ``provider_id`` against ``discovery``; returns the kwargs authlib was given."""

    def run(provider_id, discovery):
        settings = Mock(return_value={"client_id": "test-client", "server_metadata_url": discovery})
        register = Mock()
        monkeypatch.setattr(oauth_mod, "_registered", {})
        monkeypatch.setattr(oauth_mod, "_client_settings", settings)
        monkeypatch.setattr(oauth_mod.oauth, "register", register)
        assert oauth_mod.ensure_client_registered(provider_id)
        settings.assert_called_once_with(provider_id)
        register.assert_called_once()
        return register.call_args.kwargs

    return run


@pytest.mark.parametrize(
    "discovery",
    [
        GOOGLE_DISCOVERY,
        GOOGLE_DISCOVERY + "/",
        " https://Accounts.Google.COM/.well-known/openid-configuration ",
        "https://accounts.google.com:443/.well-known/openid-configuration?hl=en",
    ],
)
def test_google_is_recognised_by_its_discovery_url(discovery):
    assert oauth_mod._is_google_discovery_url(discovery)


@pytest.mark.parametrize(
    "discovery",
    [
        None,
        "",
        "https://issuer.example/.well-known/openid-configuration",
        "https://accounts.google.com.example/.well-known/openid-configuration",
        "https://evil.example/accounts.google.com/.well-known/openid-configuration",
        "http://accounts.google.com/.well-known/openid-configuration",
        "https://accounts.google.com:8443/.well-known/openid-configuration",
        "https://accounts.google.com/other",
    ],
)
def test_other_discovery_urls_are_not_google(discovery):
    assert not oauth_mod._is_google_discovery_url(discovery)


@pytest.mark.parametrize("provider_id", ["default", "google"])
def test_google_registration_asks_for_offline_access_with_parameters(configure, register, provider_id):
    configure()
    kwargs = register(provider_id, GOOGLE_DISCOVERY)
    assert kwargs["client_kwargs"]["scope"] == "openid email profile"
    assert kwargs["authorize_params"] == OFFLINE_PARAMS


@pytest.mark.parametrize("provider_id", ["default", "google"])
def test_refresh_disabled_leaves_google_request_unchanged(configure, register, provider_id):
    configure(refresh=False)
    kwargs = register(provider_id, GOOGLE_DISCOVERY)
    assert kwargs["client_kwargs"]["scope"] == "openid email profile"
    assert kwargs["authorize_params"] is None


@pytest.mark.parametrize(
    "discovery",
    [
        "https://issuer.example/.well-known/openid-configuration",
        "https://accounts.google.com.example/.well-known/openid-configuration",
    ],
)
def test_other_providers_keep_offline_access_scope(configure, register, discovery):
    configure()
    kwargs = register("default", discovery)
    assert kwargs["client_kwargs"]["scope"] == "openid email profile offline_access"
    assert kwargs["authorize_params"] is None


@pytest.mark.parametrize("refresh", [True, False])
def test_configured_offline_access_is_dropped_for_google(configure, register, refresh):
    """Google rejects the scope as invalid; sending it would make every login fail."""
    configure(refresh=refresh, scope="openid offline_access,email,email")
    kwargs = register("default", GOOGLE_DISCOVERY)
    assert kwargs["client_kwargs"]["scope"] == "openid email"


def test_configured_scopes_are_kept_for_other_providers(configure):
    configure(scope="openid offline_access,email,email")
    assert oauth_mod._build_scope() == "openid offline_access email"


def test_authorize_params_are_a_fresh_copy(configure):
    configure()
    params = oauth_mod._authorize_params(True)
    params["prompt"] = "none"
    assert oauth_mod._authorize_params(True) == OFFLINE_PARAMS


@pytest.mark.asyncio
async def test_authlib_sends_the_parameters_on_the_authorization_request(configure, monkeypatch):
    """End of the chain: the registered client puts them on the authorize URL itself."""
    from urllib.parse import parse_qs, urlparse

    from authlib.integrations.starlette_client import OAuth

    configure()
    client = OAuth().register(
        name="google-test",
        client_id="test-client",
        client_secret="test-secret",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        access_token_url="https://oauth2.googleapis.com/token",
        client_kwargs={"scope": oauth_mod._build_scope(True), "code_challenge_method": "S256"},
        authorize_params=oauth_mod._authorize_params(True),
    )
    rv = await client.create_authorization_url("https://tracking.example/callback", state="test-state")
    query = parse_qs(urlparse(rv["url"]).query)
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["scope"] == ["openid email profile"]
    assert query["state"] == ["test-state"]
    assert "code_challenge" in query
