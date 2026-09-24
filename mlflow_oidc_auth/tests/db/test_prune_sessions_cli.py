"""``mlflow-oidc db prune-sessions`` (issue #310 follow-up).

Every login inserts a row into ``auth_sessions`` and nothing else removes one, so without a
sweep the table grows without bound. Correctness never depended on it — an expired session is
refused by ``resolve`` either way — which is precisely why it needs a test: a housekeeping
command that silently deletes nothing looks exactly like one that works.
"""

from datetime import datetime, timedelta, timezone

import pytest
from click.testing import CliRunner

from mlflow_oidc_auth.db.cli import commands

PASSWORD = "prune-password"  # not a credential: only ever seeded into a tmp_path database


def _in(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


@pytest.fixture
def db(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    url = f"sqlite:///{tmp_path / 'auth.db'}"
    store = SqlAlchemyStore()
    store.init_db(url)
    store.create_user("alice@example.com", PASSWORD, "Alice")
    yield store, url
    store.engine.dispose()


def _run(url, *args):
    result = CliRunner().invoke(commands, ["prune-sessions", "--url", url, *args])
    assert result.exit_code == 0, result.output
    return result.output


class TestPruneSessions:
    def test_expired_sessions_are_deleted(self, db):
        store, url = db
        store.create_auth_session("alice@example.com", expires_at=_in(-1))

        output = _run(url)

        assert "deleted 1" in output
        assert store.auth_session_repo.delete_expired() == 0, "nothing left to sweep"

    def test_live_sessions_are_kept(self, db):
        store, url = db
        live = store.create_auth_session("alice@example.com", expires_at=_in(3600))

        _run(url)

        assert store.resolve_auth_session(live) is not None

    def test_a_revoked_but_unexpired_session_is_kept(self, db):
        """So "was this revoked, and when?" stays answerable for the life the session would
        have had."""
        store, url = db
        sid = store.create_auth_session("alice@example.com", expires_at=_in(3600))
        store.revoke_auth_session(sid)

        output = _run(url)

        assert "deleted 0" in output
        assert store.auth_session_repo.list_live_for_user("alice@example.com") == []

    def test_dry_run_deletes_nothing(self, db):
        store, url = db
        store.create_auth_session("alice@example.com", expires_at=_in(-1))

        output = _run(url, "--dry-run")

        assert "1 expired session(s) would be deleted" in output
        assert store.auth_session_repo.delete_expired() == 1, "the row is still there"


class TestPruneScimActivity:
    """SCIM activity (#325) older than ``SCIM_ACTIVITY_RETENTION_DAYS`` goes with the same sweep."""

    def _seed(self, store, days_ago: int):
        store.record_scim_activity(
            token_id=1,
            token_name="entra",
            method="GET",
            path="/Users",
            resource_id=None,
            status=200,
            outcome="ok",
            error=None,
            duration_ms=1,
            at=(datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(tzinfo=None),
        )

    def test_old_activity_is_deleted_and_recent_kept(self, db, monkeypatch):
        from mlflow_oidc_auth.config import config

        monkeypatch.setattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 30, raising=False)
        store, url = db
        self._seed(store, 31)
        self._seed(store, 1)

        output = _run(url)

        assert "deleted 1 SCIM activity row(s) older than 30 day(s)" in output
        assert len(store.list_scim_activity(limit=200)) == 1

    def test_dry_run_reports_and_keeps(self, db, monkeypatch):
        from mlflow_oidc_auth.config import config

        monkeypatch.setattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 30, raising=False)
        store, url = db
        self._seed(store, 31)

        output = _run(url, "--dry-run")

        assert "1 SCIM activity row(s) older than 30 day(s) would be deleted" in output
        assert len(store.list_scim_activity(limit=200)) == 1

    def test_zero_retention_keeps_everything(self, db, monkeypatch):
        from mlflow_oidc_auth.config import config

        monkeypatch.setattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 0, raising=False)
        store, url = db
        self._seed(store, 400)

        output = _run(url)

        assert "SCIM activity" not in output
        assert len(store.list_scim_activity(limit=200)) == 1
