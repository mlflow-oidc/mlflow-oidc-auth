"""Requests that reference a second resource need a grant on it too, as in MLflow's auth plugin.

Driven through the real hook, MLflow's real routing table and a real permission store (see
``authz_harness``). Runs and logged models named ``*-victim`` live in the VICTIM experiment,
``*-own`` in OUTSIDER's OWN experiment; ``*-gone`` do not exist.
"""

from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    EDITOR,
    OUTSIDER,
    OWN,
    PREFIXES,
    READER,
    VICTIM,
    BaseFakeTrackingStore,
    allowed,
    denied,
    hook,
    install_permission_store,
)

OWN_MODEL = "own-model"
VICTIM_MODEL = "victim-model"


def _experiment_for(resource_id: str) -> str:
    if resource_id.endswith("-victim"):
        return VICTIM
    if resource_id.endswith("-own"):
        return OWN
    raise MlflowException(f"'{resource_id}' not found", RESOURCE_DOES_NOT_EXIST)


def _gateway_name(resource_id: str) -> str:
    """``sec-victim`` -> ``victim-sec``; ids ending in ``-gone`` do not exist."""
    kind, _, owner = resource_id.partition("-")
    if owner not in ("victim", "own"):
        raise MlflowException(f"'{resource_id}' not found", RESOURCE_DOES_NOT_EXIST)
    return f"{owner}-{kind}"


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_run(self, run_id):
        return SimpleNamespace(info=SimpleNamespace(run_id=run_id, experiment_id=_experiment_for(run_id)))

    def get_logged_model(self, model_id):
        return SimpleNamespace(model_id=model_id, experiment_id=_experiment_for(model_id))

    def get_secret_info(self, secret_id=None, **_):
        return SimpleNamespace(secret_id=secret_id, secret_name=_gateway_name(secret_id))

    def get_gateway_model_definition(self, model_definition_id=None, **_):
        return SimpleNamespace(model_definition_id=model_definition_id, name=_gateway_name(model_definition_id))

    def get_gateway_endpoint(self, endpoint_id=None, **_):
        return SimpleNamespace(endpoint_id=endpoint_id, name=_gateway_name(endpoint_id))


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    s.create_registered_model_permission(OWN_MODEL, OUTSIDER, "EDIT")
    s.create_registered_model_permission(VICTIM_MODEL, OUTSIDER, "NO_PERMISSIONS")
    s.create_registered_model_permission(OWN_MODEL, READER, "EDIT")
    # Gateway: OUTSIDER holds nothing on the victim's resources and MANAGE (the default) on
    # its own; READER holds READ (below USE) and EDITOR holds USE on the victim's secret and
    # model definition, but nothing on the victim's endpoint.
    for kind in ("sec", "md"):
        create = s.create_gateway_secret_permission if kind == "sec" else s.create_gateway_model_definition_permission
        create(f"victim-{kind}", OUTSIDER, "NO_PERMISSIONS")
        create(f"victim-{kind}", READER, "READ")
        create(f"victim-{kind}", EDITOR, "USE")
    s.create_gateway_endpoint_permission("victim-ep", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    yield s
    flush_permission_cache()


# ---------------------------------------------------------------------------
# CreateModelVersion: READ on the source run / logged model / registered model
# ---------------------------------------------------------------------------

CREATE_MODEL_VERSION = "{}/2.0/mlflow/model-versions/create"


def _create_version(username, prefix="/api", query=None, **fields):
    body = {"name": OWN_MODEL, "source": "s3://bucket/path/model", **fields}
    return hook(CREATE_MODEL_VERSION.format(prefix), "POST", username, body=body, query=query)


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "fields",
    [
        {"run_id": "run-own"},
        {"model_id": "m-own"},
        {"runId": "run-own", "modelId": "m-own"},
        {"source": "runs:/run-own/model"},
        {"source": "models:/m-own"},
        {"source": f"models:/{OWN_MODEL}/1", "run_id": "run-victim"},
        {"source": f"models:/{OWN_MODEL}/1", "run_id": "run-victim", "model_id": "m-own"},
        {"run_id": None, "model_id": None},
        {},
    ],
)
def test_create_model_version_from_readable_source_is_allowed(prefix, fields):
    assert allowed(_create_version(OUTSIDER, prefix, **fields))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "fields",
    [
        {"run_id": "run-victim"},
        {"runId": "run-victim"},
        {"model_id": "m-victim"},
        {"modelId": "m-victim"},
        {"run_id": "run-own", "model_id": "m-victim"},
        {"source": "runs:/run-victim/model"},
        {"source": "models:/m-victim"},
        {"source": f"models:/{VICTIM_MODEL}/1"},
        {"source": f"models:/{VICTIM_MODEL}@champion", "run_id": "run-own"},
        {"source": f"models:/{OWN_MODEL}/1", "model_id": "m-victim"},
    ],
)
def test_create_model_version_from_unreadable_source_is_denied(prefix, fields):
    assert denied(_create_version(OUTSIDER, prefix, **fields))


