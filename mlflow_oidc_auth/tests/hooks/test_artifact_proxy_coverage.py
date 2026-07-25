"""Every artifact-proxy route MLflow serves must reach an authorization check (issue #283).

`_is_proxy_artifact_path` previously matched only the `/api/2.0` prefix and only the
`artifacts/` family. MLflow also serves the proxy under `/ajax-api/2.0` — the prefix the
web UI itself uses — and in the `mpu/{create,complete,abort}` (write) and `presigned`
(read) families. An unmatched path reaches no validator and `before_request_hook` allows
it, so any authenticated user could read and write another workspace's artifacts.
"""

import pytest

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

from mlflow.server import app  # the real routing table: view_args match production


def _mlflow_artifact_rules():
    """Every artifact-proxy (path, method) MLflow actually serves."""
    from mlflow.server import app as mlflow_flask_app

    for rule in mlflow_flask_app.url_map.iter_rules():
        path = str(rule)
        if "/mlflow-artifacts/" not in path:
            continue
        # HEAD is INCLUDED: werkzeug auto-registers it on every GET rule, and excluding
        # it hid the exact method that was being denied for everyone (#283 review).
        # OPTIONS is excluded because Flask answers it automatically — an assumption the
        # test below makes machine-checked rather than trusting it.
        for method in sorted((rule.methods or set()) - {"OPTIONS"}):
            yield path, method


def _concrete(path):
    """Turn a Flask rule into a concrete request path."""
    import re

    return re.sub(r"<[^>]+>", "some/artifact/file.json", path)


class TestEveryArtifactRouteIsGated:
    def test_no_artifact_rule_declares_its_own_options_handler(self):
        """The hook allows OPTIONS unchecked because Flask answers it itself.

        If a future MLflow registered a real OPTIONS handler on an artifact route, that
        early-return would serve it unauthorized. Pin the assumption.
        """
        from mlflow.server import app as mlflow_flask_app

        for rule in mlflow_flask_app.url_map.iter_rules():
            if "/mlflow-artifacts/" not in str(rule):
                continue
            assert rule.provide_automatic_options, f"{rule} declares an explicit OPTIONS handler; the hook would allow it unchecked"

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


class TestReviewRegressions:
    """Defects found reviewing the first cut of this fix — all availability regressions
    introduced by making the artifact branch fail closed."""

    def _hook(self, path, method, *, has_permission, default_permission):
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook
        from mlflow_oidc_auth.permissions import MANAGE, NO_PERMISSIONS

        with app.test_request_context(path=path, method=method):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", default_permission),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="u"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
                patch("mlflow_oidc_auth.validators.experiment.effective_experiment_permission") as resolved,
            ):
                resolved.return_value.permission = MANAGE if has_permission else NO_PERMISSIONS
                return before_request_hook()

    def test_head_is_treated_as_a_read_not_denied(self):
        """werkzeug registers HEAD on every GET rule; it routes to the download handler."""
        allowed = self._hook("/api/2.0/mlflow-artifacts/artifacts/12/r/artifacts/f.json", "HEAD", has_permission=True, default_permission="NO_PERMISSIONS")
        assert allowed is None, "HEAD denied for a user who holds the permission"

    def test_head_still_denied_without_permission(self):
        denied = self._hook("/api/2.0/mlflow-artifacts/artifacts/12/r/artifacts/f.json", "HEAD", has_permission=False, default_permission="NO_PERMISSIONS")
        assert denied is not None and denied.status_code == 403

    def test_options_is_not_authorization_gated(self):
        """Flask answers OPTIONS itself; it reaches no artifact handler."""
        allowed = self._hook("/api/2.0/mlflow-artifacts/artifacts/12/r/artifacts/f.json", "OPTIONS", has_permission=False, default_permission="NO_PERMISSIONS")
        assert allowed is None

    def test_list_route_resolves_the_experiment_from_the_query_param(self):
        """The list route has no path converter — the location is in ?path=.

        Without resolving it, this fell back to DEFAULT_MLFLOW_PERMISSION: fail-open on
        the shipped MANAGE default, and a 403 for the owner under a hardened default.
        """
        allowed = self._hook("/api/2.0/mlflow-artifacts/artifacts?path=12/r/artifacts", "GET", has_permission=True, default_permission="NO_PERMISSIONS")
        assert allowed is None, "list denied for a user who holds the permission"

        denied = self._hook("/api/2.0/mlflow-artifacts/artifacts?path=12/r/artifacts", "GET", has_permission=False, default_permission="MANAGE")
        assert denied is not None and denied.status_code == 403, "list allowed for a user with no permission (fail-open)"

    def test_list_route_consults_the_store_rather_than_the_default(self):
        """Proves the experiment was actually resolved, not defaulted."""
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.permissions import MANAGE
        from mlflow_oidc_auth.validators.experiment import _get_permission_from_experiment_id_artifact_proxy

        with app.test_request_context("/api/2.0/mlflow-artifacts/artifacts?path=12/r/artifacts", method="GET"):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
                patch("mlflow_oidc_auth.validators.experiment.effective_experiment_permission") as resolved,
            ):
                resolved.return_value.permission = MANAGE
                _get_permission_from_experiment_id_artifact_proxy("u")
                resolved.assert_called_once()
                assert resolved.call_args.args[0] == "12", "wrong experiment id parsed from ?path="


