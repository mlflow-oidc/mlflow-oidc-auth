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
    validate_can_invoke_scorer,
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
    """Tests for the gateway proxy request validator.

    These assert MLflow's ACTUAL contract (issue #288). ``gateway_proxy_handler`` reads

        args = request.args if request.method == "GET" else request.json
        gateway_path = args.get("gateway_path")

    so ``gateway_path`` is the only field that decides where the request is proxied,
    and the query string is ignored on a POST. ``_validate_gateway_path`` then requires
    ``gateway/{name}/invocations`` for POST and exactly ``api/2.0/endpoints`` for GET.
    The previous tests here asserted extraction from ``name``/``gateway``/``target``
    query params, none of which MLflow ever reads — they codified the bypass rather
    than a requirement.
    """

    def test_post_resolves_the_endpoint_from_gateway_path(self, flask_app: Flask) -> None:
        """POST authorizes the endpoint named inside gateway_path."""
        with (
            flask_app.test_request_context("/", method="POST", json={"gateway_path": "gateway/my-endpoint/invocations"}),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=True) as mock_upd,
        ):
            assert validate_gateway_proxy("alice") is True
        mock_upd.assert_called_once_with("my-endpoint", "alice")

    def test_post_denied_when_user_cannot_update_that_endpoint(self, flask_app: Flask) -> None:
        with (
            flask_app.test_request_context("/", method="POST", json={"gateway_path": "gateway/locked-ep/invocations"}),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=False) as mock_upd,
        ):
            assert validate_gateway_proxy("bob") is False
        mock_upd.assert_called_once_with("locked-ep", "bob")

    def test_post_ignores_the_query_string(self, flask_app: Flask) -> None:
        """THE #288 BYPASS: MLflow ignores the query string entirely on a POST.

        Authorizing a name from there let a caller point the query at an endpoint they
        own while MLflow proxied to the victim named in the body.
        """
        with (
            flask_app.test_request_context(
                "/?name=my-own&gateway=my-own&target=my-own&gateway_path=gateway/my-own/invocations",
                method="POST",
                json={"gateway_path": "gateway/VICTIM/invocations"},
            ),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=True) as mock_upd,
        ):
            validate_gateway_proxy("alice")
        mock_upd.assert_called_once_with("VICTIM", "alice")

    def test_post_ignores_other_body_keys_in_favour_of_gateway_path(self, flask_app: Flask) -> None:
        """Second #288 vector: right source, wrong field. MLflow reads gateway_path only."""
        with (
            flask_app.test_request_context("/", method="POST", json={"gateway_name": "my-own", "name": "my-own", "gateway_path": "gateway/VICTIM/invocations"}),
            patch("mlflow_oidc_auth.utils.permissions.can_update_gateway_endpoint", return_value=True) as mock_upd,
        ):
            validate_gateway_proxy("alice")
        mock_upd.assert_called_once_with("VICTIM", "alice")

    @pytest.mark.parametrize("body", [{}, {"gateway_path": ""}, {"gateway_path": "not/a/valid/path"}, {"gateway_path": "gateway//invocations"}])
    def test_post_denies_when_no_endpoint_can_be_resolved(self, flask_app: Flask, body) -> None:
        """Unresolvable must mean deny, never "any endpoint the caller happens to own".

        The old any-endpoint fallback let a caller holding UPDATE on one endpoint of
        their own proxy a request naming somebody else's. MLflow rejects a missing or
        malformed gateway_path with 400 regardless.
        """
        # The user MUST hold UPDATE on an endpoint of their own here, otherwise the
        # assertion passes whether or not the fallback exists — the fallback would find
        # nothing to grant on. This is exactly the state that made the old code unsafe.
        perm = MagicMock()
        perm.permission = "MANAGE"
        with (
            flask_app.test_request_context("/", method="POST", json=body),
            patch("mlflow_oidc_auth.store.store") as mock_store,
        ):
            mock_store.list_gateway_endpoint_permissions.return_value = [perm]
            assert validate_gateway_proxy("alice") is False

    def test_get_names_no_endpoint_and_falls_back_to_any_use(self, flask_app: Flask) -> None:
        """A GET is the endpoint listing; _validate_gateway_path forbids naming one."""
        perm = MagicMock()
        perm.permission = "EDIT"
        with (
            flask_app.test_request_context("/?gateway_path=api/2.0/endpoints", method="GET"),
            patch("mlflow_oidc_auth.store.store") as mock_store,
        ):
            mock_store.list_gateway_endpoint_permissions.return_value = [perm]
            assert validate_gateway_proxy("alice") is True
        mock_store.list_gateway_endpoint_permissions.assert_called_once_with("alice")

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


