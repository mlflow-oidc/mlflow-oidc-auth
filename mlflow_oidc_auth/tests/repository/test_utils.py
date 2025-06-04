import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository import utils
from mlflow.exceptions import MlflowException


def test_get_user_found():
    session = MagicMock()
    user = MagicMock()
    session.query().filter().one.return_value = user
    assert utils.get_user(session, "user") == user


def test_get_group_found():
    session = MagicMock()
    group = MagicMock()
    session.query().filter().one.return_value = group
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
