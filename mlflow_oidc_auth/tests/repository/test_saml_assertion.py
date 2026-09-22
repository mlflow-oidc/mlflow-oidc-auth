"""Replay records for SAML assertions (issue #328), against a real SQLite store."""

from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield s
    s.engine.dispose()


def _later(minutes: int = 5) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


class TestRecord:
    def test_the_first_use_is_recorded(self, store):
        assert store.record_saml_assertion("_a1", "corp", _later()) is True

    def test_a_second_use_is_a_replay(self, store):
        store.record_saml_assertion("_a1", "corp", _later())

        assert store.record_saml_assertion("_a1", "corp", _later()) is False

    def test_a_replay_through_another_provider_is_still_a_replay(self, store):
        store.record_saml_assertion("_a1", "corp", _later())

        assert store.record_saml_assertion("_a1", "other", _later()) is False

    def test_an_empty_id_is_never_accepted(self, store):
        assert store.record_saml_assertion("", "corp", _later()) is False

    def test_distinct_ids_are_independent(self, store):
        assert store.record_saml_assertion("_a1", "corp", _later()) is True
        assert store.record_saml_assertion("_a2", "corp", _later()) is True


class TestSweep:
    def test_only_expired_records_are_deleted(self, store):
        store.record_saml_assertion("_old", "corp", _later(-10))
        store.record_saml_assertion("_new", "corp", _later(10))

        assert store.delete_expired_saml_assertions() == 1
        assert store.record_saml_assertion("_new", "corp", _later()) is False, "the live record must survive the sweep"
        assert store.record_saml_assertion("_old", "corp", _later()) is True
