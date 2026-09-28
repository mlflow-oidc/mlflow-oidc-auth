"""``UserTokenRepository`` against a real database (issue #189).

What these pin, beyond "it works":

* authentication verifies **one** hash per request, however many tokens the user holds;
* a token authenticates only its own user, only while unexpired;
* the per-user cap, name uniqueness and lifetime limits hold;
* ``last_used_at`` is written at most once a minute;
* deleting is scoped to the owner — another user's token id reads as not found.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository import user_token as user_token_module
from mlflow_oidc_auth.repository.user_token import (
    LAST_USED_RESOLUTION_SECONDS,
    MAX_LIVE_TOKENS_PER_USER,
    parse_prefix,
)
from mlflow_oidc_auth.tests.token_helpers import set_known_token

ALICE = "alice@example.com"
BOB = "bob@example.com"
LEGACY_SECRET = "aB3dE6gH9jK2mN5pQ8sT1vW4"  # shaped like a pre-#189 secret; only ever in a tmp db


def _in(days: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ALICE, "Alice")
    s.create_user(BOB, "Bob")
    yield s
    s.engine.dispose()


def _expire(store, token_id: int) -> None:
    from mlflow_oidc_auth.db.models import SqlUserToken

    table = SqlUserToken.__table__
    with store.engine.begin() as conn:
        conn.execute(table.update().where(table.c.id == token_id).values(expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)))


class TestFormat:
    def test_the_plaintext_carries_its_prefix(self, store):
        record, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        assert plaintext.startswith(f"mlf_{record.token_prefix}_")
        assert parse_prefix(plaintext) == record.token_prefix

    @pytest.mark.parametrize("value", ["", LEGACY_SECRET, "mlf_short_x", "mlf_abcdefgh_", "scim_abcdefgh_secret", None, 42])
    def test_values_that_are_not_ours_have_no_prefix(self, value):
        assert parse_prefix(value) is None


class TestAuthenticate:
    def test_a_token_authenticates_its_user(self, store):
        _, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        assert store.authenticate_user(ALICE, plaintext) is True

    def test_the_username_is_case_insensitive(self, store):
        _, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        assert store.authenticate_user(ALICE.upper(), plaintext) is True

    def test_a_token_does_not_authenticate_another_user(self, store):
        """The prefix finds the row; the row must also belong to the named user."""
        _, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        assert store.authenticate_user(BOB, plaintext) is False

    def test_an_unknown_user_is_refused(self, store):
        _, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        assert store.authenticate_user("ghost@example.com", plaintext) is False

    def test_a_right_prefix_with_a_wrong_secret_is_refused(self, store):
        record, _ = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        assert store.authenticate_user(ALICE, f"mlf_{record.token_prefix}_not-the-secret") is False

    def test_an_expired_token_is_refused(self, store):
        record, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)
        _expire(store, record.id)

        assert store.authenticate_user(ALICE, plaintext) is False

    def test_a_deleted_token_is_refused_immediately(self, store):
        record, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        store.delete_user_token(ALICE, record.id)

        assert store.authenticate_user(ALICE, plaintext) is False

    @pytest.mark.parametrize("value", ["", None])
    def test_an_empty_secret_is_refused(self, store, value):
        set_known_token(store, ALICE, LEGACY_SECRET)

        assert store.authenticate_user(ALICE, value) is False

    def test_every_token_of_a_user_works_independently(self, store):
        tokens = [store.create_user_token(ALICE, f"t{i}", _in(30), created_by=ALICE)[1] for i in range(3)]

        assert all(store.authenticate_user(ALICE, t) for t in tokens)

    def test_one_hash_is_verified_however_many_tokens_the_user_holds(self, store):
        """The DoS the prefix exists to prevent: work must not scale with the user's token count."""
        for i in range(MAX_LIVE_TOKENS_PER_USER - 1):
            store.create_user_token(ALICE, f"t{i}", _in(30), created_by=ALICE)
        _, plaintext = store.create_user_token(ALICE, "last", _in(30), created_by=ALICE)
        set_known_token(store, ALICE, LEGACY_SECRET)

        real = user_token_module.check_password_hash
        with patch.object(user_token_module, "check_password_hash", side_effect=real) as spy:
            assert store.authenticate_user(ALICE, plaintext) is True
            assert store.authenticate_user(ALICE, f"mlf_{plaintext.split('_')[1]}_wrong") is False
            assert store.authenticate_user(ALICE, "not-any-token") is False
            assert store.authenticate_user(ALICE, LEGACY_SECRET) is True

        assert spy.call_count == 4

    def test_a_carried_over_secret_authenticates(self, store):
        set_known_token(store, ALICE, LEGACY_SECRET)

        assert store.authenticate_user(ALICE, LEGACY_SECRET) is True
        assert store.authenticate_user(BOB, LEGACY_SECRET) is False


