"""SAML 2.0 SP-initiated SSO, end to end through the real middleware (issue #328).

The ACS is a cross-site POST, and under ``SameSite=Lax`` the browser does not send our cookie with
it. Every POST here is therefore made with the cookie jar cleared: the login has to be correlated
through ``RelayState`` alone, and the session cookie has to arrive fresh on the ACS response.

Every refusal is asserted twice: the status code, and that no session came out of it.
"""

import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from mlflow_oidc_auth.saml import request_id_for
from mlflow_oidc_auth.session.token_vault import get_token_vault
from mlflow_oidc_auth.tests.saml.conftest import (
    ACS_URL,
    IDP_SSO_URL,
    NAME_ID,
    OTHER_PROVIDER_ID,
    PROTECTED,
    PROVIDER_ID,
    SP_ENTITY_ID,
    USER_EMAIL,
    decoded_request,
    install_providers,
    post_to_acs,
    requires_saml,
    saml_provider,
    start_login,
)

pytestmark = requires_saml


def _authn_id(relay_state: str) -> str:
    return request_id_for(relay_state, "authn")


def _assert_no_session(client, store, username: str = USER_EMAIL):
    assert client.get(PROTECTED).status_code == 401
    if store.has_user(username):
        assert store.auth_session_repo.list_live_for_user(username) == []


def _events(audit_events, name):
    return [event for event in audit_events if event["event"] == name]


class TestLoginStartsAtTheIdP:
    def test_login_redirects_with_an_authn_request_tied_to_the_relay_state(self, client):
        response = client.get(f"/login/{PROVIDER_ID}")

        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith(IDP_SSO_URL + "?")
        relay_state = parse_qs(urlparse(location).query)["RelayState"][0]
        request_xml = decoded_request(location)
        assert f'ID="{_authn_id(relay_state)}"' in request_xml
        assert f'AssertionConsumerServiceURL="{ACS_URL}"' in request_xml
        assert f"<saml:Issuer>{SP_ENTITY_ID}</saml:Issuer>" in request_xml
        assert response.headers["cache-control"] == "no-store"

    def test_login_sets_no_cookie(self, client):
        """The attempt lives in the ``auth_state`` row; nothing the ACS needs can be in a cookie."""
        response = client.get(f"/login/{PROVIDER_ID}")

        assert "set-cookie" not in response.headers

    def test_an_unknown_provider_is_a_404(self, client):
        assert client.get("/login/nope").status_code == 404

    def test_an_unsigned_request_carries_no_signature(self, client):
        location = client.get(f"/login/{PROVIDER_ID}").headers["location"]

        assert "Signature" not in parse_qs(urlparse(location).query)

    def test_a_signed_request_verifies_against_the_sp_certificate(self, client, monkeypatch, idp_keys, sp_keys):
        from onelogin.saml2.utils import OneLogin_Saml2_Utils

        install_providers(monkeypatch, saml_provider(idp_keys, sp_x509_cert=sp_keys.cert_body, sp_private_key=sp_keys.key_pem, sign_requests=True))

        location = client.get(f"/login/{PROVIDER_ID}").headers["location"]
        query = urlparse(location).query
        params = parse_qs(query)
        # What was signed: every parameter but the signature, in the order sent.
        signed_part = "&".join(part for part in query.split("&") if not part.startswith("Signature="))

        assert params["SigAlg"] == ["http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"]
        assert OneLogin_Saml2_Utils.validate_binary_sign(
            signed_part, base64.b64decode(params["Signature"][0]), sp_keys.cert_pem, "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
        )


