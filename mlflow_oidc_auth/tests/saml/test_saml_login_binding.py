"""SAML login CSRF: the Response must come back through the browser that started the login (issue #374).

``RelayState`` ties a Response to a live attempt, but not to a browser. Without a binding, an
attacker who completes a login for their own account can make a victim's browser POST that Response
to the ACS and sign the victim in as the attacker. ``/login`` therefore sets a per-attempt nonce
cookie — ``HttpOnly; Secure; SameSite=None``, path-scoped to the provider's ACS — and the ACS
requires it to hash to what the attempt's row recorded.

The test client talks plain http to ``testserver``, so a ``Secure`` cookie is never replayed from
its jar. Every ACS POST here is made with the jar cleared (as a cross-site POST under ``Lax``
arrives) and the binding cookie, when a test sends one, is put on the request explicitly — which
is exactly the one cookie a real browser sends on that POST.
"""

import hashlib
import logging
from http.cookies import SimpleCookie
from typing import Dict, Optional, Tuple
from urllib.parse import quote

import pytest

from mlflow_oidc_auth.routers.saml import BINDING_COOKIE_MAX_AGE_SECONDS, BINDING_COOKIE_PREFIX
from mlflow_oidc_auth.saml import request_id_for
from mlflow_oidc_auth.tests.saml.conftest import (
    PROTECTED,
    PROVIDER_ID,
    USER_EMAIL,
    _patch_live_configs,
    relay_state_of,
    requires_saml,
)

pytestmark = requires_saml

ACS_PATH = f"/callback/{PROVIDER_ID}"


def _authn_id(relay_state: str) -> str:
    return request_id_for(relay_state, "authn")


def _set_cookies(response) -> Dict[str, Tuple[str, Dict[str, str]]]:
    """Every cookie ``response`` sets: name -> (value, lower-cased attributes)."""
    cookies = {}
    for header in response.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        parsed.load(header)
        for name, morsel in parsed.items():
            attributes = {key.lower(): str(value) for key, value in morsel.items() if value not in ("", False)}
            # SimpleCookie reports flags as True; keep them visible as "True".
            cookies[name] = (morsel.value, attributes)
    return cookies


def _binding_cookies(response) -> Dict[str, Tuple[str, Dict[str, str]]]:
    return {name: value for name, value in _set_cookies(response).items() if name.startswith(BINDING_COOKIE_PREFIX)}


def _start(client) -> Tuple[str, Optional[str], Optional[str]]:
    """Start a login. Returns ``(relay_state, cookie_name, nonce)``; the last two None when unbound."""
    response = client.get(f"/login/{PROVIDER_ID}")
    assert response.status_code == 302, response.text
    relay_state = relay_state_of(response.headers["location"])
    binding = _binding_cookies(response)
    assert len(binding) <= 1
    if not binding:
        return relay_state, None, None
    [(name, (nonce, _))] = binding.items()
    return relay_state, name, nonce


def _post(client, idp, relay_state: str, cookie: Optional[Tuple[str, str]] = None):
    """The IdP's auto-submitted form, carrying only ``cookie`` (the one SameSite=None cookie)."""
    client.cookies.clear()
    headers = {"Cookie": f"{cookie[0]}={cookie[1]}"} if cookie else {}
    return client.post(ACS_PATH, data={"SAMLResponse": idp.response(_authn_id(relay_state)), "RelayState": relay_state}, headers=headers)


def _assert_no_session(client, store, response):
    assert "session" not in _set_cookies(response)
    client.cookies.clear()
    assert client.get(PROTECTED).status_code == 401
    if store.has_user(USER_EMAIL):
        assert store.auth_session_repo.list_live_for_user(USER_EMAIL) == []


def _assert_cleared(response, name: str):
    cookies = _set_cookies(response)
    assert name in cookies, f"the binding cookie was not cleared: {response.headers.get_list('set-cookie')}"
    value, attributes = cookies[name]
    assert value == ""
    assert attributes.get("max-age") == "0"
    assert attributes.get("path") == ACS_PATH