class TestLastUsed:
    def test_the_first_use_is_recorded(self, store):
        _, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        store.authenticate_user(ALICE, plaintext)

        (record,) = store.list_user_tokens(ALICE)
        assert record.last_used_at is not None

    def test_it_is_written_at_most_once_a_minute(self, store):
        _, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)
        store.authenticate_user(ALICE, plaintext)
        (first,) = store.list_user_tokens(ALICE)

        store.authenticate_user(ALICE, plaintext)
        (second,) = store.list_user_tokens(ALICE)
        assert second.last_used_at == first.last_used_at

        later = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=LAST_USED_RESOLUTION_SECONDS + 1)
        with patch.object(user_token_module, "_now", return_value=later):
            store.authenticate_user(ALICE, plaintext)
        (third,) = store.list_user_tokens(ALICE)
        assert third.last_used_at == later

    def test_a_failed_attempt_is_not_recorded(self, store):
        record, _ = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        store.authenticate_user(ALICE, f"mlf_{record.token_prefix}_wrong")

        (after,) = store.list_user_tokens(ALICE)
        assert after.last_used_at is None


class TestCreate:
    def test_the_record_carries_no_secret(self, store):
        record, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by="admin@example.com")

        assert plaintext not in repr(record) and plaintext not in str(record.to_json())
        assert record.created_by == "admin@example.com"
        assert record.to_json()["active"] is True

    def test_names_are_unique_per_user(self, store):
        store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        with pytest.raises(MlflowException) as exc:
            store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)
        assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"

    def test_two_users_may_use_the_same_name(self, store):
        store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)
        store.create_user_token(BOB, "ci", _in(30), created_by=BOB)

    def test_the_name_is_trimmed_and_required(self, store):
        record, _ = store.create_user_token(ALICE, "  laptop  ", _in(30), created_by=ALICE)
        assert record.name == "laptop"

        with pytest.raises(MlflowException) as exc:
            store.create_user_token(ALICE, "   ", _in(30), created_by=ALICE)
        assert exc.value.error_code == "INVALID_PARAMETER_VALUE"

    def test_an_over_long_name_is_refused(self, store):
        with pytest.raises(MlflowException) as exc:
            store.create_user_token(ALICE, "x" * 256, _in(30), created_by=ALICE)
        assert exc.value.error_code == "INVALID_PARAMETER_VALUE"

    @pytest.mark.parametrize("expires_at", [_in(-1), _in(400), None])
    def test_the_lifetime_is_bounded_and_required(self, store, expires_at):
        with pytest.raises(MlflowException) as exc:
            store.create_user_token(ALICE, "ci", expires_at, created_by=ALICE)
        assert exc.value.error_code == "INVALID_PARAMETER_VALUE"

    def test_an_aware_expiry_is_stored_as_the_same_instant_in_utc(self, store):
        """A +14:00 offset must not become 14 extra hours of life (the store keeps naive UTC)."""
        wanted = _in(30).replace(microsecond=0).astimezone(timezone(timedelta(hours=14)))

        record, _ = store.create_user_token(ALICE, "ci", wanted, created_by=ALICE)

        assert record.expires_at.replace(tzinfo=timezone.utc) == wanted

    def test_an_unknown_user_is_not_found(self, store):
        with pytest.raises(MlflowException) as exc:
            store.create_user_token("ghost@example.com", "ci", _in(30), created_by=None)
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    def test_the_cap_counts_only_unexpired_tokens(self, store):
        records = [store.create_user_token(ALICE, f"t{i}", _in(30), created_by=ALICE)[0] for i in range(MAX_LIVE_TOKENS_PER_USER)]

        with pytest.raises(MlflowException) as exc:
            store.create_user_token(ALICE, "one-too-many", _in(30), created_by=ALICE)
        assert exc.value.error_code == "INVALID_STATE"

        _expire(store, records[0].id)
        store.create_user_token(ALICE, "room-again", _in(30), created_by=ALICE)

    def test_the_cap_is_per_user(self, store):
        for i in range(MAX_LIVE_TOKENS_PER_USER):
            store.create_user_token(ALICE, f"t{i}", _in(30), created_by=ALICE)

        store.create_user_token(BOB, "t0", _in(30), created_by=BOB)

    def test_issuing_clears_the_users_expired_tokens(self, store):
        """Expired rows can never authenticate; clearing them on issue keeps the table bounded
        however short the lifetimes a user keeps requesting."""
        old, _ = store.create_user_token(ALICE, "old", _in(30), created_by=ALICE)
        _expire(store, old.id)
        bobs, _ = store.create_user_token(BOB, "bobs", _in(30), created_by=BOB)
        _expire(store, bobs.id)

        store.create_user_token(ALICE, "new", _in(30), created_by=ALICE)

        assert [r.name for r in store.list_user_tokens(ALICE)] == ["new"]
        assert [r.name for r in store.list_user_tokens(BOB)] == ["bobs"], "only the issuing user's rows are cleared"

    def test_a_deactivated_user_cannot_be_issued_a_token(self, store):
        """A token issued to an inactive account would come back to life on reactivation."""
        store.update_user(ALICE, active=False)

        with pytest.raises(MlflowException) as exc:
            store.create_user_token(ALICE, "ci", _in(30), created_by="admin@example.com")
        assert exc.value.error_code == "INVALID_STATE"
        with pytest.raises(MlflowException) as exc:
            store.replace_user_token(ALICE, "default", _in(30), created_by="admin@example.com")
        assert exc.value.error_code == "INVALID_STATE"
        assert store.list_user_tokens(ALICE) == []

    def test_the_name_of_an_expired_token_can_be_reused(self, store):
        """The expired row is cleared before the duplicate-name check, not after."""
        old, _ = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)
        _expire(store, old.id)

        record, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        assert record.token_prefix != old.token_prefix
        assert store.authenticate_user(ALICE, plaintext) is True

    def test_the_lifetime_limit_is_exactly_366_days(self, store):
        store.create_user_token(ALICE, "edge", _in(365.99), created_by=ALICE)

        with pytest.raises(MlflowException):
            store.create_user_token(ALICE, "over", _in(366.01), created_by=ALICE)

    def test_a_prefix_seen_by_the_pre_check_is_retried(self, store):
        taken, _ = store.create_user_token(ALICE, "first", _in(30), created_by=ALICE)
        fresh = ("0f0f0f0f", "mlf_0f0f0f0f_fresh-secret")
        with patch.object(user_token_module, "generate_token", side_effect=[(taken.token_prefix, "mlf_x_y"), fresh]):
            record, plaintext = store.create_user_token(ALICE, "second", _in(30), created_by=ALICE)

        assert (record.token_prefix, plaintext) == fresh
        assert store.authenticate_user(ALICE, plaintext) is True


