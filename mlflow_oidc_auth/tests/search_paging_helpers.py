"""Drive the search filters in ``hooks/after_request.py`` against an in-memory MLflow store (issue #456).

The fake store pages exactly like MLflow's SQL stores do for experiments, registered models and
model versions: an offset page token, ``max_results`` rows per batch, and a ``PagedList`` whose
``token`` is None on the last page. :func:`run_filtered_page` plays one request — MLflow's
handler produces the unfiltered first page, then the plugin's after-request filter rewrites it.
"""

import json
from contextlib import ExitStack
from typing import Callable, List, Optional, Tuple
from unittest.mock import patch

from flask import Flask, Response
from mlflow.entities import Experiment
from mlflow.entities.model_registry import ModelVersion, RegisteredModel
from mlflow.protos.model_registry_pb2 import SearchModelVersions, SearchRegisteredModels
from mlflow.protos.service_pb2 import SearchExperiments
from mlflow.store.entities.paged_list import PagedList
from mlflow.utils.proto_json_utils import message_to_json
from mlflow.utils.search_utils import SearchUtils

_AR = "mlflow_oidc_auth.hooks.after_request"

_app = Flask(__name__)


class FakeSearchStore:
    """An MLflow store stand-in holding ``rows`` in search order, counting search calls."""

    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.calls = 0

    def _page(self, max_results: int, page_token: Optional[str]) -> PagedList:
        self.calls += 1
        offset = SearchUtils.parse_start_offset_from_page_token(page_token)
        end = offset + max_results
        token = SearchUtils.create_page_token(end) if end < len(self.rows) else None
        return PagedList(self.rows[offset:end], token)

    def search_experiments(self, view_type=None, max_results=None, order_by=None, filter_string=None, page_token=None):
        return self._page(max_results, page_token)

    def search_registered_models(self, filter_string=None, max_results=None, order_by=None, page_token=None):
        return self._page(max_results, page_token)

    def search_model_versions(self, filter_string=None, max_results=None, order_by=None, page_token=None):
        return self._page(max_results, page_token)


def make_experiments(n: int) -> List[Experiment]:
    return [Experiment(experiment_id=str(i), name=f"exp-{i}", artifact_location="", lifecycle_stage="active") for i in range(n)]


def make_registered_models(n: int) -> List[RegisteredModel]:
    return [RegisteredModel(name=f"model-{i}") for i in range(n)]


def make_model_versions(n: int) -> List[ModelVersion]:
    return [ModelVersion(name=f"model-{i}", version="1", creation_timestamp=0) for i in range(n)]


# kind -> (request class, response field, store search method, row id, filter under test, readable-check patched)
_KINDS = {
    "experiments": (
        SearchExperiments,
        "experiments",
        "search_experiments",
        lambda r: r.experiment_id,
        "_filter_search_experiments",
        "_can_read_experiment",
    ),
    "registered_models": (
        SearchRegisteredModels,
        "registered_models",
        "search_registered_models",
        lambda r: r.name,
        "_filter_search_registered_models",
        "_can_read_registered_model",
    ),
    "model_versions": (
        SearchModelVersions,
        "model_versions",
        "search_model_versions",
        lambda r: r.name,
        "_filter_search_model_versions",
        "_can_read_registered_model",
    ),
}


def row_id(kind: str, row) -> str:
    return _KINDS[kind][3](row)


def run_filtered_page(
    kind: str,
    store: FakeSearchStore,
    readable: Callable[[str], bool],
    max_results: int,
    page_token: Optional[str],
    can_access_workspace: Optional[Callable[[str, Optional[str]], bool]] = None,
) -> Tuple[List[str], str]:
    """Serve one search request through MLflow's (fake) store and the plugin's filter.

    ``can_access_workspace`` turns workspaces on and stands in for the workspace check;
    without it workspaces are off.

    Returns:
        The ids on the filtered page, and its ``next_page_token`` (``""`` at the end).
    """
    import mlflow_oidc_auth.hooks.after_request as ar

    request_cls, field, method, ident, filter_name, can_read_name = _KINDS[kind]

    # MLflow's handler: one unfiltered page.
    first = getattr(store, method)(max_results=max_results, page_token=page_token)
    response = request_cls.Response()
    getattr(response, field).extend([row.to_proto() for row in first])
    if first.token:
        response.next_page_token = first.token
    resp = Response(message_to_json(response), mimetype="application/json")

    request_message = request_cls(max_results=max_results)
    if page_token:
        request_message.page_token = page_token

    with ExitStack() as stack:
        stack.enter_context(_app.test_request_context())
        stack.enter_context(patch(f"{_AR}.get_fastapi_admin_status", return_value=False))
        stack.enter_context(patch(f"{_AR}.get_fastapi_username", return_value="reader@example.com"))
        stack.enter_context(patch(f"{_AR}._get_request_message", return_value=request_message))
        stack.enter_context(patch(f"{_AR}._get_tracking_store", return_value=store))
        stack.enter_context(patch(f"{_AR}._get_model_registry_store", return_value=store))
        stack.enter_context(patch(f"{_AR}.{can_read_name}", side_effect=lambda _ctx, rid, *_kind: readable(rid)))
        stack.enter_context(patch.object(ar.config, "MLFLOW_ENABLE_WORKSPACES", can_access_workspace is not None))
        if can_access_workspace is not None:
            stack.enter_context(patch(f"{_AR}._can_access_workspace", side_effect=can_access_workspace))
        getattr(ar, filter_name)(resp)

    body = json.loads(resp.get_data(as_text=True))
    rows = body.get(field, [])
    key = "experiment_id" if kind == "experiments" else "name"
    return [r[key] for r in rows], body.get("next_page_token", "")
