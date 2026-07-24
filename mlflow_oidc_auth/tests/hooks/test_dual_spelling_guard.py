"""Tests for the proto-JSON dual-spelling request guard (issue #270).

MLflow parses request bodies as proto-JSON, which accepts a field under both its
snake_case name and its camelCase json_name and, when both appear, silently keeps
the last one in JSON order. A single-spelling authorization check can therefore be
bypassed. The guard rejects any request that carries one proto field under two
spellings with 400, before any authorization decision.
"""

import json

import pytest
from flask import Flask, request

from mlflow.server.handlers import get_endpoints

from mlflow_oidc_auth.hooks import dual_spelling_guard as guard
from mlflow_oidc_auth.hooks.dual_spelling_guard import find_dual_spelling_collision

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
    """MLflow builds GET protos from args keyed by field.name (snake) only."""
    with _json_ctx("/api/2.0/mlflow/experiments/get", "GET", query={"experiment_id": "own", "experimentId": "victim"}):
        assert find_dual_spelling_collision(request) is None


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
        # GET routes read args by field.name (snake) only — not a dual-spelling vector.
        with _json_ctx(path, method, query={snake: "own", camel: "victim"}):
            assert find_dual_spelling_collision(request) is None, f"unexpected GET rejection on {path}"
