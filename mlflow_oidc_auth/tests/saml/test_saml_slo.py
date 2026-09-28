"""SAML single logout, SP- and IdP-initiated (issue #329).

The property that matters most is ordering: the local session is destroyed *before* anything is
asked of the IdP, so an IdP that is down, refuses, or is never reached cannot leave a live
session here. Every SP-initiated test therefore replays the old cookie after ``/logout`` and
expects a 401, whatever became of the redirect.
"""

from urllib.parse import parse_qs, urlparse

import pytest

from mlflow_oidc_auth.saml import request_id_for
from mlflow_oidc_auth.tests.saml.conftest import (
    IDP_SLO_URL,
    NAME_ID,
    OIDC_LOGIN,
    PROTECTED,
    PROVIDER_ID,
    SLS_URL,
    USER_EMAIL,
    decoded_request,
    install_providers,
    oidc_provider,
    post_to_acs,
    relay_state_of,
    requires_saml,
    saml_provider,
    start_login,
)

pytestmark = requires_saml


def _login(client, idp, session_index: str = "_session-index-1") -> str:
    """Log in through the SAML provider; return the session cookie value."""
    relay_state = start_login(client)
    response = post_to_acs(client, idp.response(request_id_for(relay_state, "authn"), session_index=session_index), relay_state)
    assert response.status_code == 302, response.text
    return client.cookies.get("session")


def _authenticates(client, cookie: str) -> bool:
    client.cookies.clear()
    client.cookies.set("session", cookie)
    return client.get(PROTECTED).status_code == 200


def _events(audit_events, name):
    return [event for event in audit_events if event["event"] == name]


class TestSpInitiatedLogout:
    def test_logout_revokes_the_session_and_redirects_to_the_idp(self, client, idp):
        cookie = _login(client, idp, session_index="_idx-7")

        response = client.get("/logout")

        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith(IDP_SLO_URL + "?")
        request_xml = decoded_request(location)
        assert NAME_ID in request_xml
        assert "_idx-7" in request_xml
        assert f'ID="{request_id_for(relay_state_of(location), "logout")}"' in request_xml
        # The IdP is never contacted here. The old cookie must already be dead.
        assert not _authenticates(client, cookie)

    def test_the_session_is_revoked_even_when_the_logout_request_cannot_be_built(self, client, idp, monkeypatch):
        import mlflow_oidc_auth.routers.saml as saml_router_module

        def _broken(*args, **kwargs):
            raise RuntimeError("IdP unreachable")

        monkeypatch.setattr(saml_router_module, "build_logout_redirect", _broken)
        cookie = _login(client, idp)

        response = client.get("/logout")

        assert response.status_code == 302
        assert response.headers["location"].endswith("/oidc/ui/auth")
        assert not _authenticates(client, cookie)

    def test_a_provider_without_an_slo_endpoint_logs_out_locally(self, client, idp, idp_keys, monkeypatch):
        install_providers(monkeypatch, saml_provider(idp_keys, idp_slo_url=None))
        cookie = _login(client, idp)

        response = client.get("/logout")

        assert response.headers["location"].endswith("/oidc/ui/auth")
        assert not _authenticates(client, cookie)

    def test_logout_is_audited(self, client, idp, audit_events):
        _login(client, idp)

        client.get("/logout")

        assert [event["actor"] for event in _events(audit_events, "auth.logout")] == [USER_EMAIL]

    def test_the_idp_logout_response_lands_on_the_login_page(self, client, idp):
        _login(client, idp)
        relay_state = relay_state_of(client.get("/logout").headers["location"])

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_response_query(in_response_to=request_id_for(relay_state, "logout"), relay_state=relay_state))

        assert response.status_code == 302
        assert response.headers["location"].endswith("/oidc/ui/auth")

    def test_a_logout_response_to_another_request_is_refused(self, client, idp):
        _login(client, idp)
        relay_state = relay_state_of(client.get("/logout").headers["location"])

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_response_query(in_response_to="_not-ours", relay_state=relay_state))

        assert response.status_code == 400

    def test_a_logout_response_with_an_unknown_relay_state_is_refused(self, client, idp):
        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_response_query(in_response_to="_x", relay_state="made-up"))

        assert response.status_code == 400


