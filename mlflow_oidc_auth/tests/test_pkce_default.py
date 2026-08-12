"""PKCE is on by default (issue #312).

PKCE (RFC 7636) binds an authorization code to a secret held only by the client that started
the flow, so a code intercepted from a redirect — a browser history entry, a proxy log, a shared
machine — cannot be redeemed by whoever intercepted it. The plugin has always been able to do
it; it was off unless configured, which meant almost every deployment ran without it.

Turning it on by default is a behaviour change for anyone whose provider rejects it, so the two
things that need holding are the default itself and the opt-out — plus the failure mode, since
a provider that cannot do PKCE otherwise reports a bare ``invalid_grant`` naming nothing.
"""

from types import SimpleNamespace

import pytest

from mlflow_oidc_auth.config import AppConfig
from mlflow_oidc_auth.oauth import PKCEUnsupportedError, assert_pkce_supported


@pytest.fixture
def pkce_method(monkeypatch):
    """Set ``OIDC_CODE_CHALLENGE`` as seen by ``assert_pkce_supported`` itself.

    Not by module path: ``test_db_utils`` deletes ``mlflow_oidc_auth.config`` from
    ``sys.modules``, so later imports re-execute it and the process ends up holding two
    ``config`` objects. Patching ``mlflow_oidc_auth.oauth.config`` then patches whichever one
    ``sys.modules`` happens to hold, which is not necessarily the one this function closed over
    — a failure that only appears when another module ran first. Reaching through the
    function's own globals cannot be wrong.
    """

    def _set(method):
        monkeypatch.setitem(assert_pkce_supported.__globals__, "config", SimpleNamespace(OIDC_CODE_CHALLENGE=method))

    return _set


async def _never_called(*args, **kwargs):  # pragma: no cover - the PKCE check fires first
    raise AssertionError("the redirect must not be issued when PKCE is unsupported")


class FakeClient:
    """Stands in for an authlib client whose discovery document is already loaded."""

    def __init__(self, metadata=None, raises=None):
        self._metadata = metadata
        self._raises = raises

    async def load_server_metadata(self):
        if self._raises is not None:
            raise self._raises
        return self._metadata


class TestTheDefault:
    def test_pkce_is_on_when_nothing_is_configured(self):
        """The change. An unset variable used to mean "no PKCE"."""
        assert AppConfig._parse_code_challenge(None) == "S256"

    def test_s256_is_accepted_in_any_case(self):
        assert AppConfig._parse_code_challenge("s256") == "S256"
        assert AppConfig._parse_code_challenge(" S256 ") == "S256"

    @pytest.mark.parametrize("value", ["true", "yes", "on", "enabled", "1"])
    def test_affirmative_spellings_mean_s256(self, value):
        """Operators reach for whichever spelling their config tooling already uses, and a
        rejected value stops the server from starting — on the very upgrade this asks them to
        make."""
        assert AppConfig._parse_code_challenge(value) == "S256"

    def test_plain_is_refused_because_authlib_would_send_no_challenge_at_all(self):
        """RFC 7636 defines ``plain``, but authlib emits a challenge for S256 only ("only S256
        is supported", ``authlib/oauth2/client.py``). A client configured for ``plain`` sends an
        authorization request with no ``code_challenge`` — so accepting it would report PKCE as
        enabled while nothing was bound to the code. Worse than refusing it."""
        with pytest.raises(ValueError) as excinfo:
            AppConfig._parse_code_challenge("plain")

        message = str(excinfo.value)
        assert "S256" in message
        assert "none" in message


class TestTheOptOut:
    @pytest.mark.parametrize("value", ["none", "None", "off", "false", "no", "disabled", "0", "", "  "])
    def test_disabling_words_turn_pkce_off(self, value):
        assert AppConfig._parse_code_challenge(value) is None

    def test_disabling_pkce_says_so_out_loud(self, caplog):
        """An empty environment variable lands here too — a Helm value that rendered blank, a
        compose file with a trailing ``=``. Silently running without PKCE while the docs say it
        is on by default is the failure this warning exists to prevent."""
        with caplog.at_level("WARNING"):
            AppConfig._parse_code_challenge("")

        assert any("PKCE is disabled" in record.getMessage() for record in caplog.records)

    def test_a_typo_is_rejected_rather_than_sent_to_the_provider(self):
        """``S265`` would otherwise reach the authorization request as a challenge method no
        provider has heard of, failing the login with nothing pointing at the configuration."""
        with pytest.raises(ValueError) as excinfo:
            AppConfig._parse_code_challenge("S265")

        message = str(excinfo.value)
        assert "S265" in message
        assert "S256" in message, "the error has to name the value the operator wants"
        assert "none" in message, "and the way to turn it off"


