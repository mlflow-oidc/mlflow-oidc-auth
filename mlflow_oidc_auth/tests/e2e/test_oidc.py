"""OIDC against a real Keycloak: login, provisioning, the #367 refresh race, RP-initiated logout.

The provider is the registry's ``default`` entry (``identity_binding: email``, JIT provisioning,
group sync on every login, admin from the ``mlflow-admins`` claim). Keycloak issues 10-second
access tokens, rotates refresh tokens and detects their reuse, so a second exchange of the same
refresh token would end the session at the IdP — which is exactly what the race test watches for.
"""

from __future__ import annotations

import base64
import json
import time

import itsdangerous
import pytest

from mlflow_oidc_auth.tests.e2e import flows
from mlflow_oidc_auth.tests.e2e.harness import ACCESS_TOKEN_LIFESPAN_SECONDS, OIDC_PROVIDER_ID

pytestmark = pytest.mark.e2e

ALICE = "alice@example.com"
ROOT = "root@example.com"
CONCURRENT_REQUESTS = 8
# Refresh-token material or identity must never ride in the cookie (#310, #367).
FORBIDDEN_COOKIE_KEYS = {"username", "refresh_token", "access_token", "id_token", "expires_at", "token", "userinfo"}


def _cookie_payload(cookie: str) -> dict:
    """The JSON a Starlette session cookie carries (signed, not encrypted — readable by anyone)."""
    data = cookie.split(".", 1)[0]
    return json.loads(base64.b64decode(data + "=" * (-len(data) % 4)))


def _signed_cookie(secret_key: str, payload: dict) -> str:
    """A cookie signed exactly as the app signs one — i.e. by someone who holds SECRET_KEY."""
    data = base64.b64encode(json.dumps(payload).encode())
    return itsdangerous.TimestampSigner(secret_key).sign(data).decode()


def _wait_until_access_token_expired() -> None:
    time.sleep(ACCESS_TOKEN_LIFESPAN_SECONDS + 1.5)


def _settled_events(keycloak, *types, **filters) -> list:
    """Events, read until two reads agree: Keycloak persists them in the request's transaction."""
    previous = None
    for _ in range(10):
        events = keycloak.events(*types, **filters)
        if previous is not None and len(events) == len(previous):
            return events
        previous = events
        time.sleep(0.5)
    return previous


class TestLoginAndProvisioning:
    def test_login_opens_a_server_side_session_named_by_an_opaque_id(self, app_server):
        browser = flows.login(app_server, ALICE)
        cookie = flows.session_cookie(browser)
        assert cookie, "the callback set no session cookie"

        status = flows.auth_status(app_server, cookie)
        assert status["authenticated"] is True
        assert status["username"] == ALICE

        payload = _cookie_payload(cookie)
        assert set(payload) <= {"session_id", "authenticated"}, f"unexpected cookie keys: {sorted(payload)}"
        assert not FORBIDDEN_COOKIE_KEYS & set(payload)
        session_id = payload["session_id"]
        assert ALICE not in session_id and "alice" not in session_id.lower()

        rows = app_server.db.query(
            "SELECT s.provider_id, s.revoked_at, s.encrypted_tokens, u.username FROM auth_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.session_id = :sid",
            sid=session_id,
        )
        assert len(rows) == 1
        assert rows[0]["username"] == ALICE
        assert rows[0]["provider_id"] in (OIDC_PROVIDER_ID, None)
        assert rows[0]["revoked_at"] is None
        # The provider tokens are on the row, encrypted — none of them is readable there either.
        assert rows[0]["encrypted_tokens"] and "eyJ" not in rows[0]["encrypted_tokens"]

    def test_first_login_provisions_a_manual_user_with_synced_groups(self, app_server):
        alice = flows.session_cookie(flows.login(app_server, ALICE))
        profile = flows.api_get(app_server, flows.CURRENT_USER, alice)
        assert profile.status_code == 200, profile.text
        body = profile.json()
        assert body["username"] == ALICE
        assert body["is_admin"] is False
        assert "mlflow-users" in {group["group_name"] for group in body["groups"]}

        root = flows.session_cookie(flows.login(app_server, ROOT))
        details = flows.api_get(app_server, "/api/2.0/mlflow/users/details", root)
        assert details.status_code == 200, details.text
        by_name = {row["username"]: row for row in details.json()}
        assert by_name[ALICE]["managed_by"] == "manual"
        assert by_name[ALICE]["active"] is True
        assert by_name[ALICE]["is_admin"] is False
        # root is in mlflow-admins only: admin_source "claims" + OIDC_ADMIN_GROUP_NAME.
        assert by_name[ROOT]["is_admin"] is True

        identities = app_server.db.query(
            "SELECT i.provider_id FROM user_identities i JOIN users u ON u.id = i.user_id WHERE u.username = :u",
            u=ALICE,
        )
        assert OIDC_PROVIDER_ID in {row["provider_id"] for row in identities}

    def test_a_non_admin_is_refused_the_admin_api(self, app_server):
        alice = flows.session_cookie(flows.login(app_server, ALICE))
        assert flows.api_get(app_server, "/api/2.0/mlflow/users/details", alice).status_code == 403


