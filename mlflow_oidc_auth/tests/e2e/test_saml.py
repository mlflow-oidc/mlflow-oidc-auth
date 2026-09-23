"""SAML 2.0 against a real Keycloak: SP-initiated SSO, SP-initiated SLO, IdP-initiated SLO.

Keycloak's ``mlflow-saml`` client signs assertions and documents with RSA-SHA256, forces an
email NameID, and uses the HTTP-Redirect binding for single logout (the only binding the SP's
``/slo`` accepts). The SP does not sign its requests, so the client has "client signature
required" off; the SP's own signing is covered by the unit tests.

IdP-initiated logout is driven headlessly: Keycloak's own logout endpoint, submitted from the
browser that holds the Keycloak session, makes Keycloak send a signed LogoutRequest to the SP's
``/slo`` through the browser (front-channel, HTTP-Redirect) — the path a real user's "sign out
everywhere" takes. Keycloak's admin "log out user" is back-channel only and would POST, which the
SP refuses by design, so it is not used.
"""

from __future__ import annotations

import base64
import json
from urllib.parse import urlparse

import httpx
import pytest

from mlflow_oidc_auth.tests.e2e import flows
from mlflow_oidc_auth.tests.e2e.browser import parse_forms
from mlflow_oidc_auth.tests.e2e.harness import SAML_PROVIDER_ID

pytestmark = pytest.mark.e2e

BOB = "bob@example.com"
ACS = f"/callback/{SAML_PROVIDER_ID}"
SLO = f"/slo/{SAML_PROVIDER_ID}"


def _session_id(cookie: str) -> str:
    data = cookie.split(".", 1)[0]
    return json.loads(base64.b64decode(data + "=" * (-len(data) % 4)))["session_id"]


def _sessions_by_id(app_server, session_id: str) -> list:
    return app_server.db.query(
        "SELECT s.provider_id, s.revoked_at, u.username FROM auth_sessions s JOIN users u ON u.id = s.user_id WHERE s.session_id = :sid",
        sid=session_id,
    )


def _saml_login(app_server, keycloak):
    keycloak.logout_everywhere(BOB)
    browser = flows.login(app_server, BOB, provider=SAML_PROVIDER_ID)
    cookie = flows.session_cookie(browser)
    assert cookie, "the ACS set no session cookie"
    return browser, cookie


class TestSpInitiatedSso:
    def test_login_sets_the_cookie_on_the_acs_response_without_reading_one(self, app_server, keycloak):
        browser, cookie = _saml_login(app_server, keycloak)

        acs_posts = [r for r in browser.history if r.request.method == "POST" and urlparse(str(r.url)).path == ACS]
        assert len(acs_posts) == 1
        acs = acs_posts[0]
        # Cross-site POST under SameSite=Lax: the browser sends none of the app's cookies, and the
        # login must not need one — RelayState ties the Response to its attempt.
        assert "cookie" not in acs.request.headers
        assert acs.status_code == 302
        assert any(header.startswith("session=") for header in acs.headers.get_list("set-cookie"))

        status = flows.auth_status(app_server, cookie)
        assert status["authenticated"] is True and status["username"] == BOB

        rows = _sessions_by_id(app_server, _session_id(cookie))
        assert len(rows) == 1
        assert rows[0]["provider_id"] == SAML_PROVIDER_ID
        assert rows[0]["username"] == BOB

        identities = app_server.db.query(
            "SELECT i.provider_id, i.subject FROM user_identities i JOIN users u ON u.id = i.user_id WHERE u.username = :u",
            u=BOB,
        )
        assert (SAML_PROVIDER_ID, BOB) in {(row["provider_id"], row["subject"]) for row in identities}
        # Groups from a non-default provider are stored namespaced.
        profile = flows.api_get(app_server, flows.CURRENT_USER, cookie).json()
        assert f"{SAML_PROVIDER_ID}:mlflow-users" in {group["group_name"] for group in profile["groups"]}
        assert app_server.audit_events("auth.login")

    def test_a_replayed_response_is_refused(self, app_server, keycloak):
        browser, _ = _saml_login(app_server, keycloak)
        acs = next(r for r in browser.history if r.request.method == "POST" and urlparse(str(r.url)).path == ACS)
        assert b"SAMLResponse=" in acs.request.content
        replay = httpx.post(f"{app_server.url}{ACS}", content=acs.request.content, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30.0)
        # The RelayState is single-use, so a verbatim replay is refused before signature checks.
        assert replay.status_code == 400
        assert "set-cookie" not in replay.headers


