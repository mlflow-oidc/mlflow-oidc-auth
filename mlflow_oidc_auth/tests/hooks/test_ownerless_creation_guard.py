"""Layer 1 of the #262 fix: reject creates by users with no permission record, pre-commit."""

from unittest.mock import patch

from flask import Flask


def _app():
    app = Flask(__name__)
    app.secret_key = "test"
    return app


class TestRequiresExistingUserSet:
    """The gated set must cover every create endpoint whose after-request handler grants MANAGE."""

    def test_covers_all_seven_create_types_both_prefixes(self):
        from mlflow_oidc_auth.hooks.before_request import _get_create_grant_paths

        paths = {p for p, _m in _get_create_grant_paths()}
        for suffix in (
            "mlflow/experiments/create",
            "mlflow/registered-models/create",
            "mlflow/scorers/register",
            "mlflow/gateway/endpoints/create",
            "mlflow/gateway/secrets/create",
            "mlflow/gateway/model-definitions/create",
            "mlflow/workspaces",
        ):
            assert any(p.endswith(suffix) for p in paths), f"create endpoint not gated: {suffix}"

    def test_reads_and_child_creates_not_gated(self):
        from mlflow_oidc_auth.hooks.before_request import _requires_existing_user

        assert _requires_existing_user("/api/2.0/mlflow/experiments/get", "GET") is False
        assert _requires_existing_user("/api/2.0/mlflow/experiments/search", "POST") is False
        # runs/model-versions inherit permission from a parent; they must NOT be gated
        assert _requires_existing_user("/api/2.0/mlflow/runs/create", "POST") is False


class TestGateBehavior:
    def _run(self, *, username, is_admin, has_user, path="/api/2.0/mlflow/experiments/create", method="POST"):
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        with _app().test_request_context(path, method=method):
            with (
                patch("mlflow_oidc_auth.hooks.before_request._get_auth_context", return_value=(username, is_admin)),
                patch("mlflow_oidc_auth.hooks.before_request.store") as mock_store,
                patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
                patch("mlflow_oidc_auth.hooks.before_request.config") as cfg,
            ):
                cfg.MLFLOW_ENABLE_WORKSPACES = False
                mock_store.has_user.return_value = has_user
                return before_request_hook()

    def test_create_by_unprovisioned_user_denied(self):
        """The exact #262 case: authenticated, no DB record → 403 before the create runs."""
        resp = self._run(username="api-first@x.com", is_admin=False, has_user=False)
        assert resp is not None and resp.status_code == 403

    def test_create_by_provisioned_user_passes_gate(self):
        """A user with a record is not stopped by this gate."""
        resp = self._run(username="known@x.com", is_admin=False, has_user=True)
        assert resp is None or getattr(resp, "status_code", None) != 403

    def test_api_first_admin_also_denied(self):
        """The gate sits before the admin early-out: an API-first admin hits the same bug."""
        resp = self._run(username="admin@x.com", is_admin=True, has_user=False)
        assert resp is not None and resp.status_code == 403

    def test_provisioned_admin_bypasses(self):
        """A provisioned admin passes the gate and then the normal admin bypass applies."""
        resp = self._run(username="admin@x.com", is_admin=True, has_user=True)
        assert resp is None

    def test_non_create_path_not_gated_for_unprovisioned_user(self):
        """A read by an unprovisioned user is not blocked by this gate (no ownerless risk)."""
        resp = self._run(username="api-first@x.com", is_admin=False, has_user=False, path="/api/2.0/mlflow/experiments/get", method="GET")
        assert resp is None or getattr(resp, "status_code", None) != 403

    def test_has_user_checked_with_authenticated_username(self):
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        with _app().test_request_context("/api/2.0/mlflow/registered-models/create", method="POST"):
            with (
                patch("mlflow_oidc_auth.hooks.before_request._get_auth_context", return_value=("bob@x.com", False)),
                patch("mlflow_oidc_auth.hooks.before_request.store") as mock_store,
                patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
                patch("mlflow_oidc_auth.hooks.before_request.config") as cfg,
            ):
                cfg.MLFLOW_ENABLE_WORKSPACES = False
                mock_store.has_user.return_value = False
                before_request_hook()
                mock_store.has_user.assert_called_once_with("bob@x.com")
