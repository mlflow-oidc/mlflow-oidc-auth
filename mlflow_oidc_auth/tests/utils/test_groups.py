"""Tests for OIDC group access pattern matching."""

from mlflow_oidc_auth.utils.groups import matches_group_patterns, normalize_group_values


def test_exact_group_names_remain_supported():
    assert matches_group_patterns(["team-a", "mlflow-users"], ["mlflow-users"])


def test_wildcard_allows_new_matching_groups():
    assert matches_group_patterns(["mlflow-new-team"], ["mlflow-*"])


def test_star_matches_any_nonempty_string_group():
    assert matches_group_patterns(["new-keycloak-group"], ["*"])
    assert not matches_group_patterns([""], ["*"])


def test_nonmatching_and_empty_groups_are_denied():
    assert not matches_group_patterns(["other-app-users"], ["mlflow-*"])
    assert not matches_group_patterns([], ["*"])


def test_matching_is_case_sensitive():
    assert not matches_group_patterns(["MLFLOW-USERS"], ["mlflow-*"])


def test_invalid_claim_values_fail_closed():
    assert not matches_group_patterns([None, 42], ["*"])
    assert not matches_group_patterns(None, ["*"])
    assert not matches_group_patterns(["mlflow-users"], None)


def test_group_values_are_normalized_before_use():
    assert normalize_group_values("mlflow-users") == ["mlflow-users"]
    assert normalize_group_values(["mlflow-users", "", None, 42]) == ["mlflow-users"]
    assert normalize_group_values(None) == []
    assert normalize_group_values({"mlflow-users": True}) == []
