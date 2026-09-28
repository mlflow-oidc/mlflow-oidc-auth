"""Server-side sessions (issue #310).

The session used to be the cookie: Starlette signed a dict holding the username and the server
kept no record, so a valid cookie stayed valid until it expired and there was nothing to revoke.
These tests hold the property that made the change worth making — **revocation takes effect on
the next request**, not whenever the cookie happens to lapse.

Deliberately no caching sits in front of ``resolve``: a cache would put a window between
revoking a session and the session stopping, which is the one thing this issue exists to remove.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from mlflow.exceptions import MlflowException

TOKEN = "session-token"  # not a credential: only ever seeded into a tmp_path database
# An opaque stand-in for ciphertext. The repository never interprets the column.
BLOB = "opaque-encrypted-blob"
# The refresh-guard tests also run on PostgreSQL, where the row lock is real, when this is set.
POSTGRES_URI = os.environ.get("MLFLOW_OIDC_TEST_POSTGRES_URI")


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

    def test_the_token_blob_arrives_in_the_same_statement(self, store):
        """The encrypted tokens (#367) ride along in the one resolve, not a second query."""
        from sqlalchemy import event

        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600), provider_id="default", encrypted_tokens=BLOB)

        statements = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(store.engine, "before_cursor_execute", record)
        try:
            resolved = store.resolve_auth_session(sid)
        finally:
            event.remove(store.engine, "before_cursor_execute", record)

        selects = [s for s in statements if s.strip().upper().startswith("SELECT")]
        assert len(selects) == 1, f"expected one SELECT, got {len(selects)}: {selects}"
        assert resolved.encrypted_tokens == BLOB
        assert resolved.provider_id == "default"


class TestTokens:
    """The session row holds the encrypted provider tokens (#367)."""

    def test_create_stores_provider_and_tokens(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600), provider_id="corp", encrypted_tokens=BLOB)

        resolved = store.resolve_auth_session(sid)

        assert resolved.session_id == sid
        assert isinstance(resolved.session_pk, int)
        assert resolved.provider_id == "corp"
        assert resolved.encrypted_tokens == BLOB

    def test_a_session_without_tokens_resolves_with_none(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        resolved = store.resolve_auth_session(sid)

        assert resolved.encrypted_tokens is None
        assert resolved.provider_id is None

    def test_the_blob_is_kept_out_of_repr(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)
        assert BLOB not in repr(store.resolve_auth_session(sid))

    def test_store_tokens_replaces_the_blob(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)

        assert store.store_auth_session_tokens(sid, "rotated") is True
        assert store.resolve_auth_session(sid).encrypted_tokens == "rotated"

    def test_store_tokens_can_clear_the_blob(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)

        assert store.store_auth_session_tokens(sid, None) is True
        assert store.resolve_auth_session(sid).encrypted_tokens is None

    def test_store_tokens_does_not_touch_a_revoked_session(self, store):
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)
        store.revoke_auth_session(sid)

        assert store.store_auth_session_tokens(sid, "rotated") is False

    def test_store_tokens_for_an_unknown_session_reports_false(self, store):
        assert store.store_auth_session_tokens("no-such-session", "x") is False
        assert store.store_auth_session_tokens("", "x") is False


@pytest.fixture(params=["sqlite", "sqlite-row-lock-path", "postgres"])
def guard_store(request, tmp_path):
    """A store per guard implementation.

    ``sqlite-row-lock-path`` drives the ``SELECT ... FOR UPDATE`` code on SQLite, where the
    clause is a no-op: it proves the in-transaction read/write plumbing, while the real lock
    semantics are proven on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set.
    """
    from sqlalchemy import text

    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    if request.param == "postgres":
        if not POSTGRES_URI:
            pytest.skip("MLFLOW_OIDC_TEST_POSTGRES_URI is not set")
        from sqlalchemy import create_engine

        eng = create_engine(POSTGRES_URI)
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        eng.dispose()
        uri = POSTGRES_URI
    else:
        uri = f"sqlite:///{tmp_path / 'auth.db'}"

    s = SqlAlchemyStore()
    s.init_db(uri)
    if request.param == "sqlite-row-lock-path":
        s.auth_session_repo._row_locks = True
    s.create_user("keeper@example.com", TOKEN, "Keeper", is_admin=True)
    s.create_user("alice@example.com", TOKEN, "Alice")
    yield s
    s.engine.dispose()


