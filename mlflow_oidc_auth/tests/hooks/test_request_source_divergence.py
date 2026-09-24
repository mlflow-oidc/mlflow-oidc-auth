"""Tests for reading request parameters from the source MLflow reads (issues #285, #286).

Both bugs are the same shape: the plugin resolves a request one way while MLflow
resolves the same request another way, so the authorization decision is made about a
different thing than the one MLflow acts on.

#285 — ``_extract_param_from_all_sources`` preferred the query string, but MLflow's
``_get_request_message`` consults the query string ONLY for a GET with a non-empty
one; every other method is proto-parsed from the body and the query string is ignored
outright. ``POST /experiments/update?experiment_id=<own>`` with ``{"experiment_id":
"<victim>"}`` in the body therefore authorized ``<own>`` while MLflow renamed
``<victim>``.

#286 — ``_find_validator`` keyed its lookup on the literal ``request.method``, but
werkzeug auto-registers HEAD on every GET rule and dispatches it to the same view.
Every validator is registered under "GET", so HEAD matched nothing, and a missing
validator is not a deny — it falls through unvalidated, leaking an existence and
exact-size oracle over any tenant's data.
"""

import json

import pytest
from flask import Flask, request

from mlflow_oidc_auth.hooks.before_request import _find_validator
from mlflow_oidc_auth.hooks.dual_spelling_guard import proto_request_value
from mlflow_oidc_auth.utils.request_helpers import _extract_param_from_all_sources

app = Flask(__name__)
app.secret_key = "test_secret_key"

# Concrete gated proto routes used across the vector tests.
UPDATE_EXPERIMENT = "/api/2.0/mlflow/experiments/update"
DELETE_EXPERIMENT = "/api/2.0/mlflow/experiments/delete"
GET_EXPERIMENT = "/api/2.0/mlflow/experiments/get"
SET_EXPERIMENT_TAG = "/api/2.0/mlflow/experiments/set-experiment-tag"
RENAME_MODEL = "/api/2.0/mlflow/registered-models/rename"


def _ctx(path, method, body=None, query=None):
    kwargs = {"path": path, "method": method}
    if body is not None:
        kwargs["data"] = json.dumps(body)
        kwargs["content_type"] = "application/json"
    if query is not None:
        kwargs["query_string"] = query
    return app.test_request_context(**kwargs)


# ---------------------------------------------------------------------------
# #285 — the query string must never win over the body on a non-GET proto route
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/ajax-api"])
@pytest.mark.parametrize(
    "path, method, field",
    [
        (UPDATE_EXPERIMENT, "POST", "experiment_id"),
        (DELETE_EXPERIMENT, "POST", "experiment_id"),
        (SET_EXPERIMENT_TAG, "POST", "experiment_id"),
        (RENAME_MODEL, "POST", "name"),
    ],
)
def test_body_wins_over_query_string_on_non_get_proto_routes(path, method, field, prefix):
    """The body is what MLflow acts on, so the body is what must be authorized.

    Parameterized over BOTH prefixes: /ajax-api is what MLflow's own web UI calls and
    carries its own full set of proto routes and validator keys. Covering only /api
    let a mutation that classified just /api as proto keep the suite green while
    leaving #285 fully exploitable on the prefix the browser actually uses.
    """
    with _ctx(path.replace("/api", prefix, 1), method, body={field: "VICTIM"}, query={field: "OWN"}):
        assert _extract_param_from_all_sources(field) == "VICTIM"


def test_query_string_is_ignored_even_when_the_body_omits_the_field():
    """No cross-source fallback: a value MLflow cannot see must not authorize anything.

    Falling back to the query string would authorize a resource MLflow never touches,
    which is the same divergence in reverse — and on any route where an empty proto
    default means "all", authorizing an unrelated id would be actively dangerous.
    """
    with _ctx(UPDATE_EXPERIMENT, "POST", body={"new_name": "x"}, query={"experiment_id": "OWN"}):
        assert _extract_param_from_all_sources("experiment_id") is None


def test_unresolvable_param_denies_with_400_rather_than_falling_through():
    """Dropping the fallback must deny cleanly, which is what makes it safe.

    ``get_experiment_id`` raises INVALID_PARAMETER_VALUE, and ``before_request_hook``
    is wrapped in MLflow's ``catch_mlflow_exception``, which turns that into a 400
    response returned FROM the hook — so the view never runs. A request whose
    parameter MLflow cannot see is refused, not guessed at from a source MLflow
    ignores.
    """
    from mlflow.exceptions import MlflowException

    from mlflow_oidc_auth.utils.request_helpers import get_experiment_id

    with _ctx(UPDATE_EXPERIMENT, "POST", body={"new_name": "x"}, query={"experiment_id": "OWN"}):
        with pytest.raises(MlflowException) as exc:
            get_experiment_id()
    assert exc.value.get_http_status_code() == 400