class TestSpInitiatedSlo:
    def test_logout_revokes_first_then_completes_single_logout_at_keycloak(self, app_server, keycloak):
        browser, cookie = _saml_login(app_server, keycloak)
        session_id = _session_id(cookie)
        assert len(keycloak.user_sessions(BOB)) == 1

        leaving = browser.get(f"{app_server.url}/logout")
        assert leaving.status_code == 302
        assert leaving.headers["location"].startswith(f"{keycloak.saml_issuer}/protocol/saml?SAMLRequest="), leaving.headers["location"]

        # Revoked BEFORE the redirect is followed: the old cookie is dead while the browser is
        # still on its way to the IdP.
        assert flows.api_get(app_server, flows.CURRENT_USER, cookie).status_code == 401
        assert _sessions_by_id(app_server, session_id)[0]["revoked_at"] is not None

        landing = flows.drive_to_app(browser, leaving, app_server)
        slo = [r for r in browser.history if urlparse(str(r.url)).path == SLO]
        assert len(slo) == 1, [str(r.url) for r in browser.history]
        assert "SAMLResponse=" in str(slo[0].url) and "Signature=" in str(slo[0].url)
        assert slo[0].status_code == 302
        assert urlparse(slo[0].headers["location"]).path.endswith("/auth")
        assert urlparse(flows.landing_url(landing)).path == "/oidc/ui/auth"
        assert keycloak.user_sessions(BOB) == []


class TestIdpInitiatedSlo:
    def test_keycloak_logout_revokes_the_saml_session_through_the_sls(self, app_server, keycloak):
        browser, cookie = _saml_login(app_server, keycloak)
        # A second SAML session of the same user, in another browser and so another Keycloak
        # session: the LogoutRequest names one SessionIndex, and only that session may end.
        other = flows.session_cookie(flows.login(app_server, BOB, provider=SAML_PROVIDER_ID))
        assert flows.api_get(app_server, flows.CURRENT_USER, other).status_code == 200
        assert len(keycloak.user_sessions(BOB)) == 2

        browser.history.clear()
        confirm = browser.get(f"{keycloak.saml_issuer}/protocol/openid-connect/logout")
        form = next(form for form in parse_forms(confirm.text) if "logout" in form.action)
        done = browser.follow(browser.submit(confirm, form))
        assert done.status_code == 200, done.text[:500]

        slo = [r for r in browser.history if urlparse(str(r.url)).path == SLO]
        assert len(slo) == 1, [str(r.url) for r in browser.history]
        request_url = str(slo[0].url)
        assert "SAMLRequest=" in request_url and "Signature=" in request_url
        # The SP answered with a LogoutResponse to Keycloak, which then finished its logout.
        assert slo[0].status_code == 302
        assert slo[0].headers["location"].startswith(f"{keycloak.saml_issuer}/protocol/saml?SAMLResponse=")

        assert flows.api_get(app_server, flows.CURRENT_USER, cookie).status_code == 401
        assert flows.api_get(app_server, flows.CURRENT_USER, other).status_code == 200
        assert len(keycloak.user_sessions(BOB)) == 1
        events = app_server.audit_events("auth.slo_idp_initiated")
        assert events and events[-1]["detail"]["revoked"] == 1 and events[-1]["status"] == "success"

        # The signed LogoutRequest is single-use: replaying the exact URL ends nothing.
        replay = httpx.get(request_url, timeout=30.0)
        assert replay.status_code == 400
        assert app_server.audit_events("auth.slo_replay_rejected")

    def test_an_unsigned_logout_request_is_refused(self, app_server, keycloak):
        browser, cookie = _saml_login(app_server, keycloak)
        browser.history.clear()
        confirm = browser.get(f"{keycloak.saml_issuer}/protocol/openid-connect/logout")
        form = next(form for form in parse_forms(confirm.text) if "logout" in form.action)
        # Stop at the SP: take Keycloak's genuine LogoutRequest, strip its signature, deliver that.
        to_sp = browser.follow(browser.submit(confirm, form), stop_at=f"{app_server.url}{SLO}")
        signed = to_sp.headers["location"]
        unsigned = "&".join(part for part in urlparse(signed).query.split("&") if not part.startswith(("Signature=", "SigAlg=")))
        refused = httpx.get(f"{app_server.url}{SLO}?{unsigned}", timeout=30.0)
        assert refused.status_code == 400
        # Nothing was revoked by the forgery.
        assert flows.api_get(app_server, flows.CURRENT_USER, cookie).status_code == 200
        assert app_server.audit_events("auth.slo_request_rejected")
