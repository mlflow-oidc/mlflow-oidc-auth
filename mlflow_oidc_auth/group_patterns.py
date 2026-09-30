"""Matching a user's group claims against the allowed-group configuration (issue #78).

Two settings decide who may log in, and they never share a syntax:

* ``OIDC_GROUP_NAME`` — exact group names, as they always were. A name containing ``*``, ``?`` or
  ``[`` (``Data Science [EU]`` is a legitimate Entra or Okta group) still means only itself.
* ``OIDC_GROUP_NAME_PATTERN`` — case-sensitive shell-style patterns (``mlflow-*``), opt-in and
  empty by default, so an existing deployment's admission rules do not change on upgrade.

Matching is local, against the groups the provider already asserted: no provider API call.
"""

from collections.abc import Iterable, Mapping
from fnmatch import fnmatchcase
from typing import NamedTuple, Optional

#: The rule kinds :func:`admitting_rule` reports.
BY_NAME = "name"
BY_PATTERN = "pattern"


class GroupAdmission(NamedTuple):
    """Why a user was admitted: which configured rule matched which of their groups."""

    kind: str
    rule: str
    group: str


def normalize_group_values(group_values: object) -> list[str]:
    """The valid group names in a claim or a detection plugin's result.

    A single string is one group (JumpCloud sends a lone group that way). A mapping, ``None``,
    or anything that is not iterable yields no groups, and non-string or empty entries are
    dropped: an unusable value admits nobody rather than failing open.

    Parameters:
        group_values: The raw claim or plugin output.

    Returns:
        The group names, in their original order.
    """
    if isinstance(group_values, str):
        values: Iterable[object] = (group_values,)
    elif isinstance(group_values, Iterable) and not isinstance(group_values, Mapping):
        values = group_values
    else:
        return []
    return [group for group in values if isinstance(group, str) and group]


def admitting_rule(user_groups: object, names: object, patterns: object) -> Optional[GroupAdmission]:
    """The first allowed-group rule the user's groups satisfy, or ``None``.

    Exact names are checked first, then patterns; the result says which, so a login admitted by a
    pattern can be recorded as such.

    Parameters:
        user_groups: The user's groups (normalized here).
        names: ``OIDC_GROUP_NAME`` — matched exactly.
        patterns: ``OIDC_GROUP_NAME_PATTERN`` — matched with :func:`fnmatch.fnmatchcase`.

    Returns:
        A :class:`GroupAdmission`, or ``None`` when no rule matches.
    """
    groups = normalize_group_values(user_groups)
    for name in normalize_group_values(names):
        if name in groups:
            return GroupAdmission(BY_NAME, name, name)
    for pattern in normalize_group_values(patterns):
        for group in groups:
            if fnmatchcase(group, pattern):
                return GroupAdmission(BY_PATTERN, pattern, group)
    return None


#: Group names with nothing in common: a pattern matching all of them matches essentially anything.
_UNRELATED_NAMES = ("a", "zz9", "Finance Team", "x-y_z.1", "[eu] ops", "mlflow")


def matches_everything(pattern: str) -> bool:
    """Whether a pattern admits essentially any group name — ``*``, but also ``?*``, ``*?``, ``**``.

    Checked by behaviour rather than by spelling: a pattern that matches every one of a handful of
    unrelated names is not scoping anything, however it is written.
    """
    return isinstance(pattern, str) and bool(pattern) and all(fnmatchcase(name, pattern) for name in _UNRELATED_NAMES)