def test_camel_case_only_body_is_honoured():
    """ParseDict accepts the json_name spelling, so authorization must read it too.

    Unambiguous here: find_dual_spelling_collision rejects a body carrying both
    spellings before any of this runs.
    """
    with _ctx(UPDATE_EXPERIMENT, "POST", body={"experimentId": "VICTIM"}, query={"experiment_id": "OWN"}):
        assert _extract_param_from_all_sources("experiment_id") == "VICTIM"


def test_get_with_query_string_still_reads_the_query_string():
    """The legitimate GET path is unchanged — MLflow does build the proto from args."""
    with _ctx(GET_EXPERIMENT, "GET", query={"experiment_id": "MINE"}):
        assert _extract_param_from_all_sources("experiment_id") == "MINE"


def test_body_only_post_is_unchanged():
    """The overwhelmingly common real-client shape must behave exactly as before."""
    with _ctx(UPDATE_EXPERIMENT, "POST", body={"experiment_id": "MINE"}):
        assert _extract_param_from_all_sources("experiment_id") == "MINE"


def test_view_args_win_when_the_body_agrees_or_is_silent():
    """Path params stay authoritative for the shapes a real client actually sends."""
    for body in ({"model_id": "PATH"}, {"status": 1}):
        with app.test_request_context("/api/2.0/mlflow/logged-models/PATH", method="PATCH", json=body):
            # Simulate werkzeug having bound the path converter.
            request.view_args = {"model_id": "PATH"}
            assert _extract_param_from_all_sources("model_id") == "PATH"


def test_path_param_disagreeing_with_the_body_is_rejected():
    """Picking a side here is unsafe in BOTH directions, so refuse to pick.

    Most MLflow handlers act on the bound path argument, but FinalizeLoggedModel
    (PATCH /logged-models/<model_id>) ignores it entirely and acts on
    ``request_message.model_id`` from the body. "Path wins" therefore authorizes the
    URL's model while MLflow finalizes the body's; "body wins" breaks the other way
    on every route that does use the path. No real client sends two different values
    for one field, so the ambiguity is refused with a 400.
    """
    from mlflow.exceptions import MlflowException

    with app.test_request_context("/api/2.0/mlflow/logged-models/OWN", method="PATCH", json={"model_id": "VICTIM", "status": 1}):
        request.view_args = {"model_id": "OWN"}
        with pytest.raises(MlflowException) as exc:
            _extract_param_from_all_sources("model_id")
    assert exc.value.get_http_status_code() == 400


def test_non_proto_routes_keep_the_legacy_scan():
    """Off the proto surface MLflow's sourcing is handler-specific and unknowable.

    Restricting the new precedence to proto routes is what makes it provable rather
    than a guess, so a non-proto path must still fall back to the old args-then-body
    scan.
    """
    with _ctx("/some/plugin/route", "POST", body={"experiment_id": "BODY"}, query={"experiment_id": "QUERY"}):
        assert _extract_param_from_all_sources("experiment_id") == "QUERY"


def test_proto_request_value_reports_route_membership():
    """The (is_proto, value) contract is what lets the caller know to fall back."""
    with _ctx(UPDATE_EXPERIMENT, "POST", body={"experiment_id": "X"}):
        assert proto_request_value(request, "experiment_id") == (True, "X")
    with _ctx("/some/plugin/route", "POST", body={"experiment_id": "X"}):
        assert proto_request_value(request, "experiment_id") == (False, None)


# ---------------------------------------------------------------------------
# #286 — HEAD must resolve the same validator as its GET twin
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        # exact-match branch
        GET_EXPERIMENT,
        "/api/2.0/mlflow/runs/get",
        "/api/2.0/mlflow/registered-models/get",
        "/ajax-api/2.0/mlflow/experiments/get",
        # parameterized branch
        "/api/2.0/mlflow/traces/tr-1/info",
        # workspace branch
        "/api/3.0/mlflow/workspaces/ws1",
        # logged-model branch
        "/api/2.0/mlflow/logged-models/m-1",
    ],
)
def test_head_resolves_the_same_validator_as_get(path):
    """A HEAD reaches the same view as its GET, so it must reach the same validator.

    _find_validator has FOUR lookup branches (workspace, logged-model, exact and
    parameterized) and the fold had to be applied to all of them. Covering only the
    exact-match branch let a partial revert of any of the other three pass the whole
    suite while leaving HEAD unvalidated on those routes.
    """
    with _ctx(path, "GET", query={"experiment_id": "1"}) as get_ctx:
        expected = _find_validator(get_ctx.request)
    assert expected is not None, f"precondition: {path} must have a GET validator"

    with _ctx(path, "HEAD", query={"experiment_id": "1"}) as head_ctx:
        assert _find_validator(head_ctx.request) is expected


