import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.group import GroupRepository
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
    return GroupRepository(session_maker)


def test_create_group_success(repo, session):
    session.add = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.db.models.SqlGroup", return_value=MagicMock()):
        repo.create_group("g1")
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test_create_group_integrity_error(repo, session):
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with patch("mlflow_oidc_auth.db.models.SqlGroup", return_value=MagicMock()), patch(
        "mlflow_oidc_auth.repository.group.IntegrityError", Exception
    ):
        with pytest.raises(MlflowException):
            repo.create_group("g2")


def test_create_groups(repo, session):
    session.query().filter().first.side_effect = [None, MagicMock()]
    session.add = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.db.models.SqlGroup", return_value=MagicMock()):
        repo.create_groups(["g3", "g4"])
        assert session.add.call_count == 1
        session.flush.assert_called_once()


def test_list_groups(repo, session):
    g1 = MagicMock(group_name="g1")
    g2 = MagicMock(group_name="g2")
    session.query().all.return_value = [g1, g2]
    assert repo.list_groups() == ["g1", "g2"]


def test_delete_group_success(repo, session):
    grp = MagicMock()
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.group.get_one_or_raise", return_value=grp):
        repo.delete_group("g5")
        session.delete.assert_called_once_with(grp)
        session.flush.assert_called_once()


def test_add_user_to_group(repo, session):
    user = MagicMock(id=1)
    grp = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.group.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.group.get_group", return_value=grp
    ), patch("mlflow_oidc_auth.db.models.SqlUserGroup", return_value=MagicMock()):
        repo.add_user_to_group("user", "g6")
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test_remove_user_from_group(repo, session):
    user = MagicMock(id=1)
    grp = MagicMock(id=2)
    ug = MagicMock()
    session.query().filter().one.return_value = ug
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.group.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.group.get_group", return_value=grp
    ):
        repo.remove_user_from_group("user", "g7")
        session.delete.assert_called_once_with(ug)
        session.flush.assert_called_once()


def test_list_groups_for_user(repo, session):
    user = MagicMock(id=1)
    group1 = MagicMock(id=10)
    group2 = MagicMock(id=20)
    g1 = MagicMock(group_name="g1")
    g2 = MagicMock(group_name="g2")
    session.query().filter().all.return_value = [g1, g2]
    with patch("mlflow_oidc_auth.repository.group.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.group.list_user_groups", return_value=[group1, group2]
    ):
        assert repo.list_groups_for_user("user") == ["g1", "g2"]


def test_list_group_ids_for_user(repo, session):
    user = MagicMock(id=1)
    ug1 = MagicMock(group_id=10)
    ug2 = MagicMock(group_id=20)
    with patch("mlflow_oidc_auth.repository.group.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.group.list_user_groups", return_value=[ug1, ug2]
    ):
        result = repo.list_group_ids_for_user("user")
        assert result == [10, 20]


def test_set_groups_for_user(repo, session):
    user = MagicMock(id=1)
    group1 = MagicMock(id=10)
    group2 = MagicMock(id=20)
    session.delete = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.group.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.group.list_user_groups", return_value=[group1]
    ), patch("mlflow_oidc_auth.repository.group.get_group", side_effect=[group1, group2]), patch(
        "mlflow_oidc_auth.db.models.SqlUserGroup", return_value=MagicMock()
    ):
        repo.set_groups_for_user("user", ["g1", "g2"])
        session.delete.assert_called_once_with(group1)
        assert session.add.call_count == 2
        session.flush.assert_called_once()
