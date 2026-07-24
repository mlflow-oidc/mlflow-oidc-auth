"""Tests for the proto-JSON dual-spelling request guard (issue #270).

MLflow parses request bodies as proto-JSON, which accepts a field under both its
snake_case name and its camelCase json_name and, when both appear, silently keeps
the last one in JSON order. A single-spelling authorization check can therefore be
bypassed. The guard rejects any request that carries one proto field under two
spellings with 400, before any authorization decision.
"""

import json
from unittest.mock import patch

import pytest
from flask import Flask, request

from mlflow.server.handlers import get_endpoints

from mlflow_oidc_auth.hooks import dual_spelling_guard as guard
from mlflow_oidc_auth.hooks.dual_spelling_guard import (
    find_dual_spelling_collision,
    has_unexpected_get_body,
)

app = Flask(__name__)
app.secret_key = "test_secret_key"


def _json_ctx(path, method, body=None, query=None):
    kwargs = {"path": path, "method": method}
    if body is not None:
        kwargs["data"] = json.dumps(body)
        kwargs["content_type"] = "application/json"
    if query is not None:
        kwargs["query_string"] = query
    return app.test_request_context(**kwargs)


# A concrete gated route with two collidable fields, used across the vector tests.
_UPDATE_EXPERIMENT = "/api/2.0/mlflow/experiments/update"


def test_empty_route_maps_fail_loudly_instead_of_disabling_the_guard():
    """A broken MLflow contract must crash at startup, not silently disable the guard.

    The maps are derived from MLflow's registry, so a future release that changes the
    get_endpoints() handler contract would yield empty maps and turn this guard into a
    no-op — silently reopening the bypass. Verify that state is refused, not tolerated.
    """
    with (
        patch.object(guard, "_EXACT_COLLIDABLE", {}),
        patch.object(guard, "_PATTERN_COLLIDABLE", []),
    ):
        with pytest.raises(RuntimeError, match="dual-spelling authorization guard would be inert"):
            guard._assert_maps_populated()


def test_maps_populated_check_passes_with_real_mlflow():
    """The live MLflow install must yield a non-empty map (the guard is actually active)."""
    guard._assert_maps_populated()


def test_route_maps_cover_the_full_proto_surface():
    """The guard's maps are derived from MLflow's own registry, not hand-maintained."""
    assert guard._EXACT_COLLIDABLE, "exact collidable-route map is empty"
    assert guard._PATTERN_COLLIDABLE, "parameterized collidable-route map is empty"
    # UpdateExperiment is a representative gated mutating route.
    fields = guard._collidable_fields_for(_UPDATE_EXPERIMENT, "POST")
    assert ("experiment_id", "experimentId") in fields


def test_dual_spelling_in_body_is_detected():
    with _json_ctx(_UPDATE_EXPERIMENT, "POST", {"experiment_id": "own", "experimentId": "victim"}):
        assert find_dual_spelling_collision(request) == "experiment_id"


def test_snake_only_body_is_clean():
    with _json_ctx(_UPDATE_EXPERIMENT, "POST", {"experiment_id": "own", "new_name": "x"}):
        assert find_dual_spelling_collision(request) is None


def test_camel_only_body_is_clean():
    """A camelCase-only body is a single spelling — not a bypass — so the guard passes."""
    with _json_ctx(_UPDATE_EXPERIMENT, "POST", {"experimentId": "own", "newName": "x"}):
        assert find_dual_spelling_collision(request) is None


def test_get_query_dual_spelling_is_not_a_vector():
    """With a NON-EMPTY query string MLflow builds GET protos from args, keyed by snake field.name."""
    with _json_ctx("/api/2.0/mlflow/experiments/get", "GET", query={"experiment_id": "own", "experimentId": "victim"}):
        assert find_dual_spelling_collision(request) is None


def test_get_with_empty_query_and_dual_spelled_body_is_rejected():
    """A GET with an EMPTY query string proto-parses the BODY, so it must be checked.

    MLflow's _get_request_message takes the args path only when request.args is
    non-empty; otherwise it parse_dicts the body and last-spelling-wins applies.
    Exempting every GET left the #270 bypass fully open on the GET surface.
    """
    with _json_ctx("/api/2.0/mlflow/experiments/get", "GET", {"experiment_id": "own", "experimentId": "victim"}):
        assert find_dual_spelling_collision(request) == "experiment_id"


