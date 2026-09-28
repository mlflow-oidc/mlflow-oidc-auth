"""Shared harness for the route-family authorization tests in this directory.

Drives MLflow's REAL Flask routing table, the REAL ``before_request_hook`` and a REAL
permission store (SQLite). Only MLflow's tracking store is replaced, by a per-module fake,
to place resources in experiments. ``DEFAULT_MLFLOW_PERMISSION`` is MANAGE, so a denial can
only come from an explicit grant being consulted, never from a restrictive default.

Users (experiment ``VICTIM`` = "1", ``OWN`` = "2"):

* ``MANAGER``  — MANAGE on VICTIM
* ``EDITOR``   — EDIT on VICTIM
* ``READER``   — READ on VICTIM
* ``OUTSIDER`` — NO_PERMISSIONS on VICTIM, EDIT on OWN
* ``ADMIN``    — administrator
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import request
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext

VICTIM = "1"
OWN = "2"
MANAGER = "manager@example.com"
EDITOR = "editor@example.com"
READER = "reader@example.com"
OUTSIDER = "outsider@example.com"
ADMIN = "admin@example.com"

PREFIXES = ("/api", "/ajax-api")


class BaseFakeTrackingStore:
    """What every fake needs: experiments exist, so regex sources can read their names."""

    def get_experiment(self, experiment_id):
        return SimpleNamespace(experiment_id=experiment_id, name=f"experiment-{experiment_id}", workspace=None)


def install_permission_store(tmp_path, monkeypatch, tracking_store):
    """Create the real permission store with the users above and install ``tracking_store``.

    Parameters:
        tmp_path: pytest's per-test directory, for the SQLite file.
        monkeypatch: pytest's monkeypatch fixture.
        tracking_store: The fake MLflow tracking store for this module.

    Returns:
        The permission store.
    """
    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setattr("mlflow_oidc_auth.store.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.utils.permissions.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.hooks.before_request.store", s, raising=False)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr("mlflow.server.handlers._tracking_store", tracking_store)

    for user in (MANAGER, EDITOR, READER, OUTSIDER, ADMIN):
        s.create_user(user, "pw", user, is_admin=user == ADMIN)
    s.create_experiment_permission(VICTIM, MANAGER, "MANAGE")
    s.create_experiment_permission(VICTIM, EDITOR, "EDIT")
    s.create_experiment_permission(VICTIM, READER, "READ")
    s.create_experiment_permission(VICTIM, OUTSIDER, "NO_PERMISSIONS")
    s.create_experiment_permission(OWN, OUTSIDER, "EDIT")
    flush_permission_cache()
    return s


def hook(path, method, username, *, body=None, query=None, is_admin=None, app=None):
    """Run the real ``before_request_hook`` for one request and return its response (or None).

    Parameters:
        path: Concrete request path.
        method: HTTP method.
        username: Authenticated user.
        body: Optional JSON body.
        query: Optional query string (dict or list of pairs).
        is_admin: Defaults to ``username == ADMIN``.
        app: Flask app whose routing is used; MLflow's by default.

    Returns:
        The hook's response, or None when the request would reach the view.
    """
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    app = app or mlflow_app
    admin = (username == ADMIN) if is_admin is None else is_admin
    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=admin)}
    kwargs = {}
    if body is not None:
        kwargs["json"] = body
    if query is not None:
        kwargs["query_string"] = query
    with app.test_request_context(path, method=method, environ_base=environ, **kwargs):
        if app is mlflow_app:
            assert request.url_rule is not None, f"precondition: MLflow must route {method} {path}"
        return before_request_hook()


def denied(resp) -> bool:
    """True for a 403 from the hook."""
    return resp is not None and resp.status_code == 403


def allowed(resp) -> bool:
    """True when the hook let the request through to the view."""
    return resp is None
