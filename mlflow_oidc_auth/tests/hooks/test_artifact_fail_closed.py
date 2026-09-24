"""Artifact routes fail closed when no experiment resolves (issue #289).

Three gaps, all pre-existing:

* the artifact-proxy validators fell back to ``DEFAULT_MLFLOW_PERMISSION`` — which ships as
  MANAGE — whenever no experiment id could be parsed from the path, so the artifact ROOT
  (``.``, ``%2e``, ``./.``, ``.//``, ``workspaces/<ws>``) and any non-experiment path were
  allowed: ``DELETE .../artifacts/.`` recursively emptied every experiment's artifacts;
* the argument-less LIST route returned the whole root, enumerating every tenant's
  experiment ids;
* three artifact routes carried no validator at all: the logged-model ``artifacts/files``
  download (registered with ``@app.route``), the logged-model ``artifacts/directories``
  listing, and the run ``presigned-upload-url`` / ``presigned-download-url`` minting.

Driven end to end: MLflow's REAL Flask routing table, the REAL ``before_request_hook``, the
REAL MLflow view for the artifact proxy against a real local artifact root, the REAL
``after_request_hook`` and a REAL permission store. Only the MLflow tracking store is faked,
to place runs, logged models and experiments. ``DEFAULT_MLFLOW_PERMISSION`` is MANAGE, so
every denial below comes from the code, never from a restrictive default.
"""

import json
from types import SimpleNamespace

import pytest
from flask import request
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext

VICTIM = "1"  # the experiment the outsider must not touch
OWN = "2"  # the outsider's own experiment
OTHER = "3"  # nobody but the admin and OWNER holds a grant here
WS1_EXPERIMENT = "4"  # lives in workspace ws1
WS2_EXPERIMENT = "5"  # lives in workspace ws2, but a directory for it sits under ws1's root
DELETED = "6"  # soft-deleted: still exists, but is not browsable from the root
ALIASED = "12"  # a victim experiment reachable, before the fix, through "012" / "0012"

OWNER = "owner@example.com"  # MANAGE on every experiment — still cannot touch the root
READER = "reader@example.com"  # READ on the victim only
EDITOR = "editor@example.com"  # EDIT on the victim
OUTSIDER = "outsider@example.com"  # NO_PERMISSIONS on the victim, EDIT on their own
ADMIN = "admin@example.com"

EXPERIMENT_WORKSPACES = {
    VICTIM: "default",
    OWN: "default",
    OTHER: "default",
    WS1_EXPERIMENT: "ws1",
    WS2_EXPERIMENT: "ws2",
    DELETED: "default",
    ALIASED: "default",
}
# Directories under the root with no experiment behind them: a garbage-collected
# experiment's leftovers, and Unicode digits that str.isdigit() accepts.
NOT_EXPERIMENTS = ["999", "²", "١٢"]
# Non-canonical spellings of an existing id: the SQL store int()s them to experiment 12,
# but they are different directories and carry no grant of their own.
ALIASES = ["012", "0012"]
RUN_EXPERIMENTS = {"r-victim": VICTIM, "r-own": OWN}

PREFIXES = ("/api", "/ajax-api")
ROOT_SHAPES = [".", "%2e", "%252e", "./.", ".//", "./", "workspaces/ws1", "workspaces/ws1/"]


