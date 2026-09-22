"""``prune-sessions`` also sweeps SAML replay records (issue #328).

A record is needed only while its assertion could still pass validation; after that it is dead
weight, one row per SAML login. The live ones must survive: deleting a record early re-opens the
replay window for that assertion.
"""

from datetime import datetime, timedelta, timezone

import pytest
from click.testing import CliRunner

from mlflow_oidc_auth.db.cli import commands


def _in(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


@pytest.fixture
def db(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    url = f"sqlite:///{tmp_path / 'auth.db'}"
    store = SqlAlchemyStore()
    store.init_db(url)
    yield store, url
    store.engine.dispose()


def _run(url, *args):
    result = CliRunner().invoke(commands, ["prune-sessions", "--url", url, *args])
    assert result.exit_code == 0, result.output
    return result.output


def test_expired_records_are_deleted_and_live_ones_kept(db):
    store, url = db
    store.record_saml_assertion("_expired", "corp", _in(-60))
    store.record_saml_assertion("_live", "corp", _in(600))

    output = _run(url)

    assert "deleted 1 expired SAML assertion record(s)" in output
    assert store.record_saml_assertion("_live", "corp", _in(600)) is False, "a live record must survive, or its assertion is replayable"
    assert store.record_saml_assertion("_expired", "corp", _in(600)) is True


def test_dry_run_deletes_nothing(db):
    store, url = db
    store.record_saml_assertion("_expired", "corp", _in(-60))

    output = _run(url, "--dry-run")

    assert "1 expired SAML assertion record(s) would be deleted" in output
    assert store.delete_expired_saml_assertions() == 1, "the row is still there"
