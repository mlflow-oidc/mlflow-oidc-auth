"""Server-side sessions (issue #310).

The session used to be the cookie: Starlette signed a dict holding the username and the server
kept no record, so a valid cookie stayed valid until it expired and there was nothing to revoke.
These tests hold the property that made the change worth making — **revocation takes effect on
the next request**, not whenever the cookie happens to lapse.

Deliberately no caching sits in front of ``resolve``: a cache would put a window between
revoking a session and the session stopping, which is the one thing this issue exists to remove.
"""

from datetime import datetime, timedelta, timezone

import pytest
from mlflow.exceptions import MlflowException

TOKEN = "session-token"  # not a credential: only ever seeded into a tmp_path database


def _in(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    # A second admin, so the last-active-admin invariant (#311) never masks a failure here.
    s.create_user("keeper@example.com", TOKEN, "Keeper", is_admin=True)
    s.create_user("alice@example.com", TOKEN, "Alice")
    yield s
    s.engine.dispose()


class TestCreateAndResolve:
    def test_a_session_resolves_to_its_user(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        resolved = store.resolve_auth_session(sid)

        assert resolved is not None
        assert resolved.username == "alice@example.com"
        assert resolved.is_admin is False
        assert resolved.is_active is True

    def test_resolve_returns_the_users_admin_flag(self, store):
        sid = store.create_auth_session("keeper@example.com", expires_at=_in(3600))

        assert store.resolve_auth_session(sid).is_admin is True

    def test_the_id_is_not_derived_from_the_user(self, store):
        """The cookie carries only this value, so it must not encode identity or be guessable."""
        first = store.create_auth_session("alice@example.com", expires_at=_in(3600))
        second = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        assert first != second
        assert "alice" not in first
        assert len(first) >= 32

    def test_a_username_is_normalized_on_the_way_in(self, store):
        sid = store.create_auth_session("ALICE@example.com", expires_at=_in(3600))

        assert store.resolve_auth_session(sid).username == "alice@example.com"

    def test_a_session_cannot_be_opened_for_an_unknown_user(self, store):
        with pytest.raises(MlflowException) as excinfo:
            store.create_auth_session("nobody@example.com", expires_at=_in(3600))

        assert excinfo.value.error_code == "RESOURCE_DOES_NOT_EXIST"


class TestRejection:
    """The three ways a cookie is presented and not honoured. All look identical from outside."""

    def test_an_unknown_id_does_not_resolve(self, store):
        assert store.resolve_auth_session("not-a-session") is None

    def test_an_empty_id_does_not_resolve(self, store):
        assert store.resolve_auth_session("") is None

    def test_an_expired_session_does_not_resolve(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(-1))

        assert store.resolve_auth_session(sid) is None

    def test_a_revoked_session_does_not_resolve(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        store.revoke_auth_session(sid)

        assert store.resolve_auth_session(sid) is None


class TestRevocation:
    def test_revocation_takes_effect_immediately(self, store):
        """The point of the issue: no TTL, no cache, no window."""
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))
        assert store.resolve_auth_session(sid) is not None

        store.revoke_auth_session(sid)

        assert store.resolve_auth_session(sid) is None

    def test_revoking_twice_is_not_an_error(self, store):
        """A double logout is ordinary, not exceptional."""
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        assert store.revoke_auth_session(sid) is True
        assert store.revoke_auth_session(sid) is False

    def test_revoking_an_unknown_id_reports_nothing_revoked(self, store):
        assert store.revoke_auth_session("not-a-session") is False

    def test_revoke_all_ends_every_session_a_user_has(self, store):
        sids = [store.create_auth_session("alice@example.com", expires_at=_in(3600)) for _ in range(3)]

        assert store.revoke_all_auth_sessions("alice@example.com") == 3

        assert [store.resolve_auth_session(sid) for sid in sids] == [None, None, None]

    def test_revoke_all_leaves_other_users_alone(self, store):
        mine = store.create_auth_session("alice@example.com", expires_at=_in(3600))
        theirs = store.create_auth_session("keeper@example.com", expires_at=_in(3600))

        store.revoke_all_auth_sessions("alice@example.com")

        assert store.resolve_auth_session(mine) is None
        assert store.resolve_auth_session(theirs) is not None

    def test_revoke_all_for_an_unknown_user_revokes_nothing(self, store):
        assert store.revoke_all_auth_sessions("nobody@example.com") == 0


class TestDeprovisioning:
    """Deactivating or deleting an account has to end the sessions it already has."""

    def test_deactivating_a_user_ends_their_sessions(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        store.update_user("alice@example.com", active=False)

        assert store.resolve_auth_session(sid) is None

    def test_deleting_a_user_ends_their_sessions(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        store.delete_user("alice@example.com")

        assert store.resolve_auth_session(sid) is None

    def test_reactivating_a_user_does_not_bring_sessions_back(self, store):
        """Revocation is one-way. A reactivated user logs in again."""
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))
        store.update_user("alice@example.com", active=False)

        store.update_user("alice@example.com", active=True)

        assert store.resolve_auth_session(sid) is None


class TestHousekeeping:
    def test_expired_rows_can_be_swept(self, store):
        expired = store.create_auth_session("alice@example.com", expires_at=_in(-1))
        live = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        assert store.auth_session_repo.delete_expired() == 1

        assert store.resolve_auth_session(expired) is None
        assert store.resolve_auth_session(live) is not None

    def test_live_sessions_can_be_listed(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))
        revoked = store.create_auth_session("alice@example.com", expires_at=_in(3600))
        store.revoke_auth_session(revoked)

        assert store.auth_session_repo.list_live_for_user("alice@example.com") == [sid]


class TestQueryBudget:
    def test_resolving_a_session_is_one_statement(self, store):
        """The auth path runs this on every request; its statement count is a budget (#305).

        A second round trip for the user's admin and active flags would double it — which is why
        ``resolve`` joins rather than looking the user up separately.
        """
        from sqlalchemy import event

        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        statements = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(store.engine, "before_cursor_execute", record)
        try:
            store.resolve_auth_session(sid)
        finally:
            event.remove(store.engine, "before_cursor_execute", record)

        selects = [s for s in statements if s.strip().upper().startswith("SELECT")]
        assert len(selects) == 1, f"expected one SELECT, got {len(selects)}: {selects}"