class _FakeTrackingStore:
    """Behaves like MLflow's SQL store where it matters: ids are int()ed on lookup."""

    def __init__(self):
        self.calls = []

    def _experiment(self, experiment_id):
        stage = "deleted" if experiment_id == DELETED else "active"
        return SimpleNamespace(experiment_id=experiment_id, workspace=EXPERIMENT_WORKSPACES[experiment_id], lifecycle_stage=stage)

    def get_experiment(self, experiment_id):
        self.calls.append("get_experiment")
        try:
            normalized = str(int(experiment_id))
        except ValueError:
            normalized = str(experiment_id)
        if normalized not in EXPERIMENT_WORKSPACES:
            raise MlflowException(f"Experiment {experiment_id} not found", RESOURCE_DOES_NOT_EXIST)
        return self._experiment(normalized)

    def search_experiments(self, view_type=None, max_results=None, page_token=None, **_):
        from mlflow.entities import ViewType
        from mlflow.store.entities.paged_list import PagedList

        self.calls.append("search_experiments")
        experiments = [self._experiment(e) for e in EXPERIMENT_WORKSPACES]
        if view_type == ViewType.ACTIVE_ONLY:
            experiments = [e for e in experiments if e.lifecycle_stage == "active"]
        return PagedList(experiments, None)

    def get_run(self, run_id):
        return SimpleNamespace(info=SimpleNamespace(experiment_id=RUN_EXPERIMENTS.get(run_id, VICTIM), run_id=run_id))

    def get_logged_model(self, model_id):
        return SimpleNamespace(experiment_id=VICTIM if model_id != "m-own" else OWN, model_id=model_id)


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache
    from mlflow_oidc_auth.utils.workspace_cache import flush_workspace_cache

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setattr("mlflow_oidc_auth.store.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.utils.permissions.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.hooks.before_request.store", s, raising=False)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr("mlflow.server.handlers._tracking_store", _FakeTrackingStore())

    for user in (OWNER, READER, EDITOR, OUTSIDER, ADMIN):
        s.create_user(user, "pw", user, is_admin=user == ADMIN)
    for experiment in EXPERIMENT_WORKSPACES:
        s.create_experiment_permission(experiment, OWNER, "MANAGE")
        # Explicit denials everywhere the test does not grant, so the MANAGE default never
        # decides who sees what.
        for user in (READER, EDITOR, OUTSIDER):
            if (user, experiment) not in {(READER, VICTIM), (EDITOR, VICTIM), (OUTSIDER, OWN)}:
                s.create_experiment_permission(experiment, user, "NO_PERMISSIONS")
    s.create_experiment_permission(VICTIM, READER, "READ")
    s.create_experiment_permission(VICTIM, EDITOR, "EDIT")
    s.create_experiment_permission(OWN, OUTSIDER, "EDIT")

    flush_permission_cache()
    flush_workspace_cache()
    yield s
    flush_permission_cache()
    flush_workspace_cache()


@pytest.fixture
def artifact_root(tmp_path, monkeypatch):
    """A real local artifact root served by MLflow's real artifact-proxy views."""
    from mlflow.store.artifact.local_artifact_repo import LocalArtifactRepository

    root = tmp_path / "artifacts"
    for experiment in (VICTIM, OWN, OTHER, DELETED, *NOT_EXPERIMENTS, *ALIASES):
        (root / experiment / "r1" / "artifacts").mkdir(parents=True)
        (root / experiment / "r1" / "artifacts" / "model.pkl").write_text("secret")
    for workspace, experiment in (("ws1", WS1_EXPERIMENT), ("ws1", WS2_EXPERIMENT), ("ws2", WS2_EXPERIMENT)):
        (root / "workspaces" / workspace / experiment).mkdir(parents=True)
    (root / "stray.txt").write_text("not an experiment")

    monkeypatch.setenv("_MLFLOW_SERVER_SERVE_ARTIFACTS", "true")
    monkeypatch.setattr("mlflow.server.handlers._is_serving_proxied_artifacts", lambda: True)
    monkeypatch.setattr("mlflow.server.handlers._artifact_repo", LocalArtifactRepository(str(root)))
    return root


def _request(path, method, username, *, body=None, workspace=None, run_view=True):
    """Run one request through the real hooks and, when allowed, MLflow's real view."""
    from mlflow_oidc_auth.hooks.after_request import after_request_hook
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=username == ADMIN, workspace=workspace)}
    kwargs = {"json": body} if body is not None else {}
    with mlflow_app.test_request_context(path, method=method, environ_base=environ, **kwargs):
        denied = before_request_hook()
        if denied is not None or not run_view:
            return denied
        assert request.url_rule is not None, f"precondition: MLflow must route {method} {path}"
        view = mlflow_app.view_functions[request.url_rule.endpoint]
        response = mlflow_app.make_response(view(**(request.view_args or {})))
        return after_request_hook(response)


