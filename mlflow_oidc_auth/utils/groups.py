"""Utilities for matching OIDC group claims against configured access rules."""

from fnmatch import fnmatchcase
from collections.abc import Iterable, Mapping


def normalize_group_values(group_values: object) -> list[str]:
    """Return valid group names from an OIDC claim or detection plugin result."""

    if isinstance(group_values, str):
        values: Iterable[object] = (group_values,)
    elif isinstance(group_values, Iterable) and not isinstance(group_values, Mapping):
        values = group_values
    else:
        return []

    return [group for group in values if isinstance(group, str) and group]


def matches_group_patterns(user_groups: object, allowed_group_patterns: object) -> bool:
    """Return whether any claimed group matches an allowed shell-style pattern.

    Exact group names remain valid patterns, preserving the existing
    ``OIDC_GROUP_NAME`` behavior. Matching is case-sensitive on every platform,
    consistent with OIDC group claim values and Linux deployments.
    """

    groups = normalize_group_values(user_groups)
    patterns = normalize_group_values(allowed_group_patterns)
    return any(fnmatchcase(group, pattern) for group in groups for pattern in patterns)
