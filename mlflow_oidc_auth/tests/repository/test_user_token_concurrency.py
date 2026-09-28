"""Issuing a token racing a deactivation (issue #189 review), on PostgreSQL.

SQLite serialises writers, so the race only exists where row locks do. These run when
``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (the CI unit-test job sets it) and skip otherwise.

The invariant: however the two interleave, a deactivated user ends up holding no token. One
transaction is held open by hand at the interesting point while the other runs in a thread.
"""

import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from mlflow.exceptions import MlflowException
from sqlalchemy import create_engine, text

POSTGRES_URI = os.environ.get("MLFLOW_OIDC_TEST_POSTGRES_URI")
ALICE = "alice@example.com"

pytestmark = pytest.mark.skipif(not POSTGRES_URI, reason="MLFLOW_OIDC_TEST_POSTGRES_URI is not set")


@pytest.fixture
def store():
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    engine = create_engine(POSTGRES_URI)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    s = SqlAlchemyStore()
    s.init_db(POSTGRES_URI)
    s.create_user("keeper@example.com", "Keeper", is_admin=True)
    s.create_user(ALICE, "Alice")
    yield s
    s.engine.dispose()


def _in_thread(fn):
    outcome = {}

    def run():
        try:
            outcome["result"] = fn()
        except Exception as e:  # recorded and asserted on by the caller
            outcome["error"] = e

    thread = threading.Thread(target=run)
    thread.start()
    return thread, outcome


def _assert_blocked(thread):
    time.sleep(0.5)
    assert thread.is_alive(), "expected the second transaction to wait for the first one's row lock"


def test_a_deactivation_waits_for_an_in_flight_issue_and_then_deletes_its_token(store):
    """The lost-delete: issue locks the row and inserts; deactivation must not delete first."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    held = store.engine.connect()
    issuing = held.begin()
    user_id = held.execute(text("SELECT id FROM users WHERE username = :u FOR UPDATE"), {"u": ALICE}).scalar()
    held.execute(
        text(
            "INSERT INTO user_tokens (user_id, name, token_prefix, token_hash, created_at, expires_at) "
            "VALUES (:uid, 'raced', 'abcdef01', 'pbkdf2:sha256:1000$x$y', :now, :exp)"
        ),
        {"uid": user_id, "now": now, "exp": now + timedelta(days=30)},
    )

    thread, outcome = _in_thread(lambda: store.update_user(ALICE, active=False, revoke_tokens=True))
    try:
        _assert_blocked(thread)
    finally:
        issuing.commit()
        held.close()
    thread.join(timeout=10)

    assert "error" not in outcome, outcome.get("error")
    assert store.get_user_detail(ALICE)["active"] is False
    assert store.list_user_tokens(ALICE) == [], "the token issued during deactivation survived it"


def test_an_issue_waits_for_an_in_flight_deactivation_and_is_then_refused(store):
    held = store.engine.connect()
    deactivating = held.begin()
    held.execute(text("UPDATE users SET active = false WHERE username = :u"), {"u": ALICE})

    thread, outcome = _in_thread(lambda: store.create_user_token(ALICE, "raced", datetime.now(timezone.utc) + timedelta(days=30), created_by=ALICE))
    try:
        _assert_blocked(thread)
    finally:
        deactivating.commit()
        held.close()
    thread.join(timeout=10)

    assert isinstance(outcome.get("error"), MlflowException)
    assert outcome["error"].error_code == "INVALID_STATE"
    assert store.list_user_tokens(ALICE) == []
