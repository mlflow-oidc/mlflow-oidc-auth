import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.registered_model_permission_regex_group import RegisteredModelGroupRegexPermissionRepository


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
    return RegisteredModelGroupRegexPermissionRepository(session_maker)


def test_grant(repo, session):
    group = MagicMock(id=1)
    session.add = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group), patch(
        "mlflow_oidc_auth.db.models.SqlRegisteredModelGroupRegexPermission", return_value=MagicMock()
    ):
        result = repo.grant("group1", "r", "READ", priority=1, prompt=True)
        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result is not None


def test_get(repo, session):
    group = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().one.return_value = perm
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group):
        result = repo.get(1, "group1", prompt=True)
        assert result == "entity"


def test_get_not_found(repo, session):
    group = MagicMock(id=3)
    from sqlalchemy.exc import NoResultFound

    session.query().filter().one.side_effect = NoResultFound()
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group):
        with pytest.raises(MlflowException):
            repo.get(1, "group1", prompt=True)


def test_list_permissions_for_group(repo, session):
    group = MagicMock(id=4)
    perm1 = MagicMock()
    perm1.to_mlflow_entity.return_value = "entity1"
    perm2 = MagicMock()
    perm2.to_mlflow_entity.return_value = "entity2"
    session.query().filter().order_by().all.return_value = [perm1, perm2]
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group):
        result = repo.list_permissions_for_group("group1", prompt=True)
        assert result == ["entity1", "entity2"]


def test_list_permissions_for_groups(repo, session):
    group1 = MagicMock(id=5)
    group2 = MagicMock(id=6)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().order_by().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.utils.get_group", side_effect=[group1, group2]):
        result = repo.list_permissions_for_groups(["group1", "group2"], prompt=True)
        assert result == ["entity"]


def test_list_permissions_for_groups_ids(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().order_by().all.return_value = [perm]
    result = repo.list_permissions_for_groups_ids([1, 2], prompt=True)
    assert result == ["entity"]


def test_update(repo, session):
    group = MagicMock(id=7)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().one.return_value = perm
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group):
        result = repo.update(1, "r", "group1", "EDIT", priority=2, prompt=True)
        assert result == "entity"
        assert perm.permission == "EDIT"
        assert perm.priority == 2
        session.flush.assert_called_once()


def test_update_not_found(repo, session):
    group = MagicMock(id=8)
    from sqlalchemy.exc import NoResultFound

    session.query().filter().one.side_effect = NoResultFound()
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group):
        with pytest.raises(MlflowException):
            repo.update(1, "r", "group1", "EDIT", priority=2, prompt=True)


def test_revoke(repo, session):
    group = MagicMock(id=9)
    perm = MagicMock()
    session.query().filter().one.return_value = perm
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group):
        repo.revoke(1, "group1", prompt=True)
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()


def test_revoke_not_found(repo, session):
    group = MagicMock(id=10)
    from sqlalchemy.exc import NoResultFound

    session.query().filter().one.side_effect = NoResultFound()
    with patch("mlflow_oidc_auth.repository.utils.get_group", return_value=group):
        with pytest.raises(MlflowException):
            repo.revoke(1, "group1", prompt=True)


def test__get_registered_model_group_regex_permission_not_found(repo, session):
    """Test _get_registered_model_group_regex_permission when no permission is found"""
    session.query().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_registered_model_group_regex_permission(session, "test_regex", 1, prompt=False)

    assert "No model perm for id=test_regex, group_id=1, prompt=False" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test__get_registered_model_group_regex_permission_multiple_found(repo, session):
    """Test _get_registered_model_group_regex_permission when multiple permissions are found"""
    session.query().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_registered_model_group_regex_permission(session, "test_regex", 1, prompt=False)

    assert "Multiple model perms for id=test_regex, group_id=1, prompt=False" in str(exc.value)
    assert exc.value.error_code == "INVALID_STATE"


def test__get_registered_model_group_regex_permission_database_error(repo, session):
    """Test _get_registered_model_group_regex_permission when database error occurs"""
    session.query().filter().one.side_effect = Exception("Database connection error")

    with pytest.raises(Exception, match="Database connection error"):
        repo._get_registered_model_group_regex_permission(session, "test_regex", 1, prompt=False)


def test__get_registered_model_group_regex_permission_prompt_not_found(repo, session):
    """Test _get_registered_model_group_regex_permission when no prompt permission is found"""
    session.query().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_registered_model_group_regex_permission(session, "test_regex", 1, prompt=True)

    assert "No model perm for id=test_regex, group_id=1, prompt=True" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"
