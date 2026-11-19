"""The key a grant names a skill by.

MLflow's skill registry (3.18+) identifies a skill by an optional organization and a name. A grant
names it with one string, the same spelling MLflow's own auth plugin and its REST paths use:
``<name>``, or ``@<organization>/<name>``. An organization name grants nothing by itself: there is
no key for "every skill of an organization".
"""

from __future__ import annotations

from typing import Tuple


def format_skill_key(organization: str | None, name: str) -> str:
    """The grant key of the skill ``name`` in ``organization``.

    Parameters:
        organization: The organization, or ``""`` / None for a skill outside any.
        name: The skill name.

    Returns:
        ``@<organization>/<name>``, or ``<name>`` without an organization.
    """
    return f"@{organization}/{name}" if organization else name


def parse_skill_key(key: str) -> Tuple[str, str]:
    """``(organization, name)`` of a grant key, validated the way MLflow validates a skill identity.

    Parameters:
        key: ``<name>`` or ``@<organization>/<name>``.

    Returns:
        The organization (``""`` for none) and the name.

    Raises:
        ValueError: ``key`` is not the key of a skill MLflow could store, or the installed MLflow
            has no skill registry.
    """
    if not isinstance(key, str):
        raise ValueError("skill key must be a string")
    if key.startswith("@"):
        organization, sep, name = key[1:].partition("/")
        if not (sep and organization and name):
            raise ValueError("invalid skill key")
    else:
        organization, name = "", key
    if not name or "/" in name:
        raise ValueError("invalid skill key")
    validate_skill_identity(organization, name)
    return organization, name


def validate_skill_identity(organization: str, name: str) -> None:
    """Check ``organization`` and ``name`` with MLflow's own validators.

    Raises:
        ValueError: Either is not a string MLflow accepts, or MLflow has no skill registry.
    """
    if not isinstance(organization, str) or not isinstance(name, str):
        raise ValueError("skill organization and name must be strings")
    try:
        from mlflow.utils.validation import _validate_organization_name, _validate_skill_name
    except ImportError as e:
        raise ValueError("the installed MLflow has no skill registry") from e
    try:
        _validate_skill_name(name)
        _validate_organization_name(organization)
    except Exception as e:
        raise ValueError("invalid skill identity") from e
