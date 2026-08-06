from __future__ import annotations

import re
from typing import Sequence

from flask import request
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.utils import effective_experiment_permission, get_request_param


def validate_can_read_metric_history_bulk(username: str, run_ids: Sequence[str] | None = None) -> bool:
    """Validate READ permission for the legacy bulk metric-history endpoint.

    The endpoint accepts one or more run ids (query param repeated as `run_id`).
    Run permissions inherit from their parent experiment, so this checks
    READ permission on each run's experiment.

    Args:
        username: Authenticated username.
        run_ids: Optional explicit run ids (primarily for unit tests). When not provided,
            extracts `run_id` query params from the Flask request.

    Returns:
        True if the user has READ permission for all referenced runs.
    """

    if run_ids is None:
        run_ids = request.args.to_dict(flat=False).get("run_id", [])

    if not run_ids:
        raise MlflowException(
            "GetMetricHistoryBulk request must specify at least one run_id.",
            INVALID_PARAMETER_VALUE,
        )

    tracking_store = _get_tracking_store()
    for run_id in run_ids:
        run = tracking_store.get_run(run_id)
        experiment_id = run.info.experiment_id
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_search_datasets(username: str) -> bool:
    """Validate READ permission for dataset search.

    This endpoint expects `experiment_ids` (POST json or query params).

    Args:
        username: Authenticated username.

    Returns:
        True if the user has READ permission for all requested experiments.
    """

    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        experiment_ids = data.get("experiment_ids", []) or []
    else:
        experiment_ids = request.args.getlist("experiment_ids")

    if not experiment_ids:
        raise MlflowException(
            "SearchDatasets request must specify at least one experiment_id.",
            INVALID_PARAMETER_VALUE,
        )

    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_create_promptlab_run(username: str) -> bool:
    """Validate UPDATE permission for promptlab run creation.

    The request must include `experiment_id`.

    Args:
        username: Authenticated username.

    Returns:
        True if the user can UPDATE the target experiment.
    """

    try:
        experiment_id = get_request_param("experiment_id")
    except MlflowException as e:
        # Normalize the error message to keep this validator stable.
        raise MlflowException(
            "CreatePromptlabRun request must specify experiment_id.",
            INVALID_PARAMETER_VALUE,
        ) from e

    return effective_experiment_permission(experiment_id, username).permission.can_update


def validate_can_create_gateway(username: str) -> bool:
    """Validate gateway create requests.

    Gateway creation is allowed for any authenticated (non-admin) user. This
    mirrors the UX for other resource creation endpoints where creators are
    granted MANAGE post-creation in an after-request handler.
    """

    # We intentionally allow authenticated users to create gateways. The
    # after-request hook will grant MANAGE permissions to the creator.
    return True


