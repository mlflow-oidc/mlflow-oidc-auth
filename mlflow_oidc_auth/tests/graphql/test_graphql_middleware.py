"""Unit tests for GraphQL authorization middleware.

These tests validate the OIDC plugin's Graphene middleware behavior without
executing the actual MLflow GraphQL schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from mlflow_oidc_auth.graphql.middleware import GraphQLAuthorizationMiddleware


@dataclass
class _FakePermission:
    can_read: bool


@dataclass
class _FakePermissionResult:
    permission: _FakePermission


@dataclass
class _FakeRunInfo:
    experiment_id: str


@dataclass
class _FakeRun:
    info: _FakeRunInfo


class _FakeTrackingStore:
    def __init__(self, experiment_id: str):
        self._experiment_id = experiment_id

    def get_run(self, _run_id: str) -> _FakeRun:
        return _FakeRun(info=_FakeRunInfo(experiment_id=self._experiment_id))


@dataclass
class _FakeInfo:
    field_name: str


def test_unprotected_field_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-protected fields should bypass authorization."""

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(next_, None, _FakeInfo(field_name="someOtherField"), input={})

    assert result == "ok"
    assert called["count"] == 1


def test_protected_field_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Protected fields should return None when authorization fails."""

    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )
    monkeypatch.setattr(
        mw_mod,
        "effective_experiment_permission",
        lambda _exp_id, _user: _FakePermissionResult(permission=_FakePermission(can_read=False)),
    )

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(
        next_,
        None,
        _FakeInfo(field_name="mlflowGetExperiment"),
        input={"experiment_id": "1"},
    )

    assert result is None
    assert called["count"] == 0


def test_protected_field_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Protected fields should call next resolver when authorized."""

    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )
    monkeypatch.setattr(
        mw_mod,
        "effective_experiment_permission",
        lambda _exp_id, _user: _FakePermissionResult(permission=_FakePermission(can_read=True)),
    )

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(
        next_,
        None,
        _FakeInfo(field_name="mlflowGetExperiment"),
        input={"experiment_id": "1"},
    )

    assert result == "ok"
    assert called["count"] == 1


def test_search_filters_unreadable_experiments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Search fields should filter experiment_ids to readable subset."""

    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )

    def fake_perm(exp_id: str, _user: str) -> _FakePermissionResult:
        return _FakePermissionResult(permission=_FakePermission(can_read=(exp_id in {"1", "3"})))

    monkeypatch.setattr(mw_mod, "effective_experiment_permission", fake_perm)

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    input_obj = {"experiment_ids": ["1", "2", "3"]}
    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(next_, None, _FakeInfo(field_name="mlflowSearchRuns"), input=input_obj)

    assert result == "ok"
    assert called["count"] == 1
    assert input_obj["experiment_ids"] == ["1", "3"]


def test_run_based_field_uses_tracking_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run-based protected fields should resolve experiment_id via tracking store."""

    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )
    monkeypatch.setattr(mw_mod, "_get_tracking_store", lambda: _FakeTrackingStore(experiment_id="9"))
    monkeypatch.setattr(
        mw_mod,
        "effective_experiment_permission",
        lambda exp_id, _user: _FakePermissionResult(permission=_FakePermission(can_read=(exp_id == "9"))),
    )

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(next_, None, _FakeInfo(field_name="mlflowGetRun"), input={"run_id": "r1"})

    assert result == "ok"
    assert called["count"] == 1


def test_search_model_versions_denied_without_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(next_, None, _FakeInfo(field_name="mlflowSearchModelVersions"), input={})

    assert result is None
    assert called["count"] == 0


def test_search_model_versions_authorized_by_model_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )
    monkeypatch.setattr(
        mw_mod,
        "effective_registered_model_permission",
        lambda name, _user: _FakePermissionResult(permission=_FakePermission(can_read=(name == "m1"))),
    )

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(
        next_,
        None,
        _FakeInfo(field_name="mlflowSearchModelVersions"),
        input={"filter": "name = 'm1'"},
    )

    assert result == "ok"
    assert called["count"] == 1


def test_search_model_versions_authorized_by_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )
    monkeypatch.setattr(mw_mod, "_get_tracking_store", lambda: _FakeTrackingStore(experiment_id="9"))
    monkeypatch.setattr(
        mw_mod,
        "effective_experiment_permission",
        lambda exp_id, _user: _FakePermissionResult(permission=_FakePermission(can_read=(exp_id == "9"))),
    )

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(
        next_,
        None,
        _FakeInfo(field_name="mlflowSearchModelVersions"),
        input={"filter": "run_id='r1'"},
    )

    assert result == "ok"
    assert called["count"] == 1