class TestReplace:
    def test_replacing_deletes_the_old_token_of_that_name_only(self, store):
        _, old = store.create_user_token(ALICE, "default", _in(30), created_by=ALICE)
        _, other = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        record, new, replaced = store.replace_user_token(ALICE, "default", _in(60), created_by=ALICE)

        assert replaced is True and record.name == "default"
        assert store.authenticate_user(ALICE, old) is False
        assert store.authenticate_user(ALICE, new) is True
        assert store.authenticate_user(ALICE, other) is True

    def test_replacing_a_carried_over_secret_issues_a_prefixed_token(self, store):
        set_known_token(store, ALICE, LEGACY_SECRET)

        record, new, replaced = store.replace_user_token(ALICE, "default", _in(60), created_by=ALICE)

        assert replaced is True and record.token_prefix is not None
        assert store.authenticate_user(ALICE, LEGACY_SECRET) is False
        assert store.authenticate_user(ALICE, new) is True

    def test_replacing_when_there_is_none_creates_one(self, store):
        _, new, replaced = store.replace_user_token(ALICE, "default", _in(60), created_by=ALICE)

        assert replaced is False
        assert store.authenticate_user(ALICE, new) is True

    def test_replacing_at_the_cap_is_allowed(self, store):
        """Rotating must work for a user at the cap: the token being replaced frees its slot."""
        for i in range(MAX_LIVE_TOKENS_PER_USER - 1):
            store.create_user_token(ALICE, f"t{i}", _in(30), created_by=ALICE)
        store.create_user_token(ALICE, "default", _in(30), created_by=ALICE)

        store.replace_user_token(ALICE, "default", _in(60), created_by=ALICE)


