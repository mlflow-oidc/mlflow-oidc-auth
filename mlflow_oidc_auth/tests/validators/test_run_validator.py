from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
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


def _two_run_fixtures():
    from mlflow.exceptions import MlflowException
    from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

    experiments = {"OWN-RUN": "own-exp", "VICTIM-RUN": "victim-exp"}

    def run_for(run_id):
        if run_id not in experiments:
            raise MlflowException(f"Run '{run_id}' not found", RESOURCE_DOES_NOT_EXIST)
        run = MagicMock()
        run.info.experiment_id = experiments[run_id]
        return run

    def perm_for(experiment_id, username):
        return SimpleNamespace(permission=get_permission("EDIT" if experiment_id == "own-exp" else "READ"))

    return run_for, perm_for


@pytest.mark.parametrize(
    "query",
    [
        "run_uuid=OWN-RUN&run_id=VICTIM-RUN",
        "run_id=VICTIM-RUN&run_uuid=OWN-RUN",
        "run_id=OWN-RUN&run_uuid=VICTIM-RUN",
        "run_uuid=OWN-RUN&run_id=OWN-RUN&run_id=VICTIM-RUN",
        "run_id=VICTIM-RUN",
        "run_id=&run_uuid=VICTIM-RUN",
    ],
)
def test_validate_can_update_run_artifact_checks_run_id_next_to_run_uuid(query) -> None:
    """MLflow 3.18's handler writes into ``run_id or run_uuid``: an editable run under
    one name must not authorize another run under the other, in either order."""

    app = Flask(__name__)
    run_for, perm_for = _two_run_fixtures()
    with (
        app.test_request_context(f"/?{query}&path=f.txt", method="POST", data=b"artifact bytes"),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission", side_effect=perm_for),
    ):
        mock_tracking_store.return_value.get_run.side_effect = run_for
        assert validate_can_update_run_artifact("bob") is False
        # The deny came from checking the run MLflow could write into, not from anything else.
        assert "VICTIM-RUN" in {c.args[0] for c in mock_tracking_store.return_value.get_run.call_args_list}


@pytest.mark.parametrize("query", ["run_id=MISSING&run_uuid=OWN-RUN", "run_uuid=OWN-RUN&run_id=%20", "run_uuid=MISSING"])
def test_validate_can_update_run_artifact_denies_an_unknown_run(query) -> None:
    """A run that cannot be resolved (not found, or whitespace, which MLflow would look up as
    given) is refused like one the caller cannot update."""
    app = Flask(__name__)
    run_for, perm_for = _two_run_fixtures()
    with (
        app.test_request_context(f"/?{query}&path=f.txt", method="POST", data=b"x"),
        patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
        patch("mlflow_oidc_auth.validators.run.effective_experiment_permission", side_effect=perm_for),
    ):
        mock_tracking_store.return_value.get_run.side_effect = run_for
        assert validate_can_update_run_artifact("bob") is False


def test_upload_artifact_handler_reads_only_these_query_names() -> None:
    """Pins what the installed MLflow's handler reads, so an upgrade that reads another run
    parameter, another request source or the query string another way fails here instead of
    silently writing into a run the validator never checked.

    Walks the handler's syntax tree: every use of ``request`` must be one of the attributes it
    reads today, every use of the query string must be ``args.get("<literal>")`` with a known
    name, and the run it writes into must come from ``run_id`` / ``run_uuid`` only.
    """
    import ast
    import inspect
    import textwrap

    from mlflow.server import handlers

    tree = ast.parse(textwrap.dedent(inspect.getsource(inspect.unwrap(handlers.upload_artifact_handler))))
    function = tree.body[0]
    parents = {child: node for node in ast.walk(function) for child in ast.iter_child_nodes(node)}

    def is_query(node) -> bool:
        return (isinstance(node, ast.Name) and node.id == "args") or (
            isinstance(node, ast.Attribute) and node.attr == "args" and isinstance(node.value, ast.Name) and node.value.id == "request"
        )

    def query_name(call) -> str | None:
        """The literal name of an ``args.get("<name>")`` call, else None."""
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "get"
            and is_query(call.func.value)
            and len(call.args) == 1
            and not call.keywords
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        ):
            return call.args[0].value
        return None

    request_attributes = {
        node.attr for node in ast.walk(function) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "request"
    }
    assert request_attributes <= {"args", "content_length", "data"}, request_attributes

    names = set()
    for node in ast.walk(function):
        if not is_query(node) or (isinstance(node, ast.Attribute) and isinstance(parents.get(node), ast.Assign)):
            continue  # ``args = request.args`` itself
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            continue
        call = parents.get(parents.get(node))
        name = query_name(call)
        assert name is not None, f"the handler reads the query string some other way: {ast.unparse(parents.get(node))}"
        names.add(name)
    assert names <= {"run_id", "run_uuid", "path"}, names

    get_run = [n for n in ast.walk(function) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get_run"]
    assert len(get_run) == 1 and isinstance(get_run[0].args[0], ast.Name)
    run_variable = get_run[0].args[0].id
    assignments = [n for n in ast.walk(function) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == run_variable for t in n.targets)]
    assert len(assignments) == 1
    sources = {query_name(n) for n in ast.walk(assignments[0].value) if isinstance(n, ast.Call)}
    assert sources and sources <= {"run_id", "run_uuid"}, sources


def test_validate_can_update_run_artifact_accepts_run_id_alone() -> None:
    """MLflow 3.18 clients may name the run as ``run_id`` only; the owner's upload passes."""

    app = Flask(__name__)
    run_for, perm_for = _two_run_fixtures()
    for query in ("run_id=OWN-RUN", "run_id=OWN-RUN&run_uuid=OWN-RUN", "run_id=&run_uuid=OWN-RUN"):
        with (
            app.test_request_context(f"/?{query}&path=f.txt", method="POST", data=b"artifact bytes"),
            patch("mlflow_oidc_auth.validators.run._get_tracking_store") as mock_tracking_store,
            patch("mlflow_oidc_auth.validators.run.effective_experiment_permission", side_effect=perm_for),
        ):
            mock_tracking_store.return_value.get_run.side_effect = run_for
            assert validate_can_update_run_artifact("bob") is True, query
            assert {c.args[0] for c in mock_tracking_store.return_value.get_run.call_args_list} == {"OWN-RUN"}


def test_validate_can_update_run_artifact_denies_when_every_run_name_is_empty() -> None:
    app = Flask(__name__)
    with app.test_request_context("/?run_id=&run_uuid=&path=f.txt", method="POST", data=b"x"):
        assert validate_can_update_run_artifact("bob") is False
