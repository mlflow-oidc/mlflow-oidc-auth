"""Tests for validators/stuff.py — gateway proxy, dataset search, promptlab, and bulk metric validators."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.validators.stuff import (
    validate_can_create_gateway,
    validate_can_create_promptlab_run,
    validate_can_read_metric_history_bulk,
    validate_can_search_datasets,
    validate_gateway_proxy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flask_app() -> Flask:
    """Minimal Flask application for request context."""
    return Flask(__name__)


# ---------------------------------------------------------------------------
# validate_can_create_gateway
# ---------------------------------------------------------------------------

class TestValidateCanCreateGateway:
    """Tests for the simple gateway creation validator."""

    def test_returns_true_for_any_user(self) -> None:
        """Any authenticated user should be allowed to create a gateway."""
        assert validate_can_create_gateway("alice") is True

    def test_returns_true_for_empty_username(self) -> None:
        """Even edge-case empty username returns True (auth is checked elsewhere)."""
        assert validate_can_create_gateway("") is True


# ---------------------------------------------------------------------------
# validate_gateway_proxy
# ---------------------------------------------------------------------------

class TestValidateGatewayProxy:
    """Tests for the gateway proxy request validator."""

    def test_get_with_named_endpoint_checks_use(self, flask_app: Flask) -> None:
        """GET with an explicit gateway name should check can_use."""
        with (
            flask_app.test_request_context("/?name=my-endpoint", method="GET"),
            patch("mlflow_oidc_auth.utils.permissions.can_use_gateway_endpoint", return_value=True) as mock_use,
        ):
            result = validate_gateway_proxy("alice")

        assert result is True
        mock_use.assert_called_once_with("my-endpoint", "alice")

    def test_get_with_named_endpoint_denied(self, flask_app: Flask) -> None:
        """GET denied when user cannot use the named endpoint."""
        with (
            flask_app.test_request_context("/?name=secret-ep", method="GET"),
            patch("mlflow_oidc_auth.utils.permissions.can_use_gateway_endpoint", return_value=False) as mock_use,
        ):
            result = validate_gateway_proxy("bob")

        assert result is False
        mock_use.assert_called_once_with("secret-ep", "bob")

    def test_post_with_named_endpoint_checks_update(self, flask_app: Flask) -> None:
        """POST with an explicit gateway name should check can_update."""
        with (
            flask_app.test_request_context("/?name=my-endpoint", method="POST"),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=True) as mock_upd,
        ):
            result = validate_gateway_proxy("alice")

        assert result is True
        mock_upd.assert_called_once_with("my-endpoint", "alice")

    def test_post_with_named_endpoint_denied(self, flask_app: Flask) -> None:
        """POST denied when user cannot update the named endpoint."""
        with (
            flask_app.test_request_context("/?name=locked-ep", method="POST"),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=False) as mock_upd,
        ):
            result = validate_gateway_proxy("bob")

        assert result is False
        mock_upd.assert_called_once_with("locked-ep", "bob")

    def test_get_fallback_any_gateway_with_use(self, flask_app: Flask) -> None:
        """GET without explicit name falls back to listing all endpoint permissions."""
        perm = MagicMock()
        perm.permission = "EDIT"

        with (
            flask_app.test_request_context("/", method="GET"),
            patch("mlflow_oidc_auth.store.store") as mock_store,
        ):
            mock_store.list_gateway_endpoint_permissions.return_value = [perm]
            result = validate_gateway_proxy("alice")

        assert result is True
        mock_store.list_gateway_endpoint_permissions.assert_called_once_with("alice")

    def test_get_fallback_no_permissions(self, flask_app: Flask) -> None:
        """GET without explicit name returns False when user has no endpoint permissions."""
        with (
            flask_app.test_request_context("/", method="GET"),
            patch("mlflow_oidc_auth.store.store") as mock_store,
        ):
            mock_store.list_gateway_endpoint_permissions.return_value = []
            result = validate_gateway_proxy("nobody")

        assert result is False

    def test_post_fallback_any_gateway_with_update(self, flask_app: Flask) -> None:
        """POST without explicit name checks update capability on all endpoint permissions."""
        perm = MagicMock()
        perm.permission = "MANAGE"

        with (
            flask_app.test_request_context("/", method="POST"),
            patch("mlflow_oidc_auth.store.store") as mock_store,
        ):
            mock_store.list_gateway_endpoint_permissions.return_value = [perm]
            result = validate_gateway_proxy("alice")

        assert result is True

    def test_post_fallback_read_only_denied(self, flask_app: Flask) -> None:
        """POST fallback denied when user only has READ permission."""
        perm = MagicMock()
        perm.permission = "READ"

        with (
            flask_app.test_request_context("/", method="POST"),
            patch("mlflow_oidc_auth.store.store") as mock_store,
        ):
            mock_store.list_gateway_endpoint_permissions.return_value = [perm]
            result = validate_gateway_proxy("alice")

        assert result is False

    def test_extracts_gateway_name_from_query_param_gateway(self, flask_app: Flask) -> None:
        """Should extract gateway name from 'gateway' query param."""
        with (
            flask_app.test_request_context("/?gateway=gw-1", method="GET"),
            patch("mlflow_oidc_auth.utils.permissions.can_use_gateway_endpoint", return_value=True) as mock_use,
        ):
            validate_gateway_proxy("alice")

        mock_use.assert_called_once_with("gw-1", "alice")

    def test_extracts_gateway_name_from_query_param_target(self, flask_app: Flask) -> None:
        """Should extract gateway name from 'target' query param."""
        with (
            flask_app.test_request_context("/?target=tgt-1", method="GET"),
            patch("mlflow_oidc_auth.utils.permissions.can_use_gateway_endpoint", return_value=True) as mock_use,
        ):
            validate_gateway_proxy("alice")

        mock_use.assert_called_once_with("tgt-1", "alice")

    def test_extracts_gateway_name_from_json_body(self, flask_app: Flask) -> None:
        """Should extract gateway name from JSON body when not in query params."""
        with (
            flask_app.test_request_context(
                "/",
                method="POST",
                json={"name": "json-ep"},
                content_type="application/json",
            ),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=True) as mock_upd,
        ):
            validate_gateway_proxy("alice")

        mock_upd.assert_called_once_with("json-ep", "alice")

    def test_delete_checks_update(self, flask_app: Flask) -> None:
        """DELETE should check can_update (same as POST/PUT)."""
        with (
            flask_app.test_request_context("/?name=ep-del", method="DELETE"),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=True) as mock_upd,
        ):
            result = validate_gateway_proxy("alice")

        assert result is True
        mock_upd.assert_called_once_with("ep-del", "alice")

    def test_put_checks_update(self, flask_app: Flask) -> None:
        """PUT should check can_update."""
        with (
            flask_app.test_request_context("/?name=ep-put", method="PUT"),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=True) as mock_upd,
        ):
            result = validate_gateway_proxy("alice")

        assert result is True
        mock_upd.assert_called_once_with("ep-put", "alice")


# ---------------------------------------------------------------------------
# validate_can_read_metric_history_bulk
# ---------------------------------------------------------------------------

class TestValidateCanReadMetricHistoryBulk:
    """Tests for bulk metric history READ validation."""

    def test_allows_when_user_has_read(self, flask_app: Flask) -> None:
        """Should return True when user has READ on all referenced experiments."""
        mock_run = MagicMock()
        mock_run.info.experiment_id = "exp-1"

        with (
            flask_app.test_request_context("/?run_id=r1&run_id=r2", method="GET"),
            patch("mlflow_oidc_auth.validators.stuff._get_tracking_store") as mock_ts,
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_ts.return_value.get_run.return_value = mock_run
            mock_perm.return_value = SimpleNamespace(permission=get_permission("READ"))

            result = validate_can_read_metric_history_bulk("alice")

        assert result is True

    def test_denied_when_user_lacks_read(self, flask_app: Flask) -> None:
        """Should return False when user lacks READ on any experiment."""
        mock_run = MagicMock()
        mock_run.info.experiment_id = "exp-1"

        with (
            flask_app.test_request_context("/?run_id=r1", method="GET"),
            patch("mlflow_oidc_auth.validators.stuff._get_tracking_store") as mock_ts,
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_ts.return_value.get_run.return_value = mock_run
            mock_perm.return_value = SimpleNamespace(permission=get_permission("NO_PERMISSIONS"))

            result = validate_can_read_metric_history_bulk("bob")

        assert result is False

    def test_raises_when_no_run_ids(self, flask_app: Flask) -> None:
        """Should raise MlflowException when no run_ids provided."""
        from mlflow.exceptions import MlflowException

        with (
            flask_app.test_request_context("/", method="GET"),
            pytest.raises(MlflowException, match="must specify at least one run_id"),
        ):
            validate_can_read_metric_history_bulk("alice")

    def test_accepts_explicit_run_ids(self, flask_app: Flask) -> None:
        """Should accept explicit run_ids parameter (for unit tests)."""
        mock_run = MagicMock()
        mock_run.info.experiment_id = "exp-5"

        with (
            flask_app.test_request_context("/", method="GET"),
            patch("mlflow_oidc_auth.validators.stuff._get_tracking_store") as mock_ts,
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_ts.return_value.get_run.return_value = mock_run
            mock_perm.return_value = SimpleNamespace(permission=get_permission("READ"))

            result = validate_can_read_metric_history_bulk("alice", run_ids=["run-x"])

        assert result is True


# ---------------------------------------------------------------------------
# validate_can_search_datasets
# ---------------------------------------------------------------------------

class TestValidateCanSearchDatasets:
    """Tests for dataset search validation."""

    def test_allows_with_read_on_all_experiments(self, flask_app: Flask) -> None:
        """Should return True when user can read all requested experiments."""
        with (
            flask_app.test_request_context(
                "/",
                method="POST",
                json={"experiment_ids": ["e1", "e2"]},
                content_type="application/json",
            ),
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_perm.return_value = SimpleNamespace(permission=get_permission("READ"))
            result = validate_can_search_datasets("alice")

        assert result is True

    def test_denied_when_user_lacks_read(self, flask_app: Flask) -> None:
        """Should return False when user lacks READ on any experiment."""
        with (
            flask_app.test_request_context(
                "/",
                method="POST",
                json={"experiment_ids": ["e1"]},
                content_type="application/json",
            ),
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_perm.return_value = SimpleNamespace(permission=get_permission("NO_PERMISSIONS"))
            result = validate_can_search_datasets("bob")

        assert result is False

    def test_raises_when_no_experiment_ids(self, flask_app: Flask) -> None:
        """Should raise MlflowException when no experiment_ids provided."""
        from mlflow.exceptions import MlflowException

        with (
            flask_app.test_request_context(
                "/",
                method="POST",
                json={},
                content_type="application/json",
            ),
            pytest.raises(MlflowException, match="must specify at least one experiment_id"),
        ):
            validate_can_search_datasets("alice")

    def test_reads_experiment_ids_from_query_params(self, flask_app: Flask) -> None:
        """Should read experiment_ids from query params for GET requests."""
        with (
            flask_app.test_request_context("/?experiment_ids=e1", method="GET"),
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_perm.return_value = SimpleNamespace(permission=get_permission("READ"))
            result = validate_can_search_datasets("alice")

        assert result is True


# ---------------------------------------------------------------------------
# validate_can_create_promptlab_run
# ---------------------------------------------------------------------------

class TestValidateCanCreatePromptlabRun:
    """Tests for promptlab run creation validation."""

    def test_allows_with_update_permission(self, flask_app: Flask) -> None:
        """Should return True when user can UPDATE the experiment."""
        with (
            flask_app.test_request_context("/", method="POST", data={"experiment_id": "exp-1"}),
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_perm.return_value = SimpleNamespace(permission=get_permission("EDIT"))
            result = validate_can_create_promptlab_run("alice")

        assert result is True

    def test_denied_with_read_only(self, flask_app: Flask) -> None:
        """Should return False when user only has READ on the experiment."""
        with (
            flask_app.test_request_context("/", method="POST", data={"experiment_id": "exp-1"}),
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission") as mock_perm,
        ):
            mock_perm.return_value = SimpleNamespace(permission=get_permission("READ"))
            result = validate_can_create_promptlab_run("bob")

        assert result is False

    def test_raises_when_no_experiment_id(self, flask_app: Flask) -> None:
        """Should raise MlflowException when experiment_id is missing."""
        from mlflow.exceptions import MlflowException

        with (
            flask_app.test_request_context("/", method="POST"),
            pytest.raises(MlflowException, match="experiment_id"),
        ):
            validate_can_create_promptlab_run("alice")