def _events(audit_events, name):
    return [event for event in audit_events if event["event"] == name]


@pytest.fixture
def bound(monkeypatch):
    """Secure cookies on, the switch on its default: the binding is active."""
    _patch_live_configs(monkeypatch, SESSION_COOKIE_SECURE=True, SAML_LOGIN_BINDING="auto")


class TestCsrfBindingCookie:
    def test_login_sets_a_short_lived_acs_scoped_cookie(self, client, bound):
        response = client.get(f"/login/{PROVIDER_ID}")

        [(name, (nonce, attributes))] = _binding_cookies(response).items()
        assert len(nonce) >= 43  # 256 bits, url-safe base64
        assert attributes["httponly"] == "True"
        assert attributes["secure"] == "True"
        assert attributes["samesite"].lower() == "none"
        assert attributes["path"] == ACS_PATH
        assert 0 < int(attributes["max-age"]) <= 600
        assert int(attributes["max-age"]) == BINDING_COOKIE_MAX_AGE_SECONDS
        # The session cookie is untouched by this: nothing but the binding cookie is set here.
        assert set(_set_cookies(response)) == {name}

    def test_the_row_stores_the_hash_never_the_nonce(self, client, store, bound):
        from mlflow_oidc_auth.db.models import SqlAuthState

        relay_state, _, nonce = _start(client)

        with store.ManagedSessionMaker() as session:
            row = session.query(SqlAuthState).filter(SqlAuthState.state == relay_state).one()
            assert row.binding_hash == hashlib.sha256(nonce.encode()).hexdigest()
            assert nonce not in (row.binding_hash, row.nonce, row.relay_state, row.state)

    def test_a_bound_row_lives_exactly_as_long_as_its_cookie(self, client, store, bound):
        """A slow login must fail as an expired RelayState, not as a live row with its cookie gone."""
        from mlflow_oidc_auth.db.models import SqlAuthState

        relay_state, _, _ = _start(client)

        with store.ManagedSessionMaker() as session:
            row = session.query(SqlAuthState).filter(SqlAuthState.state == relay_state).one()
            lifetime = (row.expires_at - row.created_at).total_seconds()
        assert abs(lifetime - BINDING_COOKIE_MAX_AGE_SECONDS) <= 5

    def test_an_unbound_row_keeps_the_default_lifetime(self, client, store, monkeypatch):
        from mlflow_oidc_auth.db.models import SqlAuthState
        from mlflow_oidc_auth.repository.auth_state import DEFAULT_STATE_LIFETIME_SECONDS

        _patch_live_configs(monkeypatch, SESSION_COOKIE_SECURE=False, SAML_LOGIN_BINDING="auto")
        relay_state, _, _ = _start(client)

        with store.ManagedSessionMaker() as session:
            row = session.query(SqlAuthState).filter(SqlAuthState.state == relay_state).one()
            lifetime = (row.expires_at - row.created_at).total_seconds()
        assert abs(lifetime - DEFAULT_STATE_LIFETIME_SECONDS) <= 5

    def test_each_attempt_gets_its_own_cookie(self, client, bound):
        first = _start(client)
        second = _start(client)

        assert first[1] != second[1] and first[2] != second[2]


