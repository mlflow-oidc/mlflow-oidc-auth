import pytest

from mlflow_oidc_auth.db.models import SqlExperimentPermission, SqlUser
from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore


def test_delete_user_with_experiment_permissions_deletes_permissions_rows(
    tmp_path,
) -> None:
    store = SqlAlchemyStore()
    db_path = tmp_path / "test.db"
    store.init_db(f"sqlite:///{db_path.as_posix()}")

    username = "user@example.com"
    store.create_user(username=username, password="pw", display_name="User")
    store.create_experiment_permission(experiment_id="exp1", username=username, permission="READ")

    with store.ManagedSessionMaker() as session:
        user = session.query(SqlUser).filter(SqlUser.username == username).one()
        user_id = user.id
        assert session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).count() == 1

    store.delete_user(username)

    with store.ManagedSessionMaker() as session:
        assert session.query(SqlUser).filter(SqlUser.username == username).one_or_none() is None
        assert session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).count() == 0
