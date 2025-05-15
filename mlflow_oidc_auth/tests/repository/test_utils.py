import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository import utils
from mlflow.exceptions import MlflowException


def test_get_one_or_raise_found():
    session = MagicMock()
    model = MagicMock()
    obj = MagicMock()
    session.query().filter().one.return_value = obj
    result = utils.get_one_or_raise(session, model, 1, not_found_msg="not found", multiple_msg="multiple")
    assert result == obj


def test_get_one_or_raise_not_found():
    session = MagicMock()
    model = MagicMock()
    session.query().filter().one.side_effect = Exception("NoResultFound")
    with patch("mlflow_oidc_auth.repository.utils.NoResultFound", Exception):
        with pytest.raises(MlflowException):
            utils.get_one_or_raise(session, model, 1, not_found_msg="not found", multiple_msg="multiple")


def test_get_one_optional_found():
    session = MagicMock()
    model = MagicMock()
    obj = MagicMock()
    session.query().filter().one_or_none.return_value = obj
    result = utils.get_one_optional(session, model, 1)
    assert result == obj


def test_get_one_optional_multiple():
    session = MagicMock()
    model = type("Model", (), {"__tablename__": "table"})
    session.query().filter().one_or_none.side_effect = Exception("MultipleResultsFound")
    with patch("mlflow_oidc_auth.repository.utils.MultipleResultsFound", Exception):
        with pytest.raises(MlflowException):
            utils.get_one_optional(session, model, 1)


def test_get_all():
    session = MagicMock()
    model = MagicMock()
    session.query().filter().all.return_value = [1, 2]
    result = utils.get_all(session, model, 1)
    assert result == [1, 2]


def test_get_user_found():
    session = MagicMock()
    user = MagicMock()
    with patch("mlflow_oidc_auth.repository.utils.get_one_or_raise", return_value=user):
        assert utils.get_user(session, "user") == user


def test_get_group_found():
    session = MagicMock()
    group = MagicMock()
    with patch("mlflow_oidc_auth.repository.utils.get_one_or_raise", return_value=group):
        assert utils.get_group(session, "group") == group


def test_list_user_groups():
    session = MagicMock()
    user = MagicMock(id=1)
    session.query().filter().all.return_value = [1, 2]
    result = utils.list_user_groups(session, user)
    assert result == [1, 2]


def test_validate_regex_valid():
    utils.validate_regex(r"^abc.*")


def test_validate_regex_empty():
    with pytest.raises(MlflowException):
        utils.validate_regex("")


def test_validate_regex_invalid():
    with pytest.raises(MlflowException):
        utils.validate_regex("[unclosed")
