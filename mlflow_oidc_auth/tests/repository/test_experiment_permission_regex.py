import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.experiment_permission_regex import ExperimentPermissionRegexRepository
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS


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
    return ExperimentPermissionRegexRepository(session_maker)


def test_grant_integrity_error(repo, session):
    user = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex.get_user", return_value=user), patch(
        "mlflow_oidc_auth.db.models.SqlExperimentRegexPermission", return_value=MagicMock()
    ), patch("mlflow_oidc_auth.repository.experiment_permission_regex.IntegrityError", Exception):
        with pytest.raises(MlflowException):
            repo.grant("r", 1, "READ", "user")


def test_get(repo, session):
    row = MagicMock()
    row.to_mlflow_entity.return_value = "entity"
    with patch.object(repo, "_get_experiment_regex_permission", return_value=row):
        assert repo.get("r", "user") == "entity"


def test_list(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().all.return_value = [perm]
    assert repo.list() == ["entity"]


def test_list_regex_for_user(repo, session):
    user = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().order_by().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex.get_user", return_value=user):
        assert repo.list_regex_for_user("user") == ["entity"]


def test_update(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch.object(repo, "_get_experiment_regex_permission", return_value=perm):
        session.flush = MagicMock()
        result = repo.update("r", 2, "EDIT", "user")
        assert result == "entity"
        assert perm.priority == 2
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()


def test_revoke(repo, session):
    perm = MagicMock()
    with patch.object(repo, "_get_experiment_regex_permission", return_value=perm):
        session.delete = MagicMock()
        session.commit = MagicMock()
        assert repo.revoke("r", "user") is None
        session.delete.assert_called_once_with(perm)
        session.commit.assert_called_once()