class TestCsrfBindingEnforced:
    def test_a_valid_response_without_the_nonce_cookie_is_refused(self, client, idp, store, audit_events, bound):
        relay_state, _, _ = _start(client)

        response = _post(client, idp, relay_state, cookie=None)

        assert response.status_code == 400
        assert response.json() == {"detail": "SAML sign-in failed"}
        _assert_no_session(client, store, response)
        # No cookie at all is audited apart from a wrong one: a timeout is not an attack signal.
        [event] = _events(audit_events, "auth.saml_binding_missing")
        assert event["status"] == "denied" and event["detail"] == {"provider": PROVIDER_ID}
        assert not _events(audit_events, "auth.saml_binding_rejected")
        assert not _events(audit_events, "auth.login")

    def test_the_attackers_own_nonce_does_not_bind_another_attempt(self, client, idp, store, audit_events, bound):
        """The login-CSRF shape: the attacker's attempt, delivered by a browser holding a different attempt's nonce."""
        attacker_relay, _, _ = _start(client)
        _, victim_cookie, victim_nonce = _start(client)

        # The victim's browser holds a cookie for its own attempt; the attacker's RelayState names
        # another, whose cookie it does not hold. Per-attempt names make that a *missing* cookie.
        response = _post(client, idp, attacker_relay, cookie=(victim_cookie, victim_nonce))
        assert response.status_code == 400
        _assert_no_session(client, store, response)

        assert len(_events(audit_events, "auth.saml_binding_missing")) == 1

    def test_a_nonce_from_a_different_attempt_under_the_right_name_is_refused(self, client, idp, store, audit_events, bound):
        relay_state, cookie_name, nonce = _start(client)
        _, _, other_nonce = _start(client)

        response = _post(client, idp, relay_state, cookie=(cookie_name, other_nonce))

        assert response.status_code == 400
        _assert_no_session(client, store, response)
        assert _events(audit_events, "auth.saml_binding_rejected")
        assert not _events(audit_events, "auth.saml_binding_missing")
        _assert_cleared(response, cookie_name)

    @pytest.mark.parametrize("value", ["\xff" * 43, "abc\xffdef" + "a" * 40, "not a nonce!", "a" * 500])
    def test_a_malformed_nonce_is_refused_not_a_server_error(self, client, idp, store, audit_events, bound, value):
        """Starlette decodes the Cookie header as latin-1, so a non-ASCII value reaches the check intact."""
        relay_state, cookie_name, _ = _start(client)
        client.cookies.clear()
        header = f"{cookie_name}={value}".encode("latin-1")

        response = client.post(
            ACS_PATH,
            content=f"SAMLResponse={quote(idp.response(_authn_id(relay_state)), safe='')}&RelayState={quote(relay_state, safe='')}".encode("ascii"),
            headers=[(b"content-type", b"application/x-www-form-urlencoded"), (b"cookie", header)],
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "SAML sign-in failed"}
        assert len(_events(audit_events, "auth.saml_binding_rejected")) == 1
        _assert_cleared(response, cookie_name)
        _assert_no_session(client, store, response)

    def test_a_refused_attempt_is_spent(self, client, idp, store, bound):
        """The row is consumed before the binding check: the right cookie cannot rescue it afterwards."""
        relay_state, cookie_name, nonce = _start(client)
        assert _post(client, idp, relay_state, cookie=None).status_code == 400

        response = _post(client, idp, relay_state, cookie=(cookie_name, nonce))

        assert response.status_code == 400
        _assert_no_session(client, store, response)

    def test_the_matching_nonce_opens_a_session_and_clears_the_cookie(self, client, idp, audit_events, bound):
        relay_state, cookie_name, nonce = _start(client)

        response = _post(client, idp, relay_state, cookie=(cookie_name, nonce))

        assert response.status_code == 302
        cookies = _set_cookies(response)
        assert "session" in cookies and cookies["session"][1]["samesite"].lower() == "lax"
        _assert_cleared(response, cookie_name)
        assert client.get(PROTECTED).json() == {"username": USER_EMAIL}
        assert not _events(audit_events, "auth.saml_binding_rejected")
        assert not _events(audit_events, "auth.saml_binding_missing")
        assert _events(audit_events, "auth.login")

    def test_two_tabs_both_complete(self, client, idp, bound):
        first = _start(client)
        second = _start(client)

        assert _post(client, idp, second[0], cookie=(second[1], second[2])).status_code == 302
        assert _post(client, idp, first[0], cookie=(first[1], first[2])).status_code == 302

    def test_a_row_bound_before_the_switch_flipped_off_still_needs_its_cookie(self, client, idp, store, monkeypatch, bound):
        relay_state, _, _ = _start(client)
        _patch_live_configs(monkeypatch, SAML_LOGIN_BINDING="off")

        response = _post(client, idp, relay_state, cookie=None)

        assert response.status_code == 400
        _assert_no_session(client, store, response)

    def test_an_unbound_row_is_refused_while_the_binding_is_on(self, client, idp, store, audit_events, monkeypatch):
        """An attempt started before the binding was switched on carries no hash; it is not trusted."""
        relay_state, cookie_name, _ = _start(client)
        assert cookie_name is None
        _patch_live_configs(monkeypatch, SESSION_COOKIE_SECURE=True)

        response = _post(client, idp, relay_state, cookie=None)

        assert response.status_code == 400
        _assert_no_session(client, store, response)
        assert _events(audit_events, "auth.saml_binding_missing")

    def test_an_unexpected_error_is_a_500_that_still_clears_the_cookie(self, client, idp, store, audit_events, monkeypatch, bound, caplog):
        relay_state, cookie_name, nonce = _start(client)

        def outage(_state):
            raise RuntimeError(f"database unreachable (nonce {nonce})")

        monkeypatch.setattr(store, "consume_auth_state", outage)

        with caplog.at_level(logging.ERROR):
            response = _post(client, idp, relay_state, cookie=(cookie_name, nonce))

        assert response.status_code == 500
        assert response.json() == {"detail": "SAML sign-in failed"}
        _assert_cleared(response, cookie_name)
        [event] = _events(audit_events, "auth.saml_acs_error")
        assert event["status"] == "denied" and event["detail"] == {"provider": PROVIDER_ID, "error": "RuntimeError"}
        # The audit trail carries the type only, never the message.
        assert nonce not in str(event)
        assert any(record.exc_info for record in caplog.records if record.getMessage() == "Unexpected error in the SAML ACS")
        monkeypatch.undo()
        _assert_no_session(client, store, response)

    def test_an_unexpected_error_without_a_cookie_is_still_answered_and_audited(self, client, idp, store, audit_events, monkeypatch):
        relay_state, cookie_name, _ = _start(client)
        assert cookie_name is None
        monkeypatch.setattr(store, "consume_auth_state", lambda _state: (_ for _ in ()).throw(RuntimeError("down")))

        response = _post(client, idp, relay_state, cookie=None)

        assert response.status_code == 500
        assert _events(audit_events, "auth.saml_acs_error")
        assert not any(name.startswith(BINDING_COOKIE_PREFIX) for name in _set_cookies(response))

    def test_the_relaystate_check_still_comes_first(self, client, idp, audit_events, bound):
        response = _post(client, idp, "not-a-live-attempt", cookie=None)

        assert response.status_code == 400
        assert _events(audit_events, "auth.saml_relaystate_rejected")
        assert not _events(audit_events, "auth.saml_binding_rejected")
        assert not _events(audit_events, "auth.saml_binding_missing")


