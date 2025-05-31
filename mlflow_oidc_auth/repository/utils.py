from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
import re
from mlflow_oidc_auth.db.models import SqlUser, SqlGroup, SqlUserGroup
from sqlalchemy.orm import Session
import warnings


def get_one_or_raise(session: Session, model, *criterion, not_found_msg: str, multiple_msg: str):
    """
    Like .one() but raises an error if no row or >1 row.
    :param session: SQLAlchemy session
    :param model: SQLAlchemy model class
    :param criterion: SQLAlchemy filter criteria
    :param not_found_msg: Message to raise if no row is found
    :param multiple_msg: Message to raise if multiple rows are found
    :return: The single row found
    :raises MlflowException: If no row or multiple rows are found
    """
    try:
        return session.query(model).filter(*criterion).one()
    except NoResultFound:
        raise MlflowException(not_found_msg, RESOURCE_DOES_NOT_EXIST)
    except MultipleResultsFound:
        raise MlflowException(multiple_msg, INVALID_STATE)


def get_user(session: Session, username: str) -> SqlUser:
    """
    Get a user by username.
    :param session: SQLAlchemy session
    :param username: The username of the user.
    :return: The user object
    :raises MlflowException: If the user is not found or if multiple users are found with the same username.
    """
    return get_one_or_raise(
        session,
        SqlUser,
        SqlUser.username == username,
        not_found_msg=f"User with username={username} not found",
        multiple_msg=f"Found multiple users with username={username}",
    )


def get_group(session: Session, group_name: str) -> SqlGroup:
    """
    Get a group by its name.
    :param session: SQLAlchemy session
    :param group_name: The name of the group.
    :return: The group object
    :raises MlflowException: If the group is not found or if multiple groups are found with the same name.
    """
    return get_one_or_raise(
        session,
        SqlGroup,
        SqlGroup.group_name == group_name,
        not_found_msg=f"Group with name={group_name} not found",
        multiple_msg=f"Found multiple groups with name={group_name}",
    )


def list_user_groups(session: Session, user: SqlUser) -> list[SqlUserGroup]:
    """
    Get all groups for a given user ID.
    :param session: SQLAlchemy session
    :param user_id: The ID of the user.
    :return: A list of group objects
    """
    return session.query(SqlUserGroup).filter(SqlUserGroup.user_id == user.id).all()


def validate_regex(regex: str) -> None:
    """
    Validate a regex pattern.
    :param regex: The regex pattern to validate.
    :raises MlflowException: If the regex is invalid.
    """
    if not regex:
        raise MlflowException("Regex pattern cannot be empty", INVALID_STATE)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            re.compile(regex)
        except re.error as e:
            raise MlflowException(f"Invalid regex pattern: {regex}. Error: {e}", INVALID_STATE)
        for warning in w:
            if issubclass(warning.category, SyntaxWarning):
                raise MlflowException(
                    f"Regex pattern may contain invalid escape sequences: {regex}. " f"Warning: {warning.message}",
                    INVALID_STATE,
                )
