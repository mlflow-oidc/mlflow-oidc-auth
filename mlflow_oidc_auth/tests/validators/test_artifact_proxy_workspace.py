"""Artifact-proxy authorization when workspaces are enabled (issue #236).

The artifact proxy is the only authenticated path where the workspace is NOT
available from the ``X-MLFLOW-WORKSPACE`` header — MLflow's ``http_artifact_repo``
does not send it. The workspace is in the URL path instead
("workspaces/{name}/{experiment_id}/..."), so the permission check has to read it
from there or the workspace fallback never applies.

Two failures came from that, in opposite directions:
  * a user whose only grant was on the workspace fell through to
    DEFAULT_MLFLOW_PERMISSION and got 403 on upload (the reported symptom); and
  * with the shipped default of MANAGE, any authenticated user could upload into
    ANY workspace's path, including another tenant's — a cross-tenant write.
"""

import pytest
from flask import Flask, request

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.validators.experiment import (
    _parse_artifact_path,
    validate_can_delete_experiment_artifact_proxy,
    validate_can_read_experiment_artifact_proxy,
    validate_can_update_experiment_artifact_proxy,
)

app = Flask(__name__)

_OWNER = "owner@example.com"
_OWNED_WS = "own-ws"


@pytest.fixture(autouse=True)
def _clean_permission_cache():
    """The permission cache is keyed by resource+user and outlives a single test."""
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    flush_permission_cache()
    yield
    flush_permission_cache()


@pytest.fixture
def ws_enabled(monkeypatch):
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["user", "group"])


def _probe(validator, artifact_path, username=_OWNER, header_workspace=None):
    """Run a proxy validator with the given artifact path and bridge auth context."""
    from mlflow_oidc_auth.bridge.user import AUTH_CONTEXT_KEY, AuthContext

    with app.test_request_context(path="/proxy", method="PUT"):
        request.view_args = {"artifact_path": artifact_path}
        request.environ[AUTH_CONTEXT_KEY] = AuthContext(username=username, is_admin=False, workspace=header_workspace)
        return validator(username)


class TestArtifactPathParsing:
    def test_workspace_path_yields_experiment_and_workspace(self):
        with app.test_request_context("/"):
            request.view_args = {"artifact_path": "workspaces/products/8/run1/artifacts/f.json"}
            assert _parse_artifact_path() == ("8", "products")

    def test_plain_path_yields_experiment_only(self):
        with app.test_request_context("/"):
            request.view_args = {"artifact_path": "42/run1/artifacts/f.json"}
            assert _parse_artifact_path() == ("42", None)

    def test_unparseable_path_yields_nothing(self):
        with app.test_request_context("/"):
            request.view_args = {"artifact_path": "not-a-known-shape/f.json"}
            assert _parse_artifact_path() == (None, None)


class TestWorkspaceGrantAllowsUpload:
    """The reported symptom: MANAGE on the workspace, nothing on the experiment."""

    def test_upload_allowed_without_the_workspace_header(self, ws_enabled, monkeypatch):
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "READ")
        from mlflow_oidc_auth.permissions import MANAGE
        from mlflow_oidc_auth.validators import experiment as exp_mod

        monkeypatch.setattr(exp_mod, "get_workspace_permission_cached", lambda u, w: MANAGE if w == _OWNED_WS else None, raising=False)
        monkeypatch.setattr(
            "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
            lambda u, w: MANAGE if w == _OWNED_WS else None,
        )

        assert _probe(validate_can_update_experiment_artifact_proxy, f"workspaces/{_OWNED_WS}/8/r/artifacts/f.json") is True

    def test_read_and_delete_follow_the_same_workspace_grant(self, ws_enabled, monkeypatch):
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "READ")
        from mlflow_oidc_auth.permissions import MANAGE

        monkeypatch.setattr(
            "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
            lambda u, w: MANAGE if w == _OWNED_WS else None,
        )
        path = f"workspaces/{_OWNED_WS}/8/r/artifacts/f.json"

        assert _probe(validate_can_read_experiment_artifact_proxy, path) is True
        assert _probe(validate_can_delete_experiment_artifact_proxy, path) is True


class TestForgedWorkspacePathIsDenied:
    """Cross-tenant guard: the path is caller-controlled, so naming a workspace is not enough."""

    @pytest.mark.parametrize("default_permission", ["READ", "MANAGE"])
    def test_upload_to_another_tenants_workspace_is_denied(self, ws_enabled, monkeypatch, default_permission):
        """With the shipped MANAGE default this previously allowed a cross-tenant write."""
        from mlflow_oidc_auth.permissions import MANAGE

        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", default_permission)
        monkeypatch.setattr(
            "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
            lambda u, w: MANAGE if w == _OWNED_WS else None,
        )

        assert _probe(validate_can_update_experiment_artifact_proxy, "workspaces/victim-ws/9/r/artifacts/f.json") is False

    def test_unknown_workspace_is_denied(self, ws_enabled, monkeypatch):
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        monkeypatch.setattr(
            "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
            lambda u, w: None,
        )

        assert _probe(validate_can_update_experiment_artifact_proxy, "workspaces/does-not-exist/8/r/artifacts/f.json") is False


class TestNonWorkspacePathsUnchanged:
    """Deployments without workspaces, and plain paths, must behave exactly as before."""

    def test_plain_path_still_uses_the_global_default(self, ws_enabled, monkeypatch):
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        assert _probe(validate_can_update_experiment_artifact_proxy, "8/r/artifacts/f.json") is True

    def test_workspaces_disabled_ignores_the_path_workspace(self, monkeypatch):
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "PERMISSION_SOURCE_ORDER", ["user", "group"])
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")

        assert _probe(validate_can_update_experiment_artifact_proxy, "workspaces/anything/8/r/artifacts/f.json") is True

    def test_header_workspace_still_takes_precedence(self, ws_enabled, monkeypatch):
        """When the header IS present, resolve_permission's own fallback handles it."""
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "READ")
        from mlflow_oidc_auth.permissions import MANAGE

        monkeypatch.setattr(
            "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
            lambda u, w: MANAGE if w == _OWNED_WS else None,
        )

        allowed = _probe(
            validate_can_update_experiment_artifact_proxy,
            f"workspaces/{_OWNED_WS}/8/r/artifacts/f.json",
            header_workspace=_OWNED_WS,
        )
        assert allowed is True
