import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
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
    with (
        patch("mlflow_oidc_auth.db.models.SqlGroup", return_value=MagicMock()),
        patch("mlflow_oidc_auth.repository.group.IntegrityError", Exception),
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
    session.query().filter().one.return_value = grp
    session.delete = MagicMock()
    session.flush = MagicMock()
    repo.delete_group("g5")
    session.delete.assert_called_once_with(grp)
    session.flush.assert_called_once()


def test_delete_group_not_found(repo, session):
    """Test delete_group when group is not found - covers line 64"""
    session.query().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        repo.delete_group("nonexistent")

    assert "Group 'nonexistent' not found" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test_delete_group_multiple_found(repo, session):
    """Test delete_group when multiple groups found - covers line 66"""
    session.query().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        repo.delete_group("duplicate")

    assert "Multiple groups named 'duplicate'" in str(exc.value)
    assert exc.value.error_code == "INVALID_STATE"


def test_add_user_to_group(repo, session):
    user = MagicMock(id=1)
    grp = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock()
    with (
        patch("mlflow_oidc_auth.repository.group.get_user", return_value=user),
        patch("mlflow_oidc_auth.repository.group.get_group", return_value=grp),
        patch("mlflow_oidc_auth.db.models.SqlUserGroup", return_value=MagicMock()),
    ):
        repo.add_user_to_group("user", "g6")
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test_remove_user_from_group(repo, session):
    user = MagicMock(id=1, is_admin=False, username="user")
    grp = MagicMock(id=2, group_name="g7")
    ug = MagicMock(managed_by="manual")
    session.query().filter().one.return_value = ug
    session.delete = MagicMock()
    session.flush = MagicMock()
    with (
        patch("mlflow_oidc_auth.repository.group.get_user", return_value=user),
        patch("mlflow_oidc_auth.repository.group.get_group", return_value=grp),
    ):
        repo.remove_user_from_group("user", "g7")
        session.delete.assert_called_once_with(ug)
        session.flush.assert_called_once()


def test_list_groups_for_user(repo, session):
    """Resolved via a single JOIN (issue #253), so rows come back as tuples."""
    session.query().join().join().filter().order_by().all.return_value = [("g1",), ("g2",)]
    assert repo.list_groups_for_user("user") == ["g1", "g2"]


def test_list_group_ids_for_user(repo, session):
    """Joins user_groups directly so membership rows for deleted groups are preserved."""
    session.query().join().filter().all.return_value = [(10,), (20,)]
    assert repo.list_group_ids_for_user("user") == [10, 20]


def test_list_group_members(repo, session):
    """Test list_group_members to cover lines 100-104"""
    grp = MagicMock(id=1)
    ug1 = MagicMock(user_id=10)
    ug2 = MagicMock(user_id=20)
    user1 = MagicMock()
    user1.to_mlflow_entity.return_value = "user1_entity"
    user2 = MagicMock()
    user2.to_mlflow_entity.return_value = "user2_entity"

    # Mock the query chain for SqlUserGroup and SqlUser
    user_group_query = MagicMock()
    user_group_query.filter.return_value = [ug1, ug2]

    user_query = MagicMock()
    user_query.filter.return_value.all.return_value = [user1, user2]

    session.query.side_effect = [user_group_query, user_query]

    with patch("mlflow_oidc_auth.repository.group.get_group", return_value=grp):
        result = repo.list_group_members("test_group")
        assert result == ["user1_entity", "user2_entity"]


@pytest.fixture
def real_store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user("user@example.com", "unused-secret", "User")
    s.populate_groups(["g1", "g2", "g3"])
    yield s
    s.engine.dispose()


def test_set_groups_for_user(real_store):
    real_store.set_user_groups("user@example.com", ["g1"])

    outcome = real_store.set_user_groups("user@example.com", ["g2", "g3"])

    assert sorted(real_store.get_groups_for_user("user@example.com")) == ["g2", "g3"]
    assert outcome.removed == [("user@example.com", "g1")]
    assert sorted(outcome.added) == [("user@example.com", "g2"), ("user@example.com", "g3")]


def test_set_groups_for_user_deduplicates_group_names(real_store):
    """Regression test: duplicate group names in the token (e.g. Microsoft Entra ID
    emitting the same security group GUID twice when a user holds multiple app roles
    backed by the same group) must not cause a UniqueViolation on user_groups."""
    outcome = real_store.set_user_groups("user@example.com", ["g1", "g2", "g2"])  # "g2" appears twice

    assert len(outcome.added) == 2
    assert sorted(real_store.get_groups_for_user("user@example.com")) == ["g1", "g2"]