class TestSpInitiatedSsoEndToEnd:
    def test_a_valid_response_posted_without_a_cookie_opens_a_session(self, client, idp):
        relay_state = start_login(client)

        response = post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state)

        assert response.status_code == 302
        set_cookie = response.headers["set-cookie"]
        assert set_cookie.startswith("session=")
        assert "samesite=lax" in set_cookie.lower(), "the cookie policy must not be weakened for SAML"
        assert client.get(PROTECTED).json() == {"username": USER_EMAIL}

    def test_it_lands_on_the_sanitised_next_target(self, client, idp):
        relay_state = start_login(client, next_path="/#/experiments/1")

        response = post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state)

        assert response.headers["location"] == "/#/experiments/1"

    def test_an_off_site_next_is_dropped(self, client, idp):
        relay_state = start_login(client, next_path="//evil.example/")

        response = post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state)

        assert "evil.example" not in response.headers["location"]

    def test_the_session_row_holds_what_single_logout_needs(self, client, idp, store):
        relay_state = start_login(client)
        post_to_acs(client, idp.response(_authn_id(relay_state), session_index="_idx-42"), relay_state)

        [session_id] = store.auth_session_repo.list_live_for_user(USER_EMAIL)
        resolved = store.resolve_auth_session(session_id)
        tokens = get_token_vault().decrypt(resolved.encrypted_tokens)

        assert resolved.provider_id == PROVIDER_ID
        assert tokens.provider_id == PROVIDER_ID
        assert tokens.saml_name_id == NAME_ID
        assert tokens.saml_session_index == "_idx-42"
        assert tokens.refresh_token is None and tokens.id_token is None

    def test_the_identity_is_bound_to_the_provider_and_name_id(self, client, idp, store):
        relay_state = start_login(client)
        post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state)

        assert store.user_identity_repo.get_username_by_identity(PROVIDER_ID, NAME_ID) == USER_EMAIL

    def test_the_login_is_audited(self, client, idp, audit_events):
        relay_state = start_login(client)
        post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state)

        [event] = _events(audit_events, "auth.login")
        assert event["actor"] == USER_EMAIL
        assert event["detail"] == {"method": "saml", "provider": PROVIDER_ID}

    def test_groups_come_from_the_configured_attribute(self, client, idp, store):
        relay_state = start_login(client)
        post_to_acs(client, idp.response(_authn_id(relay_state), attributes={"email": [USER_EMAIL], "groups": ["mlflow", "data-science"]}), relay_state)

        # Namespaced by provider, as for any non-default provider: a partner IdP cannot name a local group.
        assert set(store.get_groups_for_user(USER_EMAIL)) == {f"{PROVIDER_ID}:mlflow", f"{PROVIDER_ID}:data-science"}

    def test_a_user_outside_the_allowed_groups_gets_no_session(self, client, idp, store):
        relay_state = start_login(client)

        response = post_to_acs(client, idp.response(_authn_id(relay_state), attributes={"email": [USER_EMAIL], "groups": ["other"]}), relay_state)

        assert response.status_code == 302
        assert "/auth?error=" in response.headers["location"]
        _assert_no_session(client, store)

    def test_admin_group_confers_nothing_when_admin_source_is_none(self, client, idp, store):
        relay_state = start_login(client)
        post_to_acs(client, idp.response(_authn_id(relay_state), attributes={"email": [USER_EMAIL], "groups": ["mlflow", "mlflow-admin"]}), relay_state)

        assert store.get_user(USER_EMAIL).is_admin is False


