import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError
from mlflow_oidc_auth.repository.user import UserRepository
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
    return UserRepository(session_maker)


def test_create_success(repo, session):
    """Test successful create"""
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.add = MagicMock()
    session.flush = MagicMock()

    with (
        patch("mlflow_oidc_auth.db.models.SqlUser", return_value=user),
        patch("mlflow_oidc_auth.repository.user._validate_username"),
    ):
        result = repo.create("user", "disp")
        assert result is not None
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test_create_integrity_error(repo, session):
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=IntegrityError("statement", "params", "orig"))
    with (
        patch("mlflow_oidc_auth.db.models.SqlUser", return_value=MagicMock()),
        patch("mlflow_oidc_auth.repository.user._validate_username"),
    ):
        with pytest.raises(MlflowException) as exc:
            repo.create("user", "disp")
        assert "User 'user' already exists" in str(exc.value)
        assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


def test_get_found(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.query().filter().one_or_none.return_value = user
    assert repo.get("user") == "entity"


def test_get_not_found(repo, session):
    session.query().filter().one_or_none.return_value = None
    with pytest.raises(MlflowException):
        repo.get("user")


def test_exist_true(repo, session):
    session.query().filter().first.return_value = True
    assert repo.exist("user") is True


def test_exist_false(repo, session):
    session.query().filter().first.return_value = None
    assert repo.exist("user") is False


def test_list_all_false(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [user]
    assert repo.list(is_service_account=False, all=False) == ["entity"]


def test_list_all_true(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.query().all.return_value = [user]
    assert repo.list(is_service_account=False, all=True) == ["entity"]


def test_update_partial_fields(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user):
        result = repo.update("user", is_admin=None, is_service_account=None)
        assert result == "entity"
        session.flush.assert_called_once()


def test_update_all_fields(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user):
        result = repo.update("user", is_admin=True, is_service_account=True)
        assert result == "entity"
        session.flush.assert_called_once()


def test_delete(repo, session):
    user = MagicMock()
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user):
        repo.delete("user")
        session.delete.assert_called_once_with(user)
        session.flush.assert_called_once()


def test_delete_non_existent_user(repo, session):
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=None):
        with pytest.raises(MlflowException):
            repo.delete("non_existent_user")
        session.delete.assert_not_called()
        session.flush.assert_not_called()
class TestUsernameCaseNormalization:
    """Usernames are case-insensitive identity keys (issues #219, #145).

    A user created with mixed case (an admin service account with capitals, or an
    OIDC email returned camelCased) must be reachable and authenticatable under any
    case. Normalization happens at the repository boundary, so every method folds
    the username before touching the store.
    """

    def test_normalize_username_folds_case(self):
        from mlflow_oidc_auth.repository.user import normalize_username

        assert normalize_username("Xyz_Abc@test.com") == "xyz_abc@test.com"
        assert normalize_username("SERVICE_ACCOUNT") == "service_account"
        assert normalize_username("already@lower.com") == "already@lower.com"

    def test_normalize_username_passes_non_strings_through(self):
        from mlflow_oidc_auth.repository.user import normalize_username

        assert normalize_username(None) is None

    def test_create_stores_lowercased_username(self, repo, session):
        """#219: an admin-created service account with capitals is stored lowercase."""
        session.add = MagicMock()
        session.flush = MagicMock()
        with (
            patch("mlflow_oidc_auth.repository.user.SqlUser") as sql_user,
            patch("mlflow_oidc_auth.repository.user._validate_username"),
        ):
            repo.create("Xyz_Abc", "Xyz Abc Display")
            assert sql_user.call_args.kwargs["username"] == "xyz_abc"
            # The human-readable display name is left untouched.
            assert sql_user.call_args.kwargs["display_name"] == "Xyz Abc Display"

    def test_get_looks_up_lowercased_username(self, repo, session):
        session.query.return_value.filter.return_value.one_or_none.return_value = None
        with pytest.raises(MlflowException) as exc:
            repo.get("Xyz_Abc")
        assert "xyz_abc" in str(exc.value)
        assert "Xyz_Abc" not in str(exc.value)

    def test_update_normalizes_username(self, repo, session):
        user = MagicMock()
        with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user) as get_user_mock:
            repo.update("Xyz_Abc")
            assert get_user_mock.call_args.args[1] == "xyz_abc"

    def test_delete_normalizes_username(self, repo, session):
        user = MagicMock()
        with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user) as get_user_mock:
            repo.delete("Xyz_Abc")
            assert get_user_mock.call_args.args[1] == "xyz_abc"

    def test_exist_returns_bool_for_mixed_case(self, repo, session):
        session.query.return_value.filter.return_value.first.return_value = MagicMock()
        assert repo.exist("Xyz_Abc") is True
        session.query.return_value.filter.return_value.first.return_value = None
        assert repo.exist("Xyz_Abc") is False