class TestForgedSessions:
    """The cookie is signed with SECRET_KEY, but the signature is not what authenticates."""

    def test_a_validly_signed_cookie_naming_no_session_is_refused(self, app_server):
        forged = _signed_cookie(app_server.secret_key, {"session_id": "forged-" + "A" * 40, "authenticated": True})
        assert flows.api_get(app_server, flows.CURRENT_USER, forged).status_code == 401
        assert flows.auth_status(app_server, forged)["authenticated"] is False

    def test_a_pre_310_username_cookie_is_refused(self, app_server):
        # The old format carried the username itself; honouring it would be unrevocable.
        legacy = _signed_cookie(app_server.secret_key, {"username": ALICE, "authenticated": True})
        assert flows.api_get(app_server, flows.CURRENT_USER, legacy).status_code == 401

    def test_garbage_and_resigned_cookies_are_refused(self, app_server):
        real = flows.session_cookie(flows.login(app_server, ALICE))
        assert flows.api_get(app_server, flows.CURRENT_USER, "not-a-cookie").status_code == 401
        # A real session id under a key the server does not hold.
        wrong_key = _signed_cookie("0" * 64, _cookie_payload(real))
        assert flows.api_get(app_server, flows.CURRENT_USER, wrong_key).status_code == 401
        # And the genuine cookie still works, so the refusals above are about the cookie.
        assert flows.api_get(app_server, flows.CURRENT_USER, real).status_code == 200


class TestRefreshSingleFlight:
    """#367 against a real IdP: rotation plus reuse detection, and concurrent expired requests."""

    def test_keycloak_revokes_a_replayed_refresh_token(self, keycloak):
        """Control: without this, one refresh event below would prove nothing."""
        tokens = keycloak.password_grant("bob@example.com", scope="openid email profile offline_access")
        first = keycloak.refresh(tokens["refresh_token"])
        assert first.status_code == 200, first.text
        replay = keycloak.refresh(tokens["refresh_token"])
        assert replay.status_code == 400 and replay.json()["error"] == "invalid_grant", replay.text
        # Reuse detection also kills the rotated token: a double exchange ends the session.
        assert keycloak.refresh(first.json()["refresh_token"]).status_code == 400

    def test_concurrent_requests_on_an_expired_session_refresh_exactly_once(self, app_server, keycloak):
        cookie = flows.session_cookie(flows.login(app_server, ALICE))
        assert flows.api_get(app_server, flows.CURRENT_USER, cookie).status_code == 200

        _wait_until_access_token_expired()
        keycloak.clear_events()

        responses = flows.concurrent_get(app_server, flows.CURRENT_USER, cookie, CONCURRENT_REQUESTS)
        assert [r.status_code for r in responses] == [200] * CONCURRENT_REQUESTS, [r.text[:200] for r in responses]

        refreshes = _settled_events(keycloak, "REFRESH_TOKEN", username=ALICE)
        assert len(refreshes) == 1, f"expected one refresh at the IdP, got {len(refreshes)}: {refreshes}"
        keycloak_session = refreshes[0]["sessionId"]
        errors = keycloak.events("REFRESH_TOKEN_ERROR", session_id=keycloak_session)
        assert errors == [], f"a refresh token was replayed: {errors}"

        # The token stored is the rotated one: the next expiry refreshes cleanly with it. A loser
        # of the race writing back the spent token would fail here with invalid_grant.
        _wait_until_access_token_expired()
        assert flows.api_get(app_server, flows.CURRENT_USER, cookie).status_code == 200
        refreshes = _settled_events(keycloak, "REFRESH_TOKEN", username=ALICE)
        assert len(refreshes) == 2
        assert keycloak.events("REFRESH_TOKEN_ERROR", session_id=keycloak_session) == []


