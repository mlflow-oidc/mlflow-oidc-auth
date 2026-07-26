"""Every artifact-proxy route MLflow serves must reach an authorization check (issue #283).

`_is_proxy_artifact_path` previously matched only the `/api/2.0` prefix and only the
`artifacts/` family. MLflow also serves the proxy under `/ajax-api/2.0` — the prefix the
web UI itself uses — and in the `mpu/{create,complete,abort}` (write) and `presigned`
(read) families. An unmatched path reaches no validator and `before_request_hook` allows
it, so any authenticated user could read and write another workspace's artifacts.
"""

import re

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


class TestExperimentRootPathsResolve:
    """Paths naming an experiment ROOT must resolve — they are the most dangerous shape.

    The id patterns required a trailing slash ("^(\\d+)/"), so "12", "12/", "12//" and
    "workspaces/ws/12" all failed to resolve and fell back to DEFAULT_MLFLOW_PERMISSION
    (ships as MANAGE = allow). DELETE on an experiment root removes its whole artifact
    tree, so this was the worst possible place to fail open.
    """

    @pytest.mark.parametrize(
        "artifact_path",
        [
            "12/r/artifacts/f.json",
            "12",
            "12/",
            "12//",
            "12/.",
            "./12",
            "./12/",
            "%2e/12/r",
            "%2531%2532/r",
            "workspaces/ws1/12",
            "workspaces/ws1/12/",
            "workspaces/ws-1/12/r/a",
        ],
    )
    def test_every_shape_naming_experiment_12_resolves(self, artifact_path):
        from mlflow_oidc_auth.validators.experiment import _experiment_id_from_artifact_path

        assert _experiment_id_from_artifact_path(artifact_path) == "12", f"{artifact_path!r} fell back to the permissive default"

    @pytest.mark.parametrize("artifact_path", ["", "/", "./", "not-a-number/x", "workspaces/ws1", "workspaces/ws1/", "models/foo"])
    def test_paths_naming_no_experiment_do_not_resolve(self, artifact_path):
        """These name no experiment — but note what "no experiment" currently MEANS.

        Returning None sends the caller to DEFAULT_MLFLOW_PERMISSION, which ships as
        MANAGE, so under the shipped default these shapes are ALLOWED rather than
        denied. This test pins the parser's output, NOT a security property: do not read
        it as a hardening assertion. Making the unresolvable case deny is tracked in
        issue #289, and doing so will require changing this test — correctly.
        """
        from mlflow_oidc_auth.validators.experiment import _experiment_id_from_artifact_path

        assert _experiment_id_from_artifact_path(artifact_path) is None

    @pytest.mark.parametrize(
        "artifact_path",
        [
            "file:12/r/artifacts/f",
            "FILE:12/r/a",
            "%66ile:12/r/a",
            "file:12",
            "file:12/",
        ],
    )
    def test_file_uri_scheme_resolves_the_experiment_mlflow_will_serve(self, artifact_path):
        """MLflow strips a file: scheme before serving, so authorization must too.

        validate_path_is_safe runs _decode -> _escape_control_characters ->
        local_file_uri_to_path. Calling only _decode left "file:12/r/artifacts"
        unresolved, which fell back to the MANAGE default and reopened the cross-tenant
        read/write/delete this function exists to close. The scheme test runs after
        decoding, so "FILE:" and "%66ile:" reach the same handler.
        """
        from mlflow_oidc_auth.validators.experiment import _experiment_id_from_artifact_path

        assert _experiment_id_from_artifact_path(artifact_path) == "12", f"{artifact_path!r} fell back to the permissive default"

    @pytest.mark.parametrize("default_permission", ["MANAGE", "NO_PERMISSIONS"])
    @pytest.mark.parametrize(
        "path, method",
        [
            ("/api/2.0/mlflow-artifacts/artifacts/12/r/a", "GET"),
            ("/api/2.0/mlflow-artifacts/artifacts/12/r/a", "DELETE"),
            ("/api/2.0/mlflow-artifacts/artifacts/file:12/r/a", "GET"),
            ("/api/2.0/mlflow-artifacts/artifacts/file:12/r/a", "DELETE"),
            ("/api/2.0/mlflow-artifacts/mpu/create/12/r/a", "POST"),
            ("/ajax-api/2.0/mlflow-artifacts/artifacts/12/r/a", "GET"),
        ],
    )
    def test_resolvable_routes_deny_regardless_of_the_configured_default(self, path, method, default_permission):
        """A denial must come from the store, not from a hardened default.

        The suite inherits DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS from the repo .env,
        under which almost anything denies — so a deny assertion alone proves nothing and
        would still pass if the code stopped resolving experiment ids entirely. Running
        each route under BOTH defaults, and asserting the store was consulted with the
        expected id, is what makes these tests non-vacuous.
        """
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS

        with app.test_request_context(path, method=method):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", default_permission),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="u"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
                patch("mlflow_oidc_auth.validators.experiment.effective_experiment_permission") as resolved,
            ):
                resolved.return_value.permission = NO_PERMISSIONS
                response = before_request_hook()
                resolved.assert_called_once()
                assert resolved.call_args.args[0] == "12", "the store must be consulted for the experiment MLflow will serve"

        assert response is not None and response.status_code == 403

    def test_delete_on_an_experiment_root_is_authorized(self):
        """DELETE /mlflow-artifacts/artifacts/12/ wipes experiment 12's artifacts."""
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS

        with app.test_request_context("/api/2.0/mlflow-artifacts/artifacts/12/", method="DELETE"):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="u"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
                patch("mlflow_oidc_auth.validators.experiment.effective_experiment_permission") as resolved,
            ):
                resolved.return_value.permission = NO_PERMISSIONS
                response = before_request_hook()
                resolved.assert_called_once()
                assert resolved.call_args.args[0] == "12"

        assert response is not None and response.status_code == 403


