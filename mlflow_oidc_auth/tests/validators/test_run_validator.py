from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.validators.run import (
    validate_can_read_run_artifact,
    validate_can_update_run_artifact,
)


def test_validate_can_read_run_artifact_supports_run_uuid_alias() -> None:
    """Ensure run validator accepts `run_uuid` when `run_id` is absent.

    MLflow clients may send `run_uuid` instead of `run_id`. The project-wide
    `get_request_param("run_id")` helper already supports this alias; this test
    verifies the run permission validator follows that behavior.
    """

    app = Flask(__name__)

    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp-123"

    with (
        app.test_request_context("/?run_uuid=uuid123", method="GET"),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as mock_effective_exp_perm,
    ):
        mock_tracking_store.return_value.get_run.return_value = mock_run
        mock_effective_exp_perm.return_value = SimpleNamespace(permission=get_permission("READ"))

        assert validate_can_read_run_artifact("alice") is True

        mock_tracking_store.return_value.get_run.assert_called_once_with("uuid123")
        mock_effective_exp_perm.assert_called_once_with("exp-123", "alice")


def test_validate_can_update_run_artifact_reads_run_uuid_from_the_query_string() -> None:
    """The real shape of the only route bound to this validator.

    POST /mlflow/upload-artifact — MLflow's upload_artifact_handler reads
    ``request.args["run_uuid"]`` and nothing else.
    """

    app = Flask(__name__)

    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp-999"

    with (
        app.test_request_context("/?run_uuid=run-999&path=f.txt", method="POST"),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as mock_effective_exp_perm,
    ):
        mock_tracking_store.return_value.get_run.return_value = mock_run
        mock_effective_exp_perm.return_value = SimpleNamespace(permission=get_permission("EDIT"))

        assert validate_can_update_run_artifact("bob") is True

        mock_tracking_store.return_value.get_run.assert_called_once_with("run-999")
        mock_effective_exp_perm.assert_called_once_with("exp-999", "bob")


def test_validate_can_update_run_artifact_authorizes_the_query_run_first() -> None:
    """THE #288 BYPASS (inverted direction).

    The shared get_request_param helper reads the BODY on a POST, so the plugin
    authorized the run named in the body while MLflow wrote the artifact into the run
    named in the query string — a cross-tenant artifact write. The query-string run is
    the one MLflow writes into, so it is resolved first; the body's run is then checked
    too under the union rule.
    """

    app = Flask(__name__)

    mock_run = MagicMock()
    mock_run.info.experiment_id = "exp-of-victim"

    with (
        app.test_request_context("/?run_uuid=VICTIM-RUN&path=f.txt", method="POST", json={"run_id": "MY-OWN-RUN"}),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as mock_effective_exp_perm,
    ):
        mock_tracking_store.return_value.get_run.return_value = mock_run
        mock_effective_exp_perm.return_value = SimpleNamespace(permission=get_permission("EDIT"))

        validate_can_update_run_artifact("bob")

        # Only the run MLflow writes into: the body is the artifact, not a parameter.
        mock_tracking_store.return_value.get_run.assert_called_once_with("VICTIM-RUN")


def test_validate_can_update_run_artifact_denies_when_any_named_run_is_denied() -> None:
    """Union rule (#285/#288): a repeated run_uuid must not ride on the first one."""

    app = Flask(__name__)

    def run_for(run_id):
        run = MagicMock()
        run.info.experiment_id = {"OWN-RUN": "own-exp", "VICTIM-RUN": "victim-exp"}[run_id]
        return run

    def perm_for(experiment_id, username):
        return SimpleNamespace(permission=get_permission("EDIT" if experiment_id == "own-exp" else "READ"))

    for first, second in (("OWN-RUN", "VICTIM-RUN"), ("VICTIM-RUN", "OWN-RUN")):
        with (
            app.test_request_context(f"/?run_uuid={first}&run_uuid={second}&path=f.txt", method="POST", data=b"artifact bytes"),
            patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
            patch("mlflow_oidc_auth.validators.run.effective_experiment_permission", side_effect=perm_for),
        ):
            mock_tracking_store.return_value.get_run.side_effect = run_for
            assert validate_can_update_run_artifact("bob") is False

    # A JSON artifact whose CONTENT names another run is still the owner's upload.
    with (
        app.test_request_context("/?run_uuid=OWN-RUN&path=f.json", method="POST", json={"run_id": "VICTIM-RUN", "run_uuid": "VICTIM-RUN"}),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission", side_effect=perm_for),
    ):
        mock_tracking_store.return_value.get_run.side_effect = run_for
        assert validate_can_update_run_artifact("bob") is True


def test_validate_can_update_run_artifact_leaves_a_multipart_body_unread() -> None:
    """Parsing the body as form data would consume the stream the handler uploads from."""
    app = Flask(__name__)
    mock_run = MagicMock()
    mock_run.info.experiment_id = "own-exp"
    payload = b'--b\r\nContent-Disposition: form-data; name="run_id"\r\n\r\nx\r\n--b--\r\n'
    with (
        app.test_request_context("/?run_uuid=OWN-RUN&path=f.txt", method="POST", data=payload, content_type="multipart/form-data; boundary=b"),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission", return_value=SimpleNamespace(permission=get_permission("EDIT"))),
    ):
        mock_tracking_store.return_value.get_run.return_value = mock_run
        assert validate_can_update_run_artifact("bob") is True
        from flask import request as live_request

        assert live_request.get_data() == payload


def test_validate_can_update_run_artifact_denies_when_run_uuid_is_absent() -> None:
    """Unresolvable must mean deny; MLflow rejects such a request with 400 anyway."""

    app = Flask(__name__)

    with app.test_request_context("/", method="POST", json={"run_id": "MY-OWN-RUN"}):
        assert validate_can_update_run_artifact("bob") is False
