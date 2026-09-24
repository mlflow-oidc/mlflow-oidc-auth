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


def test_experiment_names_leave_unresolvable_ids_out(monkeypatch):
    monkeypatch.setattr(orphans, "_lookup_workspaces", lambda: [None])
    tracking = _Tracking({"1": "team/churn"})
    with patch("mlflow.server.handlers._get_tracking_store", return_value=tracking):
        assert orphans._experiment_names(["1", "2"]) == {"1": "team/churn"}


def test_experiment_lookups_are_capped(monkeypatch):
    monkeypatch.setattr(orphans, "_EXTERNAL_LOOKUP_LIMIT", 3)
    monkeypatch.setattr(orphans, "_lookup_workspaces", lambda: [None])
    tracking = _Tracking({str(i): f"exp-{i}" for i in range(10)})
    with patch("mlflow.server.handlers._get_tracking_store", return_value=tracking):
        names = orphans._experiment_names([str(i) for i in range(10)])
    assert tracking.calls == 3 and len(names) == 3


def test_prompt_kinds_read_the_raw_prompt_tag(monkeypatch):
    monkeypatch.setattr(orphans, "_lookup_workspaces", lambda: [None])
    registry = _Registry({"summarize": {"mlflow.prompt.is_prompt": "true"}, "churn": {}})
    with patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        assert orphans._prompt_kinds(["summarize", "churn", "missing"]) == {"summarize": {True}, "churn": {False}}


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
        assert orphans._prompt_kinds(["m"]) == {}


# -- workspaces enabled: lookups are made in each workspace ------------------------------------


class _WorkspaceAwareTracking:
    """Like MLflow's workspace-aware store: an experiment is visible only from its own workspace."""

    def __init__(self, experiments):
        self.experiments = experiments  # {id: (workspace, name)}

    def get_experiment(self, experiment_id):
        from mlflow.utils.workspace_context import get_request_workspace

        workspace, name = self.experiments.get(experiment_id, (None, None))
        if workspace is None or workspace != get_request_workspace():
            raise MlflowException(f"No Experiment with id={experiment_id} exists")
        return SimpleNamespace(name=name)


class _WorkspaceAwareRegistry:
    def __init__(self, models):
        self.models = models  # {(workspace, name): tags}

    def get_registered_model(self, name):
        from mlflow.utils.workspace_context import get_request_workspace

        tags = self.models.get((get_request_workspace(), name))
        if tags is None:
            raise MlflowException(f"Registered Model with name={name} not found")
        return SimpleNamespace(_tags=tags)


def _workspaces(monkeypatch, names):
    from mlflow_oidc_auth.config import config

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    store = SimpleNamespace(list_workspaces=lambda: [SimpleNamespace(name=n) for n in names])
    return patch("mlflow.server.handlers._get_workspace_store", return_value=store)


def test_experiment_names_are_found_in_their_own_workspace(monkeypatch):
    tracking = _WorkspaceAwareTracking({"1": ("tenant-b", "team/churn")})
    with _workspaces(monkeypatch, ["default", "tenant-a", "tenant-b"]), patch("mlflow.server.handlers._get_tracking_store", return_value=tracking):
        assert orphans._experiment_names(["1", "2"]) == {"1": "team/churn"}


def test_prompt_kinds_collect_every_workspace(monkeypatch):
    registry = _WorkspaceAwareRegistry({("tenant-a", "churn"): {"mlflow.prompt.is_prompt": "true"}, ("default", "churn"): {}})
    with _workspaces(monkeypatch, ["default", "tenant-a"]), patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        assert orphans._prompt_kinds(["churn"]) == {"churn": {True, False}}


def test_unlistable_workspaces_resolve_nothing_and_warn(monkeypatch, caplog):
    import logging

    from mlflow_oidc_auth.config import config

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    with patch("mlflow.server.handlers._get_workspace_store", side_effect=RuntimeError("down")), caplog.at_level(logging.WARNING, logger=orphans.logger.name):
        assert orphans._experiment_names(["1"]) == {}
    assert any("workspaces could not be listed" in r.getMessage() for r in caplog.records)
