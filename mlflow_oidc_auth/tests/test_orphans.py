"""MLflow-side lookups behind regex orphan checks (issue #375).

Detection itself is exercised end to end in ``tests/scim/test_scim_deprovisioning.py``; these cover
the two places a regex subject lives in MLflow rather than in this plugin's tables.
"""

from types import SimpleNamespace
from unittest.mock import patch

from mlflow.exceptions import MlflowException

from mlflow_oidc_auth import orphans


class _Tracking:
    def __init__(self, names):
        self.names = names
        self.calls = 0

    def get_experiment(self, experiment_id):
        self.calls += 1
        if experiment_id not in self.names:
            raise MlflowException(f"No Experiment with id={experiment_id} exists")
        return SimpleNamespace(name=self.names[experiment_id])


class _Registry:
    def __init__(self, models):
        self.models = models

    def get_registered_model(self, name):
        if name not in self.models:
            raise MlflowException(f"Registered Model with name={name} not found")
        return SimpleNamespace(_tags=self.models[name])


def test_experiment_names_leave_unresolvable_ids_out():
    tracking = _Tracking({"1": "team/churn"})
    with patch("mlflow.server.handlers._get_tracking_store", return_value=tracking):
        assert orphans._experiment_names(["1", "2"]) == {"1": "team/churn"}


def test_experiment_lookups_are_capped(monkeypatch):
    monkeypatch.setattr(orphans, "_EXTERNAL_LOOKUP_LIMIT", 3)
    tracking = _Tracking({str(i): f"exp-{i}" for i in range(10)})
    with patch("mlflow.server.handlers._get_tracking_store", return_value=tracking):
        names = orphans._experiment_names([str(i) for i in range(10)])
    assert tracking.calls == 3 and len(names) == 3


def test_prompt_flags_read_the_raw_prompt_tag():
    registry = _Registry({"summarize": {"mlflow.prompt.is_prompt": "true"}, "churn": {}})
    with patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        assert orphans._prompt_flags(["summarize", "churn", "missing"]) == {"summarize": True, "churn": False}


def test_rule_matchers_follow_the_resolvers():
    def rule(regex, priority, permission, id_=0):
        return SimpleNamespace(id=id_, regex=regex, priority=priority, permission=permission)

    # First match by priority wins, as in utils.permissions._match_regex_permission.
    assert orphans._manages_by_rules([rule("^a", 1, "READ"), rule("^a", 2, "MANAGE")], "abc") is False
    assert orphans._manages_by_rules([rule("^b", 1, "READ"), rule("^a", 2, "MANAGE")], "abc") is True
    assert orphans._manages_by_rules([rule("^b", 1, "MANAGE")], "abc") is False
    # Workspaces: the most permissive of the best-priority matches.
    assert orphans._manages_workspace_by_rules([rule("^a", 1, "READ"), rule("^ab", 1, "MANAGE")], "abc") is True
    assert orphans._manages_workspace_by_rules([rule("^a", 1, "READ"), rule("^ab", 2, "MANAGE")], "abc") is False


def test_a_malformed_pattern_holds_nothing():
    bad = SimpleNamespace(id=0, regex="([", priority=1, permission="MANAGE")
    assert orphans._manages_by_rules([bad], "abc") is False
    assert orphans._manages_workspace_by_rules([bad], "abc") is False


def test_an_unavailable_mlflow_store_resolves_nothing():
    with patch("mlflow.server.handlers._get_tracking_store", side_effect=RuntimeError("down")):
        assert orphans._experiment_names(["1"]) == {}
    with patch("mlflow.server.handlers._get_model_registry_store", side_effect=RuntimeError("down")):
        assert orphans._prompt_flags(["m"]) == {}