@pytest.mark.parametrize(
    "fields",
    [
        {"run_id": "run-gone"},
        {"model_id": "m-gone"},
        {"run_id": ""},
        {"model_id": ""},
        {"source": "runs:/"},
        {"source": "models:/"},
    ],
)
def test_create_model_version_with_unresolvable_source_is_denied(fields):
    assert denied(_create_version(OUTSIDER, **fields))


def test_create_model_version_lineage_exemption_needs_every_source_to_be_a_registered_model():
    """A ``models:/<name>`` source elsewhere in the request does not waive the run check."""
    resp = _create_version(OUTSIDER, query={"source": f"models:/{OWN_MODEL}/1"}, run_id="run-victim")
    assert denied(resp)


def test_create_model_version_read_on_the_source_is_enough():
    assert allowed(_create_version(READER, run_id="run-victim"))
    assert allowed(_create_version(READER, model_id="m-victim"))


def test_create_model_version_still_needs_update_on_the_destination():
    assert denied(hook(CREATE_MODEL_VERSION.format("/api"), "POST", OUTSIDER, body={"name": VICTIM_MODEL, "source": "s3://b/p", "run_id": "run-own"}))


def test_create_model_version_admin_is_not_checked():
    assert allowed(_create_version(ADMIN, run_id="run-victim"))


# ---------------------------------------------------------------------------
# LogMetric / LogBatch: UPDATE on the logged model the metric is written to
# ---------------------------------------------------------------------------

LOG_METRIC = "{}/2.0/mlflow/runs/log-metric"
LOG_BATCH = "{}/2.0/mlflow/runs/log-batch"


