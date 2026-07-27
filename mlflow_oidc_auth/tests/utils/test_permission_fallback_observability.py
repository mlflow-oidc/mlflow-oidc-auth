"""A permission decision that came from the configured default must be visible (#293).

`DEFAULT_MLFLOW_PERMISSION` ships as MANAGE, so on a fresh install every resource with no
explicit grant is handed out by configuration. Nothing recorded that, which is why the
exposure was invisible in running deployments. It is surfaced before the default changes.
"""

from unittest.mock import MagicMock

import pytest

from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.utils import permissions as P
from mlflow_oidc_auth.utils.batch_permissions import (
    UserPermissionContext,
    resolve_model_permission_from_context,
)


@pytest.fixture(autouse=True)
def _clean_counters():
    """Counters are module-level, and every test in the suite can add to them."""
    P.reset_permission_fallback_counts()
    yield
    P.reset_permission_fallback_counts()


@pytest.fixture
def captured_logger(monkeypatch):
    """Assert against a mocked module logger.

    Other tests in this suite mock the logging machinery globally, so asserting on real
    log records passed in isolation and captured nothing once the whole suite ran. The
    behaviour under test is "does it warn", not "does the logging framework work".
    """
    logger = MagicMock()
    monkeypatch.setattr(P, "logger", logger)
    return logger


def _empty_context(username="alice"):
    return UserPermissionContext(
        username=username,
        group_ids=[],
        user_experiment_permissions={},
        group_experiment_permissions={},
        experiment_regex_permissions=[],
        group_experiment_regex_permissions=[],
        user_model_permissions={},
        group_model_permissions={},
        model_regex_permissions=[],
        group_model_regex_permissions=[],
        prompt_regex_permissions=[],
        group_prompt_regex_permissions=[],
    )


class TestFallbackRecording:
    def test_a_granting_fallback_warns(self, captured_logger):
        P.record_permission_fallback("experiment", "12", "alice", get_permission("MANAGE"))

        captured_logger.warning.assert_called_once()
        message = captured_logger.warning.call_args.args[0]
        assert "DEFAULT_MLFLOW_PERMISSION granted MANAGE" in message
        assert "experiment" in message, "the resource TYPE tells the operator where to look"
        assert "alice" in message
        # The resource id is deliberately absent — see TestResourceIdsStayOutOfLogs.
        assert "12" not in message.replace("#293", "")

    def test_a_denying_fallback_never_warns(self, captured_logger):
        """No access was handed out, so there is nothing for an operator to act on."""
        for i in range(50):
            P.record_permission_fallback("experiment", f"exp-{i}", "alice", get_permission("NO_PERMISSIONS"))

        captured_logger.warning.assert_not_called()
        assert P.get_permission_fallback_counts() == {"experiment": 50}, "it must still be counted"

    def test_warnings_are_throttled_but_never_stop(self, captured_logger):
        """The batch filters resolve one permission per resource.

        Listing a few thousand experiments must not emit a few thousand identical
        warnings — but the process must not go silent after startup either.
        """
        for i in range(1000):
            P.record_permission_fallback("experiment", f"exp-{i}", "alice", get_permission("MANAGE"))

        # Occurrences 1, 10, 100 and 1000 — four warnings for a thousand grants.
        assert captured_logger.warning.call_count == 4
        assert P.get_permission_fallback_counts() == {"experiment": 1000}

    def test_counts_are_kept_per_resource_type(self):
        P.record_permission_fallback("experiment", "1", "alice", get_permission("READ"))
        P.record_permission_fallback("registered_model", "m", "alice", get_permission("READ"))
        P.record_permission_fallback("registered_model", "m2", "alice", get_permission("READ"))

        assert P.get_permission_fallback_counts() == {"experiment": 1, "registered_model": 2}


class TestResolutionPathsRecord:
    """Both resolution paths must report — the batch one bypasses resolve_permission."""

    def test_single_resource_resolution_records_the_fallback(self, monkeypatch):
        monkeypatch.setattr(P, "get_permission_from_store_or_default", lambda cfg: PermissionResult(get_permission("MANAGE"), "fallback"))
        monkeypatch.setattr(P, "_apply_workspace_fallback", lambda result, username: result)
        monkeypatch.setitem(P.PERMISSION_REGISTRY, "experiment", lambda resource_id, username, **kw: {})
        P.flush_permission_cache()

        P.resolve_permission("experiment", "42", "alice")

        assert P.get_permission_fallback_counts() == {"experiment": 1}

    def test_a_real_grant_is_not_recorded_as_a_fallback(self, monkeypatch):
        monkeypatch.setattr(P, "get_permission_from_store_or_default", lambda cfg: PermissionResult(get_permission("READ"), "user"))
        monkeypatch.setattr(P, "_apply_workspace_fallback", lambda result, username: result)
        monkeypatch.setitem(P.PERMISSION_REGISTRY, "experiment", lambda resource_id, username, **kw: {})
        P.flush_permission_cache()

        P.resolve_permission("experiment", "43", "alice")

        assert P.get_permission_fallback_counts() == {}, "an explicit grant is not a fallback"

    def test_batch_resolution_records_the_fallback(self):
        """filter_manageable_* run entirely off pre-fetched context, bypassing resolve_permission."""
        result = resolve_model_permission_from_context(_empty_context(), "some-model")

        assert result.kind == "fallback", "precondition: an empty context must fall back"
        assert P.get_permission_fallback_counts() == {"registered_model": 1}


class TestResourceIdsStayOutOfLogs:
    """Identifiers are recorded in-process, not written to the log (CodeQL, #294).

    One resource type here is the gateway SECRET, whose id is the secret's name. Not its
    value — but a name like "openai-prod-key" still should not land in a log aggregator by
    default, and an operator can get the same detail on demand.
    """

    def test_the_warning_does_not_contain_the_resource_id(self, captured_logger):
        P.record_permission_fallback("gateway_secret", "openai-prod-key", "alice", get_permission("MANAGE"))

        message = captured_logger.warning.call_args.args[0]
        assert "openai-prod-key" not in message
        assert "gateway_secret" in message, "the resource TYPE is still actionable"

    def test_the_debug_line_does_not_contain_the_resource_id(self, captured_logger):
        P.record_permission_fallback("gateway_secret", "openai-prod-key", "alice", get_permission("MANAGE"))

        rendered = " ".join(str(part) for call in captured_logger.debug.call_args_list for part in call.args)
        assert "openai-prod-key" not in rendered

    def test_ids_are_available_on_demand(self):
        P.record_permission_fallback("experiment", "12", "alice", get_permission("MANAGE"))
        P.record_permission_fallback("experiment", "13", "alice", get_permission("MANAGE"))
        P.record_permission_fallback("experiment", "12", "bob", get_permission("MANAGE"))

        assert P.get_permission_fallback_samples() == {"experiment": ["12", "13"]}, "deduplicated, in order"

    def test_the_sample_is_bounded(self):
        """Never drained, and keyed on caller-supplied ids — unbounded would be a leak."""
        for i in range(500):
            P.record_permission_fallback("experiment", f"exp-{i}", "alice", get_permission("MANAGE"))

        assert len(P.get_permission_fallback_samples()["experiment"]) == P._FALLBACK_SAMPLE_LIMIT
        assert P.get_permission_fallback_counts() == {"experiment": 500}, "counting is not capped"
