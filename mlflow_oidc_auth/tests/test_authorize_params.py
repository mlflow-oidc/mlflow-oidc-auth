"""Per-provider authorization parameters, and ``offline_access`` only where a provider supports it.

Neither piece names a vendor. Google — which rejects ``offline_access`` and wants
``access_type=offline`` — is one configuration of them, exercised end to end at the bottom.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

import pytest

import mlflow_oidc_auth.oauth as oauth_mod
import mlflow_oidc_auth.routers.auth as auth_mod
from mlflow_oidc_auth.provider_registry import RESERVED_AUTHORIZE_PARAMS, _legacy_authorize_params, _validate, _validate_authorize_params
from mlflow_oidc_auth.tests.test_provider_login import DummyRequest

OFFLINE = {"access_type": "offline", "prompt": "consent"}


def _oidc_entry(**extra):
    entry = {
        "id": "corp",
        "type": "oidc",
        "audience": "test-audience",
        "issuer": "https://issuer.example",
        "discovery_url": "https://issuer.example/.well-known/openid-configuration",
        "client_id": "test-client",
    }
    entry.update(extra)
    return entry


# ── Registry validation ─────────────────────────────────────────────────────


def test_registry_accepts_string_parameters_on_an_oidc_provider():
    provider, errors = _validate(_oidc_entry(authorize_params={"prompt": "consent", "access_type": "offline"}), 0, set())
    assert errors == []
    assert dict(provider.authorize_params) == OFFLINE
    assert hash(provider) is not None


@pytest.mark.parametrize("value", [None, {}])
def test_absent_or_empty_parameters_are_none(value):
    assert _validate_authorize_params(value, "oidc", "entry 0") == ((), [])


@pytest.mark.parametrize("name", sorted(RESERVED_AUTHORIZE_PARAMS) + ["State", " REDIRECT_URI ", "Code_Challenge"])
def test_reserved_parameters_are_refused(name):
    """Negative test: an operator value must never replace state, nonce, PKCE, the redirect or the scope."""
    params, errors = _validate_authorize_params({name: "attacker-chosen"}, "oidc", "entry 0")
    assert params == ()
    assert len(errors) == 1 and "may not set" in errors[0]


def test_a_configured_code_verifier_cannot_pin_pkce():
    """Negative test: authlib takes ``code_verifier`` from the same kwargs as the PKCE secret."""
    assert "code_verifier" in RESERVED_AUTHORIZE_PARAMS
    _, errors = _validate_authorize_params({"code_verifier": "known-to-the-attacker"}, "oidc", "entry 0")
    assert errors


@pytest.mark.asyncio
async def test_every_allowed_name_reaches_the_url_without_breaking_the_login():
    """Any name the registry accepts is a URL parameter to authlib, never one of its own arguments."""
    from authlib.integrations.starlette_client import OAuth

    client = OAuth().register(
        name="names-probe",
        client_id="test-client",
        client_secret="test-secret",
        authorize_url="https://issuer.example/authorize",
        access_token_url="https://issuer.example/token",
        client_kwargs={"scope": "openid", "code_challenge_method": "S256"},
    )
    client.load_server_metadata = AsyncMock(return_value={})
    params, errors = _validate_authorize_params({"access_type": "offline", "prompt": "consent", "login_hint": "a@b.example"}, "oidc", "entry 0")
    assert errors == []
    rv = await client.create_authorization_url("https://tracking.example/callback", state="s", **dict(params))
    query = parse_qs(urlparse(rv["url"]).query)
    assert query["login_hint"] == ["a@b.example"] and query["access_type"] == ["offline"]
    assert rv["code_verifier"] and rv["code_verifier"] != "known-to-the-attacker"


def test_every_authlib_argument_name_on_the_way_to_the_url_is_reserved():
    """A name that is one of authlib's own arguments would make every login raise TypeError.

    Read from the installed authlib, so an upgrade that adds an argument fails here, not at login.
    """
    import inspect

    from authlib.integrations.base_client.sync_app import OAuth2Base
    from authlib.integrations.starlette_client import StarletteOAuth2App
    from authlib.oauth2.client import OAuth2Client
    from authlib.oauth2.rfc6749.parameters import prepare_grant_uri

    functions = (
        StarletteOAuth2App.authorize_redirect,
        StarletteOAuth2App.create_authorization_url,
        OAuth2Base._create_oauth2_authorization_url,
        OAuth2Client.create_authorization_url,
        prepare_grant_uri,
    )
    names = {
        name
        for function in functions
        for name, parameter in inspect.signature(function).parameters.items()
        if parameter.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
    }
    assert names - RESERVED_AUTHORIZE_PARAMS == set()


def test_names_that_collide_after_trimming_are_refused():
    _, errors = _validate_authorize_params({"prompt": "consent", " prompt ": "none"}, "oidc", "entry 0")
    assert errors and "more than once" in errors[0]


def test_a_reserved_parameter_drops_the_whole_provider():
    provider, errors = _validate(_oidc_entry(authorize_params={"access_type": "offline", "state": "fixed"}), 0, set())
    assert provider is None
    assert any("may not set 'state'" in e for e in errors)


@pytest.mark.parametrize(
    "value,message",
    [
        ("access_type=offline", "must be a JSON object"),
        (["access_type", "offline"], "must be a JSON object"),
        ({"access_type": True}, "must be a string"),
        ({"access_type": {"nested": "x"}}, "must be a string"),
        ({"": "x"}, "empty parameter name"),
    ],
)
def test_malformed_parameters_are_refused(value, message):
    params, errors = _validate_authorize_params(value, "oidc", "entry 0")
    assert params == ()
    assert errors and message in errors[0]


@pytest.mark.parametrize("provider_type", ["saml", "k8s"])
def test_parameters_apply_only_to_oidc(provider_type):
    params, errors = _validate_authorize_params({"access_type": "offline"}, provider_type, "entry 0")
    assert params == ()
    assert errors and "applies only to an 'oidc' provider" in errors[0]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ('{"access_type": "offline"}', {"access_type": "offline"}),
        ("access_type=offline", "access_type=offline"),
    ],
)
def test_legacy_variable_is_parsed_as_json(raw, expected):
    assert _legacy_authorize_params(raw) == expected


# ── What a login sends ──────────────────────────────────────────────────────


@pytest.fixture
def setup(monkeypatch):
    """Configure refresh, scope, the provider's params and the metadata its client serves."""

    def configure(refresh=True, scope="openid email profile", params=(), metadata=None, metadata_error=None):
        provider = SimpleNamespace(id="corp", authorize_params=tuple(sorted(dict(params).items())))
        monkeypatch.setattr(oauth_mod.config, "AUTH_PROVIDERS", SimpleNamespace(by_id=lambda pid: provider if pid == "corp" else None))
        monkeypatch.setattr(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", refresh)
        monkeypatch.setattr(oauth_mod.config, "OIDC_SCOPE", scope)
        monkeypatch.setattr(oauth_mod, "_offline_access_warned", set())
        loader = AsyncMock(side_effect=metadata_error) if metadata_error else AsyncMock(return_value=metadata)
        return SimpleNamespace(load_server_metadata=loader)

    return configure


@pytest.mark.asyncio
async def test_configured_parameters_are_sent(setup):
    client = setup(refresh=False, params=OFFLINE)
    assert await oauth_mod.authorization_request_params(client, "corp") == OFFLINE
    client.load_server_metadata.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_provider_gets_nothing(setup):
    client = setup(params=OFFLINE)
    assert await oauth_mod.authorization_request_params(client, "other") == {}


@pytest.mark.asyncio
async def test_offline_access_is_left_out_when_the_provider_does_not_support_it(setup, caplog):
    client = setup(metadata={"scopes_supported": ["openid", "email", "profile"]})
    assert await oauth_mod.authorization_request_params(client, "corp") == {"scope": "openid email profile"}
    assert await oauth_mod.authorization_request_params(client, "corp") == {"scope": "openid email profile"}
    assert sum("does not list 'offline_access'" in r.getMessage() for r in caplog.records) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        {"scopes_supported": ["openid", "offline_access"]},
        {},
        None,
        {"scopes_supported": "openid offline_access"},
    ],
)
async def test_registered_scope_is_kept_when_the_provider_supports_it_or_does_not_say(setup, metadata):
    client = setup(metadata=metadata)
    assert await oauth_mod.authorization_request_params(client, "corp") == {}


