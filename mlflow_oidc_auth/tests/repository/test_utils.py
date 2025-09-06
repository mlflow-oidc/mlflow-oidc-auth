import pytest
import warnings
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from mlflow_oidc_auth.repository import utils
from mlflow.exceptions import MlflowException


def test_get_user_found():
    session = MagicMock()
    user = MagicMock()
    session.query().filter().one.return_value = user
    assert utils.get_user(session, "user") == user


def test_get_user_not_found():
    """Test get_user when user is not found - covers lines 23-26"""
    session = MagicMock()
    session.query().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        utils.get_user(session, "nonexistent")

    assert "User with username=nonexistent not found" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test_get_user_multiple_found():
    """Test get_user when multiple users found - covers lines 27-28"""
    session = MagicMock()
    session.query().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        utils.get_user(session, "duplicate")

    assert "Found multiple users with username=duplicate" in str(exc.value)
    assert exc.value.error_code == "INVALID_STATE"


def test_get_group_found():
    session = MagicMock()
    group = MagicMock()
    session.query().filter().one.return_value = group
    assert utils.get_group(session, "group") == group


def test_get_group_not_found():
    """Test get_group when group is not found - covers lines 46-49"""
    session = MagicMock()
    session.query().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        utils.get_group(session, "nonexistent")

    assert "Group with name=nonexistent not found" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test_get_group_multiple_found():
    """Test get_group when multiple groups found - covers lines 50-52"""
    session = MagicMock()
    session.query().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        utils.get_group(session, "duplicate")

    assert "Found multiple groups with name=duplicate" in str(exc.value)
    assert exc.value.error_code == "INVALID_STATE"


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


def test_validate_regex_with_syntax_warning():
    """Test validate_regex with syntax warning - covers lines 81-82"""
    # Mock the warnings.catch_warnings to simulate a SyntaxWarning
    with patch("warnings.catch_warnings") as mock_catch_warnings, patch("re.compile") as mock_compile:
        mock_warning = MagicMock()
        mock_warning.category = SyntaxWarning
        mock_warning.message = "invalid escape sequence"

        mock_context = MagicMock()
        mock_context.__enter__.return_value = [mock_warning]
        mock_context.__exit__.return_value = None
        mock_catch_warnings.return_value = mock_context

        # Mock re.compile to not raise an error so we can test the warning path
        mock_compile.return_value = MagicMock()

        with pytest.raises(MlflowException) as exc:
            utils.validate_regex("test_pattern")

        assert "Regex pattern may contain invalid escape sequences" in str(exc.value)
        assert exc.value.error_code == "INVALID_STATE"