def test_get_with_query_args_and_a_body_ignores_the_body():
    """When args are present MLflow ignores the body entirely, so it is not a vector."""
    with _json_ctx(
        "/api/2.0/mlflow/experiments/get",
        "GET",
        {"experiment_id": "own", "experimentId": "victim"},
        query={"experiment_id": "own"},
    ):
        assert find_dual_spelling_collision(request) is None
        assert has_unexpected_get_body(request) is False


def test_get_body_on_proto_route_is_rejected_even_without_dual_spelling():
    """A GET body defeats args-only validators, which then authorize with no store lookup.

    validate_can_read_metric_history_bulk_interval reads request.args; on a GET with an
    empty query string it finds no run_ids and returns True without consulting the store,
    while MLflow proto-parses the body and serves the run named there. No dual spelling
    is needed, so has_unexpected_get_body must reject it.
    """
    with _json_ctx(
        "/ajax-api/2.0/mlflow/metrics/get-history-bulk-interval",
        "GET",
        {"run_ids": ["victim_run"], "metric_key": "loss"},
    ):
        assert has_unexpected_get_body(request) is True


def test_plain_get_without_body_is_allowed():
    with _json_ctx("/api/2.0/mlflow/experiments/get", "GET"):
        assert has_unexpected_get_body(request) is False


def test_get_body_on_non_proto_route_is_allowed():
    """Routes MLflow never proto-parses read args only, so a stray body is harmless."""
    with _json_ctx("/api/2.0/mlflow/get-artifact", "GET", {"stray": "body"}):
        assert has_unexpected_get_body(request) is False


def test_live_search_datasets_route_is_covered():
    """MLflow serves search-datasets via @app.route, so it is absent from get_endpoints().

    Only the malformed twins ("/api/2.0mlflow/...", missing a slash, bound to
    _not_implemented) appear in the registry. Binding only those would leave the real
    route unguarded, so the live path is bound from the Flask routing table.
    """
    for path in (
        "/ajax-api/2.0/mlflow/experiments/search-datasets",
        "/api/2.0mlflow/experiments/search-datasets",
    ):
        with _json_ctx(path, "POST", {"experiment_ids": ["own"], "experimentIds": ["victim"]}):
            assert find_dual_spelling_collision(request) == "experiment_ids", f"unguarded: {path}"


def test_unmapped_route_is_ignored():
    with _json_ctx("/api/2.0/mlflow/does-not-exist", "POST", {"experiment_id": "a", "experimentId": "b"}):
        assert find_dual_spelling_collision(request) is None


def test_non_json_body_does_not_crash():
    with app.test_request_context(path=_UPDATE_EXPERIMENT, method="POST", data="not json", content_type="text/plain"):
        assert find_dual_spelling_collision(request) is None


def test_empty_body_is_clean():
    with app.test_request_context(path=_UPDATE_EXPERIMENT, method="POST"):
        assert find_dual_spelling_collision(request) is None


def _iter_collidable_routes():
    """Yield (path, method, snake, camel) for every gated collidable route.

    Exact routes plus one representative concrete path per parameterized route
    (with ``<param>`` segments filled in), so the structural assertion exercises
    real request paths.
    """
    for (path, method), pairs in guard._EXACT_COLLIDABLE.items():
        snake, camel = pairs[0]
        yield path, method, snake, camel
    seen = set()
    for _pattern, method, pairs in guard._PATTERN_COLLIDABLE:
        # Recover a concrete path from the same registry the maps were built from.
        for http_path, handler, methods in get_endpoints(lambda rc: rc):
            if "<" not in http_path or method not in methods:
                continue
            descriptor = getattr(handler, "DESCRIPTOR", None)
            if descriptor is None:
                continue
            collidable = [(f.name, f.json_name) for f in descriptor.fields if f.name != f.json_name]
            if collidable != pairs:
                continue
            concrete = _fill_path_params(http_path)
            key = (concrete, method)
            if key in seen:
                continue
            seen.add(key)
            snake, camel = pairs[0]
            yield concrete, method, snake, camel
            break


def _fill_path_params(path):
    import re

    return re.sub(r"<[^>]+>", "PLACEHOLDER", path)