class TestResponseValidation:
    """Each of these is a forged, stale or misdirected Response. None may open a session."""

    @pytest.fixture
    def relay_state(self, client):
        return start_login(client)

    def _refused(self, client, store, saml_response, relay_state, audit_events=None):
        response = post_to_acs(client, saml_response, relay_state)
        assert response.status_code == 400, response.text
        assert response.json() == {"detail": "SAML sign-in failed"}, "a refusal must not say why"
        assert "set-cookie" not in response.headers
        _assert_no_session(client, store)
        return response

    def test_a_tampered_assertion_is_refused(self, client, store, idp, relay_state):
        signed = idp.sign(idp.assertion_xml(in_response_to=_authn_id(relay_state)))
        tampered = signed.replace("alice@example.com", "alicf@example.com")
        assert tampered != signed
        document = idp.response_xml(tampered, in_response_to=_authn_id(relay_state))

        self._refused(client, store, base64.b64encode(document.encode()).decode(), relay_state)

    def test_an_unsigned_assertion_is_refused(self, client, store, idp, relay_state):
        self._refused(client, store, idp.response(_authn_id(relay_state), sign_assertion=False), relay_state)

    def test_an_assertion_signed_by_another_key_is_refused(self, client, store, idp, relay_state, rogue_keys):
        self._refused(client, store, idp.response(_authn_id(relay_state), signing_keys=rogue_keys), relay_state)

    def test_the_wrong_audience_is_refused(self, client, store, idp, relay_state):
        self._refused(client, store, idp.response(_authn_id(relay_state), audience="https://other-sp.example.test"), relay_state)

    def test_a_missing_audience_is_refused(self, client, store, idp, relay_state):
        """python3-saml accepts an assertion with no AudienceRestriction; this SP does not."""
        self._refused(client, store, idp.response(_authn_id(relay_state), audience=None), relay_state)

    def test_the_wrong_issuer_is_refused(self, client, store, idp, relay_state):
        self._refused(client, store, idp.response(_authn_id(relay_state), issuer="https://evil-idp.example.test"), relay_state)

    def test_the_wrong_destination_is_refused(self, client, store, idp, relay_state):
        response = idp.response(_authn_id(relay_state), response_kwargs={"destination": "https://other-sp.example.test/acs"})

        self._refused(client, store, response, relay_state)

    def test_an_expired_assertion_is_refused(self, client, store, idp, relay_state):
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        response = idp.response(_authn_id(relay_state), not_before=past - timedelta(minutes=5), not_on_or_after=past, subject_not_on_or_after=past)

        self._refused(client, store, response, relay_state)

    def test_expiry_beyond_the_configured_skew_is_refused(self, client, store, idp, relay_state):
        """Two minutes stale passes python3-saml's fixed 300 s drift, but not the default 60 s."""
        stale = datetime.now(timezone.utc) - timedelta(minutes=2)
        response = idp.response(_authn_id(relay_state), not_on_or_after=stale, not_before=stale - timedelta(minutes=5))

        self._refused(client, store, response, relay_state)

    def test_expiry_within_a_wider_configured_skew_is_accepted(self, client, monkeypatch, idp, idp_keys):
        install_providers(monkeypatch, saml_provider(idp_keys, clock_skew_seconds=180))
        relay_state = start_login(client)
        stale = datetime.now(timezone.utc) - timedelta(minutes=2)

        response = post_to_acs(client, idp.response(_authn_id(relay_state), not_on_or_after=stale, not_before=stale - timedelta(minutes=5)), relay_state)

        assert response.status_code == 302

    def test_a_not_yet_valid_assertion_is_refused(self, client, store, idp, relay_state):
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        response = idp.response(_authn_id(relay_state), not_before=future, not_on_or_after=future + timedelta(minutes=5))

        self._refused(client, store, response, relay_state)

    def test_an_assertion_with_no_expiry_at_all_is_refused(self, client, store, idp, relay_state):
        """It would stay replayable forever, so it cannot be kept out of the replay table."""
        response = idp.response(_authn_id(relay_state), include_conditions_expiry=False, include_subject_expiry=False)

        self._refused(client, store, response, relay_state)

    def test_an_unsolicited_response_is_refused(self, client, store, idp, relay_state):
        """No InResponseTo is IdP-initiated SSO: nothing here asked for this assertion."""
        self._refused(client, store, idp.response(None), relay_state)

    def test_a_response_to_another_request_is_refused(self, client, store, idp, relay_state):
        other_relay_state = start_login(client)

        self._refused(client, store, idp.response(_authn_id(other_relay_state)), relay_state)

    def test_an_external_entity_is_never_expanded(self, client, store, idp, relay_state, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("xxe-marker-should-never-appear")
        assertion = idp.assertion_xml(in_response_to=_authn_id(relay_state), name_id="&xxe;")
        document = f'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY xxe SYSTEM "file://{secret}">]>' + idp.response_xml(
            assertion, in_response_to=_authn_id(relay_state)
        )

        response = self._refused(client, store, base64.b64encode(document.encode()).decode(), relay_state)

        assert "xxe-marker" not in response.text

    def test_the_library_parser_refuses_entities_outright(self):
        """Asserted directly too: the only XML parser in the SAML path forbids DTDs and entities."""
        from onelogin.saml2.xmlparser import fromstring

        with pytest.raises(Exception):
            fromstring(b'<!DOCTYPE r [<!ENTITY e "x">]><r>&e;</r>')

    def test_a_response_signature_is_required_when_configured(self, client, monkeypatch, store, idp, idp_keys):
        install_providers(monkeypatch, saml_provider(idp_keys, want_response_signed=True))

        relay_state = start_login(client)
        self._refused(client, store, idp.response(_authn_id(relay_state)), relay_state)

        relay_state = start_login(client)
        accepted = post_to_acs(client, idp.response(_authn_id(relay_state), sign_response=True), relay_state)
        assert accepted.status_code == 302

    def test_a_malformed_body_is_refused(self, client, store, relay_state):
        self._refused(client, store, "not-base64-%%%", relay_state)

    def test_a_non_form_body_is_refused(self, client, store):
        client.cookies.clear()
        response = client.post(f"/callback/{PROVIDER_ID}", json={"SAMLResponse": "x"})

        assert response.status_code == 400

    def test_a_duplicated_field_is_refused(self, client, store, idp, relay_state):
        client.cookies.clear()
        body = f"SAMLResponse=a&SAMLResponse=b&RelayState={relay_state}"

        response = client.post(f"/callback/{PROVIDER_ID}", content=body, headers={"content-type": "application/x-www-form-urlencoded"})

        assert response.status_code == 400

    def test_an_oversized_body_is_refused(self, client):
        client.cookies.clear()
        body = "SAMLResponse=" + "A" * (600 * 1024)

        response = client.post(f"/callback/{PROVIDER_ID}", content=body, headers={"content-type": "application/x-www-form-urlencoded"})

        assert response.status_code == 413

    def test_the_refusal_is_audited(self, client, store, idp, relay_state, audit_events):
        self._refused(client, store, idp.response(_authn_id(relay_state), sign_assertion=False), relay_state)

        [event] = _events(audit_events, "auth.saml_response_rejected")
        assert event["status"] == "denied"
        assert event["detail"] == {"provider": PROVIDER_ID}


class TestRelayStateAndReplay:
    def test_the_same_response_posted_twice_is_refused_the_second_time(self, client, store, idp):
        relay_state = start_login(client)
        saml_response = idp.response(_authn_id(relay_state))
        assert post_to_acs(client, saml_response, relay_state).status_code == 302
        store.revoke_all_auth_sessions(USER_EMAIL)

        replay = post_to_acs(client, saml_response, relay_state)

        assert replay.status_code == 400
        _assert_no_session(client, store)

    def test_a_replayed_assertion_id_is_refused_even_under_a_fresh_relay_state(self, client, store, idp, audit_events):
        """The RelayState is single-use, but the assertion table is what stops a copied assertion."""
        first = start_login(client)
        assert post_to_acs(client, idp.response(_authn_id(first), assertion_id="_same-assertion"), first).status_code == 302
        store.revoke_all_auth_sessions(USER_EMAIL)

        second = start_login(client)
        replay = post_to_acs(client, idp.response(_authn_id(second), assertion_id="_same-assertion"), second)

        assert replay.status_code == 400
        _assert_no_session(client, store)
        assert len(_events(audit_events, "auth.saml_replay_rejected")) == 1

    def test_a_relay_state_from_another_provider_is_refused(self, client, store, idp, audit_events):
        relay_state = start_login(client, provider_id=OTHER_PROVIDER_ID)

        response = post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state, provider_id=PROVIDER_ID)

        assert response.status_code == 400
        _assert_no_session(client, store)
        [event] = _events(audit_events, "auth.saml_relaystate_rejected")
        assert event["status"] == "denied"

    def test_a_relay_state_from_an_oidc_attempt_is_refused(self, client, store, idp):
        relay_state = store.create_auth_state("corp-oidc")

        assert post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state).status_code == 400

    def test_an_unknown_relay_state_is_refused(self, client, store, idp):
        assert post_to_acs(client, idp.response(_authn_id("made-up")), "made-up").status_code == 400
        _assert_no_session(client, store)

    def test_a_missing_relay_state_is_refused(self, client, store, idp):
        assert post_to_acs(client, idp.response(_authn_id("")), None).status_code == 400

    def test_an_expired_relay_state_is_refused(self, client, store, idp):
        relay_state = store.create_auth_state(PROVIDER_ID, lifetime_seconds=-1)

        assert post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state).status_code == 400
        _assert_no_session(client, store)

    def test_the_acs_of_an_unknown_or_non_saml_provider_is_a_404(self, client, idp):
        client.cookies.clear()
        assert client.post("/callback/nope", data={"SAMLResponse": "x", "RelayState": "y"}).status_code == 404
        assert client.post("/callback/corp-oidc", data={"SAMLResponse": "x", "RelayState": "y"}).status_code == 404

    def test_replay_records_are_swept_once_the_assertion_has_expired(self, client, store, idp):
        relay_state = start_login(client)
        post_to_acs(client, idp.response(_authn_id(relay_state)), relay_state)

        assert store.delete_expired_saml_assertions() == 0, "still inside its validity window"
        assert store.delete_expired_saml_assertions(datetime.now(timezone.utc) + timedelta(hours=1)) == 1


