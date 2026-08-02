"""Utilities for matching OIDC group claims against configured access rules."""

from fnmatch import fnmatchcase
from typing import Iterable


def matches_group_patterns(user_groups: Iterable[str], allowed_group_patterns: Iterable[str]) -> bool:
    """Return whether any claimed group matches an allowed shell-style pattern.

    Exact group names remain valid patterns, preserving the existing
    ``OIDC_GROUP_NAME`` behavior. Matching is case-sensitive on every platform,
    consistent with OIDC group claim values and Linux deployments.
    """

    patterns = [pattern for pattern in allowed_group_patterns if isinstance(pattern, str)]
    return any(isinstance(group, str) and any(fnmatchcase(group, pattern) for pattern in patterns) for group in user_groups)