class TestUnsupportedProviderIsReportedClearly:
    """The acceptance criterion: a non-PKCE provider produces a clear, actionable error."""

    @pytest.mark.asyncio
    async def test_a_provider_that_excludes_the_method_fails_before_the_redirect(self, pkce_method):
        pkce_method("S256")
        client = FakeClient({"code_challenge_methods_supported": ["plain"]})

        with pytest.raises(PKCEUnsupportedError) as excinfo:
            await assert_pkce_supported(client, "entra")

        message = str(excinfo.value)
        assert "entra" in message
        assert "S256" in message
        assert "plain" in message, "the message should say what the provider *does* support"
        assert "OIDC_CODE_CHALLENGE" in message, "and name the variable to change"

    @pytest.mark.asyncio
    async def test_a_provider_that_advertises_the_method_passes(self, pkce_method):
        pkce_method("S256")
        client = FakeClient({"code_challenge_methods_supported": ["S256", "plain"]})

        await assert_pkce_supported(client)

    @pytest.mark.asyncio
    async def test_silence_is_not_evidence_of_absence(self, pkce_method):
        """RFC 8414 makes the field optional and many providers support PKCE without listing it.
        Failing on a missing field would break logins that work today."""
        pkce_method("S256")

        await assert_pkce_supported(FakeClient({}))
        await assert_pkce_supported(FakeClient({"code_challenge_methods_supported": []}))
        await assert_pkce_supported(FakeClient(None))

    @pytest.mark.asyncio
    async def test_the_check_is_skipped_when_pkce_is_disabled(self, pkce_method):
        """Opting out must not then fail on the provider's advertised methods."""
        pkce_method(None)

        await assert_pkce_supported(FakeClient({"code_challenge_methods_supported": ["plain"]}))

    @pytest.mark.asyncio
    async def test_unreachable_discovery_does_not_break_login(self, pkce_method):
        """Discovery being down is a different failure, reported by the code that needs the
        metadata for real. This check must never be the thing that breaks a login."""
        pkce_method("S256")

        await assert_pkce_supported(FakeClient(raises=RuntimeError("connection refused")))

    @pytest.mark.asyncio
    async def test_a_client_without_metadata_support_is_left_alone(self, pkce_method):
        pkce_method("S256")

        await assert_pkce_supported(object())
        await assert_pkce_supported(None)


class TestTheRegisteredClientCarriesTheMethod:
    def test_the_challenge_method_reaches_authlib(self, monkeypatch):
        """The setting is only worth anything if it is handed to the client that builds the
        authorization request."""
        import mlflow_oidc_auth.oauth as oauth_module

        recorded = {}

        def fake_register(**kwargs):
            recorded.update(kwargs)

        monkeypatch.setattr(oauth_module.oauth, "register", fake_register)
        monkeypatch.setattr(oauth_module, "_registered", {})
        monkeypatch.setattr(
            oauth_module,
            "_client_settings",
            lambda provider_id: {"client_id": "cid", "client_secret": "sec", "server_metadata_url": "https://idp.invalid/.well-known/openid-configuration"},
        )
        monkeypatch.setattr(oauth_module.config, "OIDC_CODE_CHALLENGE", "S256")

        assert oauth_module.ensure_client_registered() is True

        assert recorded["client_kwargs"]["code_challenge_method"] == "S256"


class TestTheErrorReachesTheUser:
    """A clear message in a log nobody reads is not an actionable error."""

    @pytest.mark.asyncio
    async def test_login_reports_the_reason_to_the_operator(self, monkeypatch, caplog):
        from fastapi import HTTPException

        import mlflow_oidc_auth.routers.auth as auth_router_mod

        async def _unsupported(client, provider_id="default"):
            # The router's own class object: with duplicate modules in the process, the one
            # imported here may not be the one its ``except`` clause names.
            raise auth_router_mod.PKCEUnsupportedError("Provider 'default' does not support the configured PKCE method 'S256'. Set OIDC_CODE_CHALLENGE to ...")

        monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)
        monkeypatch.setattr(auth_router_mod, "assert_pkce_supported", _unsupported)
        # A registered client has to exist, or login fails earlier for an unrelated reason.
        monkeypatch.setattr(auth_router_mod.oauth, "oidc", SimpleNamespace(authorize_redirect=_never_called), raising=False)

        class DummyRequest:
            def __init__(self):
                self.session = {}
                self.base_url = "http://testserver"
                self.query_params = {}

        with caplog.at_level("ERROR"), pytest.raises(HTTPException) as excinfo:
            await auth_router_mod.login(DummyRequest())

        assert excinfo.value.status_code == 500
        # The detail stays generic: /login is unauthenticated and the message names an internal
        # registry id. The actionable sentence goes to the log instead.
        assert "OIDC_CODE_CHALLENGE" not in excinfo.value.detail
        assert "logs" in excinfo.value.detail
        assert any("OIDC_CODE_CHALLENGE" in record.getMessage() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_an_invalid_grant_exchange_failure_names_pkce(self, monkeypatch, caplog):
        """For providers that support nothing and advertise nothing: the pre-redirect check
        cannot see them, so the exchange failure is where the hint has to appear."""
        import mlflow_oidc_auth.routers.auth as auth_router_mod

        monkeypatch.setattr(auth_router_mod.config, "OIDC_CODE_CHALLENGE", "S256")

        async def _boom(request):
            raise RuntimeError("invalid_grant: PKCE verification failed")

        monkeypatch.setattr(auth_router_mod, "_authorize_access_token_with_retry", _boom)
        monkeypatch.setattr(auth_router_mod.oauth, "oidc", SimpleNamespace(authorize_access_token=_boom), raising=False)

        class DummyRequest:
            def __init__(self):
                self.session = {}
                self.base_url = "http://testserver"
                self.query_params = {"state": "s", "code": "c"}

        request = DummyRequest()
        session = {"oauth_state": "s"}

        with caplog.at_level("ERROR"):
            username, errors = await auth_router_mod._process_oidc_callback_fastapi(request, session)

        assert username is None and errors
        assert any("OIDC_CODE_CHALLENGE=none" in record.getMessage() for record in caplog.records)
