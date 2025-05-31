import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.experiment_permission import ExperimentPermissionRepository
from mlflow.exceptions import MlflowException


@pytest.fixture
def session():
    s = MagicMock()
    s.__enter__.return_value = s
    s.__exit__.return_value = None
    return s


@pytest.fixture
def session_maker(session):
    return MagicMock(return_value=session)


@pytest.fixture
def repo(session_maker):
    return ExperimentPermissionRepository(session_maker)


def test_grant_permission_integrity_error(repo, session):
    user = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with patch("mlflow_oidc_auth.repository.experiment_permission.get_user", return_value=user), patch(
        "mlflow_oidc_auth.db.models.SqlExperimentPermission", return_value=MagicMock()
    ):
        with patch("mlflow_oidc_auth.repository.experiment_permission.IntegrityError", Exception):
            with pytest.raises(MlflowException):
                repo.grant_permission("exp2", "user", "READ")


def test_get_permission(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch.object(repo, "_get_experiment_permission", return_value=perm):
        assert repo.get_permission("exp3", "user") == "entity"


def test__get_experiment_permission(repo, session):
    perm = MagicMock()
    # Mock the SQLAlchemy query chain: session.query().join().filter().one()
    session.query().join().filter().one.return_value = perm
    result = repo._get_experiment_permission(session, "exp4", "user")
    assert result == perm


def test_list_permissions_for_user(repo, session):
    user = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.experiment_permission.get_user", return_value=user):
        assert repo.list_permissions_for_user("user") == ["entity"]


def test_list_permissions_for_experiment(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    assert repo.list_permissions_for_experiment("exp5") == ["entity"]


def test_update_permission(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch.object(repo, "_get_experiment_permission", return_value=perm):
        session.flush = MagicMock()
        result = repo.update_permission("exp6", "user", "EDIT")  # Use valid permission
        assert result == "entity"
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()


def test_revoke_permission(repo, session):
    perm = MagicMock()
    with patch.object(repo, "_get_experiment_permission", return_value=perm):
        session.delete = MagicMock()
        session.flush = MagicMock()
        assert repo.revoke_permission("exp7", "user") is None
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()
