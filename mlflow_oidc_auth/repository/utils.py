import re
import warnings

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup


def get_user(session: Session, username: str) -> SqlUser:
    """
    Get a user by username.
    :param session: SQLAlchemy session
    :param username: The username of the user.
    :return: The user object
    :raises MlflowException: If the user is not found or if multiple users are found with the same username.
    """
    try:
        return session.query(SqlUser).filter(SqlUser.username == username).one()
    except NoResultFound:
        raise MlflowException(
            f"User with username={username} not found",
            RESOURCE_DOES_NOT_EXIST,
        )
    except MultipleResultsFound:
        raise MlflowException(
            f"Found multiple users with username={username}",
            INVALID_STATE,
        )


def get_group(session: Session, group_name: str) -> SqlGroup:
    """
    Get a group by its name.
    :param session: SQLAlchemy session
    :param group_name: The name of the group.
    :return: The group object
    :raises MlflowException: If the group is not found or if multiple groups are found with the same name.
    """
    try:
        return session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one()
    except NoResultFound:
        raise MlflowException(
            f"Group with name={group_name} not found",
            RESOURCE_DOES_NOT_EXIST,
        )
    except MultipleResultsFound:
        raise MlflowException(
            f"Found multiple groups with name={group_name}",
            INVALID_STATE,
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
                    f"Regex pattern may contain invalid escape sequences: {regex}. Warning: {warning.message}",
                    INVALID_STATE,
                )
