import pytest
from unittest.mock import MagicMock, patch, ANY

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.repository.experiment_permission_group import ExperimentPermissionGroupRepository
from mlflow_oidc_auth.db.models import SqlExperimentGroupPermission, SqlGroup, SqlUserGroup
from mlflow_oidc_auth.entities import ExperimentPermission


@pytest.fixture
def repo():
    return ExperimentPermissionGroupRepository(session_maker=MagicMock())


@pytest.fixture
def session():
    return MagicMock()


def make_group(id=1, group_name="group1"):
    group = MagicMock(spec=SqlGroup)
    group.id = id
    group.group_name = group_name
    return group


def make_permission(experiment_id="exp1", group_id=1, permission="READ"):
    perm = MagicMock(spec=SqlExperimentGroupPermission)
    perm.experiment_id = experiment_id
    perm.group_id = group_id
    perm.permission = permission
    perm.to_mlflow_entity.return_value = f"entity-{experiment_id}-{group_id}-{permission}"
    return perm


def make_user(id=1, username="user1"):
    user = MagicMock()
    user.id = id
    user.username = username
    return user


@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_one_optional")
def test__get_experiment_group_permission_found(mock_get_one_optional, repo, session):
    group = make_group()
    perm = make_permission()
    # First call returns group, second call returns permission
    mock_get_one_optional.side_effect = [group, perm]
    result = repo._get_experiment_group_permission(session, "exp1", "group1")
    assert result == perm
    assert mock_get_one_optional.call_count == 2


@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_one_optional")
def test__get_experiment_group_permission_group_not_found(mock_get_one_optional, repo, session):
    mock_get_one_optional.side_effect = [None]
    result = repo._get_experiment_group_permission(session, "exp1", "group1")
    assert result is None


@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_user")
@patch("mlflow_oidc_auth.repository.experiment_permission_group.list_user_groups")
def test__list_user_groups(mock_list_user_groups, mock_get_user, repo):
    session = MagicMock()
    user = make_user()
    mock_get_user.return_value = user
    group1 = make_group(id=1, group_name="g1")
    group2 = make_group(id=2, group_name="g2")
    mock_list_user_groups.return_value = [group1, group2]
    session.query().filter().all.return_value = [group1, group2]
    repo._Session.return_value.__enter__.return_value = session
    result = repo._list_user_groups("user1")
    assert result == ["g1", "g2"]


@patch("mlflow_oidc_auth.repository.experiment_permission_group._validate_permission")
@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_group")
def test_grant_group_permission(mock_get_group, mock_validate, repo):
    session = MagicMock()
    group = make_group()
    mock_get_group.return_value = group
    perm = make_permission()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.__enter__.return_value = session
    session.__exit__ = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    # Patch SqlExperimentGroupPermission to return our mock
    with patch("mlflow_oidc_auth.repository.experiment_permission_group.SqlExperimentGroupPermission", return_value=perm):
        result = repo.grant_group_permission("group1", "exp1", "READ")
    assert result == perm.to_mlflow_entity()


@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_group")
def test_list_permissions_for_group(mock_get_group, repo):
    session = MagicMock()
    group = make_group()
    mock_get_group.return_value = group
    perm1 = make_permission("exp1", group.id, "READ")
    perm2 = make_permission("exp2", group.id, "EDIT")
    session.query().filter().all.return_value = [perm1, perm2]
    repo._Session.return_value.__enter__.return_value = session
    result = repo.list_permissions_for_group("group1")
    assert result == [perm1.to_mlflow_entity(), perm2.to_mlflow_entity()]


def test_list_permissions_for_group_id(repo):
    session = MagicMock()
    perm1 = make_permission("exp1", 1, "READ")
    perm2 = make_permission("exp2", 1, "EDIT")
    session.query().filter().all.return_value = [perm1, perm2]
    repo._Session.return_value.__enter__.return_value = session
    result = repo.list_permissions_for_group_id(1)
    assert result == [perm1.to_mlflow_entity(), perm2.to_mlflow_entity()]


@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_user")
@patch("mlflow_oidc_auth.repository.experiment_permission_group.list_user_groups")
def test_list_permissions_for_user_groups(mock_list_user_groups, mock_get_user, repo):
    session = MagicMock()
    user = make_user()
    mock_get_user.return_value = user
    group1 = make_group(id=1)
    group2 = make_group(id=2)
    mock_list_user_groups.return_value = [group1, group2]
    perm1 = make_permission("exp1", 1, "READ")
    perm2 = make_permission("exp2", 2, "EDIT")
    session.query().filter().all.return_value = [perm1, perm2]
    repo._Session.return_value.__enter__.return_value = session
    result = repo.list_permissions_for_user_groups("user1")
    assert result == [perm1.to_mlflow_entity(), perm2.to_mlflow_entity()]


