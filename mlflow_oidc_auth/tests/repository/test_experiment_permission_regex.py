import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.experiment_permission_regex import (
    ExperimentPermissionRegexRepository,
)


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


def test_grant_success(repo, session):
    """Test successful grant to cover line 60"""
    user = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.add = MagicMock()
    session.flush = MagicMock()

    with (
        patch(
            "mlflow_oidc_auth.repository.experiment_permission_regex.get_user",
            return_value=user,
        ),
        patch("mlflow_oidc_auth.db.models.SqlExperimentRegexPermission", return_value=perm),
        patch("mlflow_oidc_auth.repository.experiment_permission_regex._validate_permission"),
        patch("mlflow_oidc_auth.repository.experiment_permission_regex.validate_regex"),
    ):
        result = repo.grant("test_regex", 1, "READ", "user")
        assert result is not None
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test_grant_integrity_error(repo, session):
    user = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with (
        patch(
            "mlflow_oidc_auth.repository.experiment_permission_regex.get_user",
            return_value=user,
        ),
        patch(
            "mlflow_oidc_auth.db.models.SqlExperimentRegexPermission",
            return_value=MagicMock(),
        ),
        patch(
            "mlflow_oidc_auth.repository.experiment_permission_regex.IntegrityError",
            Exception,
        ),
    ):
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
    with patch(
        "mlflow_oidc_auth.repository.experiment_permission_regex.get_user",
        return_value=user,
    ):
        assert repo.list_regex_for_user("user") == ["entity"]


def test_update(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch.object(repo, "_get_experiment_regex_permission", return_value=perm):
        session.flush = MagicMock()
        result = repo.update("r", 2, "EDIT", "user", 1)
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


def test__get_experiment_regex_permission_not_found(repo, session):
    """Test _get_experiment_regex_permission when no permission is found"""
    session.query().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_experiment_regex_permission(session, "test_regex", 1)

    assert "Permission not found for user_id: test_regex, and id: 1" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test__get_experiment_regex_permission_multiple_found(repo, session):
    """Test _get_experiment_regex_permission when multiple permissions are found"""
    session.query().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_experiment_regex_permission(session, "test_regex", 1)

    assert "Multiple Permissions found for user_id: test_regex, and id: 1" in str(exc.value)
    assert exc.value.error_code == "INVALID_STATE"


def test__get_experiment_regex_permission_database_error(repo, session):
    """Test _get_experiment_regex_permission when database error occurs"""
    session.query().filter().one.side_effect = Exception("Database connection error")

    with pytest.raises(Exception, match="Database connection error"):
        repo._get_experiment_regex_permission(session, "test_regex", 1)