class TestProviderListing:
    def test_the_saml_provider_is_listed_with_its_login_url(self, client):
        listed = {entry["id"]: entry for entry in client.get("/providers").json()["providers"]}

        assert listed[PROVIDER_ID]["type"] == "saml"
        assert listed[PROVIDER_ID]["login_url"] == f"/login/{PROVIDER_ID}"


class TestTheSignedAssertionMustAnswerThisRequest:
    """The Response wrapper is unsigned when only the assertion is signed, so its InResponseTo and
    Destination prove nothing. The signed SubjectConfirmationData has to name this request and
    exactly this ACS."""

    def _wrapped(self, idp, relay_state, **assertion_kwargs):
        assertion = idp.sign(idp.assertion_xml(**assertion_kwargs))
        document = idp.response_xml(assertion, in_response_to=_authn_id(relay_state))
        return base64.b64encode(document.encode()).decode()

    def test_an_unsolicited_assertion_in_a_forged_wrapper_is_refused(self, client, store, idp):
        relay_state = start_login(client)

        response = post_to_acs(client, self._wrapped(idp, relay_state, in_response_to=None), relay_state)

        assert response.status_code == 400
        _assert_no_session(client, store)

    def test_an_assertion_for_a_provider_whose_id_extends_this_one_is_refused(self, client, store, idp):
        relay_state = start_login(client)

        response = post_to_acs(client, self._wrapped(idp, relay_state, in_response_to=_authn_id(relay_state), recipient=ACS_URL + "x"), relay_state)

        assert response.status_code == 400
        _assert_no_session(client, store)


