"""A route without a validator is refused to non-admins (AGENTS rule 6).

``before_request_hook`` used to let a request through when ``_find_validator`` found
nothing. It now refuses it with 403 for a non-admin unless the route is on the open list in
``hooks/route_policy.py``, has its response filtered in ``after_request``, or sits under an
unprotected prefix. Admins keep access.
"""

import re

import pytest
from flask import Flask, request
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.hooks import before_request
from mlflow_oidc_auth.hooks.http_method import authorization_method
from mlflow_oidc_auth.hooks.route_policy import (
    LEGITIMATELY_OPEN,
    is_filtered_in_after_request,
    is_legitimately_open,
    strip_static_prefix,
)
from mlflow_oidc_auth.tests.hooks.authz_harness import ADMIN, EDITOR, allowed, denied, hook, install_permission_store


class _NoTrackingStore:
    """No route exercised here reaches MLflow's tracking store."""


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    yield install_permission_store(tmp_path, monkeypatch, _NoTrackingStore())
    flush_permission_cache()


@pytest.fixture
def unmapped_app():
    """A Flask app serving one route that no validator, filter or open-list entry covers."""
    app = Flask("unmapped-route-policy")
    app.add_url_rule("/api/3.0/mlflow/not-mapped/<item_id>", "not_mapped", lambda item_id: "served", methods=["GET", "POST"])
    return app


# ---------------------------------------------------------------------------
# A route the policy does not know
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST"])
def test_unmapped_route_is_refused_to_a_non_admin(unmapped_app, method):
    assert denied(hook("/api/3.0/mlflow/not-mapped/x", method, EDITOR, app=unmapped_app))


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST"])
def test_unmapped_route_is_served_to_an_admin(unmapped_app, method):
    assert allowed(hook("/api/3.0/mlflow/not-mapped/x", method, ADMIN, app=unmapped_app))


def test_automatic_options_on_an_unmapped_route_is_not_refused(unmapped_app):
    """Flask answers OPTIONS itself; no view runs and no data is returned."""
    assert allowed(hook("/api/3.0/mlflow/not-mapped/x", "OPTIONS", EDITOR, app=unmapped_app))


def test_a_path_with_no_route_is_left_to_flask(unmapped_app):
    """No rule matches, so Flask answers 404 without running a view."""
    assert allowed(hook("/api/3.0/mlflow/nothing-here", "GET", EDITOR, app=unmapped_app))


def test_unauthenticated_request_is_still_401(unmapped_app):
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    with unmapped_app.test_request_context("/api/3.0/mlflow/not-mapped/x", method="GET"):
        resp = before_request_hook()
    assert resp is not None and resp.status_code == 401


# ---------------------------------------------------------------------------
# Every route MLflow serves
# ---------------------------------------------------------------------------


def _mlflow_pairs():
    pairs = []
    for rule in mlflow_app.url_map.iter_rules():
        methods = set(rule.methods or ()) - {"OPTIONS"} if rule.provide_automatic_options else set(rule.methods or ())
        for method in sorted({authorization_method(m) for m in methods}):
            pairs.append((str(rule), method))
    return sorted(set(pairs))


def _without_validator(rule_path, method):
    path = re.sub(r"<[^>]+>", "x", rule_path)
    if before_request._is_unprotected_route(path) or before_request._is_proxy_artifact_path(path):
        return False
    with mlflow_app.test_request_context(path, method=method):
        return before_request._find_validator(request) is None


_UNVALIDATED = [p for p in _mlflow_pairs() if _without_validator(*p)]


@pytest.mark.parametrize("rule_path, method", _UNVALIDATED)
def test_every_mlflow_route_without_a_validator_is_open_filtered_or_refused(rule_path, method):
    """A route with no validator is served to a non-admin only if the policy accounts for it."""
    body = {} if method in ("POST", "PUT", "PATCH", "DELETE") else None
    resp = hook(re.sub(r"<[^>]+>", "x", rule_path), method, EDITOR, body=body)
    if is_legitimately_open(rule_path, method) or is_filtered_in_after_request(rule_path, method):
        assert allowed(resp), f"{method} {rule_path} is open or filtered but was refused"
    else:
        assert denied(resp), f"{method} {rule_path} has no validator and was served to a non-admin"


@pytest.mark.parametrize("rule_path, method", _UNVALIDATED)
def test_every_mlflow_route_without_a_validator_is_served_to_an_admin(rule_path, method):
    body = {} if method in ("POST", "PUT", "PATCH", "DELETE") else None
    assert allowed(hook(re.sub(r"<[^>]+>", "x", rule_path), method, ADMIN, body=body))


def test_every_mlflow_route_without_a_validator_is_open_or_filtered():
    """Every MLflow route either has a validator or is deliberately open or filtered.

    The refusal itself is exercised by the unmapped-route tests above; a route listed here
    works for admins only until it gets a validator.
    """
    refused = [p for p in _UNVALIDATED if not (is_legitimately_open(*p) or is_filtered_in_after_request(*p))]
    assert [p for p in _UNVALIDATED if p not in refused], "expected open or filtered routes without a validator"
    assert not refused, refused


# ---------------------------------------------------------------------------
# The open list
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule_path, method", sorted({(p, m) for p, ms in LEGITIMATELY_OPEN for m in ms}))
def test_open_routes_are_served_to_any_authenticated_user(rule_path, method):
    body = {} if method == "POST" else None
    assert allowed(hook(re.sub(r"<[^>]+>", "x", rule_path), method, EDITOR, body=body))


def test_open_list_honours_mlflow_static_prefix(monkeypatch):
    from mlflow.server.handlers import STATIC_PREFIX_ENV_VAR

    monkeypatch.setenv(STATIC_PREFIX_ENV_VAR, "/mlflow-ui/")
    assert strip_static_prefix("/mlflow-ui/version") == "/version"
    assert strip_static_prefix("/mlflow-ui") == "/"
    assert strip_static_prefix("/mlflow-uix/version") == "/mlflow-uix/version"
    assert is_legitimately_open("/mlflow-ui/", "GET")
    assert is_legitimately_open("/mlflow-ui/ajax-api/3.0/mlflow/server-info", "GET")
    assert not is_legitimately_open("/mlflow-ui/api/3.0/mlflow/datasets/create", "POST")


def test_open_list_is_exact_on_method():
    assert is_legitimately_open("/version", "GET")
    assert not is_legitimately_open("/version", "POST")
    assert not is_legitimately_open("/api/3.0/mlflow/server-info", "POST")