class TestDelete:
    def test_another_users_token_reads_as_not_found(self, store):
        record, plaintext = store.create_user_token(ALICE, "ci", _in(30), created_by=ALICE)

        with pytest.raises(MlflowException) as exc:
            store.delete_user_token(BOB, record.id)

        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"
        assert store.authenticate_user(ALICE, plaintext) is True

    def test_delete_all_removes_only_that_users_tokens(self, store):
        for i in range(3):
            store.create_user_token(ALICE, f"t{i}", _in(30), created_by=ALICE)
        _, bobs = store.create_user_token(BOB, "ci", _in(30), created_by=BOB)

        assert store.delete_user_tokens(ALICE) == 3

        assert store.list_user_tokens(ALICE) == []
        assert store.authenticate_user(BOB, bobs) is True

    def test_listing_includes_expired_tokens(self, store):
        record, _ = store.create_user_token(ALICE, "old", _in(30), created_by=ALICE)
        store.create_user_token(ALICE, "new", _in(30), created_by=ALICE)
        _expire(store, record.id)

        listed = {r.name: r.to_json()["active"] for r in store.list_user_tokens(ALICE)}

        assert listed == {"old": False, "new": True}


class TestIssueRacingADeactivationOnSqlite:
    """SQLite's driver begins a transaction only at the first write, so the issue path must take
    the write lock before it reads ``active`` — otherwise a deactivation that commits in between
    is missed and the new token survives it (#415 review)."""

    def test_an_issue_waits_for_an_open_deactivation_and_is_then_refused(self, store):
        import sqlite3
        import threading
        import time

        held = sqlite3.connect(store.engine.url.database, timeout=10, isolation_level=None)
        held.execute("BEGIN IMMEDIATE")
        held.execute("UPDATE users SET active = 0 WHERE username = ?", (ALICE,))
        outcome = {}

        def issue():
            try:
                outcome["result"] = store.create_user_token(ALICE, "raced", _in(30), created_by=ALICE)
            except MlflowException as e:
                outcome["error"] = e

        thread = threading.Thread(target=issue)
        thread.start()
        try:
            time.sleep(0.5)
            assert thread.is_alive(), "expected the issue to wait for the open deactivation"
        finally:
            held.execute("COMMIT")
            held.close()
        thread.join(timeout=15)

        assert outcome.get("error") is not None and outcome["error"].error_code == "INVALID_STATE", outcome
        assert store.list_user_tokens(ALICE) == []
