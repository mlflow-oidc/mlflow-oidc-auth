"""Allowed-group matching: exact names and opt-in patterns (issue #78)."""

import pytest

from mlflow_oidc_auth.group_patterns import BY_NAME, BY_PATTERN, GroupAdmission, admitting_rule, matches_everything, normalize_group_values


class TestExactNames:
    def test_an_exact_name_admits(self):
        assert admitting_rule(["team-a", "mlflow-users"], ["mlflow-users"], []) == GroupAdmission(BY_NAME, "mlflow-users", "mlflow-users")

    @pytest.mark.parametrize("name", ["Data Science [EU]", "mlflow-*", "team?"])
    def test_a_name_with_pattern_characters_means_only_itself(self, name):
        """The reason names and patterns are separate settings: an existing name must not start
        matching other groups, or stop matching its own, when patterns are introduced."""
        assert admitting_rule([name], [name], []) is not None
        others = ["Data Science E", "mlflow-anything", "team1"]
        assert admitting_rule(others, [name], []) is None

    def test_names_are_not_patterns_even_with_no_patterns_configured(self):
        assert admitting_rule(["mlflow-new-team"], ["mlflow-*"], None) is None


class TestPatterns:
    def test_a_pattern_admits_a_new_matching_group(self):
        assert admitting_rule(["mlflow-new-team"], [], ["mlflow-*"]) == GroupAdmission(BY_PATTERN, "mlflow-*", "mlflow-new-team")

    def test_names_are_checked_before_patterns(self):
        admission = admitting_rule(["mlflow", "mlflow-x"], ["mlflow"], ["mlflow-*"])

        assert admission.kind == BY_NAME

    def test_matching_is_case_sensitive(self):
        assert admitting_rule(["MLFLOW-USERS"], [], ["mlflow-*"]) is None

    def test_a_non_matching_group_is_refused(self):
        assert admitting_rule(["other-app-users"], [], ["mlflow-*"]) is None

    def test_star_admits_any_non_empty_group_but_not_none(self):
        assert admitting_rule(["anything"], [], ["*"]) is not None
        assert admitting_rule([], [], ["*"]) is None
        assert admitting_rule([""], [], ["*"]) is None


class TestFailClosed:
    @pytest.mark.parametrize("groups", [None, 42, {"mlflow": True}, [None, 42, ""]])
    def test_unusable_claims_admit_nobody(self, groups):
        assert admitting_rule(groups, ["mlflow"], ["*"]) is None

    @pytest.mark.parametrize("rules", [None, [None, 42, ""], ""])
    def test_unusable_rules_admit_nobody(self, rules):
        assert admitting_rule(["mlflow"], rules, rules) is None


class TestNormalize:
    def test_values_are_normalized(self):
        assert normalize_group_values("mlflow-users") == ["mlflow-users"]
        assert normalize_group_values(["mlflow-users", "", None, 42]) == ["mlflow-users"]
        assert normalize_group_values(None) == []
        assert normalize_group_values({"mlflow-users": True}) == []


@pytest.mark.parametrize(
    "pattern, expected",
    [("*", True), ("**", True), ("?*", True), ("*?", True), ("mlflow-*", False), ("*-*", False), ("[!x]*", False), ("", False), ("?", False)],
)
def test_matches_everything(pattern, expected):
    assert matches_everything(pattern) is expected
