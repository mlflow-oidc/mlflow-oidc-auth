"""Shared group name validation.

A group name is accepted through two independent paths — SCIM's ``displayName``
(``routers/scim.py``) and the admin create-group API (``routers/group_permissions.py``) — and both
must hold it to the same rule. This module is the one place that rule is written; each router
wraps :func:`validate_group_name_chars` in its own error type so the two keep raising exactly the
errors they always have.
"""

import unicodedata
from typing import Any

#: Same bound on both paths: a group's ``displayName`` (SCIM) and the admin API's ``group_name``.
MAX_GROUP_NAME_LENGTH = 255

#: A group name becomes a path segment (this repo's ``{group_name:path}`` route parameter and
#: SCIM's ``/Groups/{id}`` alike), so none of these may appear in it.
GROUP_NAME_RESERVED_CHARS = frozenset("/?#%")


def validate_group_name_chars(value: Any) -> str:
    """Validate and normalize a group name's characters, independent of how it will be used.

    Stripped, non-empty, at most :data:`MAX_GROUP_NAME_LENGTH` characters, no control or
    non-printing characters, and valid Unicode. Does not check for the path-segment reserved
    characters (:data:`GROUP_NAME_RESERVED_CHARS`) — callers that create a new name, rather than
    only re-validating an existing one, check that separately (see ``routers/scim.py``'s
    ``scim_create_group`` and ``routers/group_permissions.py``'s ``create_group``).

    :param value: The raw, client-supplied group name.
    :return: The stripped, validated group name.
    :raises ValueError: If the name fails any of these checks. The message names the rule broken
        (e.g. ``"must not be empty"``) without naming a field, so each caller can prefix it with
        whichever field name it uses (``displayName`` for SCIM, ``group_name`` for the admin API).
    """
    if not isinstance(value, str):
        raise ValueError("must be a string")
    name = value.strip()
    if not name:
        raise ValueError("must not be empty")
    if len(name) > MAX_GROUP_NAME_LENGTH:
        raise ValueError(f"must be at most {MAX_GROUP_NAME_LENGTH} characters")
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise ValueError("must not contain control or non-printing characters")
    try:
        name.encode("utf-8")
    except UnicodeError:
        raise ValueError("is not valid Unicode")
    return name
