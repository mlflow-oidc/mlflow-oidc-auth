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
    Validate a regex pattern, including ReDoS safety checks.

    Rejects patterns that are empty, syntactically invalid, or contain
    constructs likely to cause catastrophic backtracking (ReDoS).

    :param regex: The regex pattern to validate.
    :raises MlflowException: If the regex is invalid or potentially dangerous.
    """
    if not regex:
        raise MlflowException("Regex pattern cannot be empty", INVALID_STATE)

    # Reject excessively long patterns (defense-in-depth)
    if len(regex) > 1024:
        raise MlflowException(
            f"Regex pattern exceeds maximum length of 1024 characters (got {len(regex)})",
            INVALID_STATE,
        )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            compiled = re.compile(regex)
        except re.error as e:
            raise MlflowException(
                f"Invalid regex pattern: {regex}. Error: {e}", INVALID_STATE
            )
        for warning in w:
            if issubclass(warning.category, SyntaxWarning):
                raise MlflowException(
                    f"Regex pattern may contain invalid escape sequences: {regex}. Warning: {warning.message}",
                    INVALID_STATE,
                )

    # ReDoS safety: reject patterns with nested quantifiers.
    # These are the primary cause of catastrophic backtracking:
    #   (a+)+  (a*)*  (a+)*  (a*)+  (a{2,})+  etc.
    # We detect this by looking for quantifiers applied to groups that
    # themselves contain quantifiers.
    _check_redos_patterns(regex)


# Quantifier characters/patterns that follow an atom
_QUANTIFIER_CHARS = set("+*?")

# Pattern matching a group that contains a quantifier, followed by a repeating quantifier.
# This catches constructs like (a+)+, (?:a+)*, (a+){2,} etc.
# The outer quantifier must be repeating: + * {n,} {n,m} but NOT {n} (exact count).
_NESTED_QUANTIFIER_RE = re.compile(
    r"\("  # opening group paren
    r"(?:\?[:<>=!])?"  # optional non-capturing or lookahead prefix
    r"[^)]*"  # group contents
    r"[+*?]"  # quantifier inside the group
    r"[^)]*"  # any remaining group contents
    r"\)"  # closing group paren
    r"(?:"  # outer quantifier alternatives:
    r"[+*]"  # + or *
    r"|"
    r"\{\d+,\d*\}"  # {n,m} or {n,} (open-ended repetition)
    r")"
)


def _check_redos_patterns(regex: str) -> None:
    """Reject regex patterns with constructs that cause catastrophic backtracking.

    Detects nested quantifiers — the most common ReDoS vector — by scanning
    for groups containing a quantifier that are themselves followed by a quantifier.

    :param regex: The regex pattern string.
    :raises MlflowException: If a nested quantifier pattern is detected.
    """
    if _NESTED_QUANTIFIER_RE.search(regex):
        raise MlflowException(
            f"Regex pattern rejected: nested quantifiers detected (potential ReDoS). Pattern: {regex}",
            INVALID_STATE,
        )
