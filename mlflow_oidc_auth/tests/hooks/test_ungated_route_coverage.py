"""Routes that reached no validator at all (issue #291).

A ``None`` validator is not a deny: ``before_request_hook`` falls through and serves the
request. Two clusters were reachable by any authenticated non-admin.
"""

from unittest.mock import patch

import pytest
from flask import Flask

from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.hooks.before_request import _deny_non_admin, _find_validator

probe = Flask(__name__)


def _validator_for(path, method):
    with probe.test_request_context(path, method=method) as ctx:
        return _find_validator(ctx.request)


class TestRunInputsAndOutputsAreGated:
    """log-inputs and outputs attach data to a run; every sibling proto was already gated."""

    @pytest.mark.parametrize("prefix", ["/api", "/ajax-api"])
    @pytest.mark.parametrize("suffix", ["runs/log-inputs", "runs/outputs"])
    def test_route_requires_update_on_the_run(self, prefix, suffix):
        validator = _validator_for(f"{prefix}/2.0/mlflow/{suffix}", "POST")

        assert validator is not None, f"{suffix} still reaches no validator"
        assert validator.__name__ == "validate_can_update_run"

    def test_it_denies_a_user_without_update_on_that_run(self):
        """Wiring is not a decision — drive it to an actual deny."""
        from mlflow_oidc_auth.permissions import get_permission
        from mlflow_oidc_auth.validators.run import validate_can_update_run

        with probe.test_request_context("/api/2.0/mlflow/runs/log-inputs", method="POST", json={"run_id": "VICTIM-RUN"}):
            with (
                patch("mlflow_oidc_auth.validators.run._get_tracking_store") as store,
                patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as resolved,
            ):
                store.return_value.get_run.return_value.info.experiment_id = "exp-of-victim"
                resolved.return_value.permission = get_permission("READ")

                assert validate_can_update_run("bob") is False
                store.return_value.get_run.assert_called_once_with("VICTIM-RUN")


class TestNativeWebhookRoutesAreAdminOnly:
    """MLflow's own registry-webhook CRUD bypassed the plugin's admin-only webhook API.

    Delivery is filtered by event type with no tenant scoping, so a non-admin webhook
    receives the whole server's registry events.
    """

    @staticmethod
    def _native_webhook_routes():
        seen = set()
        for rule in mlflow_app.url_map.iter_rules():
            path = str(rule)
            if "/mlflow/webhooks" not in path:
                continue
            for method in (rule.methods or set()) - {"OPTIONS", "HEAD"}:
                seen.add((path, method))
        return sorted(seen)

    def test_mlflow_actually_serves_them(self):
        assert self._native_webhook_routes(), "precondition: MLflow must register a native webhook API"

    def test_every_native_webhook_route_denies_non_admins(self):
        ungated = []
        for path, method in self._native_webhook_routes():
            concrete = path.replace("<webhook_id>", "wh-1")
            if _validator_for(concrete, method) is not _deny_non_admin:
                ungated.append(f"{method} {path}")

        assert not ungated, "native webhook routes reachable by non-admins: " + ", ".join(ungated)

    def test_the_sentinel_really_denies(self):
        """_deny_non_admin runs only for non-admins; admins short-circuit earlier."""
        assert _deny_non_admin("anyone") is False


def test_structural_every_run_mutating_proto_is_gated():
    """A future MLflow that adds a run-mutating RPC must fail here, not ship ungated.

    log-inputs and outputs were missing precisely because nothing asserted this.
    """
    from mlflow.protos import service_pb2

    from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS

    # Protos whose name says they write to a run.
    candidates = [
        name
        for name in dir(service_pb2)
        if name.startswith(("Log", "Set", "Delete", "Update", "Create", "Restore")) and "Run" in name and hasattr(getattr(service_pb2, name), "DESCRIPTOR")
    ]
    assert candidates, "precondition: expected run-mutating protos in MLflow's service"

    ungated = [name for name in candidates if getattr(service_pb2, name) not in BEFORE_REQUEST_HANDLERS]
    assert not ungated, "run-mutating protos with no validator: " + ", ".join(sorted(ungated))