class TestWorkspaceAssignment:
    """A configured workspace-detection plugin is the only source of membership. It reads an
    OAuth access token, which a SAML login does not have — so a SAML login gets no workspaces
    rather than falling back to an attribute the operator chose not to trust."""

    @pytest.fixture
    def granted(self, store, monkeypatch):
        from mlflow_oidc_auth.tests.saml.conftest import _patch_live_configs

        _patch_live_configs(monkeypatch, MLFLOW_ENABLE_WORKSPACES=True, OIDC_WORKSPACE_CLAIM_NAME="workspace")
        calls = []
        monkeypatch.setattr(store, "create_workspace_permission", lambda *args, **kwargs: calls.append(args))
        return calls

    def _login(self, client, idp):
        relay_state = start_login(client)
        attributes = {"email": [USER_EMAIL], "groups": ["mlflow"], "workspace": ["acme-finance"]}
        assert post_to_acs(client, idp.response(_authn_id(relay_state), attributes=attributes), relay_state).status_code == 302

    def test_with_a_plugin_configured_the_attribute_is_ignored(self, client, idp, granted, monkeypatch):
        from mlflow_oidc_auth.tests.saml.conftest import _patch_live_configs

        _patch_live_configs(monkeypatch, OIDC_WORKSPACE_DETECTION_PLUGIN="mlflow_oidc_auth.tests.saml.no_such_plugin")

        self._login(client, idp)

        assert granted == []

    def test_without_a_plugin_the_attribute_assigns_workspaces(self, client, idp, granted, monkeypatch):
        from mlflow_oidc_auth.tests.saml.conftest import _patch_live_configs

        _patch_live_configs(monkeypatch, OIDC_WORKSPACE_DETECTION_PLUGIN=None)

        self._login(client, idp)

        assert [call[:2] for call in granted] == [("acme-finance", USER_EMAIL)]