class TestRpInitiatedLogout:
    def test_logout_revokes_the_session_before_leaving_and_logs_out_at_keycloak(self, app_server, keycloak):
        keycloak.logout_everywhere(ALICE)
        browser = flows.login(app_server, ALICE)
        cookie = flows.session_cookie(browser)
        session_id = _cookie_payload(cookie)["session_id"]

        leaving = browser.get(f"{app_server.url}/logout")
        assert leaving.status_code == 302
        location = leaving.headers["location"]
        assert location.startswith(f"{keycloak.issuer}/protocol/openid-connect/logout"), location
        # The session's own ID token is offered, so Keycloak can end the session without asking.
        assert "id_token_hint=" in location and "post_logout_redirect_uri=" in location and "client_id=mlflow" in location

        # Before the browser reaches Keycloak: the copied cookie is already dead, and the row says so.
        assert flows.api_get(app_server, flows.CURRENT_USER, cookie).status_code == 401
        assert flows.auth_status(app_server, cookie)["authenticated"] is False
        revoked = app_server.db.query("SELECT revoked_at FROM auth_sessions WHERE session_id = :sid", sid=session_id)
        assert revoked[0]["revoked_at"] is not None
        assert app_server.audit_events("auth.logout")

        # Keycloak accepts the logout request as built (a bad hint or an unregistered
        # post_logout_redirect_uri is an error page there) and sends the browser back to the app.
        landing = flows.drive_to_app(browser, leaving, app_server)
        assert landing.status_code == 200
        assert "/oidc/ui/auth" in str(landing.url)
        assert keycloak.user_sessions(ALICE) == []
        # A fresh login needs credentials again: nothing at the IdP signs the browser straight back in.
        again = browser.follow(browser.get(f"{app_server.url}/login"))
        assert "kc-form-login" in again.text

    def test_the_idp_grant_outlives_logout_because_refresh_uses_offline_access(self, app_server, keycloak):
        """Documents a known gap rather than a guarantee (see docs/development.md).

        With ``OIDC_USE_REFRESH_TOKEN`` the plugin asks for ``offline_access``. Keycloak then keeps
        an *offline* session for the grant, which RP-initiated logout does not end — the plugin
        revokes its own session row, so the grant is unusable through MLflow, but the refresh token
        stays valid at the IdP until its offline idle timeout. This test pins the current behaviour
        so a change to it (for example RFC 7009 revocation at logout) is noticed and the docs
        updated; it asserts nothing about MLflow access, which the test above covers.
        """
        keycloak.logout_everywhere(ALICE)
        before = keycloak.offline_session_count(ALICE)
        browser = flows.login(app_server, ALICE)
        assert keycloak.offline_session_count(ALICE) == before + 1
        flows.drive_to_app(browser, browser.get(f"{app_server.url}/logout"), app_server)
        assert keycloak.offline_session_count(ALICE) == before + 1