class TestRefreshGuard:
    """Single-flight refresh (#367): one holder per session at a time, and a waiter sees its write."""

    def test_the_guard_yields_the_current_blob(self, guard_store):
        sid = guard_store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)

        with guard_store.auth_session_refresh_guard(sid) as guard:
            assert guard.live is True
            assert guard.encrypted_tokens == BLOB
            assert BLOB not in repr(guard)

    def test_a_write_inside_the_guard_is_stored(self, guard_store):
        sid = guard_store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)

        with guard_store.auth_session_refresh_guard(sid) as guard:
            written = guard.write("rotated")
            assert written is True
            assert guard.reread() == "rotated"

        assert guard_store.resolve_auth_session(sid).encrypted_tokens == "rotated"

    def test_a_revoked_session_is_not_live_and_cannot_be_written(self, guard_store):
        sid = guard_store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)
        guard_store.revoke_auth_session(sid)

        with guard_store.auth_session_refresh_guard(sid) as guard:
            assert guard.live is False
            assert guard.encrypted_tokens is None
            written = guard.write("rotated")
            assert written is False

    def test_holders_are_serialised_and_a_waiter_sees_the_previous_write(self, guard_store):
        import threading

        sid = guard_store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens="v0")
        first_inside = threading.Event()
        release_first = threading.Event()
        seen = {}

        def first():
            with guard_store.auth_session_refresh_guard(sid) as guard:
                first_inside.set()
                release_first.wait(5)
                guard.write("v1")

        def second():
            first_inside.wait(5)
            with guard_store.auth_session_refresh_guard(sid) as guard:
                seen["blob"] = guard.encrypted_tokens

        t1, t2 = threading.Thread(target=first), threading.Thread(target=second)
        t1.start()
        t2.start()
        first_inside.wait(5)
        t2.join(0.3)
        assert t2.is_alive(), "the second holder must wait while the first holds the guard"
        release_first.set()
        t1.join(5)
        t2.join(5)

        assert seen["blob"] == "v1"

    def test_different_sessions_do_not_block_each_other(self, guard_store):
        a = guard_store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens="a")
        b = guard_store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens="b")

        with guard_store.auth_session_refresh_guard(a):
            with guard_store.auth_session_refresh_guard(b) as guard_b:
                assert guard_b.encrypted_tokens == "b"

    def test_an_exception_releases_the_guard(self, guard_store):
        sid = guard_store.create_auth_session("alice@example.com", expires_at=_in(3600), encrypted_tokens=BLOB)

        def _boom():
            raise RuntimeError("boom")

        # The row-lock path re-wraps the error, so only the broad type is stable here.
        with pytest.raises(Exception):
            with guard_store.auth_session_refresh_guard(sid):
                _boom()

        with guard_store.auth_session_refresh_guard(sid) as guard:
            assert guard.encrypted_tokens == BLOB


class TestProcessLocks:
    def test_a_waiter_times_out_rather_than_hanging(self):
        import threading

        from mlflow_oidc_auth.repository.auth_session import _KeyedLocks

        locks = _KeyedLocks()
        held = threading.Event()
        release = threading.Event()

        def holder():
            with locks.hold("sid", timeout=5):
                held.set()
                release.wait(5)

        t = threading.Thread(target=holder)
        t.start()
        held.wait(5)
        try:
            with pytest.raises(TimeoutError):
                with locks.hold("sid", timeout=0.05):
                    pass
        finally:
            release.set()
            t.join(5)

    def test_entries_are_dropped_when_unused(self):
        from mlflow_oidc_auth.repository.auth_session import _KeyedLocks

        locks = _KeyedLocks()
        with locks.hold("a", timeout=1):
            assert len(locks) == 1
        assert len(locks) == 0
