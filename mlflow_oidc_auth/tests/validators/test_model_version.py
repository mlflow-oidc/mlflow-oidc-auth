"""Unit tests for validate_can_create_model_version and its source-location helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from mlflow_oidc_auth.permissions import EDIT, NO_PERMISSIONS, READ
from mlflow_oidc_auth.validators import model_version

app = Flask(__name__)

RUN_ROOT = "s3://bucket/2/r1/artifacts"
MODEL_ROOT = "s3://bucket/2/models/m-1/artifacts"


def _create_version(
    body,
    *,
    can_update=True,
    run_perm=READ,
    model_perm=READ,
    source_model_perm=READ,
    experiment_perm=READ,
    lineage_model_id=None,
):
    registry = MagicMock()
    registry.get_model_version.return_value = SimpleNamespace(model_id=lineage_model_id)
    with (
        app.test_request_context("/api/2.0/mlflow/model-versions/create", method="POST", json=body),
        patch.object(model_version, "validate_can_update_registered_model", return_value=can_update),
        patch.object(model_version, "referenced_run_permission", return_value=run_perm) as run_check,
        patch.object(model_version, "referenced_logged_model_permission", return_value=model_perm) as model_check,
        patch.object(model_version, "referenced_experiment_permission", return_value=experiment_perm) as experiment_check,
        patch.object(model_version, "referenced_run", return_value=SimpleNamespace(info=SimpleNamespace(artifact_uri=RUN_ROOT))),
        patch.object(model_version, "referenced_logged_model", return_value=SimpleNamespace(artifact_location=MODEL_ROOT)),
        patch.object(model_version, "_get_model_registry_store", return_value=registry),
        patch.object(model_version, "effective_registered_model_permission", return_value=MagicMock(permission=source_model_perm)),
    ):
        result = model_version.validate_can_create_model_version("alice")
        return result, run_check, model_check, experiment_check


def test_requires_update_on_destination():
    result, run_check, _, _ = _create_version({"name": "m", "source": RUN_ROOT, "run_id": "r1"}, can_update=False)
    assert result is False
    run_check.assert_not_called()


def test_checks_run_and_model_ids():
    result, run_check, model_check, _ = _create_version({"name": "m", "source": RUN_ROOT + "/model", "run_id": "r1", "model_id": "m-1"})
    assert result is True
    run_check.assert_called_once_with("r1", "alice")
    model_check.assert_called_once_with("m-1", "alice")


def test_denied_without_read_on_run():
    assert _create_version({"name": "m", "source": RUN_ROOT, "run_id": "r1"}, run_perm=NO_PERMISSIONS)[0] is False


def test_denied_without_read_on_logged_model():
    assert _create_version({"name": "m", "source": MODEL_ROOT, "model_id": "m-1"}, model_perm=NO_PERMISSIONS)[0] is False


@pytest.mark.parametrize("field", ["run_id", "model_id", "runId", "modelId"])
def test_denies_present_but_empty_id(field):
    assert _create_version({"name": "m", "source": "runs:/r1/model", field: ""})[0] is False


def test_null_ids_are_absent():
    result, run_check, model_check, _ = _create_version({"name": "m", "source": "runs:/r1/model", "run_id": None, "model_id": None})
    assert result is True
    run_check.assert_called_once_with("r1", "alice")
    model_check.assert_not_called()


def test_checks_logged_model_named_by_models_uri():
    result, _, model_check, _ = _create_version({"name": "m", "source": "models:/m-9"})
    assert result is True
    model_check.assert_called_once_with("m-9", "alice")


def test_copy_needs_read_on_source_registered_model():
    assert _create_version({"name": "m", "source": "models:/other/1"}, source_model_perm=NO_PERMISSIONS)[0] is False


def test_copy_with_lineage_model_id_skips_run_check_and_needs_read_on_the_model():
    body = {"name": "m", "source": "models:/other/1", "run_id": "r1", "model_id": "m-1"}
    result, run_check, model_check, _ = _create_version(body, lineage_model_id="m-1")
    assert result is True
    run_check.assert_not_called()
    model_check.assert_called_once_with("m-1", "alice")


def test_copy_with_unreadable_lineage_model_id_is_denied():
    body = {"name": "m", "source": "models:/other/1", "model_id": "m-1"}
    assert _create_version(body, lineage_model_id="m-1", model_perm=NO_PERMISSIONS)[0] is False


@pytest.mark.parametrize("perm, expected", [(READ, False), (EDIT, True)])
def test_copy_with_other_model_id_needs_update(perm, expected):
    body = {"name": "m", "source": "models:/other/1", "model_id": "m-2"}
    result, _, model_check, _ = _create_version(body, lineage_model_id="m-1", model_perm=perm)
    assert result is expected
    model_check.assert_called_once_with("m-2", "alice")


@pytest.mark.parametrize("source", ["runs:/", "models:/", "runs:abc/model", RUN_ROOT + "/../x", RUN_ROOT + "/%252e%252e/x", "s3://b/p\x00"])
def test_denies_unparseable_or_relative_source(source):
    assert _create_version({"name": "m", "source": source, "run_id": "r1"})[0] is False


@pytest.mark.parametrize(
    "source, experiment_id",
    [
        ("mlflow-artifacts:/7/r1/artifacts/model", "7"),
        ("mlflow-artifacts://host:5000/7/r1/artifacts", "7"),
        ("mlflow-artifacts:/workspaces/ws/7/r1/artifacts", "7"),
        ("http://h/api/2.0/mlflow-artifacts/artifacts/7/r1/artifacts", "7"),
        ("mlflow-artifacts:/", None),
        ("mlflow-artifacts:/models/x", None),
    ],
)
def test_proxied_source_checks_the_experiment_it_names(source, experiment_id):
    result, _, _, experiment_check = _create_version({"name": "m", "source": source}, experiment_perm=NO_PERMISSIONS)
    assert result is False
    experiment_check.assert_called_once_with(experiment_id, "alice")
    result, _, _, _ = _create_version({"name": "m", "source": source}, experiment_perm=READ)
    assert result is True


def test_storage_source_without_ids_is_denied():
    assert _create_version({"name": "m", "source": RUN_ROOT})[0] is False


@pytest.mark.parametrize(
    "source, fields, expected",
    [
        (RUN_ROOT + "/model", {"run_id": "r1"}, True),
        ("s3://bucket/2/r1/artifactsX", {"run_id": "r1"}, False),
        ("s3://other/2/r1/artifacts", {"run_id": "r1"}, False),
        (MODEL_ROOT + "/x", {"model_id": "m-1"}, True),
        (MODEL_ROOT, {"run_id": "r1"}, False),
    ],
)
def test_storage_source_must_be_under_a_referenced_artifact_root(source, fields, expected):
    assert _create_version({"name": "m", "source": source, **fields})[0] is expected


def test_prompt_placeholder_source_needs_nothing_more():
    tags = [{"key": "mlflow.prompt.is_prompt", "value": "true"}]
    assert _create_version({"name": "p", "source": "dummy-source", "tags": tags})[0] is True
    assert _create_version({"name": "m", "source": "dummy-source"})[0] is False


@pytest.mark.parametrize(
    "source, root, expected",
    [
        ("s3://b/1/r/artifacts", "s3://b/1/r/artifacts", True),
        ("s3://b/1/r/artifacts/", "s3://b/1/r/artifacts", True),
        ("s3://b/1/r/artifacts/model", "s3://b/1/r/artifacts/", True),
        ("s3://b/1/r/artifacts2", "s3://b/1/r/artifacts", False),
        ("S3://b/1/r/artifacts/m", "s3://b/1/r/artifacts", True),
        ("s3://c/1/r/artifacts/m", "s3://b/1/r/artifacts", False),
        ("gs://b/1/r/artifacts/m", "s3://b/1/r/artifacts", False),
        ("/srv/mlruns/1/r/artifacts/model", "file:///srv/mlruns/1/r/artifacts", True),
        ("file:///srv/mlruns/1/r/artifacts//model", "/srv/mlruns/1/r/artifacts", True),
        ("/srv/mlruns/1/r2/artifacts", "file:///srv/mlruns/1/r/artifacts", False),
        ("relative/model", "relative", False),
        ("", "s3://b/1", False),
    ],
)
def test_is_under_location(source, root, expected):
    assert model_version.is_under_location(source, root) is expected