def _denied(resp):
    return resp is not None and resp.status_code == 403


def _listed(resp):
    assert resp is not None and resp.status_code == 200, getattr(resp, "status_code", resp)
    return sorted(f["path"] for f in json.loads(resp.get_data())["files"])


def _tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


# ---------------------------------------------------------------------------
# Root and traversal shapes: DELETE / PUT / download never reach the store
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("shape", ROOT_SHAPES)
@pytest.mark.parametrize("method", ["DELETE", "PUT", "GET"])
def test_root_shapes_are_denied_on_the_artifact_path_routes(artifact_root, prefix, shape, method):
    """Even a user holding MANAGE on every experiment cannot act on the whole root."""
    before = _tree(artifact_root)
    for user in (OWNER, OUTSIDER):
        assert _denied(_request(f"{prefix}/2.0/mlflow-artifacts/artifacts/{shape}", method, user)), f"{method} {shape!r} allowed for {user}"
    assert _tree(artifact_root) == before, "the artifact root was modified"


@pytest.mark.parametrize("method", ["DELETE", "PUT"])
def test_empty_artifact_path_is_denied(artifact_root, method):
    """The trailing-slash form routes nowhere, but must still not be allowed through."""
    assert _denied(_request("/api/2.0/mlflow-artifacts/artifacts/", method, OWNER, run_view=False))


@pytest.mark.parametrize(
    "path, method",
    [
        ("/api/2.0/mlflow-artifacts/mpu/create/.", "POST"),
        ("/api/2.0/mlflow-artifacts/mpu/complete/%2e", "POST"),
        ("/api/2.0/mlflow-artifacts/mpu/abort/workspaces/ws1", "POST"),
        ("/api/2.0/mlflow-artifacts/presigned/.", "GET"),
        ("/ajax-api/2.0/mlflow-artifacts/presigned/workspaces/ws1", "GET"),
    ],
)
def test_root_shapes_are_denied_on_the_mpu_and_presigned_families(path, method):
    assert _denied(_request(path, method, OWNER, run_view=False))


def test_delete_root_is_denied_under_the_shipped_default(artifact_root):
    """The exact reproduction from #289: the whole root emptied on a MANAGE default."""
    assert _denied(_request("/api/2.0/mlflow-artifacts/artifacts/.", "DELETE", OUTSIDER))
    assert (artifact_root / VICTIM / "r1" / "artifacts" / "model.pkl").exists()


def test_admin_is_not_affected(artifact_root):
    assert _request("/api/2.0/mlflow-artifacts/artifacts/.", "DELETE", ADMIN, run_view=False) is None


# ---------------------------------------------------------------------------
# Paths that name no experiment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", ["models/foo", "not-a-number/x", "workspaces", "workspaces/ws1/not-a-number", "999x/r1"])
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_unresolvable_paths_are_denied(artifact_root, shape, method):
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts/{shape}", method, OWNER))


@pytest.mark.parametrize("shape", ["models/foo", "not-a-number/x", "workspaces", "workspaces/ws1/not-a-number"])
def test_unresolvable_list_paths_are_denied(artifact_root, shape):
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts?path={shape}", "GET", OWNER))


def test_experiment_paths_still_authorize_against_the_store(artifact_root):
    """The positive and negative halves of the ordinary case are unchanged."""
    path = f"/api/2.0/mlflow-artifacts/artifacts/{VICTIM}/r1/artifacts/model.pkl"
    assert _denied(_request(path, "GET", OUTSIDER))
    assert _denied(_request(path, "DELETE", READER))
    resp = _request(path, "GET", READER)
    assert resp.status_code == 200
    assert _listed(_request(f"/api/2.0/mlflow-artifacts/artifacts?path={VICTIM}/r1/artifacts", "GET", READER)) == ["model.pkl"]
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts?path={VICTIM}/r1/artifacts", "GET", OUTSIDER))


