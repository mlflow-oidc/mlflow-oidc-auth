"""In-flight authorization state as rows (issue #316).

The state used to be one ``oauth_state`` key in the cookie, which cannot hold two logins and
cannot say which provider started one. Both are what these cases pin.
"""

import pytest


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield s
    s.engine.dispose()


class TestAnAttemptRoundTrips:
    def test_what_was_started_is_what_comes_back(self, store):
        state = store.create_auth_state("entra", redirect_after_login="/oidc/ui/models")

        attempt = store.consume_auth_state(state)

        assert attempt.provider_id == "entra"
        assert attempt.redirect_after_login == "/oidc/ui/models"

    def test_the_state_is_unguessable(self, store):
        """It is the only thing tying a callback to the attempt that started it."""
        first = store.create_auth_state("entra")
        second = store.create_auth_state("entra")

        assert first != second
        assert len(first) >= 32
        assert "entra" not in first


class TestTwoTabsDoNotClobberEachOther:
    """The concrete bug a single cookie key caused: start a login in one tab, start another in a
    second, and the first tab's callback failed a CSRF check it should have passed."""

    def test_both_attempts_survive(self, store):
        first = store.create_auth_state("entra", redirect_after_login="/first")
        second = store.create_auth_state("okta", redirect_after_login="/second")

        assert store.consume_auth_state(first).redirect_after_login == "/first"
        assert store.consume_auth_state(second).redirect_after_login == "/second"

    def test_they_can_come_back_in_either_order(self, store):
        first = store.create_auth_state("entra")
        second = store.create_auth_state("okta")

        assert store.consume_auth_state(second).provider_id == "okta"
        assert store.consume_auth_state(first).provider_id == "entra"


class TestAnAttemptIsSingleUse:
    def test_the_second_use_finds_nothing(self, store):
        """A callback replayed from a browser history entry, a proxy log, or an attacker who
        captured the redirect must not be exchanged a second time."""
        state = store.create_auth_state("entra")

        assert store.consume_auth_state(state) is not None
        assert store.consume_auth_state(state) is None

    def test_an_unknown_state_finds_nothing(self, store):
        assert store.consume_auth_state("never-issued") is None

    def test_an_empty_state_finds_nothing(self, store):
        assert store.consume_auth_state("") is None


class TestExpiry:
    def test_an_expired_attempt_is_refused(self, store):
        state = store.create_auth_state("entra", lifetime_seconds=-1)

        assert store.consume_auth_state(state) is None

    def test_an_expired_attempt_is_still_consumed(self, store):
        """Refusing it is not enough — the row goes, so a stale state cannot be retried until it
        happens to race something."""
        state = store.create_auth_state("entra", lifetime_seconds=-1)
        store.consume_auth_state(state)

        assert store.auth_state_repo.delete_expired() == 0

    def test_abandoned_attempts_can_be_swept(self, store):
        store.create_auth_state("entra", lifetime_seconds=-1)
        live = store.create_auth_state("entra")

        assert store.auth_state_repo.delete_expired() == 1
        assert store.consume_auth_state(live) is not None


class TestConcurrentCallbacks:
    def test_only_one_of_two_racing_consumers_gets_the_attempt(self, store):
        """Two callbacks arriving with the same state — the victim's real one and a captured copy
        replayed at the same moment. Exactly one may proceed."""
        import threading

        state = store.create_auth_state("entra")
        results = []
        barrier = threading.Barrier(2)

        def consume():
            barrier.wait()
            results.append(store.consume_auth_state(state))

        threads = [threading.Thread(target=consume) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(result is None for result in results) == [False, True], f"expected exactly one winner, got {results}"