def _metric(**fields):
    return {"key": "loss", "value": 0.1, "timestamp": 1, "step": 0, **fields}


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("fields", [{}, {"model_id": "m-own"}, {"modelId": "m-own"}])
def test_log_metric_to_updatable_logged_model_is_allowed(prefix, fields):
    body = {"run_id": "run-own", **_metric(**fields)}
    assert allowed(hook(LOG_METRIC.format(prefix), "POST", OUTSIDER, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("fields", [{"model_id": "m-victim"}, {"modelId": "m-victim"}, {"model_id": "m-gone"}])
def test_log_metric_to_other_logged_model_is_denied(prefix, fields):
    body = {"run_id": "run-own", **_metric(**fields)}
    assert denied(hook(LOG_METRIC.format(prefix), "POST", OUTSIDER, body=body))


def test_log_metric_logged_model_in_query_string_is_also_checked():
    body = {"run_id": "run-own", **_metric()}
    assert denied(hook(LOG_METRIC.format("/api"), "POST", OUTSIDER, body=body, query={"model_id": "m-victim"}))


def test_log_metric_read_on_logged_model_is_not_enough():
    """READER can read the victim experiment but not write to it."""
    body = {"run_id": "run-victim", **_metric(model_id="m-victim")}
    assert denied(hook(LOG_METRIC.format("/api"), "POST", READER, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "metrics",
    [
        [_metric()],
        [_metric(model_id="m-own")],
        [_metric(), _metric(modelId="m-own")],
    ],
)
def test_log_batch_to_updatable_logged_models_is_allowed(prefix, metrics):
    assert allowed(hook(LOG_BATCH.format(prefix), "POST", OUTSIDER, body={"run_id": "run-own", "metrics": metrics}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "metrics",
    [
        [_metric(model_id="m-victim")],
        [_metric(model_id="m-own"), _metric(model_id="m-victim")],
        [_metric(modelId="m-victim")],
        [_metric(model_id="m-gone")],
    ],
)
def test_log_batch_to_other_logged_model_is_denied(prefix, metrics):
    assert denied(hook(LOG_BATCH.format(prefix), "POST", OUTSIDER, body={"run_id": "run-own", "metrics": metrics}))


def test_log_batch_still_needs_update_on_the_run():
    assert denied(hook(LOG_BATCH.format("/api"), "POST", OUTSIDER, body={"run_id": "run-victim", "metrics": [_metric()]}))


def test_log_batch_admin_is_not_checked():
    body = {"run_id": "run-victim", "metrics": [_metric(model_id="m-victim")]}
    assert allowed(hook(LOG_BATCH.format("/api"), "POST", ADMIN, body=body))


# ---------------------------------------------------------------------------
# CreatePresignedUploadUrl: UPDATE on the run or on the logged model
# ---------------------------------------------------------------------------

PRESIGNED_UPLOAD = "{}/2.0/mlflow/artifacts/presigned-upload-url"


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("ids", [{"run_id": "run-own"}, {"model_id": "m-own"}, {"modelId": "m-own"}])
def test_presigned_upload_to_updatable_target_is_allowed(prefix, ids):
    assert allowed(hook(PRESIGNED_UPLOAD.format(prefix), "POST", OUTSIDER, body={"path": "model.pkl", **ids}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "ids",
    [
        {"model_id": "m-victim"},
        {"modelId": "m-victim"},
        {"model_id": "m-gone"},
        {"run_id": "run-gone"},
        {"run_id": "run-own", "model_id": "m-victim"},
        {"run_id": "run-victim", "model_id": "m-own"},
        {},
    ],
)
def test_presigned_upload_to_other_or_missing_target_is_denied(prefix, ids):
    assert denied(hook(PRESIGNED_UPLOAD.format(prefix), "POST", OUTSIDER, body={"path": "model.pkl", **ids}))


def test_presigned_upload_logged_model_needs_update_not_read():
    assert denied(hook(PRESIGNED_UPLOAD.format("/api"), "POST", READER, body={"path": "x", "model_id": "m-victim"}))


def test_presigned_upload_logged_model_in_query_string_is_also_checked():
    resp = hook(PRESIGNED_UPLOAD.format("/api"), "POST", OUTSIDER, body={"path": "x", "run_id": "run-own"}, query={"model_id": "m-victim"})
    assert denied(resp)


def test_presigned_upload_admin_is_not_checked():
    assert allowed(hook(PRESIGNED_UPLOAD.format("/api"), "POST", ADMIN, body={"path": "x", "model_id": "m-victim"}))


# ---------------------------------------------------------------------------
# Gateway: USE on the secret / model definitions a resource is built from
# ---------------------------------------------------------------------------

GW = "{}/3.0/mlflow/gateway/"
CREATE_MODEL_DEF = GW + "model-definitions/create"
UPDATE_MODEL_DEF = GW + "model-definitions/update"
CREATE_ENDPOINT = GW + "endpoints/create"
UPDATE_ENDPOINT = GW + "endpoints/update"
ATTACH_MODEL = GW + "endpoints/models/attach"


def _model_def_body(**fields):
    return {"name": "new-md", "provider": "openai", "model_name": "gpt-4o", **fields}


def _configs(*ids, key="model_definition_id"):
    return [{key: i, "linkage_type": "PRIMARY", "weight": 1.0} for i in ids]


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_model_definition_needs_use_on_the_secret(prefix):
    path = CREATE_MODEL_DEF.format(prefix)
    assert allowed(hook(path, "POST", OUTSIDER, body=_model_def_body(secret_id="sec-own")))
    assert allowed(hook(path, "POST", EDITOR, body=_model_def_body(secret_id="sec-victim"))), "USE is enough"
    assert denied(hook(path, "POST", READER, body=_model_def_body(secret_id="sec-victim"))), "READ is not enough"
    assert denied(hook(path, "POST", OUTSIDER, body=_model_def_body(secret_id="sec-victim")))
    assert denied(hook(path, "POST", OUTSIDER, body=_model_def_body(secretId="sec-victim")))
    assert denied(hook(path, "POST", OUTSIDER, body=_model_def_body(secret_id="sec-gone")))
    assert denied(hook(path, "POST", OUTSIDER, body=_model_def_body(secret_id="sec-own"), query={"secret_id": "sec-victim"}))
    assert allowed(hook(path, "POST", ADMIN, body=_model_def_body(secret_id="sec-victim")))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_update_model_definition_needs_use_on_a_new_secret(prefix):
    path = UPDATE_MODEL_DEF.format(prefix)
    own = {"model_definition_id": "md-own"}
    assert allowed(hook(path, "POST", OUTSIDER, body=own))
    assert allowed(hook(path, "POST", OUTSIDER, body={**own, "secret_id": "sec-own"}))
    assert denied(hook(path, "POST", OUTSIDER, body={**own, "secret_id": "sec-victim"}))
    assert denied(hook(path, "POST", OUTSIDER, body={**own, "secret_id": "sec-gone"}))
    # The target check is unchanged.
    assert denied(hook(path, "POST", OUTSIDER, body={"model_definition_id": "md-victim", "secret_id": "sec-own"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_endpoint_needs_use_on_every_model_definition(prefix):
    path = CREATE_ENDPOINT.format(prefix)
    assert allowed(hook(path, "POST", OUTSIDER, body={"name": "new-ep", "model_configs": _configs("md-own")}))
    assert allowed(hook(path, "POST", EDITOR, body={"name": "new-ep", "model_configs": _configs("md-victim")}))
    assert denied(hook(path, "POST", READER, body={"name": "new-ep", "model_configs": _configs("md-victim")}))
    assert denied(hook(path, "POST", OUTSIDER, body={"name": "new-ep", "model_configs": _configs("md-own", "md-victim")}))
    assert denied(hook(path, "POST", OUTSIDER, body={"name": "new-ep", "modelConfigs": _configs("md-victim", key="modelDefinitionId")}))
    assert denied(hook(path, "POST", OUTSIDER, body={"name": "new-ep", "model_configs": _configs("md-gone")}))
    assert allowed(hook(path, "POST", ADMIN, body={"name": "new-ep", "model_configs": _configs("md-victim")}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_update_endpoint_needs_use_on_every_model_definition(prefix):
    path = UPDATE_ENDPOINT.format(prefix)
    assert allowed(hook(path, "POST", OUTSIDER, body={"endpoint_id": "ep-own"}))
    assert allowed(hook(path, "POST", OUTSIDER, body={"endpoint_id": "ep-own", "model_configs": _configs("md-own")}))
    assert denied(hook(path, "POST", OUTSIDER, body={"endpoint_id": "ep-own", "model_configs": _configs("md-victim")}))
    assert denied(hook(path, "POST", OUTSIDER, body={"endpoint_id": "ep-own", "model_configs": _configs("md-gone")}))
    assert denied(hook(path, "POST", OUTSIDER, body={"endpoint_id": "ep-victim", "model_configs": _configs("md-own")}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_attach_model_needs_use_on_the_model_definition(prefix):
    path = ATTACH_MODEL.format(prefix)

    def body(endpoint_id, md_id, key="model_config"):
        return {"endpoint_id": endpoint_id, key: _configs(md_id)[0]}

    assert allowed(hook(path, "POST", OUTSIDER, body=body("ep-own", "md-own")))
    assert denied(hook(path, "POST", OUTSIDER, body=body("ep-own", "md-victim")))
    assert denied(hook(path, "POST", OUTSIDER, body=body("ep-own", "md-victim", key="modelConfig")))
    assert denied(hook(path, "POST", OUTSIDER, body=body("ep-own", "md-gone")))
    assert denied(hook(path, "POST", OUTSIDER, body=body("ep-victim", "md-own")))
    assert allowed(hook(path, "POST", ADMIN, body=body("ep-victim", "md-victim")))