# ---------------------------------------------------------------------------
# Root LIST: allowed, filtered to readable experiments
# ---------------------------------------------------------------------------

ROOT_LIST_QUERIES = ["", "?path=", "?path=.", "?path=./", "?path=%2e", "?path=%252e", "?path=.//", "?path=./."]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("query", ROOT_LIST_QUERIES)
def test_root_listing_is_filtered_to_readable_experiments(artifact_root, prefix, query):
    path = f"{prefix}/2.0/mlflow-artifacts/artifacts{query}"
    assert _listed(_request(path, "GET", OUTSIDER)) == [OWN]
    assert _listed(_request(path, "GET", READER)) == [VICTIM]
    # MANAGE on every experiment: still no stray file, no orphan directory, no "workspaces".
    # Nor a soft-deleted experiment, nor a directory that names no experiment.
    assert _listed(_request(path, "GET", OWNER)) == sorted([VICTIM, OWN, OTHER])


def test_admin_root_listing_is_unfiltered(artifact_root):
    assert _listed(_request("/api/2.0/mlflow-artifacts/artifacts", "GET", ADMIN)) == sorted(
        [VICTIM, OWN, OTHER, DELETED, *NOT_EXPERIMENTS, *ALIASES, "stray.txt", "workspaces"]
    )


def test_head_on_the_list_route_is_filtered_like_get(artifact_root):
    """MLflow parses a HEAD from its (empty) body, so it lists the ROOT whatever ?path= says.

    The hook authorizes both the query path and the root; the filter then trims the
    root listing, so Content-Length is not an oracle over every tenant's ids.
    """
    resp = _request(f"/api/2.0/mlflow-artifacts/artifacts?path={OWN}", "HEAD", OUTSIDER)
    assert _listed(resp) == [OWN]
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts?path={VICTIM}", "HEAD", OUTSIDER))


def test_a_root_cannot_smuggle_an_unreadable_experiment_into_the_list(artifact_root):
    """Every ?path= value is authorized, not just the first."""
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts?path=.&path={VICTIM}/r1", "GET", OUTSIDER))


def test_listing_decides_root_on_the_first_path_like_mlflow(artifact_root):
    """MLflow lists only the FIRST ?path= value. A root named second is denied rather
    than turning an experiment listing into an (emptied) root listing; a root named
    first is listed and filtered, and every other value is still authorized."""
    base = "/api/2.0/mlflow-artifacts/artifacts"
    assert _denied(_request(f"{base}?path={VICTIM}/r1&path=.", "GET", READER))
    assert _listed(_request(f"{base}?path=.&path={VICTIM}/r1", "GET", READER)) == [VICTIM]
    assert _denied(_request(f"{base}?path=.&path={VICTIM}/r1", "GET", OUTSIDER))
    assert _listed(_request(f"{base}?path={VICTIM}/r1&path={VICTIM}/r1/artifacts", "GET", READER)) == ["artifacts"]
    assert _denied(_request(f"{base}?path={OWN}/r1&path={VICTIM}/r1", "GET", OUTSIDER))


@pytest.mark.parametrize("name", NOT_EXPERIMENTS)
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_directories_that_name_no_experiment_are_denied(artifact_root, name, method):
    """An id-shaped first segment with no experiment behind it is not an experiment.

    It used to reach effective_experiment_permission, which falls back to the MANAGE
    default for an unknown id: any user could read, overwrite or delete a garbage-collected
    experiment's leftovers, or create new trees under the root.
    """
    before = _tree(artifact_root)
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts/{name}/r1/artifacts/model.pkl", method, OWNER))
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts?path={name}/r1", "GET", OWNER))
    assert _tree(artifact_root) == before


@pytest.mark.parametrize("alias", ALIASES)
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_non_canonical_ids_are_denied(artifact_root, alias, method):
    """ "012" is not experiment 12: the store would resolve it to 12, the grant lookup would
    not (no grant on "012", so the MANAGE default), and MLflow would serve <root>/012."""
    before = _tree(artifact_root)
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts/{alias}/r1/artifacts/model.pkl", method, OUTSIDER))
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts?path={alias}/r1", "GET", OUTSIDER))
    assert _tree(artifact_root) == before