@patch("mlflow_oidc_auth.repository.experiment_permission_group.ExperimentPermissionGroupRepository._list_user_groups")
@patch(
    "mlflow_oidc_auth.repository.experiment_permission_group.ExperimentPermissionGroupRepository._get_experiment_group_permission"
)
@patch("mlflow_oidc_auth.repository.experiment_permission_group.compare_permissions")
def test_get_group_permission_for_user_experiment_best_permission(
    mock_compare_permissions, mock_get_experiment_group_permission, mock_list_user_groups, repo
):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    mock_list_user_groups.return_value = ["g1", "g2"]
    perm1 = make_permission("exp1", 1, "READ")
    perm2 = make_permission("exp1", 2, "EDIT")
    # First call returns perm1, second call returns perm2
    mock_get_experiment_group_permission.side_effect = [perm1, perm2]
    # compare_permissions returns True, so perm2 is "better"
    mock_compare_permissions.return_value = True
    result = repo.get_group_permission_for_user_experiment("exp1", "user1")
    assert result == perm2.to_mlflow_entity()


@patch("mlflow_oidc_auth.repository.experiment_permission_group.ExperimentPermissionGroupRepository._list_user_groups")
@patch(
    "mlflow_oidc_auth.repository.experiment_permission_group.ExperimentPermissionGroupRepository._get_experiment_group_permission"
)
def test_get_group_permission_for_user_experiment_none_found(mock_get_experiment_group_permission, mock_list_user_groups, repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    mock_list_user_groups.return_value = ["g1", "g2"]
    mock_get_experiment_group_permission.side_effect = [None, None]
    with pytest.raises(MlflowException) as exc:
        repo.get_group_permission_for_user_experiment("exp1", "user1")
    assert "not found" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


@patch("mlflow_oidc_auth.repository.experiment_permission_group.ExperimentPermissionGroupRepository._list_user_groups")
@patch(
    "mlflow_oidc_auth.repository.experiment_permission_group.ExperimentPermissionGroupRepository._get_experiment_group_permission"
)
def test_get_group_permission_for_user_experiment_attribute_error(
    mock_get_experiment_group_permission, mock_list_user_groups, repo
):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    mock_list_user_groups.return_value = ["g1"]

    # Return an object with no .permission attribute to trigger AttributeError
    class Dummy:
        def to_mlflow_entity(self):
            raise AttributeError()

    mock_get_experiment_group_permission.return_value = Dummy()
    with pytest.raises(MlflowException) as exc:
        repo.get_group_permission_for_user_experiment("exp1", "user1")
    assert "not found" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


@patch("mlflow_oidc_auth.repository.experiment_permission_group._validate_permission")
@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_group")
def test_update_group_permission(mock_get_group, mock_validate, repo):
    session = MagicMock()
    group = make_group()
    mock_get_group.return_value = group
    perm = make_permission()
    session.query().filter().one.return_value = perm
    session.flush = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    result = repo.update_group_permission("group1", "exp1", "EDIT")
    assert result == perm.to_mlflow_entity()
    assert perm.permission == "EDIT"


@patch("mlflow_oidc_auth.repository.experiment_permission_group._validate_permission")
@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_group")
def test_update_group_permission_not_found(mock_get_group, mock_validate, repo):
    session = MagicMock()
    group = make_group()
    mock_get_group.return_value = group
    session.query().filter().one.side_effect = Exception("not found")
    repo._Session.return_value.__enter__.return_value = session
    with pytest.raises(Exception):
        repo.update_group_permission("group1", "exp1", "EDIT")


@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_group")
def test_revoke_group_permission(mock_get_group, repo):
    session = MagicMock()
    group = make_group()
    mock_get_group.return_value = group
    perm = make_permission()
    session.query().filter().one.return_value = perm
    session.delete = MagicMock()
    session.flush = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    repo.revoke_group_permission("group1", "exp1")
    session.delete.assert_called_once_with(perm)
    session.flush.assert_called_once()


@patch("mlflow_oidc_auth.repository.experiment_permission_group.get_group")
def test_revoke_group_permission_not_found(mock_get_group, repo):
    session = MagicMock()
    group = make_group()
    mock_get_group.return_value = group
    session.query().filter().one.side_effect = Exception("not found")
    repo._Session.return_value.__enter__.return_value = session
    with pytest.raises(Exception):
        repo.revoke_group_permission("group1", "exp1")