def test_search_model_versions_denied_for_complex_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Complex/unknown filters should fail closed (return None)."""

    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(
        mw_mod,
        "_get_auth_context",
        lambda: mw_mod._AuthContext(username="alice", is_admin=False),
    )

    # Defensive: if the middleware unexpectedly tries to authorize by model name,
    # make the test fail loudly.
    def _unexpected(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Unexpected call while parsing complex filter")

    monkeypatch.setattr(mw_mod, "effective_registered_model_permission", _unexpected)
    monkeypatch.setattr(mw_mod, "_get_tracking_store", _unexpected)

    called = {"count": 0}

    def next_(root: Any, info: Any, **kwargs: Any) -> str:
        called["count"] += 1
        return "ok"

    mw = GraphQLAuthorizationMiddleware()
    result = mw.resolve(
        next_,
        None,
        _FakeInfo(field_name="mlflowSearchModelVersions"),
        input={"filter": "name LIKE 'm%' AND (run_id = 'r1' OR run_id = 'r2')"},
    )

    assert result is None
    assert called["count"] == 0


@dataclass
class _FakeModelVersion:
    name: str
    version: str = "1"


def _patch_model_versions_permissions(monkeypatch: pytest.MonkeyPatch, readable_experiments: set[str], readable_models: set[str], is_admin: bool = False):
    from mlflow_oidc_auth.graphql import middleware as mw_mod

    monkeypatch.setattr(mw_mod, "_get_auth_context", lambda: mw_mod._AuthContext(username="alice", is_admin=is_admin))
    monkeypatch.setattr(
        mw_mod,
        "effective_experiment_permission",
        lambda exp_id, _user: _FakePermissionResult(permission=_FakePermission(can_read=exp_id in readable_experiments)),
    )
    model_calls: list[str] = []

    def fake_model_permission(name: str, _user: str) -> _FakePermissionResult:
        model_calls.append(name)
        if name == "broken":
            raise RuntimeError("lookup failed")
        return _FakePermissionResult(permission=_FakePermission(can_read=name in readable_models))

    monkeypatch.setattr(mw_mod, "effective_registered_model_permission", fake_model_permission)
    return model_calls


_VERSIONS = [_FakeModelVersion("readable"), _FakeModelVersion("hidden"), _FakeModelVersion("readable", "2"), _FakeModelVersion("broken")]


def test_run_model_versions_filtered_to_readable_models(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_model_versions_permissions(monkeypatch, {"1"}, {"readable"})
    root = _FakeRun(info=_FakeRunInfo(experiment_id="1"))
    mw = GraphQLAuthorizationMiddleware()

    result = mw.resolve(lambda *_a, **_k: list(_VERSIONS), root, _FakeInfo(field_name="modelVersions"))

    assert result == [_FakeModelVersion("readable"), _FakeModelVersion("readable", "2")]
    # One lookup per distinct model name.
    assert sorted(calls) == ["broken", "hidden", "readable"]


def test_run_model_versions_all_hidden_without_model_grants(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_model_versions_permissions(monkeypatch, {"1"}, set())
    root = _FakeRun(info=_FakeRunInfo(experiment_id="1"))

    result = GraphQLAuthorizationMiddleware().resolve(lambda *_a, **_k: list(_VERSIONS), root, _FakeInfo(field_name="modelVersions"))

    assert result == []


def test_run_model_versions_denied_without_experiment_read(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_model_versions_permissions(monkeypatch, set(), {"readable"})
    called = {"count": 0}

    def next_(*_a: Any, **_k: Any) -> list:
        called["count"] += 1
        return list(_VERSIONS)

    root = _FakeRun(info=_FakeRunInfo(experiment_id="1"))
    result = GraphQLAuthorizationMiddleware().resolve(next_, root, _FakeInfo(field_name="modelVersions"))

    assert result is None
    assert called["count"] == 0


def test_run_model_versions_unfiltered_for_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_model_versions_permissions(monkeypatch, set(), set(), is_admin=True)
    root = _FakeRun(info=_FakeRunInfo(experiment_id="1"))

    result = GraphQLAuthorizationMiddleware().resolve(lambda *_a, **_k: list(_VERSIONS), root, _FakeInfo(field_name="modelVersions"))

    assert result == _VERSIONS
    assert calls == []


def test_run_model_versions_filtered_through_mlflow_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """``run.modelVersions`` executed through MLflow's own GraphQL schema is filtered per model."""
    import mlflow.server.handlers as handlers
    from mlflow.protos import model_registry_pb2, service_pb2
    from mlflow.server.graphql.graphql_schema_extensions import schema

    from mlflow_oidc_auth.graphql import middleware as mw_mod

    _patch_model_versions_permissions(monkeypatch, {"1"}, {"readable"})
    monkeypatch.setattr(mw_mod, "_get_tracking_store", lambda: _FakeTrackingStore("1"))

    def fake_get_run_impl(_request):
        response = service_pb2.GetRun.Response()
        response.run.info.run_id = "r1"
        response.run.info.experiment_id = "1"
        return response

    def fake_search_model_versions_impl(_request):
        response = model_registry_pb2.SearchModelVersions.Response()
        for name in ("readable", "hidden"):
            mv = response.model_versions.add()
            mv.name = name
            mv.version = "1"
        return response

    monkeypatch.setattr(handlers, "get_run_impl", fake_get_run_impl)
    monkeypatch.setattr(handlers, "search_model_versions_impl", fake_search_model_versions_impl)

    result = schema.execute(
        '{ mlflowGetRun(input: {runId: "r1"}) { run { modelVersions { name } } } }',
        middleware=[GraphQLAuthorizationMiddleware()],
    )

    assert result.errors is None
    assert result.data["mlflowGetRun"]["run"]["modelVersions"] == [{"name": "readable"}]
