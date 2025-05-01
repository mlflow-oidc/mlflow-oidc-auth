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


def test__get_experiment_group_permission_group_none(repo):
    session = MagicMock()
    # Patch get_one_optional to return None for group
    with patch("mlflow_oidc_auth.repository.experiment_permission_group.get_one_optional", side_effect=[None]):
        result = repo._get_experiment_group_permission(session, "1", "group_name")
        assert result is None


def test__get_experiment_group_permission_found(repo):
    session = MagicMock()
    group = MagicMock(id=1)
    perm = MagicMock()
    # Patch get_one_optional to return group then perm
    with patch("mlflow_oidc_auth.repository.experiment_permission_group.get_one_optional", side_effect=[group, perm]):
        result = repo._get_experiment_group_permission(session, "1", "group_name")
        assert result == perm


def test__list_user_groups(repo):
    session = MagicMock()
    user = MagicMock(id=1)
    user_groups_ids = [MagicMock(group_id=1), MagicMock(group_id=2)]
    user_groups = [MagicMock(group_name="g1"), MagicMock(group_name="g2")]
    with patch("mlflow_oidc_auth.repository.experiment_permission_group.get_user", return_value=user):
        repo._Session.return_value.__enter__.return_value = session
        session.query.return_value.filter.return_value.all.side_effect = [user_groups_ids, user_groups]
        result = repo._list_user_groups("user")
        assert result == ["g1", "g2"]


def test_create_success(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    group = MagicMock(id=1)
    session.query.return_value.filter.return_value.one.return_value = group
    # Patch SqlExperimentGroupPermission to allow isinstance check
    with patch("mlflow_oidc_auth.db.models.SqlExperimentGroupPermission") as perm_cls:
        perm_instance = MagicMock()
        perm_instance.to_mlflow_entity.return_value = "entity"
        perm_cls.return_value = perm_instance
        result = repo.create("group", "1", "READ")
        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result == "entity"


def test_create_invalid_permission(repo):
    with patch(
        "mlflow_oidc_auth.repository.experiment_permission_group._validate_permission", side_effect=MlflowException("Invalid")
    ):
        with pytest.raises(MlflowException):
            repo.create("group", "1", "INVALID")


def test_list_group_permissions(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    group = MagicMock(id=1)
    session.query.return_value.filter.return_value.one.return_value = group
    perms = [
        MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
        MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
    ]
    session.query.return_value.filter.return_value.all.return_value = perms
    result = repo.list_group_permissions("group")
    assert result == ["perm1", "perm2"]


def test_list_group_permissions_by_id(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    perms = [
        MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
        MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
    ]
    session.query.return_value.filter.return_value.all.return_value = perms
    result = repo.list_group_permissions_by_id(1)
    assert result == ["perm1", "perm2"]


def test_list_user_permissions(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    user = MagicMock(id=1)
    with patch("mlflow_oidc_auth.repository.experiment_permission_group.get_user", return_value=user):
        user_groups = [MagicMock(group_id=1), MagicMock(group_id=2)]
        perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        session.query.return_value.filter.return_value.all.side_effect = [user_groups, perms]
        result = repo.list_user_permissions("user")
        assert result == ["perm1", "perm2"]


def test_get_user_experiment_permission_happy_path(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    repo._list_user_groups = MagicMock(return_value=["g1", "g2"])
    perm1 = MagicMock(permission="READ", to_mlflow_entity=MagicMock(return_value="entity1"))
    perm2 = MagicMock(permission="EDIT", to_mlflow_entity=MagicMock(return_value="entity2"))
    # Patch _get_experiment_group_permission to return perm1 then perm2
    repo._get_experiment_group_permission = MagicMock(side_effect=[perm1, perm2])
    with patch("mlflow_oidc_auth.repository.experiment_permission_group.compare_permissions", return_value=True):
        result = repo.get_user_experiment_permission("1", "user")
        assert result == "entity2"


def test_get_user_experiment_permission_compare_permissions_attribute_error(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    repo._list_user_groups = MagicMock(return_value=["g1", "g2"])
    perm1 = MagicMock(permission="READ", to_mlflow_entity=MagicMock(return_value="entity1"))
    perm2 = MagicMock(permission="EDIT", to_mlflow_entity=MagicMock(return_value="entity2"))
    repo._get_experiment_group_permission = MagicMock(side_effect=[perm1, perm2])
    with patch("mlflow_oidc_auth.repository.experiment_permission_group.compare_permissions", side_effect=AttributeError):
        result = repo.get_user_experiment_permission("1", "user")
        assert result == "entity2"


def test_get_user_experiment_permission_skips_none(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    repo._list_user_groups = MagicMock(return_value=["g1", "g2"])
    repo._get_experiment_group_permission = MagicMock(
        side_effect=[None, MagicMock(permission="READ", to_mlflow_entity=MagicMock(return_value="entity"))]
    )
    result = repo.get_user_experiment_permission("1", "user")
    assert result == "entity"


def test_get_user_experiment_permission_no_perms(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    repo._list_user_groups = MagicMock(return_value=["g1"])
    repo._get_experiment_group_permission = MagicMock(return_value=None)
    with pytest.raises(MlflowException) as exc_info:
        repo.get_user_experiment_permission("1", "user")
    assert "not found" in str(exc_info.value)


def test_get_user_experiment_permission_to_mlflow_entity_attribute_error(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    repo._list_user_groups = MagicMock(return_value=["g1"])
    bad_perm = MagicMock()
    bad_perm.to_mlflow_entity.side_effect = AttributeError()
    repo._get_experiment_group_permission = MagicMock(return_value=bad_perm)
    with pytest.raises(MlflowException) as exc_info:
        repo.get_user_experiment_permission("1", "user")
    assert "not found" in str(exc_info.value)


def test_update_success(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    group = MagicMock(id=1)
    perm = MagicMock(to_mlflow_entity=MagicMock(return_value="entity"))
    session.query.return_value.filter.return_value.one.side_effect = [group, perm]
    result = repo.update("group", "1", "READ")
    assert result == "entity"
    assert perm.permission == "READ"
    session.flush.assert_called_once()


def test_update_invalid_permission(repo):
    with patch(
        "mlflow_oidc_auth.repository.experiment_permission_group._validate_permission", side_effect=MlflowException("Invalid")
    ):
        with pytest.raises(MlflowException):
            repo.update("group", "1", "INVALID")


def test_delete_success(repo):
    session = MagicMock()
    repo._Session.return_value.__enter__.return_value = session
    group = MagicMock(id=1)
    perm = MagicMock()
    session.query.return_value.filter.return_value.one.side_effect = [group, perm]
    repo.delete("group", "1")
    session.delete.assert_called_once_with(perm)
    session.flush.assert_called_once()