def test_non_canonical_directories_are_never_listed(artifact_root, permission_store):
    """Even for a caller who can read experiment 12, "012" is a stray directory."""
    permission_store.update_experiment_permission(ALIASED, OUTSIDER, "READ")
    assert _listed(_request("/api/2.0/mlflow-artifacts/artifacts", "GET", OUTSIDER)) == [OWN]


def test_root_listing_makes_a_bounded_number_of_store_calls(artifact_root, monkeypatch):
    """No N+1: one batched lookup whatever the number of listed directories."""
    for i in range(100, 300):
        (artifact_root / str(i)).mkdir()
    store = _FakeTrackingStore()
    monkeypatch.setattr("mlflow.server.handlers._tracking_store", store)
    assert _listed(_request("/api/2.0/mlflow-artifacts/artifacts", "GET", OWNER)) == sorted([VICTIM, OWN, OTHER])
    assert store.calls == ["search_experiments"]


def test_a_store_outage_denies_and_is_logged_once(artifact_root, monkeypatch):
    """A lookup failure fails closed, and says so instead of claiming the experiment is missing."""
    from unittest.mock import MagicMock

    class _Down(_FakeTrackingStore):
        def get_experiment(self, experiment_id):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr("mlflow.server.handlers._tracking_store", _Down())
    logger = MagicMock()
    monkeypatch.setattr("mlflow_oidc_auth.validators.experiment.logger", logger)
    assert _denied(_request(f"/api/2.0/mlflow-artifacts/artifacts/{VICTIM}/r1/artifacts/model.pkl", "GET", OWNER))

    from mlflow_oidc_auth.validators.experiment import get_artifact_experiment

    logger.reset_mock()
    with mlflow_app.test_request_context("/"):
        assert get_artifact_experiment(VICTIM) is None
        assert get_artifact_experiment(OWN) is None
    outage = [c for c in logger.warning.call_args_list if "RuntimeError: database unavailable" in c.args[0]]
    assert len(outage) == 1, "an outage must be logged, once per request"


def test_a_soft_deleted_experiment_is_still_its_owners(artifact_root):
    """Soft-deleted still exists: its owner keeps access, others stay denied."""
    path = f"/api/2.0/mlflow-artifacts/artifacts/{DELETED}/r1/artifacts/model.pkl"
    assert _request(path, "GET", OWNER).status_code == 200
    assert _denied(_request(path, "GET", OUTSIDER))


def test_non_root_listing_is_not_filtered(artifact_root):
    """Inside an experiment the entries are file names; the filter must leave them alone."""
    assert _listed(_request(f"/api/2.0/mlflow-artifacts/artifacts?path={VICTIM}/r1", "GET", READER)) == ["artifacts"]


class TestRootListingWithWorkspaces:
    @pytest.fixture(autouse=True)
    def workspaces(self, permission_store, monkeypatch):
        from mlflow.utils import workspace_context

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.utils.workspace_cache import flush_workspace_cache

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
        monkeypatch.setenv("MLFLOW_ENABLE_WORKSPACES", "true")
        token = workspace_context.set_server_request_workspace("ws1")
        # OUTSIDER may read experiment 4 itself, but holds no grant on its workspace.
        permission_store.update_experiment_permission(WS1_EXPERIMENT, OUTSIDER, "READ")
        permission_store.create_workspace_permission("ws1", OWNER, "READ")
        permission_store.create_workspace_permission("ws2", OWNER, "READ")
        flush_workspace_cache()
        yield
        workspace_context._WORKSPACE.reset(token)
        flush_workspace_cache()

    @pytest.mark.parametrize("query", ["", "?path=.", "?path=workspaces/ws1", "?path=workspaces/ws1/."])
    def test_listing_keeps_only_the_request_workspaces_readable_experiments(self, artifact_root, query):
        """MLflow lists workspaces/ws1. Experiment 5 has a directory there but lives in ws2."""
        assert _listed(_request(f"/api/2.0/mlflow-artifacts/artifacts{query}", "GET", OWNER, workspace="ws1")) == [WS1_EXPERIMENT]

    def test_listing_is_empty_without_access_to_the_workspace(self, artifact_root):
        """OUTSIDER can read experiment 4 but holds no grant on ws1, so it is hidden."""
        assert _listed(_request("/api/2.0/mlflow-artifacts/artifacts", "GET", OUTSIDER, workspace="ws1")) == []


