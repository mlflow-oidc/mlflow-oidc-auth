"""OIDC against a real Keycloak: login, provisioning, the #367 refresh race, RP-initiated logout.

The provider is mostly the registry's ``default`` entry (``identity_binding: email``, JIT provisioning,
group sync on every login, admin from the ``mlflow-admins`` claim). Keycloak issues 10-second
access tokens, rotates refresh tokens and detects their reuse, so a second exchange of the same
refresh token would end the session at the IdP — which is exactly what the race test watches for.
One test logs in through a *named* OIDC entry over the same realm, to check that logout goes to
the provider that opened the session.
"""

from __future__ import annotations

import base64
import json
import time

from urllib.parse import parse_qs, urlparse

import itsdangerous
import pytest

from mlflow_oidc_auth.session.token_vault import SessionTokens, TokenVault
from mlflow_oidc_auth.tests.e2e import flows
from mlflow_oidc_auth.tests.e2e.harness import ACCESS_TOKEN_LIFESPAN_SECONDS, NAMED_OIDC_PROVIDER_ID, OIDC_PROVIDER_ID

pytestmark = pytest.mark.e2e

ALICE = "alice@example.com"
ROOT = "root@example.com"
# Bound to the named provider on first login; an account bound to one provider refuses another.
CAROL = "carol@example.com"
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


def _stored_tokens(app_server, cookie: str) -> SessionTokens:
    """The provider tokens the app keeps on the session row, decrypted with the app's key.

    Only a test holding ``SECRET_KEY`` can do this; it is how the suite gets the refresh token the
    app would present, to check afterwards what Keycloak thinks of it.
    """
    rows = app_server.db.query("SELECT encrypted_tokens FROM auth_sessions WHERE session_id = :sid", sid=_cookie_payload(cookie)["session_id"])
    tokens = TokenVault(app_server.secret_key).decrypt(rows[0]["encrypted_tokens"])
    assert tokens is not None and tokens.has_refresh_token, "the session row holds no refresh token"
    return tokens


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
        # The provider tokens are on the row, encrypted: a Fernet token (version byte 0x80 encodes
        # as "gAAAA"), never a JSON document, and it decrypts with the server's key into the
        # tokens the IdP issued. A substring check for a JWT prefix would be flaky here, since
        # random ciphertext eventually contains any short string.
        blob = rows[0]["encrypted_tokens"]
        assert blob and blob.startswith("gAAAA") and not blob.lstrip().startswith("{")
        tokens = TokenVault(app_server.secret_key).decrypt(blob)
        assert tokens is not None and tokens.refresh_token and tokens.id_token
        assert tokens.id_token.startswith("eyJ") and tokens.expires_at

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
        assert urlparse(flows.landing_url(landing)).path == "/oidc/ui/auth"
        assert keycloak.user_sessions(ALICE) == []
        # A fresh login needs credentials again: nothing at the IdP signs the browser straight back in.
        again = browser.follow(browser.get(f"{app_server.url}/login"))
        assert "kc-form-login" in again.text

    def test_logout_revokes_the_refresh_token_at_keycloak(self, app_server, keycloak):
        """RFC 7009 at logout: the ``offline_access`` grant does not outlive it.

        With ``OIDC_USE_REFRESH_TOKEN`` the plugin asks for ``offline_access``, and Keycloak keeps an
        *offline* session for the grant that RP-initiated logout alone does not end. ``/logout``
        therefore revokes the stored refresh token at Keycloak's ``revocation_endpoint`` before
        leaving, so the token is dead at the IdP, not merely forgotten by MLflow.
        """
        keycloak.logout_everywhere(ALICE)
        before = keycloak.offline_session_count(ALICE)
        browser = flows.login(app_server, ALICE)
        assert keycloak.offline_session_count(ALICE) == before + 1
        refresh_token = _stored_tokens(app_server, flows.session_cookie(browser)).refresh_token

        leaving = browser.get(f"{app_server.url}/logout")
        # Revoked before the redirect is even issued: nothing depends on the browser reaching Keycloak.
        refused = keycloak.refresh(refresh_token)
        assert refused.status_code == 400 and refused.json()["error"] == "invalid_grant", refused.text
        # Exactly this session's offline grant is gone; other logins' grants are untouched.
        assert keycloak.offline_session_count(ALICE) == before
        assert not app_server.audit_events("auth.token_revocation_failed")

        flows.drive_to_app(browser, leaving, app_server)


class TestNamedProviderLogout:
    def test_a_named_oidc_providers_session_is_logged_out_at_that_provider(self, app_server, keycloak):
        keycloak.logout_everywhere(CAROL)
        before = keycloak.offline_session_count(CAROL)
        browser = flows.login(app_server, CAROL, provider=NAMED_OIDC_PROVIDER_ID)
        cookie = flows.session_cookie(browser)
        status = flows.auth_status(app_server, cookie)
        assert status["authenticated"] is True and status["username"] == CAROL
        # Reported under the provider that opened the session, not the default one.
        assert status["provider"] == "Keycloak (named OIDC)"
        session_id = _cookie_payload(cookie)["session_id"]
        rows = app_server.db.query("SELECT provider_id FROM auth_sessions WHERE session_id = :sid", sid=session_id)
        assert rows[0]["provider_id"] == NAMED_OIDC_PROVIDER_ID
        tokens = _stored_tokens(app_server, cookie)
        assert keycloak.offline_session_count(CAROL) == before + 1

        leaving = browser.get(f"{app_server.url}/logout")
        assert leaving.status_code == 302
        location = leaving.headers["location"]
        # That provider's end-session endpoint — its issuer, not the default provider's.
        assert location.startswith(f"{keycloak.named_issuer}/protocol/openid-connect/logout?"), location
        query = parse_qs(urlparse(location).query)
        assert query["id_token_hint"] == [tokens.id_token]
        assert query["client_id"] == ["mlflow"]
        assert urlparse(query["post_logout_redirect_uri"][0]).path == "/oidc/ui/auth"
        assert flows.api_get(app_server, flows.CURRENT_USER, cookie).status_code == 401

        # Its refresh token was revoked at that provider too.
        refused = keycloak.refresh(tokens.refresh_token, issuer=keycloak.named_issuer)
        assert refused.status_code == 400 and refused.json()["error"] == "invalid_grant", refused.text
        assert keycloak.offline_session_count(CAROL) == before

        landing = flows.drive_to_app(browser, leaving, app_server)
        assert urlparse(flows.landing_url(landing)).path == "/oidc/ui/auth"
        assert keycloak.user_sessions(CAROL) == []
        # Keycloak's session at that issuer is over: logging in there again needs credentials.
        again = browser.follow(browser.get(f"{app_server.url}/login/{NAMED_OIDC_PROVIDER_ID}"))
        assert urlparse(str(again.url)).hostname == urlparse(keycloak.named_issuer).hostname
        assert "kc-form-login" in again.text