def test_head_does_not_borrow_a_non_get_validator():
    """The fold maps HEAD onto GET only — it must not match a POST/DELETE validator."""
    with _ctx(UPDATE_EXPERIMENT, "HEAD") as ctx:
        # UpdateExperiment is POST-only, so there is no GET validator to fold onto.
        assert _find_validator(ctx.request) is None


def test_other_methods_are_unaffected_by_the_fold():
    """POST/DELETE lookups must resolve exactly as before the fold was introduced."""
    with _ctx(UPDATE_EXPERIMENT, "POST", body={"experiment_id": "1"}) as ctx:
        assert _find_validator(ctx.request) is not None


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_head_reaches_a_decision_rather_than_an_unsupported_method_error(method):
    """Closing the HEAD hole must make HEAD decide like GET, not deny everything.

    Folding HEAD in _find_validator alone routed HEAD into get_request_param, whose
    method whitelist had no HEAD branch — so it raised BAD_REQUEST and every HEAD on a
    gated route 400'd, including for the rightful owner, and including routes MLflow
    serves happily (/get-artifact is registered GET+HEAD and its handler reads
    request.args with no method check). Trading a leak for a blanket denial is not
    closing the hole.
    """
    from mlflow_oidc_auth.utils.request_helpers import get_request_param

    with app.test_request_context("/get-artifact?run_uuid=r1&path=secret.txt", method=method):
        assert get_request_param("path") == "secret.txt"
        assert get_request_param("run_uuid") == "r1"


def test_head_is_filtered_by_the_after_request_handlers():
    """The response half of #286: HEAD must not skip tenant filtering.

    werkzeug strips a HEAD body but PRESERVES Content-Length, so a HEAD that skipped
    the search/list filters was served the unfiltered global result set and leaked its
    exact size — precisely the existence/size oracle the issue is about.
    """
    from unittest.mock import patch

    from flask import Response

    from mlflow_oidc_auth.hooks import after_request as ar

    path = "/api/2.0/mlflow/experiments/search"
    called = []
    fake = {(path, "GET"): lambda resp: called.append(resp)}

    with patch.object(ar, "AFTER_REQUEST_HANDLERS", fake):
        for method in ("GET", "HEAD"):
            called.clear()
            with app.test_request_context(path, method=method):
                ar.after_request_hook(Response(status=200))
            assert called, f"{method} must reach the filtering handler"