class TestCsrfBindingSwitch:
    def test_auto_is_off_without_secure_cookies(self, client, idp, monkeypatch):
        _patch_live_configs(monkeypatch, SESSION_COOKIE_SECURE=False, SAML_LOGIN_BINDING="auto")
        relay_state, cookie_name, _ = _start(client)

        assert cookie_name is None
        assert _post(client, idp, relay_state, cookie=None).status_code == 302

    def test_on_forces_the_binding_without_secure_cookies(self, client, idp, store, monkeypatch):
        _patch_live_configs(monkeypatch, SESSION_COOKIE_SECURE=False, SAML_LOGIN_BINDING="on")
        relay_state, cookie_name, nonce = _start(client)

        assert cookie_name is not None
        assert _post(client, idp, relay_state, cookie=None).status_code == 400
        relay_state, cookie_name, nonce = _start(client)
        assert _post(client, idp, relay_state, cookie=(cookie_name, nonce)).status_code == 302

    def test_on_still_marks_the_cookie_secure(self, client, monkeypatch):
        """``SameSite=None`` without ``Secure`` is rejected by current browsers; loopback http counts as secure."""
        _patch_live_configs(monkeypatch, SESSION_COOKIE_SECURE=False, SAML_LOGIN_BINDING="on")

        [(_, (_, attributes))] = _binding_cookies(client.get(f"/login/{PROVIDER_ID}")).items()

        assert attributes["secure"] == "True" and attributes["samesite"].lower() == "none" and attributes["httponly"] == "True"

    def test_off_disables_it_even_with_secure_cookies(self, client, idp, monkeypatch):
        _patch_live_configs(monkeypatch, SESSION_COOKIE_SECURE=True, SAML_LOGIN_BINDING="off")
        relay_state, cookie_name, _ = _start(client)

        assert cookie_name is None
        assert _post(client, idp, relay_state, cookie=None).status_code == 302


