import gzip
import zlib

from flask import Response, jsonify, request

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.responses.client_error import make_forbidden_response
from mlflow_oidc_auth.utils.permissions import effective_experiment_permission
from mlflow_oidc_auth.utils.request_helpers import get_username

logger = get_logger()


def _decompress_otlp_body(raw_body: bytes, content_encoding: str | None) -> bytes:
    """
    Decompress an OTLP/HTTP protobuf request body according to Content-Encoding.

    Supported encodings:
    - gzip
    - deflate (RFC-compliant and raw deflate)
    """
    enc = (content_encoding or "").strip().lower()
    if not enc:
        return raw_body

    if enc == "gzip":
        return gzip.decompress(raw_body)
    if enc == "deflate":
        try:
            return zlib.decompress(raw_body)
        except Exception:
            # Try raw DEFLATE stream (some clients send this)
            return zlib.decompress(raw_body, -zlib.MAX_WBITS)

    raise ValueError(f"Unsupported Content-Encoding: {enc}")


def ingest_otlp_traces() -> Response:
    """
    OTLP traces ingest endpoint for MLflow Tracing.

    This endpoint is required by MLflow's TracingClient.log_spans(), which posts OTLP protobuf payloads
    to /v1/traces with an x-mlflow-experiment-id header.

    Auth is handled by the global before_request hook (basic/bearer/session). This handler also enforces
    per-experiment permissions based on the authenticated user.
    """
    try:
        # Import lazily so environments without full tracing deps still start up (endpoint will 500 if hit).
        from mlflow.entities.span import Span
        from mlflow.server.handlers import _get_tracking_store
        from mlflow.store.tracking.rest_store import ExportTraceServiceRequest, MLFLOW_EXPERIMENT_ID_HEADER
    except Exception as e:
        logger.error(f"Failed to import MLflow tracing components: {e}")
        return Response("Tracing ingest is not available on this server.", status=501, mimetype="text/plain")

    experiment_id = request.headers.get(MLFLOW_EXPERIMENT_ID_HEADER) or request.headers.get("x-mlflow-experiment-id")
    if not experiment_id:
        return Response(
            "Missing required header: x-mlflow-experiment-id",
            status=400,
            mimetype="text/plain",
        )

    # Permission check: require at least update permission on the experiment.
    try:
        username = get_username()
        perm = effective_experiment_permission(str(experiment_id), username).permission
        if not (perm.can_update or perm.can_manage):
            return make_forbidden_response({"message": "Permission denied for trace ingestion"})
    except Exception as e:
        logger.warning(f"Permission check failed for OTLP ingest: {e}")
        return make_forbidden_response({"message": "Permission denied for trace ingestion"})

    raw_body = request.get_data(cache=False) or b""
    try:
        body = _decompress_otlp_body(raw_body, request.headers.get("Content-Encoding"))
    except Exception as e:
        return Response(f"Invalid OTLP payload encoding: {e}", status=400, mimetype="text/plain")

    otlp_req = ExportTraceServiceRequest()
    try:
        otlp_req.ParseFromString(body)
    except Exception as e:
        return Response(f"Invalid OTLP protobuf payload: {e}", status=400, mimetype="text/plain")

    mlflow_spans = []
    try:
        for resource_spans in otlp_req.resource_spans:
            for scope_spans in resource_spans.scope_spans:
                for otel_span in scope_spans.spans:
                    # location_id is used for V4 trace IDs; for OSS it is the experiment_id.
                    mlflow_spans.append(Span.from_otel_proto(otel_span, location_id=str(experiment_id)))
    except Exception as e:
        logger.warning(f"Failed to translate OTLP spans to MLflow spans: {e}")
        return Response("Failed to parse OTLP spans.", status=400, mimetype="text/plain")

    # Persist spans in MLflow tracking store.
    try:
        store = _get_tracking_store()
        try:
            store.log_spans(location=str(experiment_id), spans=mlflow_spans, tracking_uri=None)
        except TypeError:
            # Older/alternative store implementations may not accept tracking_uri kwarg.
            store.log_spans(location=str(experiment_id), spans=mlflow_spans)
    except Exception as e:
        logger.error(f"Failed to persist OTLP spans: {e}")
        return Response("Failed to log spans.", status=500, mimetype="text/plain")

    # OTLP ExportTraceServiceResponse is an empty message; clients only require 200.
    return Response(b"", status=200, content_type="application/x-protobuf")


