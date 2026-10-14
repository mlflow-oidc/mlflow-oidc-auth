"""Which regex grant decides when several match (issue #459, maintainer decision on PR #463).

Priority decides first: only matches in the best (lowest-number) priority tier count. Within that
tier the permission rank decides, by the same rule direct group grants use
(``compare_permissions``): any ``NO_PERMISSIONS`` match wins; otherwise the most capable
permission (MANAGE > EDIT > USE > READ). Row id plays no part in the result.

Every case runs through the single-resource path (the permission source builders that
``resolve_permission`` uses) and the batch path (``resolve_*_from_context``), for user and group
patterns and for registered models and prompts, and both must agree.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.utils.batch_permissions import (
    UserPermissionContext,
    resolve_model_permission_from_context,
    resolve_prompt_permission_from_context,
)
from mlflow_oidc_auth.utils.permissions import (
    _build_prompt_sources,
    _build_registered_model_sources,
    _match_regex_permission,
    _match_regex_permission_or_none,
)


def _rule(id_, priority, permission, regex=".*", group_id=None, workspace="*"):
    return SimpleNamespace(id=id_, priority=priority, permission=permission, regex=regex, group_id=group_id, workspace=workspace)


# (rules, resource name, expected permission). Ids are chosen so that "lowest id wins" would give
# the wrong answer in the cases where rank must decide.
CASES = {
    "equal_priority_read_then_manage": ([_rule(1, 1, "READ"), _rule(2, 1, "MANAGE")], "team-x", "MANAGE"),
    "equal_priority_manage_then_read": ([_rule(1, 1, "MANAGE"), _rule(2, 1, "READ")], "team-x", "MANAGE"),
    "equal_priority_manage_then_no_permissions": ([_rule(1, 1, "MANAGE"), _rule(2, 1, "NO_PERMISSIONS")], "team-x", "NO_PERMISSIONS"),
    "equal_priority_no_permissions_then_manage": ([_rule(1, 1, "NO_PERMISSIONS"), _rule(2, 1, "MANAGE")], "team-x", "NO_PERMISSIONS"),
    "cross_group_broad_read_narrow_manage": (
        [_rule(1, 1, "READ", regex=".*", group_id=1), _rule(2, 1, "MANAGE", regex="^team-.*", group_id=2)],
        "team-x",
        "MANAGE",
    ),
    "better_priority_beats_higher_rank": ([_rule(1, 1, "READ"), _rule(2, 2, "MANAGE")], "team-x", "READ"),
    "better_priority_beats_higher_rank_unsorted": ([_rule(1, 2, "MANAGE"), _rule(2, 1, "READ")], "team-x", "READ"),
    "better_priority_beats_no_permissions": ([_rule(1, 1, "READ"), _rule(2, 2, "NO_PERMISSIONS")], "team-x", "READ"),
    "non_matching_higher_rank_ignored": ([_rule(1, 1, "READ"), _rule(2, 1, "MANAGE", regex="^other-.*")], "team-x", "READ"),
    "out_of_scope_higher_rank_ignored": ([_rule(1, 1, "READ"), _rule(2, 1, "MANAGE", workspace="team-b")], "team-x", "READ"),
    "out_of_scope_no_permissions_ignored": ([_rule(1, 1, "READ"), _rule(2, 1, "NO_PERMISSIONS", workspace="team-b")], "team-x", "READ"),
}


@pytest.fixture(autouse=True)
def _workspaces_disabled():
    """Workspaces off: every resource is in ``default``, so a pattern for ``team-b`` is out of scope."""
    from mlflow_oidc_auth.config import config

    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False):
        yield


@pytest.mark.parametrize("rules, name, expected", CASES.values(), ids=CASES.keys())
def test_matcher(rules, name, expected):
    assert _match_regex_permission(rules, name, "model name") == expected
    assert _match_regex_permission_or_none(rules, name, "model name") == expected


def _single_path(kind: str, source: str, rules, name: str) -> str:
    """The regex source the single-resource path (``resolve_permission``) evaluates."""
    fake_store = MagicMock()
    fake_store.get_groups_ids_for_user.return_value = [1, 2]
    fake_store.list_registered_model_regex_permissions.return_value = rules
    fake_store.list_group_registered_model_regex_permissions_for_groups_ids.return_value = rules
    fake_store.list_prompt_regex_permissions.return_value = rules
    fake_store.list_group_prompt_regex_permissions_for_groups_ids.return_value = rules
    builder = _build_prompt_sources if kind == "prompt" else _build_registered_model_sources
    with patch("mlflow_oidc_auth.utils.permissions.store", fake_store):
        return builder(name, "alice")[source]()


def _batch_path(kind: str, source: str, rules, name: str) -> str:
    """The same decision through the batch resolver, with only that source configured."""
    lists = {
        "model_regex_permissions": [],
        "group_model_regex_permissions": [],
        "prompt_regex_permissions": [],
        "group_prompt_regex_permissions": [],
    }
    prefix = "" if source == "regex" else "group_"
    lists[f"{prefix}{'prompt' if kind == 'prompt' else 'model'}_regex_permissions"] = rules
    ctx = UserPermissionContext(
        username="alice",
        group_ids=[1, 2],
        user_experiment_permissions={},
        group_experiment_permissions={},
        experiment_regex_permissions=[],
        group_experiment_regex_permissions=[],
        user_model_permissions={},
        group_model_permissions={},
        **lists,
    )
    resolve = resolve_prompt_permission_from_context if kind == "prompt" else resolve_model_permission_from_context
    with patch("mlflow_oidc_auth.utils.batch_permissions.config") as mock_config:
        mock_config.PERMISSION_SOURCE_ORDER = [source]
        mock_config.DEFAULT_MLFLOW_PERMISSION = "READ"
        mock_config.MLFLOW_ENABLE_WORKSPACES = False
        result = resolve(ctx, name)
    assert result.kind == source
    return result.permission.name


@pytest.mark.parametrize("kind", ["registered_model", "prompt"])
@pytest.mark.parametrize("source", ["regex", "group-regex"])
@pytest.mark.parametrize("rules, name, expected", CASES.values(), ids=CASES.keys())
def test_batch_path_agrees_with_single_path(kind, source, rules, name, expected):
    single = _single_path(kind, source, rules, name)
    batch = _batch_path(kind, source, rules, name)

    assert single == expected
    assert batch == expected