# ---------------------------------------------------------------------------
# Routes that had no validator at all
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_logged_model_artifact_files_requires_read(method):
    """Registered with @app.route, so it never reached the logged-model validator map."""
    path = "/ajax-api/2.0/mlflow/logged-models/m-victim/artifacts/files?artifact_file_path=model.pkl"
    assert _denied(_request(path, method, OUTSIDER, run_view=False))
    assert _request(path, method, READER, run_view=False) is None
    own = "/ajax-api/2.0/mlflow/logged-models/m-own/artifacts/files?artifact_file_path=model.pkl"
    assert _request(own, method, OUTSIDER, run_view=False) is None


def test_logged_model_artifact_files_authorizes_every_model_id():
    """The union rule: a second model_id in the query string is authorized too."""
    path = "/ajax-api/2.0/mlflow/logged-models/m-own/artifacts/files?artifact_file_path=x&model_id=m-victim"
    assert _denied(_request(path, "GET", OUTSIDER, run_view=False))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_logged_model_artifact_directories_requires_read(prefix, method):
    path = f"{prefix}/2.0/mlflow/logged-models/m-victim/artifacts/directories"
    assert _denied(_request(path, method, OUTSIDER, run_view=False))
    assert _request(path, method, READER, run_view=False) is None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_presigned_upload_url_requires_update_on_the_run(prefix):
    """Minting an upload URL for another tenant's run is a cross-tenant write."""
    path = f"{prefix}/2.0/mlflow/artifacts/presigned-upload-url"
    body = {"run_id": "r-victim", "path": "model.pkl"}
    assert _denied(_request(path, "POST", OUTSIDER, body=body, run_view=False))
    assert _denied(_request(path, "POST", READER, body=body, run_view=False)), "READ is not enough to write"
    assert _request(path, "POST", EDITOR, body=body, run_view=False) is None
    assert _request(path, "POST", OUTSIDER, body={"run_id": "r-own", "path": "x"}, run_view=False) is None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_presigned_download_url_requires_read_on_the_run(prefix):
    path = f"{prefix}/2.0/mlflow/artifacts/presigned-download-url"
    body = {"run_id": "r-victim", "path": "model.pkl"}
    assert _denied(_request(path, "POST", OUTSIDER, body=body, run_view=False))
    assert _request(path, "POST", READER, body=body, run_view=False) is None


@pytest.mark.parametrize("suffix", ["presigned-upload-url", "presigned-download-url"])
@pytest.mark.parametrize(
    "query, body",
    [
        pytest.param("?run_id=r-victim", {"run_id": "r-own", "path": "x"}, id="query-names-victim"),
        pytest.param("", {"runId": "r-victim", "path": "x"}, id="camel-case-body"),
        pytest.param("?run_uuid=r-victim", {"run_id": "r-own", "path": "x"}, id="run-uuid-alias"),
    ],
)
def test_presigned_urls_authorize_every_run_the_request_names(suffix, query, body):
    """The union rule (#285/#288): whichever source MLflow reads, it has been authorized."""
    assert _denied(_request(f"/api/2.0/mlflow/artifacts/{suffix}{query}", "POST", OUTSIDER, body=body, run_view=False))


@pytest.mark.parametrize("suffix", ["presigned-upload-url", "presigned-download-url"])
def test_presigned_urls_without_a_run_are_not_allowed(suffix):
    resp = _request(f"/api/2.0/mlflow/artifacts/{suffix}", "POST", EDITOR, body={"path": "x"}, run_view=False)
    assert resp is not None and resp.status_code in (400, 403)