# ---------------------------------------------------------------------------
# #285 end-to-end: the real validator against a real store
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A REAL SqlAlchemyStore, so the permission decision is not mocked away."""
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    # utils.permissions binds the singleton by name at import time
    # ("from ...store import store"), so patching the module attribute alone would
    # leave the resolver reading the real, empty store and pass vacuously.
    monkeypatch.setattr("mlflow_oidc_auth.store.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.utils.permissions.store", s, raising=False)
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    flush_permission_cache()
    yield s
    flush_permission_cache()


def test_attacker_cannot_authorize_with_a_query_string_while_mlflow_mutates_the_body(store):
    """The full validator path must decide about the experiment MLflow will rename.

    Alice holds MANAGE on her own experiment and only READ on the victim's. The
    grants are deliberately asymmetric rather than absent so the assertion cannot
    pass merely because DEFAULT_MLFLOW_PERMISSION happens to be restrictive — it
    fails if the decision is made about "1", whatever the default is.
    """
    from mlflow_oidc_auth.validators.experiment import validate_can_update_experiment

    store.create_user("alice@example.com", "pw", "Alice")
    store.create_experiment_permission("1", "alice@example.com", "MANAGE")
    store.create_experiment_permission("2", "alice@example.com", "READ")

    # Sanity: the two ids really do decide differently.
    with _ctx(UPDATE_EXPERIMENT, "POST", body={"experiment_id": "1"}):
        assert validate_can_update_experiment("alice@example.com") is True

    # The attack: own id in the query string, victim id in the body MLflow parses.
    with _ctx(UPDATE_EXPERIMENT, "POST", body={"experiment_id": "2", "new_name": "PWNED"}, query={"experiment_id": "1"}):
        assert validate_can_update_experiment("alice@example.com") is False


# ---------------------------------------------------------------------------
# Validator/handler pairing (issue #288)
# ---------------------------------------------------------------------------


def test_gateway_validator_guards_only_gateway_routes():
    """One validator must not guard routes whose handlers read different bodies.

    validate_gateway_proxy mirrors gateway_proxy_handler, which reads `gateway_path`.
    It was also bound to POST /mlflow/scorer/invoke, whose handler reads experiment_id /
    serialized_scorer / trace_ids and has no gateway_path at all — so tightening the
    gateway parsing for #288 denied every scorer invocation. Nothing caught it because
    the tests asserted binding identity in one file and validator behaviour in another,
    and no test drove a scorer body through the validator it was bound to.
    """
    from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_VALIDATORS
    from mlflow_oidc_auth.validators import validate_can_invoke_scorer, validate_gateway_proxy

    guarded = {path for (path, _method), v in BEFORE_REQUEST_VALIDATORS.items() if v is validate_gateway_proxy}
    assert guarded, "precondition: the gateway validator must still be bound to something"
    assert all("gateway" in path for path in guarded), f"gateway validator leaked onto non-gateway routes: {sorted(guarded)}"

    scorer = {(path, method) for (path, method), v in BEFORE_REQUEST_VALIDATORS.items() if v is validate_can_invoke_scorer}
    assert scorer, "scorer/invoke must be bound to its own validator"
    assert all(m == "POST" for _p, m in scorer), "MLflow registers scorer/invoke POST-only"


def test_head_on_a_proto_get_route_fails_closed():
    """Do NOT 'complete' the HEAD fold in _mlflow_reads_args — this pins why.

    MLflow's _get_request_message takes the query-string path only when the method is
    literally "GET", so a HEAD is proto-parsed from the BODY even with a query string.
    has_unexpected_get_body rejects a HEAD that carries a body, so the proto resolves to
    nothing and the request is refused. Folding HEAD into _mlflow_reads_args would make
    the plugin authorize the query string while MLflow parsed the body — reopening #285
    for HEAD. The 400 here is correct, not a gap.
    """
    from mlflow.exceptions import MlflowException

    from mlflow_oidc_auth.utils.request_helpers import get_experiment_id

    with _ctx(GET_EXPERIMENT, "GET", query={"experiment_id": "42"}):
        assert get_experiment_id() == "42"

    with _ctx(GET_EXPERIMENT, "HEAD", query={"experiment_id": "42"}):
        with pytest.raises(MlflowException) as exc:
            get_experiment_id()
    assert exc.value.get_http_status_code() == 400


# ---------------------------------------------------------------------------
# Union rule, every proto route (issues #285, #288)
#
# Mirroring MLflow's request source is a hand-maintained model of MLflow's parsing,
# and it has drifted before. So on top of it, every value a request carries for a
# resource field — in ANY source — must be authorized. This is the durable
# regression: it enumerates every proto route bound in BEFORE_REQUEST_VALIDATORS,
# puts one id in the query string (or the path) and a different id in the body, and
# drives the real before_request_hook against a real permission store. Denied on
# either id must mean denied, on GET and non-GET routes alike, whichever source MLflow
# happens to read. A newly bound validator must be classified below or this fails.
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

USER = "alice@example.com"
OWN, OWN2, VICTIM = "own", "own2", "victim"

# validator name -> (field, is_list, constant fields the request also needs)
_UNION_SPECS = {
    "validate_can_read_experiment": ("experiment_id", False, {}),
    "validate_can_update_experiment": ("experiment_id", False, {}),
    "validate_can_delete_experiment": ("experiment_id", False, {}),
    "validate_can_manage_experiment": ("experiment_id", False, {}),
    "validate_can_read_experiment_by_name": ("experiment_name", False, {}),
    "validate_can_read_experiments_from_experiment_ids": ("experiment_ids", True, {}),
    "validate_can_read_run": ("run_id", False, {}),
    "validate_can_update_run": ("run_id", False, {}),
    "validate_can_delete_run": ("run_id", False, {}),
    "validate_can_read_registered_model": ("name", False, {}),
    "validate_can_update_registered_model": ("name", False, {}),
    "validate_can_delete_registered_model": ("name", False, {}),
    "validate_can_manage_registered_model": ("name", False, {}),
    "validate_can_read_scorer": ("experiment_id", False, {"name": "scorer"}),
    "validate_can_update_scorer": ("experiment_id", False, {"name": "scorer"}),
    "validate_can_delete_scorer": ("experiment_id", False, {"name": "scorer"}),
    "validate_can_manage_scorer": ("experiment_id", False, {"name": "scorer"}),
    "validate_can_read_trace": ("trace_id", False, {}),
    "validate_can_update_trace": ("trace_id", False, {}),
    "validate_can_read_traces_from_experiment_ids": ("experiment_ids", True, {}),
    "validate_can_read_traces_from_trace_ids": ("trace_ids", True, {}),
    "validate_can_update_trace_from_run_id": ("run_id", False, {}),
    "validate_can_delete_traces_from_experiment_id": ("experiment_id", False, {}),
    "validate_can_update_trace_from_experiment_id": ("experiment_id", False, {}),
    "validate_can_read_metric_history_bulk_interval": ("run_ids", True, {}),
    "validate_can_search_datasets": ("experiment_ids", True, {}),
    "validate_can_read_gateway_endpoint": ("name", False, {}),
    "validate_can_delete_gateway_endpoint": ("name", False, {}),
    "validate_can_update_gateway_endpoint": ("endpoint_id", False, {}),
    "validate_can_read_gateway_secret": ("secret_name", False, {}),
    "validate_can_delete_gateway_secret": ("secret_name", False, {}),
    "validate_can_update_gateway_secret": ("secret_id", False, {}),
    "validate_can_read_gateway_model_definition": ("name", False, {}),
    "validate_can_delete_gateway_model_definition": ("name", False, {}),
    "validate_can_update_gateway_model_definition": ("model_definition_id", False, {}),
    "validate_can_read_dataset": ("dataset_id", False, {}),
    "validate_can_update_dataset": ("dataset_id", False, {}),
    "validate_can_delete_dataset": ("dataset_id", False, {}),
    "validate_can_create_dataset": ("experiment_ids", True, {"name": "ds"}),
    "validate_can_search_evaluation_datasets": ("experiment_ids", True, {}),
    "validate_can_link_dataset_experiments": ("experiment_ids", True, {"dataset_id": OWN}),
    "validate_can_read_issue": ("issue_id", False, {}),
    "validate_can_update_issue": ("issue_id", False, {}),
    "validate_can_create_issue": ("experiment_id", False, {"name": "n", "description": "d"}),
    "validate_can_search_issues": ("experiment_id", False, {}),
    "validate_can_read_label_schema": ("schema_id", False, {}),
    "validate_can_update_label_schema": ("schema_id", False, {}),
    "validate_can_delete_label_schema": ("schema_id", False, {}),
    "validate_can_get_or_create_user_queue": ("experiment_id", False, {"user": USER}),
    "validate_can_read_review_queue": ("queue_id", False, {}),
    "validate_can_update_review_queue": ("queue_id", False, {}),
    "validate_can_delete_review_queue": ("queue_id", False, {}),
    "validate_can_update_review_queue_items": ("queue_id", False, {}),
    "validate_can_set_review_queue_item_status": ("queue_id", False, {}),
}

# Validators that read no caller-chosen id for an EXISTING resource, with the reason.
_UNION_EXEMPT = {
    "_deny_non_admin": "unconditional deny; no request field feeds the decision",
    "validate_can_create_experiment": "creation: no existing resource; name-gated only under RESTRICT_RESOURCE_CREATION",
    "validate_can_create_registered_model": "creation: no existing resource; name-gated only under RESTRICT_RESOURCE_CREATION",
    "validate_can_create_gateway": "creation: allowed for any authenticated user",
    "validate_can_read_prompt_optimization_job": "job_id is read from the URL path only (get_url_param)",
    "validate_can_update_prompt_optimization_job": "job_id is read from the URL path only (get_url_param)",
    "validate_can_delete_prompt_optimization_job": "job_id is read from the URL path only (get_url_param)",
    "validate_can_start_trace_v3": "ids are NESTED under trace.trace_info, which the flat spec cannot express; "
    "covered by test_start_trace_v3_applies_the_union below",
}


def _union_routes():
    from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_VALIDATORS
    from mlflow_oidc_auth.hooks.dual_spelling_guard import _is_proto_route

    for (path, method), validator in sorted(BEFORE_REQUEST_VALIDATORS.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if _is_proto_route(path, method):
            yield path, method, validator.__name__


def test_every_proto_validator_is_classified_for_the_union_rule():
    """A new proto validator must be added to _UNION_SPECS (and so tested) or exempted with a reason."""
    unclassified = sorted({name for _p, _m, name in _union_routes() if name not in _UNION_SPECS and name not in _UNION_EXEMPT})
    assert not unclassified, f"classify these validators for the union-rule regression: {unclassified}"


class _FakeTrackingStore:
    """Resolves every token-named run / trace / logged model / gateway id to a same-named parent."""

    def get_run(self, run_id):
        return SimpleNamespace(info=SimpleNamespace(experiment_id=run_id))

    def get_trace_info(self, trace_id):
        return SimpleNamespace(experiment_id=trace_id)

    def get_logged_model(self, model_id):
        return SimpleNamespace(experiment_id=model_id)

    def get_experiment_by_name(self, name):
        return SimpleNamespace(experiment_id=name)

    def get_gateway_endpoint(self, endpoint_id=None, **_):
        return SimpleNamespace(name=endpoint_id)

    def get_secret_info(self, secret_id=None, **_):
        return SimpleNamespace(secret_name=secret_id)

    def get_gateway_model_definition(self, model_definition_id=None, **_):
        return SimpleNamespace(name=model_definition_id)

    def get_dataset_experiment_ids(self, dataset_id):
        return [dataset_id]

    def get_issue(self, issue_id):
        return SimpleNamespace(experiment_id=issue_id)

    def get_label_schema(self, schema_id):
        return SimpleNamespace(experiment_id=schema_id)

    def get_review_queue(self, queue_id):
        return SimpleNamespace(experiment_id=queue_id)


@pytest.fixture
def union_world(store, monkeypatch):
    """OWN and OWN2 are MANAGE for alice on every resource type; VICTIM is an explicit NO_PERMISSIONS.

    The denial is explicit rather than absent, so the assertions cannot pass merely
    because DEFAULT_MLFLOW_PERMISSION happens to be restrictive.
    """
    store.create_user(USER, "pw", "Alice")
    for token, level in ((OWN, "MANAGE"), (OWN2, "MANAGE"), (VICTIM, "NO_PERMISSIONS")):
        store.create_experiment_permission(token, USER, level)
        store.create_registered_model_permission(token, USER, level)
        store.create_scorer_permission(token, "scorer", USER, level)
        store.create_gateway_endpoint_permission(token, USER, level)
        store.create_gateway_secret_permission(token, USER, level)
        store.create_gateway_model_definition_permission(token, USER, level)

    fake = _FakeTrackingStore()
    for target in (
        "mlflow.server.handlers._get_tracking_store",
        "mlflow_oidc_auth.validators.run._get_tracking_store",
        "mlflow_oidc_auth.validators.registered_model._get_tracking_store",
        "mlflow_oidc_auth.validators.experiment._get_tracking_store",
        "mlflow_oidc_auth.validators.trace._get_tracking_store",
        "mlflow_oidc_auth.utils.request_helpers._get_tracking_store",
        "mlflow_oidc_auth.validators.dataset._get_tracking_store",
        "mlflow_oidc_auth.validators.issue._get_tracking_store",
        "mlflow_oidc_auth.validators.review._get_tracking_store",
        "mlflow_oidc_auth.validators._experiment_scope._get_tracking_store",
    ):
        monkeypatch.setattr(target, lambda: fake)
    monkeypatch.setattr("mlflow_oidc_auth.hooks.before_request.store", store)
    monkeypatch.setattr("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", lambda: USER)
    monkeypatch.setattr("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", lambda: False)
    return store


def _hook(path, method, *, view_args=None, query=None, body=None):
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    with _ctx(path, method, body=body, query=query):
        if view_args:
            request.view_args = view_args
        return before_request_hook()


def _union_request(template, method, field, is_list, extra, first, second):
    """``first`` where MLflow might read it (the path, else the query string), ``second`` elsewhere.

    Off the path, ``second`` goes in the body. On a path route it goes in the body for a
    mutating method and in the query string for a GET — a GET body with an otherwise
    empty query string is already refused by the #270 guard, which would mask the
    union check this test is about.
    """
    import re

    view_args = {}

    def fill(match):
        name = match.group(1)
        # The field under test takes ``first``; another path parameter takes a value the
        # spec supplies (so it matches the same field in the body), else a placeholder.
        view_args[name] = first if name in ("trace_id", "request_id", field) else str(extra.get(name, "a1"))
        return view_args[name]

    path = re.sub(r"<([^>]+)>", fill, template)
    query = dict(extra)
    body = dict(extra)
    if field not in view_args:
        query[field] = first
        body[field] = [second] if is_list else second
    elif method == "GET":
        query[field] = second
        body = None
    else:
        body[field] = [second] if is_list else second
    return path, view_args or None, query, body


_UNION_CASES = [(p, m, n) for p, m, n in _union_routes() if n in _UNION_SPECS]


@pytest.mark.parametrize("path, method, validator_name", _UNION_CASES, ids=[f"{m} {p}" for p, m, _n in _UNION_CASES])
def test_a_second_id_in_another_source_is_authorized_too(union_world, path, method, validator_name):
    field, is_list, extra = _UNION_SPECS[validator_name]

    # Denied on EITHER id means denied — in both orientations, so the outcome does not
    # depend on which source MLflow reads for this method.
    for first, second in ((OWN, VICTIM), (VICTIM, OWN)):
        p, view_args, query, body = _union_request(path, method, field, is_list, extra, first, second)
        resp = _hook(p, method, view_args=view_args, query=query, body=body)
        assert resp is not None and resp.status_code in (400, 403), f"{method} {path}: {field} {first!r} vs {second!r} was allowed"
        if not view_args:
            # Off the path, the only way to refuse is the union check itself (403),
            # not an ambiguity 400 that a different code path might stop raising.
            assert resp.status_code == 403, f"{method} {path}: expected 403, got {resp.status_code}"

    # Control: two different ids the caller holds MANAGE on are allowed, so the denials
    # above are the union rule at work, not a blanket refusal of the request shape.
    p, view_args, query, body = _union_request(path, method, field, is_list, extra, OWN, OWN2)
    if not view_args:
        assert _hook(p, method, query=query, body=body) is None, f"{method} {path}: {OWN!r} + {OWN2!r} should be allowed"

    # And the ordinary shape — one id, repeated or in one place — still passes.
    p, view_args, query, body = _union_request(path, method, field, is_list, extra, OWN, OWN)
    assert _hook(p, method, view_args=view_args, query=query, body=body) is None, f"{method} {path}: plain request denied"


def _v3_body(experiment_id, trace_id="new-trace"):
    return {"trace": {"trace_info": {"trace_id": trace_id, "trace_location": {"mlflow_experiment": {"experiment_id": experiment_id}}}}}


class _TraceStoreWithNewIds(_FakeTrackingStore):
    """As _FakeTrackingStore, but a ``new-*`` trace id does not exist yet."""

    def get_trace_info(self, trace_id):
        from mlflow.exceptions import MlflowException
        from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

        if trace_id.startswith("new-"):
            raise MlflowException("not found", RESOURCE_DOES_NOT_EXIST)
        return super().get_trace_info(trace_id)


@pytest.mark.parametrize("prefix", ["/api", "/ajax-api"])
def test_start_trace_v3_applies_the_union(union_world, monkeypatch, prefix):
    """StartTraceV3 names its experiment and trace NESTED in the body; a flat id anywhere else
    (query string, top-level body) must be authorized too — in both orientations."""
    monkeypatch.setattr("mlflow_oidc_auth.validators.trace._get_tracking_store", _TraceStoreWithNewIds)
    path = f"{prefix}/3.0/mlflow/traces"
    for nested, flat in ((OWN, VICTIM), (VICTIM, OWN)):
        for field in ("experiment_id", "trace_id"):
            for where in ("query", "body"):
                body = _v3_body(nested)
                query = None
                if where == "query":
                    query = {field: flat}
                else:
                    body[field] = flat
                # Either the nested destination or the flat id (an experiment, or an existing
                # trace living in it) is VICTIM, so the request must be refused.
                resp = _hook(path, "POST", query=query, body=body)
                assert resp is not None and resp.status_code == 403, f"nested {nested!r} + {field}={flat!r} in {where} was allowed"
    # Control: two ids the caller may write are allowed, and the plain request passes.
    assert _hook(path, "POST", query={"experiment_id": OWN2}, body=_v3_body(OWN)) is None
    assert _hook(path, "POST", body=_v3_body(OWN)) is None


def test_union_covers_both_get_and_non_get_routes():
    """The regression must exercise GET and mutating routes alike, or it proves half the rule."""
    methods = {m for _p, m, _n in _UNION_CASES}
    assert {"GET", "POST"} <= methods, methods
    assert len(_UNION_CASES) >= 50, len(_UNION_CASES)


def _raw_hook(path, method, *, query=None, data=None, content_type=None):
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    kwargs = {"path": path, "method": method}
    if query is not None:
        kwargs["query_string"] = query
    if data is not None:
        kwargs["data"] = data
    if content_type is not None:
        kwargs["content_type"] = content_type
    with app.test_request_context(**kwargs):
        return before_request_hook()


@pytest.mark.parametrize(
    "path, method, query, data, content_type",
    [
        # Double-encoded JSON body (legacy clients) — MLflow decodes it a second time.
        (UPDATE_EXPERIMENT, "POST", {"experiment_id": OWN}, json.dumps(json.dumps({"experiment_id": VICTIM})), "application/json"),
        # camelCase-only body.
        (UPDATE_EXPERIMENT, "POST", {"experiment_id": OWN}, json.dumps({"experimentId": VICTIM}), "application/json"),
        # run_uuid alias in the body, run_id in the query.
        ("/api/2.0/mlflow/runs/update", "POST", {"run_id": OWN}, json.dumps({"run_uuid": VICTIM}), "application/json"),
        # Both aliases in one body.
        ("/api/2.0/mlflow/runs/update", "POST", None, json.dumps({"run_id": OWN, "run_uuid": VICTIM}), "application/json"),
        # Repeated query parameter on a GET: MLflow takes the first, the check takes all.
        (GET_EXPERIMENT, "GET", [("experiment_id", OWN), ("experiment_id", VICTIM)], None, None),
        # camelCase in a GET query string (MLflow never reads it; still authorized).
        (GET_EXPERIMENT, "GET", {"experiment_id": OWN, "experimentId": VICTIM}, None, None),
        # DELETE body without a JSON content type: MLflow force-parses it.
        (
            "/api/3.0/mlflow/scorers/delete",
            "DELETE",
            {"experiment_id": OWN, "name": "scorer"},
            json.dumps({"experiment_id": VICTIM, "name": "scorer"}),
            "text/plain",
        ),
        ("/api/3.0/mlflow/scorers/delete", "DELETE", {"experiment_id": OWN, "name": "scorer"}, json.dumps({"experiment_id": VICTIM, "name": "scorer"}), None),
        # Integer id in the body.
        (UPDATE_EXPERIMENT, "POST", {"experiment_id": OWN}, json.dumps({"experiment_id": 7}), "application/json"),
    ],
    ids=["double-encoded", "camel-only", "run_uuid-alias", "both-aliases", "repeated-query", "camel-query", "delete-text-plain", "delete-no-ctype", "int-id"],
)
def test_parser_edge_shapes_are_denied(union_world, path, method, query, data, content_type):
    """The shapes that caused past drift (#270, #283, #285, #288), pinned end to end.

    ``7`` has no grant and gets DEFAULT_MLFLOW_PERMISSION, so it is made an explicit
    NO_PERMISSIONS here to keep the assertion independent of the configured default.
    """
    union_world.create_experiment_permission("7", USER, "NO_PERMISSIONS")
    resp = _raw_hook(path, method, query=query, data=data, content_type=content_type)
    assert resp is not None and resp.status_code in (400, 403), resp


def test_scorer_name_half_of_the_key_is_also_unioned(union_world):
    """A scorer is keyed by (experiment_id, name); the name half must be unioned too.

    Runs against the real store AND the real permission cache: both scorers live in the
    same experiment and are resolved in the same request, i.e. within one cache TTL.
    Before the cache key carried the scorer name, the first scorer's MANAGE was served
    for the second and this request was allowed.
    """
    union_world.create_scorer_permission(OWN, "theirs", USER, "NO_PERMISSIONS")
    resp = _raw_hook(
        "/api/3.0/mlflow/scorers/delete",
        "DELETE",
        query={"experiment_id": OWN, "name": "theirs"},
        data=json.dumps({"experiment_id": OWN, "name": "scorer"}),
        content_type="application/json",
    )
    assert resp is not None and resp.status_code == 403


@pytest.mark.parametrize(
    "path, method, query, body",
    [
        # Non-proto routes changed by this branch: each mirrors its handler, plus the union.
        ("/ajax-api/2.0/mlflow/gateway-proxy", "POST", {"gateway_path": f"gateway/{VICTIM}/invocations"}, {"gateway_path": f"gateway/{OWN}/invocations"}),
        ("/ajax-api/2.0/mlflow/gateway-proxy", "POST", {"gateway_path": f"gateway/{OWN}/invocations"}, {"gateway_path": f"gateway/{VICTIM}/invocations"}),
        ("/ajax-api/3.0/mlflow/scorer/invoke", "POST", {"experiment_id": VICTIM}, {"experiment_id": OWN}),
        ("/ajax-api/2.0/mlflow/runs/create-promptlab-run", "POST", {"experiment_id": VICTIM}, {"experiment_id": OWN}),
        ("/ajax-api/2.0/mlflow/experiments/search-datasets", "POST", {"experiment_ids": VICTIM}, {"experiment_ids": [OWN]}),
    ],
)
def test_non_proto_routes_apply_the_union(union_world, path, method, query, body):
    resp = _hook(path, method, query=query, body=body)
    assert resp is not None and resp.status_code == 403, resp


def test_upload_artifact_union_is_the_query_string_only(union_world):
    """upload-artifact's body is the artifact; only repeated run_uuid values are unioned."""
    upload = "/ajax-api/2.0/mlflow/upload-artifact"
    resp = _raw_hook(upload, "POST", query=[("run_uuid", OWN), ("run_uuid", VICTIM), ("path", "f.txt")], data=b"x", content_type="application/octet-stream")
    assert resp is not None and resp.status_code == 403
    # A JSON artifact whose content names another run is the owner's upload, not a second run.
    resp = _raw_hook(upload, "POST", query={"run_uuid": OWN, "path": "f.json"}, data=json.dumps({"run_id": VICTIM}), content_type="application/json")
    assert resp is None