# ---------------------------------------------------------------------------
# Issue #289 — fail closed, and gate the routes that reached no validator
# ---------------------------------------------------------------------------


class TestUnresolvableArtifactPathFailsClosed:
    """An artifact-proxy path naming no experiment must deny, not fall back to the default.

    Every one of these ran with DEFAULT_MLFLOW_PERMISSION="MANAGE" — the SHIPPED default,
    not the NO_PERMISSIONS the test .env sets. Under NO_PERMISSIONS these assertions pass
    whether or not the fix is present, which is exactly how the hole survived four review
    rounds.
    """

    @pytest.mark.parametrize(
        "path, method",
        [
            # The root shapes. DELETE here reaches delete_artifacts(".") which recursively
            # empties EVERY experiment's artifacts.
            ("/api/2.0/mlflow-artifacts/artifacts/.", "DELETE"),
            ("/api/2.0/mlflow-artifacts/artifacts/%2e", "DELETE"),
            ("/api/2.0/mlflow-artifacts/artifacts/./.", "DELETE"),
            ("/api/2.0/mlflow-artifacts/artifacts/.//", "DELETE"),
            ("/api/2.0/mlflow-artifacts/artifacts/.", "GET"),
            ("/ajax-api/2.0/mlflow-artifacts/artifacts/.", "DELETE"),
            # Names a whole tenant rather than one experiment.
            ("/api/2.0/mlflow-artifacts/artifacts/workspaces/wsA", "DELETE"),
        ],
    )
    def test_root_shaped_paths_are_denied(self, path, method):
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        with app.test_request_context(path, method=method):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="u"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
            ):
                response = before_request_hook()

        assert response is not None and response.status_code == 403, f"{method} {path} was allowed on the shipped MANAGE default"

    @pytest.mark.parametrize("query", ["", "path=", "path=.", "path=./"])
    def test_root_listing_is_denied(self, query):
        """GET the proxy root returns every experiment id on the server.

        The real client never sends this: HttpArtifactRepository.list_artifacts always
        sends a path, and for a proxied run repository it starts with the experiment id.
        """
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        with app.test_request_context(f"/api/2.0/mlflow-artifacts/artifacts?{query}", method="GET"):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="u"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
            ):
                response = before_request_hook()

        assert response is not None and response.status_code == 403

    def test_a_resolvable_path_is_still_authorized_normally(self):
        """The fail-closed change must not swallow the normal path — the store still decides."""
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook
        from mlflow_oidc_auth.permissions import get_permission

        with app.test_request_context("/api/2.0/mlflow-artifacts/artifacts?path=12/r/a", method="GET"):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="u"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
                patch("mlflow_oidc_auth.validators.experiment.effective_experiment_permission") as resolved,
            ):
                resolved.return_value.permission = get_permission("READ")
                response = before_request_hook()
                assert resolved.call_args.args[0] == "12"

        assert response is None, "a user holding READ must still be served"