# ---------------------------------------------------------------------------
# validate_can_invoke_scorer (issue #288)
# ---------------------------------------------------------------------------


class TestValidateCanInvokeScorer:
    """POST /mlflow/scorer/invoke is authorized on the experiment, not a gateway endpoint.

    This route used to share validate_gateway_proxy, which never matched what MLflow's
    _invoke_scorer_handler reads (experiment_id / serialized_scorer / trace_ids from the
    JSON body — no gateway endpoint anywhere). When that validator was tightened for
    #288 the mismatch became a hard 403 on every scorer invocation.
    """

    BODY = {"experiment_id": "exp-1", "serialized_scorer": "{}", "trace_ids": ["t1"]}

    def _perm(self, name):
        return patch(
            "mlflow_oidc_auth.validators.stuff.effective_experiment_permission",
            return_value=SimpleNamespace(permission=get_permission(name)),
        )

    def test_read_permission_is_enough_without_log_assessments(self, flask_app: Flask) -> None:
        """THE REGRESSION: this shape returned False for every non-admin."""
        with flask_app.test_request_context("/", method="POST", json=self.BODY), self._perm("READ"):
            assert validate_can_invoke_scorer("bob") is True

    def test_logging_assessments_requires_update(self, flask_app: Flask) -> None:
        """The handler writes into the experiment only when log_assessments is set."""
        body = dict(self.BODY, log_assessments=True)
        with flask_app.test_request_context("/", method="POST", json=body), self._perm("READ"):
            assert validate_can_invoke_scorer("bob") is False
        with flask_app.test_request_context("/", method="POST", json=body), self._perm("EDIT"):
            assert validate_can_invoke_scorer("bob") is True

    def test_denied_without_experiment_permission(self, flask_app: Flask) -> None:
        with flask_app.test_request_context("/", method="POST", json=self.BODY), self._perm("NO_PERMISSIONS"):
            assert validate_can_invoke_scorer("bob") is False

    def test_authorizes_the_body_experiment_not_the_query_string(self, flask_app: Flask) -> None:
        """MLflow reads request.json here, so the query string must not decide."""
        seen = {}

        def record(experiment_id, username):
            seen["experiment_id"] = experiment_id
            return SimpleNamespace(permission=get_permission("READ"))

        with (
            flask_app.test_request_context("/?experiment_id=MY-OWN", method="POST", json={"experiment_id": "VICTIM"}),
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission", side_effect=record),
        ):
            validate_can_invoke_scorer("bob")

        assert seen["experiment_id"] == "VICTIM"

    def test_denies_when_experiment_id_is_absent(self, flask_app: Flask) -> None:
        """Unresolvable must never mean allow; MLflow rejects this with 400 anyway."""
        with flask_app.test_request_context("/", method="POST", json={"trace_ids": ["t1"]}):
            assert validate_can_invoke_scorer("bob") is False


# ---------------------------------------------------------------------------
# Hostile body types (issue #288)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body", [[1, 2], "a string", 5, True])
@pytest.mark.parametrize("validator", [validate_gateway_proxy, validate_can_invoke_scorer])
def test_non_dict_json_body_denies_instead_of_raising(flask_app: Flask, validator, body) -> None:
    """A truthy non-dict body must not escape as an AttributeError.

    before_request_hook is wrapped in catch_mlflow_exception, which catches only
    MlflowException — so an AttributeError from `.get` on a list would surface as a 500
    rather than a denial.
    """
    with flask_app.test_request_context("/", method="POST", json=body):
        assert validator("alice") is False
