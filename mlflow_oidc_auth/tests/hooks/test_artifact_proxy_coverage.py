"""Every artifact-proxy route MLflow serves must reach an authorization check (issue #283).

`_is_proxy_artifact_path` previously matched only the `/api/2.0` prefix and only the
`artifacts/` family. MLflow also serves the proxy under `/ajax-api/2.0` — the prefix the
web UI itself uses — and in the `mpu/{create,complete,abort}` (write) and `presigned`
(read) families. An unmatched path reaches no validator and `before_request_hook` allows
it, so any authenticated user could read and write another workspace's artifacts.
"""

import pytest
from flask import Flask

from mlflow_oidc_auth.hooks.before_request import (
    _ARTIFACT_PROXY_PREFIXES,
    _artifact_proxy_family,
    _get_proxy_artifact_validator,
    _is_proxy_artifact_path,
)
from mlflow_oidc_auth.validators import (
    validate_can_delete_experiment_artifact_proxy,
    validate_can_read_experiment_artifact_proxy,
    validate_can_update_experiment_artifact_proxy,
)

app = Flask(__name__)


def _mlflow_artifact_rules():
    """Every artifact-proxy (path, method) MLflow actually serves."""
    from mlflow.server import app as mlflow_flask_app

    for rule in mlflow_flask_app.url_map.iter_rules():
        path = str(rule)
        if "/mlflow-artifacts/" not in path:
            continue
        for method in sorted((rule.methods or set()) - {"HEAD", "OPTIONS"}):
            yield path, method


def _concrete(path):
    """Turn a Flask rule into a concrete request path."""
    import re

    return re.sub(r"<[^>]+>", "some/artifact/file.json", path)


class TestEveryArtifactRouteIsGated:
    def test_prefixes_cover_both_api_and_ajax_api(self):
        assert any(p.startswith("/api/") for p in _ARTIFACT_PROXY_PREFIXES)
        assert any(p.startswith("/ajax-api/") for p in _ARTIFACT_PROXY_PREFIXES), "the UI prefix must be covered"

    def test_structural_every_served_artifact_route_resolves_to_a_validator(self):
        """Derived from MLflow's routing table, so new artifact routes are auto-covered."""
        rules = list(_mlflow_artifact_rules())
        assert rules, "expected MLflow to serve artifact-proxy routes"

        gaps = []
        for path, method in rules:
            concrete = _concrete(path)
            if not _is_proxy_artifact_path(concrete):
                gaps.append(f"{method} {path} — not recognised as an artifact-proxy path")
                continue
            validator = _get_proxy_artifact_validator(method, {"artifact_path": "x"}, concrete)
            if validator is None:
                gaps.append(f"{method} {path} — recognised but no validator")

        assert not gaps, "artifact routes reaching no authorization check (#283):\n" + "\n".join(gaps)

    @pytest.mark.parametrize(
        "path,method,expected",
        [
            ("/ajax-api/2.0/mlflow-artifacts/artifacts/w/9/f.json", "GET", validate_can_read_experiment_artifact_proxy),
            ("/ajax-api/2.0/mlflow-artifacts/artifacts/w/9/f.json", "PUT", validate_can_update_experiment_artifact_proxy),
            ("/ajax-api/2.0/mlflow-artifacts/artifacts/w/9/f.json", "DELETE", validate_can_delete_experiment_artifact_proxy),
            ("/api/2.0/mlflow-artifacts/mpu/create/w/9/f.json", "POST", validate_can_update_experiment_artifact_proxy),
            ("/api/2.0/mlflow-artifacts/mpu/complete/w/9/f.json", "POST", validate_can_update_experiment_artifact_proxy),
            ("/api/2.0/mlflow-artifacts/mpu/abort/w/9/f.json", "POST", validate_can_update_experiment_artifact_proxy),
            ("/api/2.0/mlflow-artifacts/presigned/w/9/f.json", "GET", validate_can_read_experiment_artifact_proxy),
        ],
    )
    def test_route_maps_to_the_right_permission(self, path, method, expected):
        """mpu/* WRITE, so they must require update — not read."""
        assert _get_proxy_artifact_validator(method, {"artifact_path": "x"}, path) is expected

    def test_family_parsing(self):
        assert _artifact_proxy_family("/api/2.0/mlflow-artifacts/artifacts/x") == "artifacts"
        assert _artifact_proxy_family("/api/2.0/mlflow-artifacts/mpu/create/x") == "mpu"
        assert _artifact_proxy_family("/ajax-api/2.0/mlflow-artifacts/presigned/x") == "presigned"
        assert _artifact_proxy_family("/api/2.0/mlflow/experiments/get") is None


class TestUnrecognisedArtifactRouteIsDenied:
    """Fail closed: an artifact route we cannot classify must not be served unchecked."""

    def test_unknown_family_yields_no_validator(self):
        assert _get_proxy_artifact_validator("GET", {"artifact_path": "x"}, "/api/2.0/mlflow-artifacts/brand-new-family/x") is None

    def test_wrong_method_on_a_known_family_yields_no_validator(self):
        assert _get_proxy_artifact_validator("DELETE", {"artifact_path": "x"}, "/api/2.0/mlflow-artifacts/mpu/create/x") is None
        assert _get_proxy_artifact_validator("PUT", {"artifact_path": "x"}, "/api/2.0/mlflow-artifacts/presigned/x") is None

    def test_hook_denies_an_unrecognised_artifact_route(self):
        from unittest.mock import patch

        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        with app.test_request_context(path="/api/2.0/mlflow-artifacts/brand-new-family/x", method="GET"):
            with (
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="u"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
            ):
                resp = before_request_hook()

        assert resp is not None and resp.status_code == 403
