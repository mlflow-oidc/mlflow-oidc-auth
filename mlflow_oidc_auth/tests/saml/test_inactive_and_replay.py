"""Two seam fixes: a deactivated account cannot complete a login, and a LogoutRequest is single-use.

**Deactivated accounts.** SCIM deprovisions by deactivating, and the middleware refuses a
deactivated user's requests. A login that still *completed* — refreshing the row and minting a
session — would leave a credential that starts working again the moment the directory
reactivates the account. Both callbacks share ``_provision_login``, so both are driven here end to
end: SAML through a real signed Response, OIDC through the real callback with only the token
exchange stubbed.

**LogoutRequest replay.** A signed IdP-initiated LogoutRequest is a URL. Leaked from browser
history or a proxy log and replayed later, it would end sessions opened since.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from mlflow_oidc_auth.saml import request_id_for
from mlflow_oidc_auth.tests.saml.conftest import (
    PROTECTED,
    PROVIDER_ID,
    USER_EMAIL,
    _patch_live_configs,
    post_to_acs,
    requires_saml,
    start_login,
)

pytestmark = requires_saml

OIDC_PROVIDER = "corp-oidc"


def _events(audit_events, name):
    return [event for event in audit_events if event["event"] == name]


def _saml_login(client, idp, groups=("mlflow",), session_index="_session-index-1"):
    relay_state = start_login(client)
    attributes = {"email": [USER_EMAIL], "groups": list(groups)}
    return post_to_acs(client, idp.response(request_id_for(relay_state, "authn"), attributes=attributes, session_index=session_index), relay_state)


def _deactivate(store, username=USER_EMAIL):
    store.revoke_all_auth_sessions(username)
    store.update_user(username, active=False)
    assert store.get_user(username).active is False


@pytest.fixture
def oidc_login(client, store, monkeypatch):
    """Drive the real OIDC callback for ``corp-oidc``, stubbing only the IdP round trip."""
    import mlflow_oidc_auth.routers.auth as auth_module

    async def _exchange(request, provider_id=None):
        return {
            "access_token": "at",
            "userinfo": {"sub": "oidc|alice", "email": USER_EMAIL, "name": "Alice", "groups": ["mlflow"]},
        }

    async def _no_iss(provider):
        return False

    monkeypatch.setattr(auth_module, "is_oidc_configured", lambda provider_id=None: True)
    monkeypatch.setattr(auth_module, "get_client", lambda provider_id=None: SimpleNamespace(authorize_access_token=_exchange))
    monkeypatch.setattr(auth_module, "_authorize_access_token_with_key_refresh", _exchange)
    monkeypatch.setattr(auth_module, "_iss_parameter_supported", _no_iss)
    _patch_live_configs(monkeypatch, OIDC_GROUP_DETECTION_PLUGIN=None, OIDC_GROUPS_ATTRIBUTE="groups", OIDC_USERNAME_FIELD=["email"])

    def _login():
        client.cookies.clear()
        state = store.create_auth_state(OIDC_PROVIDER)
        return client.get(f"/callback/{OIDC_PROVIDER}", params={"state": state, "code": "c"})

    return _login


class TestADeactivatedAccountCannotSignIn:
    def test_saml_login_of_an_inactive_user_opens_nothing_and_writes_nothing(self, client, store, idp, audit_events):
        assert _saml_login(client, idp).status_code == 302
        groups_before = set(store.get_groups_for_user(USER_EMAIL))
        _deactivate(store)
        client.cookies.clear()

        response = _saml_login(client, idp, groups=("mlflow", "new-group"))

        assert response.status_code == 302
        assert "/auth?error=" in response.headers["location"]
        assert "set-cookie" not in response.headers, "no cookie may be issued for a deactivated account"
        assert client.get(PROTECTED).status_code == 401
        assert store.auth_session_repo.list_live_for_user(USER_EMAIL) == [], "no session row may be minted for a deactivated account"
        assert set(store.get_groups_for_user(USER_EMAIL)) == groups_before, "a refused login must not rewrite the account"
        [event] = _events(audit_events, "auth.denied_inactive")
        assert event["status"] == "denied"
        assert event["detail"] == {"method": "saml", "provider": PROVIDER_ID}
        assert len(_events(audit_events, "auth.login")) == 1, "only the login before deactivation succeeded"

    def test_reactivation_does_not_revive_anything_and_a_fresh_login_works(self, client, store, idp):
        _saml_login(client, idp)
        _deactivate(store)
        _saml_login(client, idp)

        store.update_user(USER_EMAIL, active=True)

        assert store.auth_session_repo.list_live_for_user(USER_EMAIL) == [], "nothing minted while inactive may come back"
        client.cookies.clear()
        assert _saml_login(client, idp).status_code == 302
        assert client.get(PROTECTED).json() == {"username": USER_EMAIL}

    def test_oidc_login_of_an_inactive_user_opens_nothing(self, client, store, oidc_login, audit_events):
        first = oidc_login()
        assert first.status_code == 302 and "error" not in first.headers["location"], first.headers.get("location")
        _deactivate(store)

        response = oidc_login()

        assert response.status_code == 302
        assert "/auth?error=" in response.headers["location"]
        assert client.get(PROTECTED).status_code == 401
        assert store.auth_session_repo.list_live_for_user(USER_EMAIL) == []
        [event] = _events(audit_events, "auth.denied_inactive")
        assert event["detail"] == {"method": "oidc", "provider": OIDC_PROVIDER}

    def test_oidc_login_works_again_after_reactivation(self, client, store, oidc_login):
        oidc_login()
        _deactivate(store)
        oidc_login()

        store.update_user(USER_EMAIL, active=True)

        assert store.auth_session_repo.list_live_for_user(USER_EMAIL) == []
        response = oidc_login()
        assert "error" not in response.headers["location"]
        assert client.get(PROTECTED).json() == {"username": USER_EMAIL}


class TestALogoutRequestIsSingleUse:
    def test_a_replayed_logout_request_is_refused_and_spares_later_sessions(self, client, store, idp, audit_events):
        _saml_login(client, idp)
        first_cookie = client.cookies.get("session")
        client.cookies.clear()
        query = idp.logout_request_query()

        assert client.get(f"/slo/{PROVIDER_ID}?" + query).status_code == 302
        _saml_login(client, idp)  # the same SessionIndex, opened after the logout
        later_cookie = client.cookies.get("session")
        client.cookies.clear()

        replay = client.get(f"/slo/{PROVIDER_ID}?" + query)

        assert replay.status_code == 400
        client.cookies.set("session", first_cookie)
        assert client.get(PROTECTED).status_code == 401
        client.cookies.clear()
        client.cookies.set("session", later_cookie)
        assert client.get(PROTECTED).status_code == 200, "a replay must not end a session opened after the original"
        assert len(_events(audit_events, "auth.slo_replay_rejected")) == 1

    def test_a_stale_request_without_not_on_or_after_is_refused(self, client, idp):
        _saml_login(client, idp)
        cookie = client.cookies.get("session")
        client.cookies.clear()

        stale = datetime.now(timezone.utc) - timedelta(minutes=30)
        response = client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(issue_instant=stale))

        assert response.status_code == 400
        client.cookies.set("session", cookie)
        assert client.get(PROTECTED).status_code == 200

    def test_a_request_with_not_on_or_after_is_kept_until_then(self, client, store, idp):
        _saml_login(client, idp)
        client.cookies.clear()
        until = datetime.now(timezone.utc) + timedelta(minutes=10)

        assert client.get(f"/slo/{PROVIDER_ID}?" + idp.logout_request_query(not_on_or_after=until)).status_code == 302

        assert store.delete_expired_saml_assertions() == 0
        # The login's assertion record lapses first (about five minutes); the logout record not
        # until the request's own NotOnOrAfter has passed.
        assert store.delete_expired_saml_assertions(datetime.now(timezone.utc) + timedelta(minutes=8)) == 1
        assert store.delete_expired_saml_assertions(until + timedelta(minutes=5)) == 1