class TestPreviouslyUngatedArtifactRoutes:
    """These reached NO validator at all — and a None validator is not a deny (#289)."""

    @pytest.mark.parametrize(
        "path, method, expected",
        [
            ("/ajax-api/2.0/mlflow/logged-models/m-1/artifacts/files", "GET", "validate_can_read_logged_model"),
            ("/ajax-api/2.0/mlflow/logged-models/m-1/artifacts/directories", "GET", "validate_can_read_logged_model"),
            ("/api/2.0/mlflow/logged-models/m-1/artifacts/directories", "GET", "validate_can_read_logged_model"),
            ("/api/2.0/mlflow/artifacts/presigned-upload-url", "POST", "validate_can_create_presigned_upload_url"),
            ("/ajax-api/2.0/mlflow/artifacts/presigned-upload-url", "POST", "validate_can_create_presigned_upload_url"),
        ],
    )
    def test_route_now_resolves_a_validator(self, path, method, expected):
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        with app.test_request_context(path, method=method) as ctx:
            validator = _find_validator(ctx.request)

        assert validator is not None, f"{method} {path} still reaches no validator"
        assert validator.__name__ == expected

    @pytest.mark.parametrize("permission, allowed", [("READ", True), ("NO_PERMISSIONS", False)])
    def test_logged_model_artifact_files_decides_on_the_owning_experiment(self, permission, allowed):
        """Resolving a validator is not enough — it must reach a real allow/deny.

        A wiring assertion alone would pass even if the validator always errored, which is
        the failure mode that has bitten this codebase before.
        """
        from unittest.mock import MagicMock, patch

        from flask import request

        from mlflow_oidc_auth.permissions import get_permission
        from mlflow_oidc_auth.validators import validate_can_read_logged_model

        with app.test_request_context("/ajax-api/2.0/mlflow/logged-models/m-1/artifacts/files", method="GET"):
            request.view_args = {"model_id": "m-1"}
            with (
                patch("mlflow_oidc_auth.validators.registered_model._get_tracking_store") as store,
                patch("mlflow_oidc_auth.validators.registered_model.effective_experiment_permission") as resolved,
            ):
                model = MagicMock()
                model.experiment_id = "exp-7"
                store.return_value.get_logged_model.return_value = model
                resolved.return_value.permission = get_permission(permission)

                assert validate_can_read_logged_model("bob") is allowed
                store.return_value.get_logged_model.assert_called_once_with("m-1")
                assert resolved.call_args.args[0] == "exp-7"

    def test_presigned_upload_url_denies_without_update_on_the_run(self):
        """It mints a cloud upload URL for a caller-supplied run_id — a write primitive."""
        from unittest.mock import MagicMock, patch

        from mlflow_oidc_auth.permissions import get_permission
        from mlflow_oidc_auth.validators.run import validate_can_create_presigned_upload_url

        run = MagicMock()
        run.info.experiment_id = "exp-of-victim"

        with (
            app.test_request_context(
                "/api/2.0/mlflow/artifacts/presigned-upload-url",
                method="POST",
                json={"run_id": "VICTIM-RUN", "path": "f.bin"},
            ),
            patch("mlflow_oidc_auth.validators.run._get_tracking_store") as store,
            patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as resolved,
        ):
            store.return_value.get_run.return_value = run
            resolved.return_value.permission = get_permission("READ")
            allowed = validate_can_create_presigned_upload_url("bob")

            store.return_value.get_run.assert_called_once_with("VICTIM-RUN")
            assert resolved.call_args.args[0] == "exp-of-victim"

        assert allowed is False, "READ must not be enough to mint an upload URL"

    def test_presigned_upload_url_reads_the_body_not_the_query_string(self):
        """It is a proto route, so MLflow reads run_id from the body (issues #285, #289)."""
        from unittest.mock import MagicMock, patch

        from mlflow_oidc_auth.permissions import get_permission
        from mlflow_oidc_auth.validators.run import validate_can_create_presigned_upload_url

        run = MagicMock()
        run.info.experiment_id = "exp-1"

        with (
            app.test_request_context(
                "/api/2.0/mlflow/artifacts/presigned-upload-url?run_id=MY-OWN-RUN",
                method="POST",
                json={"run_id": "VICTIM-RUN", "path": "f.bin"},
            ),
            patch("mlflow_oidc_auth.validators.run._get_tracking_store") as store,
            patch("mlflow_oidc_auth.validators.run.effective_experiment_permission") as resolved,
        ):
            store.return_value.get_run.return_value = run
            resolved.return_value.permission = get_permission("EDIT")
            allowed = validate_can_create_presigned_upload_url("bob")

            store.return_value.get_run.assert_called_once_with("VICTIM-RUN")

        # Assert the ALLOW direction too: without this an always-deny validator passes
        # the whole suite, which is exactly what the review found.
        assert allowed is True