# Gated routes MLflow never proto-parses: their handlers read request.args only, so
# neither dual spelling nor a GET body can make the validator and MLflow disagree.
# Verified by inspecting each live view for a _get_request_message call.
_ARGS_ONLY_EXEMPT_SUFFIXES = (
    "/get-artifact",
    "/model-versions/get-artifact",
    "mlflow/gateway-proxy",
    "mlflow/get-trace-artifact",
    "mlflow/metrics/get-history-bulk",
    "mlflow/runs/create-promptlab-run",
    "mlflow/upload-artifact",
    "mlflow/gateway/provider-config",
    "mlflow/gateway/secrets/config",
    "mlflow/gateway/supported-models",
    "mlflow/gateway/supported-providers",
    "mlflow/scorer/invoke",
)


def test_every_gated_route_is_guard_covered_or_explicitly_exempt():
    """Coverage assertion: no gated route may silently escape the guard.

    This is what would have caught experiments/search-datasets, whose live path MLflow
    registers with @app.route and therefore never appears in get_endpoints(). A gated
    route is acceptable only if the guard covers it, or its validator is an
    unconditional deny (no field is read, so there is nothing to bypass), or MLflow
    never proto-parses it. Anything else is a gap and must fail here.
    """
    from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_VALIDATORS, _deny_non_admin

    gaps = []
    for (path, method), validator in BEFORE_REQUEST_VALIDATORS.items():
        if guard._is_proto_route(path, method):
            continue
        if validator is _deny_non_admin:
            continue  # admin-only hard deny: no request field feeds the decision
        if any(path.endswith(suffix) for suffix in _ARGS_ONLY_EXEMPT_SUFFIXES):
            continue
        gaps.append(f"{method} {path} -> {getattr(validator, '__name__', validator)}")

    assert not gaps, "gated routes neither guard-covered nor exempt (see #270):\n" + "\n".join(sorted(gaps))


def _hook_response(path, method, body):
    from unittest.mock import patch

    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    with _json_ctx(path, method, body):
        with (
            patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="test_user"),
            patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
        ):
            return before_request_hook()


def test_hook_returns_400_on_dual_spelling():
    """End-to-end: the hook rejects a dual-spelled body before authorization runs."""
    resp = _hook_response(_UPDATE_EXPERIMENT, "POST", {"experiment_id": "own", "experimentId": "victim", "new_name": "x"})
    assert resp is not None
    assert resp.status_code == 400


def test_hook_returns_400_on_get_with_body():
    """End-to-end: a GET carrying a proto-parsable body is rejected before authorization."""
    resp = _hook_response("/api/2.0/mlflow/experiments/get", "GET", {"experiment_id": "own"})
    assert resp is not None
    assert resp.status_code == 400


def test_hook_rejects_dual_spelling_even_for_admin():
    """A dual-spelled body is malformed regardless of who sends it."""
    from unittest.mock import patch

    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    with _json_ctx(_UPDATE_EXPERIMENT, "POST", {"experiment_id": "own", "experimentId": "victim"}):
        with (
            patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="admin"),
            patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=True),
        ):
            resp = before_request_hook()
    assert resp is not None
    assert resp.status_code == 400


def test_every_collidable_route_rejects_dual_spelling():
    """Structural guard: every current AND future gated route auto-gets coverage.

    A new proto endpoint added to MLflow, or a new field, is picked up by the
    registry-derived maps, so no route can silently reintroduce the bypass.
    """
    routes = list(_iter_collidable_routes())
    assert routes, "expected at least some collidable routes"
    body_routes = [r for r in routes if r[1] != "GET"]
    assert body_routes, "expected at least some collidable body routes"
    for path, method, snake, camel in body_routes:
        # Body-carrying routes must reject a dual-spelled field.
        with _json_ctx(path, method, {snake: "own", camel: "victim"}):
            assert find_dual_spelling_collision(request) == snake, f"guard missed dual-spelling on {method} {path}"
    for path, method, snake, camel in routes:
        if method != "GET":
            continue
        # With a non-empty query string MLflow reads args by field.name (snake) only,
        # so a camelCase query param is never read — not a dual-spelling vector.
        with _json_ctx(path, method, query={snake: "own", camel: "victim"}):
            assert find_dual_spelling_collision(request) is None, f"unexpected GET rejection on {path}"
        # But with an EMPTY query string MLflow proto-parses the body, so the same
        # dual spelling in a body IS a vector and must be rejected.
        with _json_ctx(path, method, {snake: "own", camel: "victim"}):
            assert find_dual_spelling_collision(request) == snake, f"guard missed GET-body dual-spelling on {path}"
        # And any GET body on a proto route defeats args-only validators.
        with _json_ctx(path, method, {snake: "own"}):
            assert has_unexpected_get_body(request) is True, f"guard missed GET body on {path}"
