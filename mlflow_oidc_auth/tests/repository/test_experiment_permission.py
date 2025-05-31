import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, INVALID_STATE

from mlflow_oidc_auth.repository.experiment_permission import ExperimentPermissionRepository


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


def test__get_experiment_permission_not_found(repo, session):
    """Test _get_experiment_permission when no permission is found"""
    session.query().join().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_experiment_permission(session, "exp1", "user1")

    assert "No permission for exp=exp1, user=user1" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test__get_experiment_permission_multiple_found(repo, session):
    """Test _get_experiment_permission when multiple permissions are found"""
    session.query().join().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_experiment_permission(session, "exp1", "user1")

    assert "Multiple perms for exp=exp1, user=user1" in str(exc.value)
    assert exc.value.error_code == "INVALID_STATE"


def test__get_experiment_permission_database_error(repo, session):
    """Test _get_experiment_permission when database error occurs"""
    session.query().join().filter().one.side_effect = Exception("Database connection error")

    with pytest.raises(Exception, match="Database connection error"):
        repo._get_experiment_permission(session, "exp1", "user1")


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