class TestCsrfBindingConfig:
    @pytest.mark.parametrize(
        "mode,secure,enabled",
        [("auto", True, True), ("auto", False, False), ("on", False, True), ("on", True, True), ("off", True, False), ("off", False, False)],
    )
    def test_enabled_matrix(self, monkeypatch, mode, secure, enabled):
        from mlflow_oidc_auth.config import AppConfig

        monkeypatch.setenv("SAML_LOGIN_BINDING", mode)
        monkeypatch.setenv("SESSION_COOKIE_SECURE", str(secure).lower())

        assert AppConfig().saml_login_binding_enabled is enabled

    def test_default_is_auto(self, monkeypatch):
        from mlflow_oidc_auth.config import AppConfig

        monkeypatch.delenv("SAML_LOGIN_BINDING", raising=False)

        assert AppConfig().SAML_LOGIN_BINDING == "auto"

    def test_an_unknown_value_is_refused(self, monkeypatch):
        from mlflow_oidc_auth.config import AppConfig

        monkeypatch.setenv("SAML_LOGIN_BINDING", "yes-please")

        with pytest.raises(ValueError, match="SAML_LOGIN_BINDING") as raised:
            AppConfig()
        assert "yes-please" not in str(raised.value)

    @pytest.mark.parametrize(
        "mode,secure,expected",
        [
            ("auto", False, "SAML login binding is disabled while a SAML provider is configured"),
            ("off", True, "SAML login binding is disabled while a SAML provider is configured"),
            ("on", False, "SAML login binding is forced on without secure cookies"),
            ("auto", True, None),
        ],
    )
    def test_startup_says_when_the_binding_is_off_or_forced(self, monkeypatch, caplog, idp_keys, mode, secure, expected):
        from mlflow_oidc_auth.config import AppConfig
        from mlflow_oidc_auth.tests.saml.conftest import saml_provider

        monkeypatch.setenv("SAML_LOGIN_BINDING", mode)
        monkeypatch.setenv("SESSION_COOKIE_SECURE", str(secure).lower())
        app_config = AppConfig()
        app_config.AUTH_PROVIDERS.providers.append(saml_provider(idp_keys))

        with caplog.at_level(logging.WARNING):
            app_config._log_saml_login_binding()

        messages = [record.getMessage() for record in caplog.records if "SAML login binding" in record.getMessage()]
        if expected is None:
            assert messages == []
        else:
            assert len(messages) == 1 and messages[0].startswith(expected)
            # No config value is interpolated into the line (CodeQL py/clear-text-logging-sensitive-data).
            assert "SAML_LOGIN_BINDING=" not in messages[0] and "=true" not in messages[0] and "=false" not in messages[0]

    def test_startup_is_silent_without_a_saml_provider(self, monkeypatch, caplog):
        from mlflow_oidc_auth.config import AppConfig

        monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
        app_config = AppConfig()

        with caplog.at_level(logging.WARNING):
            app_config._log_saml_login_binding()

        assert not [record for record in caplog.records if "SAML" in record.getMessage()]
