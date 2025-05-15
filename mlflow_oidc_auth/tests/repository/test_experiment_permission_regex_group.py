import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.experiment_permission_regex_group import ExperimentPermissionGroupRegexRepository
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission


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
    return ExperimentPermissionGroupRegexRepository(session_maker)


def test_get(repo, session):
    group = MagicMock(id=2)
    row = MagicMock()
    row.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.experiment_permission_regex_group.get_one_or_raise", return_value=row
    ):
        assert repo.get("g", "r") == "entity"


def test_update(repo, session):
    group = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.experiment_permission_regex_group._validate_permission"
    ), patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.validate_regex"), patch.object(
        repo, "_get_experiment_group_regex_permission", return_value=perm
    ):
        session.commit = MagicMock()
        result = repo.update("g", "r", 2, "EDIT")
        assert result == "entity"
        assert perm.permission == "EDIT"
        assert perm.priority == 2
        session.commit.assert_called_once()


def test_update_not_found(repo, session):
    group = MagicMock(id=4)
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.experiment_permission_regex_group._validate_permission"
    ), patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.validate_regex"), patch.object(
        repo, "_get_experiment_group_regex_permission", return_value=None
    ):
        with pytest.raises(ValueError):
            repo.update("g", "r", 2, "EDIT")


def test_revoke(repo, session):
    group = MagicMock(id=5)
    perm = MagicMock()
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.experiment_permission_regex_group.validate_regex"
    ), patch.object(repo, "_get_experiment_group_regex_permission", return_value=perm):
        session.delete = MagicMock()
        session.commit = MagicMock()
        assert repo.revoke("g", "r") is None
        session.delete.assert_called_once_with(perm)
        session.commit.assert_called_once()


def test_revoke_not_found(repo, session):
    group = MagicMock(id=6)
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.experiment_permission_regex_group.validate_regex"
    ), patch.object(repo, "_get_experiment_group_regex_permission", return_value=None):
        with pytest.raises(ValueError):
            repo.revoke("g", "r")


def test_list_permissions_for_group(repo, session):
    group = MagicMock(id=7)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_group", return_value=group):
        result = repo.list_permissions_for_group("g")
        assert result == ["entity"]


def test_list_permissions_for_group_id(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    result = repo.list_permissions_for_group_id(8)
    assert result == ["entity"]


def test_list_permissions_for_user_groups(repo, session):
    user = MagicMock()
    group1 = MagicMock(id=1)
    group2 = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.experiment_permission_regex_group.list_user_groups", return_value=[group1, group2]
    ):
        result = repo.list_permissions_for_user_groups("user")
        assert result == ["entity"]


def test__get_experiment_group_regex_permission(repo, session):
    with patch("mlflow_oidc_auth.repository.experiment_permission_regex_group.get_one_or_raise", return_value="perm") as m:
        result = repo._get_experiment_group_regex_permission(session, "r", 1)
        assert result == "perm"
        m.assert_called_once()


def test__experiment_id_to_name(repo, session):
    assert repo._experiment_id_to_name(session, "expid") == "expid"


def test__is_experiment_in_regex(repo, session):
    assert repo._is_experiment_in_regex(session, "expid", "regex") is False
