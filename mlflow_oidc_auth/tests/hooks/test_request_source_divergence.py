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