class TestDoubleEncodedPathCannotBypass:
    """MLflow decodes the artifact path REPEATEDLY; werkzeug decodes a URL once.

    Parsing the once-decoded value let a double-encoded path miss the experiment-id
    match, fall back to DEFAULT_MLFLOW_PERMISSION (shipped default MANAGE = allow), and
    still be served by MLflow — a fail-open on both the list and download routes.
    """

    @pytest.mark.parametrize(
        "url,source",
        [
            ("/api/2.0/mlflow-artifacts/artifacts?path=%2531%2532/r/artifacts", "query"),
            ("/api/2.0/mlflow-artifacts/artifacts/%2531%2532/r/artifacts/f.json", "view_args"),
        ],
    )
    def test_plugin_and_mlflow_resolve_the_same_experiment(self, url, source):
        from flask import request
        from mlflow.utils.uri import validate_path_is_safe

        from mlflow_oidc_auth.validators.experiment import _get_experiment_id_from_view_args

        with app.test_request_context(url, method="GET"):
            resolved = _get_experiment_id_from_view_args()
            raw = request.args.get("path") if source == "query" else request.view_args.get("artifact_path")
            served = validate_path_is_safe(raw)

        assert resolved == "12", f"double-encoded path not resolved (would fall back to the default): {resolved}"
        assert served.startswith("12/"), "precondition: MLflow serves experiment 12"


class TestScopedReviewBypasses:
    """Two divergences found reviewing the post-review changes — in both, the plugin
    authorized a different experiment than MLflow would serve."""

    @pytest.mark.parametrize("prefix", ["", "./", "%2e/", "%252e/", ".//"])
    def test_dot_prefix_cannot_defeat_the_anchored_patterns(self, prefix):
        """Both id patterns anchor at position 0, so a leading "./" made them miss and
        resolution fell back to DEFAULT_MLFLOW_PERMISSION — allow on the shipped default —
        while MLflow normalises the same path and serves the experiment."""
        import posixpath

        from flask import request
        from mlflow.utils.uri import validate_path_is_safe

        from mlflow_oidc_auth.validators.experiment import _get_experiment_id_from_view_args

        with app.test_request_context(f"/api/2.0/mlflow-artifacts/artifacts?path={prefix}12/r/artifacts", method="GET"):
            resolved = _get_experiment_id_from_view_args()
            served = posixpath.normpath(validate_path_is_safe(request.args.get("path")))

        assert resolved == "12", f"prefix {prefix!r} defeated experiment resolution"
        assert served.startswith("12/"), "precondition: MLflow serves experiment 12"

    @pytest.mark.parametrize("query", ["?path=99/artifacts", ""])
    def test_head_carrying_a_body_is_rejected(self, query):
        """MLflow reads request.args only when the method is literally GET, so a HEAD is
        always proto-parsed from the BODY. Authorizing ?path= while MLflow lists the body's
        experiment leaks an exact Content-Length oracle over another tenant's artifacts."""
        from flask import request

        from mlflow_oidc_auth.hooks.dual_spelling_guard import has_unexpected_get_body

        with app.test_request_context(
            f"/api/2.0/mlflow-artifacts/artifacts{query}", method="HEAD", data='{"path": "12/artifacts"}', content_type="application/json"
        ):
            assert has_unexpected_get_body(request) is True, "HEAD body accepted — cross-tenant listing oracle"

    def test_legitimate_head_without_a_body_is_untouched(self):
        from flask import request

        from mlflow_oidc_auth.hooks.dual_spelling_guard import has_unexpected_get_body

        with app.test_request_context("/api/2.0/mlflow-artifacts/artifacts?path=12/artifacts", method="HEAD"):
            assert has_unexpected_get_body(request) is False