class TestIdpInitiatedLogout:
    def test_a_signed_logout_request_ends_the_saml_sessions_and_answers_the_idp(self, client, idp, store, audit_events):
        saml_cookie = _login(client, idp)
        client.cookies.clear()
        assert client.get(OIDC_LOGIN).status_code == 200
        oidc_cookie = client.cookies.get("session")
        client.cookies.clear()

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query())

        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith(IDP_SLO_URL + "?")
        assert "SAMLResponse" in parse_qs(urlparse(location).query)
        assert parse_qs(urlparse(location).query)["RelayState"] == ["idp-relay"]
        assert not _authenticates(client, saml_cookie)
        assert _authenticates(client, oidc_cookie), "a SAML logout must not reach another provider's session"
        [event] = _events(audit_events, "auth.slo_idp_initiated")
        assert event["actor"] == USER_EMAIL
        assert event["detail"]["revoked"] == 1
        assert event["status"] == "success"

    def test_only_the_named_session_index_is_ended(self, client, idp):
        first = _login(client, idp, session_index="_idx-a")
        client.cookies.clear()
        second = _login(client, idp, session_index="_idx-b")
        client.cookies.clear()

        assert client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(session_indexes=("_idx-a",))).status_code == 302

        assert not _authenticates(client, first)
        assert _authenticates(client, second)

    def test_no_session_index_ends_every_session_from_the_provider(self, client, idp):
        first = _login(client, idp, session_index="_idx-a")
        client.cookies.clear()
        second = _login(client, idp, session_index="_idx-b")
        client.cookies.clear()

        assert client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(session_indexes=())).status_code == 302

        assert not _authenticates(client, first)
        assert not _authenticates(client, second)

    def test_a_request_for_an_unknown_subject_is_answered_and_revokes_nothing(self, client, idp):
        cookie = _login(client, idp)
        client.cookies.clear()

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(name_id="nobody@example.com"))

        assert response.status_code == 302
        assert _authenticates(client, cookie)

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"sign": False}, id="unsigned"),
            pytest.param({"issuer": "https://evil-idp.example.test"}, id="wrong-issuer"),
            pytest.param({"destination": "https://other-sp.example.test/slo"}, id="wrong-destination"),
            # python3-saml compares Destination by prefix: a request meant for /slo/saml1-eu
            # (same IdP certificate, another provider) would otherwise validate here.
            pytest.param({"destination": SLS_URL + "-eu"}, id="destination-prefix-of-another-provider"),
            pytest.param({"destination": SLS_URL + "/extra"}, id="destination-with-a-suffix"),
        ],
    )
    def test_an_invalid_logout_request_is_refused_and_revokes_nothing(self, client, idp, kwargs, audit_events):
        cookie = _login(client, idp)
        client.cookies.clear()

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(**kwargs))

        assert response.status_code == 400
        assert response.json() == {"detail": "SAML logout failed"}
        assert _authenticates(client, cookie)
        assert len(_events(audit_events, "auth.slo_request_rejected")) == 1
        assert _events(audit_events, "auth.slo_idp_initiated") == []

    def test_a_logout_request_signed_by_another_key_is_refused(self, client, idp, rogue_keys):
        cookie = _login(client, idp)
        client.cookies.clear()

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(signing_keys=rogue_keys))

        assert response.status_code == 400
        assert _authenticates(client, cookie)

    def test_a_tampered_signed_request_is_refused(self, client, idp):
        cookie = _login(client, idp)
        client.cookies.clear()
        query = idp.logout_request_query(relay_state="original")

        response = client.get(f"/slo/{PROVIDER_ID}?" + query.replace("RelayState=original", "RelayState=changed"))

        assert response.status_code == 400
        assert _authenticates(client, cookie)

    def test_a_provider_without_an_slo_endpoint_refuses_logout_requests(self, client, idp, idp_keys, monkeypatch):
        """Otherwise the LogoutResponse would be sent to the RelayState — a URL the sender chose."""
        install_providers(monkeypatch, saml_provider(idp_keys, idp_slo_url=None), oidc_provider())
        cookie = _login(client, idp)
        client.cookies.clear()

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(relay_state="https://evil.example/"))

        assert response.status_code == 400
        assert _authenticates(client, cookie)

    def test_a_revocation_failure_is_a_400_not_a_success(self, client, idp, store, monkeypatch):
        _login(client, idp)
        client.cookies.clear()

        def _fail(session_id):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(store, "revoke_auth_session", _fail)

        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query())

        assert response.status_code == 400

    def test_a_transient_revocation_failure_does_not_burn_the_request(self, client, idp, store, monkeypatch):
        """The IdP retries a LogoutRequest that got a 400. Its ID must not already be recorded
        as consumed, or the retry would be refused as a replay and the session left live."""
        cookie = _login(client, idp)
        client.cookies.clear()
        query = idp.logout_request_query()
        real_revoke = store.revoke_auth_session
        calls = {"n": 0}

        def _fail_once(session_id):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("database unavailable")
            return real_revoke(session_id)

        monkeypatch.setattr(store, "revoke_auth_session", _fail_once)

        assert client.get(f"/slo/{PROVIDER_ID}?" + query).status_code == 400
        assert _authenticates(client, cookie), "nothing was revoked by the failed attempt"
        client.cookies.clear()

        retried = client.get(f"/slo/{PROVIDER_ID}?" + query)

        assert retried.status_code == 302, retried.text
        assert not _authenticates(client, cookie)
        client.cookies.clear()
        assert client.get(f"/slo/{PROVIDER_ID}?" + query).status_code == 400, "once it succeeded, it is single use again"

    def test_a_failure_inside_revocation_also_releases_the_request(self, client, idp, store, monkeypatch):
        from mlflow_oidc_auth.routers import saml as saml_router_module

        cookie = _login(client, idp)
        client.cookies.clear()
        query = idp.logout_request_query()
        real = saml_router_module._revoke_for_logout_request
        calls = {"n": 0}

        def _explode_once(provider, logout):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("database unavailable")
            return real(provider, logout)

        monkeypatch.setattr(saml_router_module, "_revoke_for_logout_request", _explode_once)

        assert client.get(f"/slo/{PROVIDER_ID}?" + query).status_code == 400
        assert client.get(f"/slo/{PROVIDER_ID}?" + query).status_code == 302
        assert not _authenticates(client, cookie)

    @pytest.mark.parametrize("message", ["SAMLRequest", "SAMLResponse"])
    def test_the_post_binding_is_not_accepted(self, client, idp, message):
        """python3-saml verifies only redirect-binding signatures on logout messages, so a
        POST-bound LogoutRequest could never validate and a POST-bound LogoutResponse would be
        accepted unsigned. SLO is HTTP-Redirect only."""
        response = client.post(f"/slo/{PROVIDER_ID}", data={message: "x", "RelayState": "r"})

        assert response.status_code == 405

    def test_the_slo_endpoint_of_an_unknown_provider_is_a_404(self, client, idp):
        assert client.get("/slo/nope?" + idp.logout_request_query()).status_code == 404

    def test_a_request_with_neither_message_is_refused(self, client):
        assert client.get(f"/slo/{PROVIDER_ID}").status_code == 400

    def test_a_duplicated_parameter_is_refused(self, client, idp):
        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query() + "&SAMLRequest=x")

        assert response.status_code == 400
