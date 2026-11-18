"""The schedule writer repository: a concurrent first insert of a row is retried as an update."""

from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.repository.issue_detection_schedule import IssueDetectionScheduleRepository


def test_a_concurrent_first_insert_is_retried_as_an_update(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    repo = IssueDetectionScheduleRepository(s.ManagedSessionMaker)
    real_row = repo._row
    raced = []

    def row_after_a_racing_insert(session, experiment_id):
        if not raced:
            raced.append(1)
            # Another writer inserts the row between this read and this insert.
            other = IssueDetectionScheduleRepository(s.ManagedSessionMaker)
            other.record_author(experiment_id, None, "first@example.com", "f1")
            return None
        return real_row(session, experiment_id)

    repo._row = row_after_a_racing_insert
    repo.record_author("7", None, "second@example.com", "f2")

    record = repo.get("7")
    assert record.author == "second@example.com" and record.model_fingerprint == "f2"


def test_a_second_integrity_error_is_raised(tmp_path, monkeypatch):
    import pytest

    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    repo = IssueDetectionScheduleRepository(s.ManagedSessionMaker)

    def always_conflicts(row):
        raise IntegrityError("insert", {}, Exception("unique"))

    from mlflow.exceptions import MlflowException

    with pytest.raises(MlflowException) as raised:
        repo._upsert("7", always_conflicts)
    assert isinstance(raised.value.__cause__, IntegrityError)