@pytest.mark.asyncio
async def test_unreadable_metadata_keeps_the_registered_scope(setup):
    client = setup(metadata_error=RuntimeError("discovery unreachable"))
    assert await oauth_mod.authorization_request_params(client, "corp") == {}


@pytest.mark.asyncio
async def test_offline_access_written_into_the_scope_is_the_operators_call(setup):
    client = setup(scope="openid offline_access", metadata={"scopes_supported": ["openid"]})
    assert await oauth_mod.authorization_request_params(client, "corp") == {}
    client.load_server_metadata.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_off_never_reads_metadata(setup):
    client = setup(refresh=False, metadata={"scopes_supported": ["openid"]})
    assert await oauth_mod.authorization_request_params(client, "corp") == {}
    client.load_server_metadata.assert_not_awaited()


def test_build_scope_without_offline_access(monkeypatch):
    monkeypatch.setattr(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", True)
    monkeypatch.setattr(oauth_mod.config, "OIDC_SCOPE", "openid,email")
    assert oauth_mod._build_scope() == "openid email offline_access"
    assert oauth_mod._build_scope(offline_access=False) == "openid email"


@pytest.mark.asyncio
async def test_login_forwards_the_parameters_with_its_own_state_and_redirect(setup, monkeypatch):
    setup(params=OFFLINE)
    redirect = AsyncMock(return_value=SimpleNamespace(status_code=302))
    client = SimpleNamespace(authorize_redirect=redirect, load_server_metadata=AsyncMock(return_value={"scopes_supported": ["openid", "email", "profile"]}))
    monkeypatch.setattr(auth_mod.store, "create_auth_state", Mock(return_value="test-state"))
    monkeypatch.setattr(auth_mod, "is_oidc_configured", lambda pid: True)
    monkeypatch.setattr(auth_mod, "assert_pkce_supported", AsyncMock())
    monkeypatch.setattr(auth_mod, "get_client", lambda pid: client)
    monkeypatch.setattr(auth_mod, "get_configured_or_dynamic_redirect_uri", lambda *args, **kwargs: "https://tracking.example/callback")
    request = DummyRequest()
    await auth_mod._begin_login(request, "corp")
    redirect.assert_awaited_once_with(
        request,
        redirect_uri="https://tracking.example/callback",
        state="test-state",
        access_type="offline",
        prompt="consent",
        scope="openid email profile",
    )


@pytest.mark.asyncio
async def test_google_configuration_end_to_end(setup):
    """Google as configuration: its real scopes_supported, the documented authorize_params, and a
    real authlib client building the authorization URL."""
    from authlib.integrations.starlette_client import OAuth

    setup(params=OFFLINE)
    metadata = {
        "issuer": "https://accounts.google.com",
        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.googleapis.com/token",
        "scopes_supported": ["openid", "email", "profile"],
        "code_challenge_methods_supported": ["plain", "S256"],
    }
    client = OAuth().register(
        name="google-e2e",
        client_id="test-client",
        client_secret="test-secret",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": oauth_mod._build_scope(), "code_challenge_method": "S256"},
    )
    client.load_server_metadata = AsyncMock(return_value=metadata)

    params = await oauth_mod.authorization_request_params(client, "corp")
    rv = await client.create_authorization_url("https://tracking.example/callback", state="test-state", **params)
    query = parse_qs(urlparse(rv["url"]).query)
    assert query["scope"] == ["openid email profile"]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["state"] == ["test-state"]
    assert query["redirect_uri"] == ["https://tracking.example/callback"]
    assert "code_challenge" in query and "nonce" in query


# ── The synthesised default provider ────────────────────────────────────────


def _legacy_registry(raw):
    from mlflow_oidc_auth.provider_registry import build_provider_registry
    from mlflow_oidc_auth.tests.test_provider_registry import FakeConfigManager, legacy_app_config

    return build_provider_registry(
        FakeConfigManager(),
        legacy_app_config(OIDC_AUDIENCE="test-audience", OIDC_ISSUER="https://idp.example.com", OIDC_AUTHORIZE_PARAMS=raw),
    )


def test_legacy_default_provider_takes_oidc_authorize_params():
    result = _legacy_registry('{"access_type": "offline", "prompt": "consent"}')
    assert result.errors == []
    assert dict(result.providers[0].authorize_params) == OFFLINE


@pytest.mark.parametrize("raw", ['{"redirect_uri": "https://evil.example/cb"}', "access_type=offline", '{"access_type": 1}'])
def test_invalid_oidc_authorize_params_drop_the_parameters_not_the_provider(raw, caplog):
    """Negative test: a reserved name is never sent. The provider stays, so a typo cannot lock everyone out."""
    result = _legacy_registry(raw)
    assert [p.id for p in result.providers] == ["default"]
    assert result.providers[0].authorize_params == ()
    assert any("OIDC_AUTHORIZE_PARAMS" in r.getMessage() and r.levelname == "ERROR" for r in caplog.records)


def test_legacy_default_provider_without_the_variable_is_unchanged():
    result = _legacy_registry("")
    assert result.errors == []
    assert result.providers[0].authorize_params == ()
