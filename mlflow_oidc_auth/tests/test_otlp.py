from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from mlflow_oidc_auth.views.otlp import ingest_otlp_traces


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test_secret_key"
    return app


def test_ingest_otlp_traces_requires_experiment_header(app):
    with app.test_request_context(path="/v1/traces", method="POST", data=b""):
        resp = ingest_otlp_traces()
        assert resp.status_code == 400


@patch("mlflow_oidc_auth.views.otlp._get_tracking_store")
@patch("mlflow_oidc_auth.views.otlp.Span")
@patch("mlflow_oidc_auth.views.otlp.ExportTraceServiceRequest")
@patch("mlflow_oidc_auth.views.otlp.get_username", return_value="user@example.com")
@patch("mlflow_oidc_auth.views.otlp.effective_experiment_permission")
def test_ingest_otlp_traces_logs_spans(
    mock_effective_perm,
    _mock_get_username,
    mock_export_req_cls,
    mock_span_cls,
    mock_get_store,
    app,
):
    # Permission allows update
    mock_effective_perm.return_value = MagicMock(permission=MagicMock(can_update=True, can_manage=False))

    # Fake OTLP request containing one span
    fake_span = MagicMock()
    fake_scope_spans = MagicMock(spans=[fake_span])
    fake_resource_spans = MagicMock(scope_spans=[fake_scope_spans])

    mock_export_req = MagicMock()
    mock_export_req.resource_spans = [fake_resource_spans]
    mock_export_req_cls.return_value = mock_export_req

    # Span.from_otel_proto returns a "mlflow span" object
    mlflow_span_obj = MagicMock()
    mock_span_cls.from_otel_proto.return_value = mlflow_span_obj

    # Tracking store mock
    store = MagicMock()
    mock_get_store.return_value = store

    with app.test_request_context(
        path="/v1/traces",
        method="POST",
        headers={"x-mlflow-experiment-id": "23"},
        data=b"ignored",
    ):
        resp = ingest_otlp_traces()

    assert resp.status_code == 200
    mock_span_cls.from_otel_proto.assert_called_once_with(fake_span, location_id="23")
    store.log_spans.assert_called_once()