def test_structural_every_artifact_serving_route_reaches_a_validator():
    """No artifact route MLflow serves may reach the view unauthorized.

    Derived from MLflow's live url_map rather than a hardcoded list, so a future MLflow
    that adds an artifact route fails this test instead of shipping it ungated. This is
    the check that would have caught all five routes in #289 the moment they appeared.
    """
    from flask import Flask as _Flask

    from mlflow.server import app as mlflow_app

    from mlflow_oidc_auth.hooks.before_request import _find_validator, _is_proxy_artifact_path

    probe = _Flask(__name__)
    ungated = []
    for rule in mlflow_app.url_map.iter_rules():
        path = str(rule)
        if "artifact" not in path.lower():
            continue
        for method in sorted((rule.methods or set()) - {"OPTIONS", "HEAD"}):
            concrete = re.sub(r"<[^>]+>", "x", path)
            with probe.test_request_context(concrete, method=method) as ctx:
                if _find_validator(ctx.request) is None and not _is_proxy_artifact_path(concrete):
                    ungated.append(f"{method} {path}")

    assert not ungated, "artifact routes reachable with no authorization: " + ", ".join(sorted(ungated))


class TestPrefixedArtifactRoots:
    """A prefixed artifact root must still resolve to its experiment (issue #289).

    The first cut of the fail-closed change assumed segment 0 is always the experiment id.
    It is not: `--default-artifact-root mlflow-artifacts:/mlartifacts` makes every run's
    proxy path "mlartifacts/{experiment_id}/{run_id}/artifacts/...", a per-experiment
    artifact_location can add any prefix, and this plugin's own workspace API exposes a
    per-workspace default_artifact_root. Denying those refused every read/write/delete for
    the user holding MANAGE, with no grant able to restore access — an outage, not a
    security win. Resolution now anchors on the "artifacts" marker instead.
    """

    RUN = "1f1635b6c312404381490146137572aa"

    @pytest.mark.parametrize(
        "artifact_path",
        [
            # default layout
            "1/{run}/artifacts",
            "1/{run}/artifacts/model.pkl",
            # --default-artifact-root mlflow-artifacts:/mlartifacts
            "mlartifacts/1/{run}/artifacts",
            "mlartifacts/1/{run}/artifacts/model.pkl",
            # deeper prefixes
            "a/b/c/1/{run}/artifacts/model.pkl",
            # workspace-scoped
            "workspaces/wsA/1/{run}/artifacts/model.pkl",
        ],
    )
    def test_experiment_resolves_whatever_the_prefix_depth(self, artifact_path):
        from mlflow_oidc_auth.validators.experiment import _experiment_id_from_artifact_path

        resolved = _experiment_id_from_artifact_path(artifact_path.format(run=self.RUN))
        assert resolved == "1", f"{artifact_path!r} did not resolve — a MANAGE holder would be locked out"

    @pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
    def test_a_manage_holder_is_served_under_a_prefixed_root(self, method):
        """End to end through the hook: the permission store must decide, and allow."""
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook
        from mlflow_oidc_auth.permissions import get_permission

        path = f"/api/2.0/mlflow-artifacts/artifacts/mlartifacts/1/{self.RUN}/artifacts/model.pkl"
        with app.test_request_context(path, method=method):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="owner"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
                patch("mlflow_oidc_auth.validators.experiment.effective_experiment_permission") as resolved,
            ):
                resolved.return_value.permission = get_permission("MANAGE")
                response = before_request_hook()
                resolved.assert_called_once()
                assert resolved.call_args.args[0] == "1", "the store must be consulted for the real experiment"

        assert response is None, f"{method} was denied for a MANAGE holder under a prefixed artifact root"

    def test_an_unprivileged_user_is_still_denied_under_a_prefixed_root(self):
        """Resolving the prefix must not become a way to bypass the check."""
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook
        from mlflow_oidc_auth.permissions import NO_PERMISSIONS

        path = f"/api/2.0/mlflow-artifacts/artifacts/mlartifacts/1/{self.RUN}/artifacts/model.pkl"
        with app.test_request_context(path, method="DELETE"):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE"),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="stranger"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
                patch("mlflow_oidc_auth.validators.experiment.effective_experiment_permission") as resolved,
            ):
                resolved.return_value.permission = NO_PERMISSIONS
                response = before_request_hook()

        assert response is not None and response.status_code == 403

    @pytest.mark.parametrize("artifact_path", [".", "%2e", "%252e", "./.", ".//", "", "workspaces", "workspaces/wsA"])
    def test_root_scoped_paths_are_still_root_scoped_after_decoding(self, artifact_path):
        """The root check must decode exactly as the id parser does.

        These two used to normalize the value separately, so "%2e" looked like an ordinary
        segment to the root check while MLflow resolved it to "." — the parse-it-two-ways
        bug again, this time inside the fix for it.
        """
        from mlflow_oidc_auth.validators.experiment import _artifact_request_targets_the_whole_root

        assert _artifact_request_targets_the_whole_root(artifact_path) is True

    @pytest.mark.parametrize("artifact_path", ["1/r/artifacts", "mlartifacts/1/r/artifacts", "team-a/proj/r/artifacts"])
    def test_paths_naming_something_within_the_root_are_not_root_scoped(self, artifact_path):
        from mlflow_oidc_auth.validators.experiment import _artifact_request_targets_the_whole_root

        assert _artifact_request_targets_the_whole_root(artifact_path) is False

    @pytest.mark.parametrize("default_permission, allowed", [("MANAGE", True), ("NO_PERMISSIONS", False)])
    def test_an_undecomposable_prefix_falls_back_rather_than_locking_the_tenant_out(self, default_permission, allowed):
        """A layout we cannot parse must NOT be denied outright — that is an outage.

        A per-experiment ``artifact_location`` (or a per-workspace ``default_artifact_root``,
        which this plugin's own API exposes) can put the experiment id nowhere in the path
        at all: "team-a/proj/{run_id}/artifacts". Denying those refuses every operation for
        the user who holds MANAGE, and because the store is never consulted no grant can
        restore access — only the admin bypass.

        So this branch deliberately keeps the pre-change behaviour and defers to the
        configured default. It is no worse than before; the fail-closed tightening is
        scoped to the provably root-scoped shapes instead. Both directions are asserted so
        the branch cannot be silently flipped to deny (an outage) or hardcoded to allow.
        """
        from unittest.mock import patch

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        path = f"/api/2.0/mlflow-artifacts/artifacts/team-a/proj/{self.RUN}/artifacts/model.pkl"
        with app.test_request_context(path, method="GET"):
            with (
                patch.object(config, "DEFAULT_MLFLOW_PERMISSION", default_permission),
                patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="owner"),
                patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False),
                patch("mlflow_oidc_auth.hooks.before_request._requires_existing_user", return_value=False),
            ):
                response = before_request_hook()

        assert (response is None) is allowed, f"undecomposable prefix under default={default_permission} should {'allow' if allowed else 'deny'}"