def validate_gateway_proxy(username: str) -> bool:
    """Validate gateway proxy requests.

    This attempts to extract a gateway identifier from the request and
    enforce READ for GET requests and UPDATE for POST (create/update).

    When no explicit gateway name can be extracted, it falls back to
    checking whether the user has the required capability on any gateway.
    """

    from mlflow_oidc_auth.store import store
    from mlflow_oidc_auth.permissions import get_permission
    from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint, can_update_gateway_endpoint

    def _extract_gateway_name():
        """The endpoint MLflow will actually proxy to, or None.

        Mirrors ``gateway_proxy_handler`` exactly (issue #288). MLflow reads::

            args = request.args if request.method == "GET" else request.json
            gateway_path = args.get("gateway_path")

        so ``gateway_path`` is the ONLY field it consults, and the query string is
        ignored on a POST. The previous scan searched gateway_name/gateway/name/target
        before gateway_path, across query args *then* body, and diverged from that in
        two independent ways: a POST carrying ``?name=<own>`` authorized the caller's
        own endpoint while MLflow proxied to the body's ``gateway_path``; and a body
        carrying both ``gateway_name`` and ``gateway_path`` authorized the former while
        MLflow used the latter. Either one is a cross-tenant invocation of another
        tenant's model endpoint.

        MLflow then enforces the shape via ``_validate_gateway_path``: a POST path must
        be ``gateway/{name}/invocations``, and a GET path must be exactly
        ``api/2.0/endpoints`` (a list, which names no endpoint). So the endpoint name is
        the middle segment on POST and absent by construction on GET.
        """
        if request.method == "GET":
            args = request.args
        else:
            # A truthy non-dict body (a JSON array, string or number) would make .get
            # raise AttributeError, and catch_mlflow_exception only catches
            # MlflowException — so the hook would 500 instead of denying.
            body = request.get_json(silent=True)
            args = body if isinstance(body, dict) else {}
        gateway_path = args.get("gateway_path")
        if not gateway_path:
            return None
        match = re.fullmatch(r"gateway/([^/]+)/invocations", str(gateway_path).strip("/"))
        return match.group(1) if match else None

    gateway_name = _extract_gateway_name()

    # Map HTTP method to required capability
    if request.method == "GET":
        # USE. A GET is the endpoint listing: _validate_gateway_path requires the path to
        # be exactly "api/2.0/endpoints", so it names no single endpoint and the
        # any-endpoint check below is the gate. Note the proxied listing itself is NOT
        # filtered per-tenant — gateway-proxy is a plain Flask route, so it has no
        # AFTER_REQUEST_HANDLERS entry (that map is built from proto endpoints only).
        # That exposure is pre-existing and tracked separately.
        if gateway_name:
            return can_use_gateway_endpoint(str(gateway_name), username)
        # Fallback: check if user has any gateway endpoint with use
        perms = store.list_gateway_endpoint_permissions(username)
        return any(get_permission(p.permission).can_use for p in perms)
    else:
        # POST -> UPDATE required
        if gateway_name:
            return can_update_gateway_endpoint(str(gateway_name), username)
        # No resolvable endpoint on a mutating proxy call. Previously this fell through
        # to "does the user hold UPDATE on ANY endpoint", which let a caller with one
        # endpoint of their own invoke a path naming somebody else's. MLflow rejects a
        # missing or malformed gateway_path with 400 anyway, so refuse instead.
        #
        # This branch is reachable ONLY for gateway-proxy itself. Every other route that
        # used to share this validator now has its own — see validate_can_invoke_scorer.
        return False


def validate_can_invoke_scorer(username: str) -> bool:
    """Authorize POST /mlflow/scorer/invoke on the experiment MLflow will act on.

    This route was previously gated by ``validate_gateway_proxy``, which is wrong on its
    face: MLflow's ``_invoke_scorer_handler`` reads ``experiment_id``,
    ``serialized_scorer``, ``trace_ids`` and ``log_assessments`` from the JSON body and
    never touches a gateway endpoint at all. Sharing the gateway validator meant the
    check was "does the caller hold UPDATE on some unrelated gateway endpoint" — and
    when that validator was tightened for #288 it began denying the route outright,
    because a scorer body has no ``gateway_path`` to resolve.

    The permission required mirrors what MLflow will actually do: the handler writes
    assessments into the experiment only when ``log_assessments`` is set, so that flag
    selects UPDATE versus READ. The flag is caller-controlled, which is fine — it
    controls MLflow's behaviour identically, so the two stay in step, which is the whole
    point of this PR.
    """
    body = request.get_json(silent=True)
    args = body if isinstance(body, dict) else {}
    experiment_id = args.get("experiment_id")
    if not experiment_id:
        # MLflow raises INVALID_PARAMETER_VALUE for a missing experiment_id, and an
        # unresolvable resource must never mean allow.
        return False
    permission = effective_experiment_permission(str(experiment_id), username).permission
    if args.get("log_assessments", False):
        return permission.can_update
    return permission.can_read
