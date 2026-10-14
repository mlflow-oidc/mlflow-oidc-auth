"""The grant-context resolver decides exactly as the pre-refactor resolver did (issue #460).

``grant_context.resolve`` replaced the per-resource source walk of ``resolve_permission``, the batch
path's own walk and the workspace resolver's. The property test below generates random grants —
user, group, regex and group-regex, on all eight resource types, at equal and unequal priorities,
including ``NO_PERMISSIONS`` grants, with patterns and name-keyed grants spread over workspaces —
and asserts, for every (user, resource, workspace), that ``grant_context.resolve`` returns what the
pre-refactor ``resolve_permission`` returned. That function is vendored below, unchanged but for
taking its store and tracking store as arguments, as the oracle.

The required negative tests for the refactor live here too:
``batch_denies_experiment_outside_request_workspace``, ``revoke_invalidates_context``,
``membership_removal_invalidates_context`` and ``no_permissions_grant_beats_lower_source``.
"""

import random
import re
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Callable, Dict
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AuthContext
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, compare_permissions, get_permission, in_regex_grant_order
from mlflow_oidc_auth.utils import grant_context
from mlflow_oidc_auth.utils.grant_context import load_grant_context, resolve

# ---------------------------------------------------------------------------
# The oracle: pre-refactor resolve_permission (utils/permissions.py at b122b771), uncached.
# ---------------------------------------------------------------------------


def _old_match_regex_permission(regexes, name: str, label: str, workspace: str | None = None) -> str:
    from mlflow_oidc_auth.utils.grant_workspace import pattern_in_scope

    best = None
    for regex in in_regex_grant_order(regexes):
        if best is not None and regex.priority > best.priority:
            break  # past the best tier
        if not pattern_in_scope(regex, workspace) or not re.match(regex.regex, name):
            continue
        if best is None or not compare_permissions(regex.permission, best.permission):
            best = regex
    if best is None:
        raise MlflowException(f"{label} {name}", error_code=RESOURCE_DOES_NOT_EXIST)
    return best.permission


def _old_build_sources(store, tracking, resource_type: str, resource_id: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    m = _old_match_regex_permission
    groups = lambda: store.get_groups_ids_for_user(username)  # noqa: E731
    if resource_type == "experiment":
        return {
            "user": lambda: store.get_experiment_permission(resource_id, username).permission,
            "group": lambda: store.get_user_groups_experiment_permission(resource_id, username).permission,
            "regex": lambda: m(store.list_experiment_regex_permissions(username), tracking().get_experiment(resource_id).name, "experiment"),
            "group-regex": lambda: m(
                store.list_group_experiment_regex_permissions_for_groups_ids(groups()), tracking().get_experiment(resource_id).name, "experiment"
            ),
        }
    if resource_type == "registered_model":
        return {
            "user": lambda: store.get_registered_model_permission(resource_id, username).permission,
            "group": lambda: store.get_user_groups_registered_model_permission(resource_id, username).permission,
            "regex": lambda: m(store.list_registered_model_regex_permissions(username), resource_id, "model name"),
            "group-regex": lambda: m(store.list_group_registered_model_regex_permissions_for_groups_ids(groups()), resource_id, "model name"),
        }
    if resource_type == "prompt":
        return {
            "user": lambda: store.get_registered_model_permission(resource_id, username).permission,
            "group": lambda: store.get_user_groups_registered_model_permission(resource_id, username).permission,
            "regex": lambda: m(store.list_prompt_regex_permissions(username), resource_id, "prompt name"),
            "group-regex": lambda: m(store.list_group_prompt_regex_permissions_for_groups_ids(groups()), resource_id, "prompt name"),
        }
    if resource_type == "scorer":
        scorer_name = kwargs["scorer_name"]
        return {
            "user": lambda: store.get_scorer_permission(resource_id, scorer_name, username).permission,
            "group": lambda: store.get_user_groups_scorer_permission(resource_id, scorer_name, username).permission,
            "regex": lambda: m(store.list_scorer_regex_permissions(username), scorer_name, "scorer name"),
            "group-regex": lambda: m(store.list_group_scorer_regex_permissions_for_groups_ids(groups()), scorer_name, "scorer name"),
        }
    if resource_type == "mcp_server":
        return {
            "user": lambda: store.get_mcp_server_permission(resource_id, username).permission,
            "group": lambda: store.get_user_mcp_server_group_permission(resource_id, username).permission,
        }
    kind = {"gateway_endpoint": "endpoint", "gateway_secret": "secret", "gateway_model_definition": "model_definition"}[resource_type]
    return {
        "user": lambda: getattr(store, f"get_gateway_{kind}_permission")(resource_id, username).permission,
        "group": lambda: getattr(store, f"get_user_gateway_{kind}_group_permission")(resource_id, username).permission,
        "regex": lambda: m(getattr(store, f"list_gateway_{kind}_regex_permissions")(username), resource_id, "gateway name"),
        "group-regex": lambda: m(getattr(store, f"list_group_gateway_{kind}_regex_permissions_for_groups_ids")(groups()), resource_id, "gateway name"),
    }


def _old_get_permission_from_store_or_default(sources: Dict[str, Callable[[], str]]) -> PermissionResult:
    for source_name in config.PERMISSION_SOURCE_ORDER:
        if source_name in sources:
            try:
                return PermissionResult(get_permission(sources[source_name]()), source_name)
            except MlflowException as e:
                if e.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                    raise
    return PermissionResult(get_permission(config.DEFAULT_MLFLOW_PERMISSION), "fallback")


def _old_experiment_in_request_workspace(tracking, experiment_id) -> bool:
    if not experiment_id:
        return False
    try:
        return tracking().get_experiment(str(experiment_id)) is not None
    except Exception:
        return False


def _old_apply_workspace_fallback(tracking, result: PermissionResult, username: str, resource_type=None, resource_id=None) -> PermissionResult:
    if result.kind != "fallback" or not config.MLFLOW_ENABLE_WORKSPACES:
        return result
    from mlflow_oidc_auth.bridge.user import get_request_workspace
    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    workspace = get_request_workspace()
    if not workspace:
        return result
    if resource_type in ("experiment", "scorer") and not _old_experiment_in_request_workspace(tracking, resource_id):
        return PermissionResult(NO_PERMISSIONS, "workspace-deny")
    ws_perm = get_workspace_permission_cached(username, workspace)
    if ws_perm is not None:
        return PermissionResult(ws_perm, "workspace")
    return PermissionResult(NO_PERMISSIONS, "workspace-deny")


def oracle_resolve_permission(store, tracking, resource_type: str, resource_id: str, username: str, **kwargs) -> PermissionResult:
    """Pre-refactor ``resolve_permission``, without its result cache."""
    result = _old_get_permission_from_store_or_default(_old_build_sources(store, tracking, resource_type, resource_id, username, **kwargs))
    return _old_apply_workspace_fallback(tracking, result, username, resource_type, resource_id)


# ---------------------------------------------------------------------------
# A world of resources and random grants
# ---------------------------------------------------------------------------

PERMISSIONS = ["READ", "USE", "EDIT", "MANAGE", "NO_PERMISSIONS"]
PATTERNS = [".*", "^alpha", "^beta", "1$", "-2$", "^alpha-1$", "^m-", "s$", "zzz"]
USERS = ["u0", "u1", "u2"]
GROUPS = ["g0", "g1", "g2"]
WORKSPACES = ["default", "ws-a", "ws-b"]
# id -> (name, workspace)
EXPERIMENTS = {"1": ("alpha-1", "ws-a"), "2": ("beta-2", "ws-b"), "3": ("alpha-3", "default"), "4": ("m-4", "ws-a")}
NAMES = ["alpha-1", "beta-2", "m-3"]
SCORERS = [("1", "alpha-s"), ("2", "beta-1"), ("3", "alpha-s"), ("4", "m-2")]
NAME_KEYED = ["registered_model", "prompt", "gateway_endpoint", "gateway_secret", "gateway_model_definition", "mcp_server"]


class FakeTrackingStore:
    """MLflow's tracking store as the resolvers see it: a workspace-scoped ``get_experiment``."""

    def __init__(self, experiments):
        self.experiments = experiments

    def get_experiment(self, experiment_id):
        from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace

        found = self.experiments.get(str(experiment_id))
        if found is None or (config.MLFLOW_ENABLE_WORKSPACES and found[1] != current_grant_workspace()):
            raise MlflowException(f"No experiment {experiment_id}", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(experiment_id=str(experiment_id), name=found[0], workspace=found[1])


@contextmanager
def as_request(username: str, workspace: str | None):
    """Run as a request of ``username`` naming ``workspace`` (None: no header)."""
    token = set_auth_context(AuthContext(username=username, is_admin=False, workspace=workspace))
    try:
        yield
    finally:
        clear_auth_context(token)


def _try(write):
    try:
        write()
    except MlflowException:
        pass  # a duplicate grant drawn twice


def _random_grants(store, rng: random.Random) -> None:
    """Grant random permissions on every resource type, in random workspaces."""
    for user in USERS:
        store.create_user(user, user)
    store.populate_groups(GROUPS)
    for user in USERS:
        store.set_user_groups(user, rng.sample(GROUPS, rng.randint(0, 2)))

    def perm():
        return rng.choice(PERMISSIONS)

    def priority():
        return rng.choice([1, 1, 2])

    def some(population, k_max=2):
        return rng.sample(population, rng.randint(0, min(k_max, len(population))))

    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True):
        for _ in range(3):
            # Name-keyed grants are recorded in the workspace the creating request names; patterns
            # in that workspace, or in every workspace when none is named.
            workspace = rng.choice(WORKSPACES + [None])
            with as_request("admin", workspace):
                for user in USERS:
                    for exp in some(list(EXPERIMENTS)):
                        _try(lambda: store.create_experiment_permission(exp, user, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_registered_model_permission(name, user, perm()))
                    for exp, scorer in some(SCORERS):
                        _try(lambda: store.create_scorer_permission(exp, scorer, user, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_gateway_endpoint_permission(name, user, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_gateway_secret_permission(name, user, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_gateway_model_definition_permission(name, user, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_mcp_server_permission(name, user, perm()))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_experiment_regex_permission(pattern, priority(), perm(), user))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_registered_model_regex_permission(pattern, priority(), perm(), user))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_prompt_regex_permission(pattern, priority(), perm(), user))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_scorer_regex_permission(pattern, priority(), perm(), user))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_gateway_endpoint_regex_permission(pattern, priority(), perm(), user))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_gateway_secret_regex_permission(pattern, priority(), perm(), user))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_gateway_model_definition_regex_permission(pattern, priority(), perm(), user))
                for group in GROUPS:
                    for exp in some(list(EXPERIMENTS)):
                        _try(lambda: store.create_group_experiment_permission(group, exp, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_group_model_permission(group, name, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_group_prompt_permission(group, name, perm()))
                    for exp, scorer in some(SCORERS):
                        _try(lambda: store.create_group_scorer_permission(group, exp, scorer, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_group_gateway_endpoint_permission(group, name, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_group_gateway_secret_permission(group, name, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_group_gateway_model_definition_permission(group, name, perm()))
                    for name in some(NAMES):
                        _try(lambda: store.create_group_mcp_server_permission(group, name, perm()))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_group_experiment_regex_permission(group, pattern, priority(), perm()))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_group_registered_model_regex_permission(group, pattern, priority(), perm()))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_group_prompt_regex_permission(pattern, priority(), perm(), group))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_group_scorer_regex_permission(group, pattern, priority(), perm()))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_group_gateway_endpoint_regex_permission(group, pattern, priority(), perm()))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_group_gateway_secret_regex_permission(group, pattern, priority(), perm()))
                    for pattern in some(PATTERNS):
                        _try(lambda: store.create_group_gateway_model_definition_regex_permission(group, pattern, priority(), perm()))
        # Workspace grants, for the workspace fallback.
        for user in USERS:
            for workspace in some(WORKSPACES):
                _try(lambda: store.create_workspace_permission(workspace, user, perm()))
            for pattern in some(["^ws-", ".*", "a$"], 1):
                _try(lambda: store.create_workspace_regex_permission(pattern, priority(), perm(), user))
        for group in GROUPS:
            for workspace in some(WORKSPACES):
                _try(lambda: store.create_workspace_group_permission(workspace, group, perm()))
            for pattern in some(["^ws-", ".*", "b$"], 1):
                _try(lambda: store.create_workspace_group_regex_permission(group, pattern, priority(), perm()))


def _legacy_grants(store, rng: random.Random) -> None:
    """Rows only a rolling upgrade or the backfill leaves behind, written straight to the tables.

    Unassigned (``workspace IS NULL``) grants beside a ``default`` one and beside each other, and
    grants the backfill could not place (``::unresolved``). With workspaces disabled the
    per-resource lookup decides between duplicates by its precedence (``default``, else the
    oldest); the bulk read must decide identically.
    """
    from mlflow_oidc_auth.db.models import (
        SqlGatewayEndpointPermission,
        SqlGroup,
        SqlMCPServerPermission,
        SqlRegisteredModelGroupPermission,
        SqlRegisteredModelPermission,
        SqlUser,
    )
    from mlflow_oidc_auth.utils.grant_workspace import UNRESOLVED_WORKSPACE

    tables = [
        (SqlRegisteredModelPermission, "name"),
        (SqlGatewayEndpointPermission, "endpoint_id"),
        (SqlMCPServerPermission, "name"),
    ]
    with store.ManagedSessionMaker(read_only=False) as session:
        user_ids = {u.username: u.id for u in session.query(SqlUser).filter(SqlUser.username.in_(USERS)).all()}
        group_ids = [g.id for g in session.query(SqlGroup).filter(SqlGroup.group_name.in_(GROUPS)).all()]
        for model, column in tables:
            for user in USERS:
                for name in rng.sample(NAMES, 2):
                    for workspace in rng.sample([None, None, UNRESOLVED_WORKSPACE, "default"], rng.randint(1, 3)):
                        try:
                            with session.begin_nested():
                                session.add(model(**{column: name, "user_id": user_ids[user], "permission": rng.choice(PERMISSIONS), "workspace": workspace}))
                        except IntegrityError:
                            pass  # a second ``default`` grant on the same name
        for group_id in group_ids:
            for name in rng.sample(NAMES, 2):
                for workspace in rng.sample([None, None, UNRESOLVED_WORKSPACE], rng.randint(1, 2)):
                    session.add(SqlRegisteredModelGroupPermission(name=name, group_id=group_id, permission=rng.choice(PERMISSIONS), workspace=workspace))
                    session.flush()
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    flush_permission_cache()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A real store, made the singleton, plus a fake tracking store the resolvers both read."""
    import mlflow_oidc_auth.store as store_module
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils import permissions
    from mlflow_oidc_auth.utils.workspace_cache import flush_workspace_cache

    store = SqlAlchemyStore()
    store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setattr(store_module, "store", store)
    tracking = FakeTrackingStore(EXPERIMENTS)
    monkeypatch.setattr(permissions, "_get_tracking_store", lambda: tracking)
    permissions.flush_permission_cache()
    flush_workspace_cache()
    yield store, (lambda: tracking)
    permissions.flush_permission_cache()
    flush_workspace_cache()
    store.engine.dispose()


def _modes():
    """``(workspaces enabled, workspace the request names)`` pairs to evaluate in."""
    yield False, None
    for workspace in [None] + WORKSPACES:
        yield True, workspace


def _resources():
    """``(resource type, resource id, scorer name)`` of every resource, plus some that do not exist."""
    for experiment_id in list(EXPERIMENTS) + ["99"]:
        yield "experiment", experiment_id, None
    for resource_type in NAME_KEYED:
        for name in NAMES + ["missing"]:
            yield resource_type, name, None
    for experiment_id, scorer in SCORERS + [("1", "beta-1"), ("99", "alpha-s")]:
        yield "scorer", experiment_id, scorer


@pytest.mark.parametrize("seed", range(10))
def test_resolve_matches_pre_refactor_resolve_permission(world, seed):
    """For every (user, resource, workspace), ``grant_context.resolve`` equals the oracle."""
    store, tracking = world
    rng = random.Random(seed)
    _random_grants(store, rng)
    if seed % 3 == 0:
        _legacy_grants(store, rng)
    order = ["user", "group", "regex", "group-regex"]
    if seed % 2:
        rng.shuffle(order)
    default = rng.choice(["NO_PERMISSIONS", "READ", "MANAGE"])

    compared = 0
    with patch.object(config, "PERMISSION_SOURCE_ORDER", order), patch.object(config, "DEFAULT_MLFLOW_PERMISSION", default):
        for enabled, request_workspace in _modes():
            with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", enabled):
                grant_context.flush_grant_contexts()
                for user in USERS:
                    with as_request(user, request_workspace):
                        # A single-check context (direct grants by SQL) and a bulk one (in memory).
                        for bulk in (False, True):
                            ctx = load_grant_context(user, bulk=bulk)
                            for resource_type, resource_id, scorer in _resources():
                                kwargs = {"scorer_name": scorer} if scorer else {}
                                expected = oracle_resolve_permission(store, tracking, resource_type, resource_id, user, **kwargs)
                                actual = resolve(ctx, resource_type, resource_id, name=scorer)
                                assert actual == expected, (seed, bulk, enabled, request_workspace, user, resource_type, resource_id, scorer)
                                compared += 1
                                if resource_type == "experiment":
                                    # The caller holds the entity: MLflow found it in the request's workspace.
                                    try:
                                        entity = tracking().get_experiment(resource_id)
                                    except MlflowException:
                                        continue
                                    actual = resolve(ctx, "experiment", resource_id, name=entity.name, resource_workspace=entity.workspace)
                                    assert actual == expected, (seed, bulk, enabled, request_workspace, user, resource_id, "entity")
    assert compared > 1000


@pytest.mark.parametrize("seed", range(4))
def test_resolve_permission_matches_pre_refactor(world, seed):
    """The public single-resource entry point, with its result cache, agrees with the oracle too."""
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache, resolve_permission

    store, tracking = world
    _random_grants(store, random.Random(1000 + seed))
    for enabled, request_workspace in _modes():
        with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", enabled):
            flush_permission_cache()
            for user in USERS:
                with as_request(user, request_workspace):
                    for resource_type, resource_id, scorer in _resources():
                        kwargs = {"scorer_name": scorer} if scorer else {}
                        expected = oracle_resolve_permission(store, tracking, resource_type, resource_id, user, **kwargs)
                        assert resolve_permission(resource_type, resource_id, user, **kwargs) == expected


# ---------------------------------------------------------------------------
# Required negative tests
# ---------------------------------------------------------------------------


def test_batch_denies_experiment_outside_request_workspace(world):
    """MANAGE on the request workspace does not reach an experiment of another workspace (batch path).

    The batch path used to apply the workspace fallback without checking that the experiment was in
    the request's workspace; it now judges each experiment by its own ``workspace``.
    """
    from mlflow_oidc_auth.utils.batch_permissions import batch_resolve_experiment_permissions, filter_manageable_experiments

    store, _ = world
    store.create_user("alice", "Alice")
    store.create_workspace_permission("ws-a", "alice", "MANAGE")
    outside = SimpleNamespace(experiment_id="7", name="theirs", workspace="ws-b")
    inside = SimpleNamespace(experiment_id="8", name="ours", workspace="ws-a")

    with (
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
        patch("mlflow.utils.workspace_context.get_request_workspace", return_value="ws-a"),
        as_request("alice", "ws-a"),
    ):
        results = batch_resolve_experiment_permissions("alice", [outside, inside])
        manageable = filter_manageable_experiments("alice", [outside, inside])

    assert results["7"] == PermissionResult(NO_PERMISSIONS, "workspace-deny")
    assert results["7"].permission.can_read is False
    # Control: the same grant does reach an experiment of the request's workspace.
    assert results["8"].kind == "workspace" and results["8"].permission.can_manage
    assert manageable == [inside]


@contextmanager
def _deny_by_default():
    with (
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", False),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
        patch.object(config, "PERMISSION_SOURCE_ORDER", ["user", "group", "regex", "group-regex"]),
    ):
        yield


def _cached_section_keys():
    return [key for key in grant_context._get_section_cache()._cache.keys()]


def test_revoke_invalidates_context(world):
    """A cached context never outlives a revoked group grant."""
    from mlflow_oidc_auth.utils.permissions import resolve_permission

    store, _ = world
    store.create_user("alice", "Alice")
    store.populate_groups(["team"])
    store.set_user_groups("alice", ["team"])
    store.create_group_experiment_permission("team", "1", "MANAGE")

    with _deny_by_default():
        assert resolve_permission("experiment", "1", "alice").permission.can_manage
        assert resolve(load_grant_context("alice", bulk=True), "experiment", "1", name="alpha-1").permission.can_manage
        assert _cached_section_keys(), "precondition: the context is cached"

        store.delete_group_experiment_permission("team", "1")

        assert resolve_permission("experiment", "1", "alice") == PermissionResult(NO_PERMISSIONS, "fallback")
        assert resolve(load_grant_context("alice", bulk=True), "experiment", "1", name="alpha-1") == PermissionResult(NO_PERMISSIONS, "fallback")


@pytest.mark.parametrize("removal", ["remove_user_from_group", "set_user_groups"])
def test_membership_removal_invalidates_context(world, removal):
    """Leaving a group drops that group's grants from every cached context at once."""
    from mlflow_oidc_auth.utils.permissions import resolve_permission

    store, _ = world
    store.create_user("alice", "Alice")
    store.populate_groups(["team", "other"])
    store.set_user_groups("alice", ["team", "other"])
    store.create_group_model_permission("team", "alpha-1", "EDIT")
    store.create_group_experiment_regex_permission("team", ".*", 1, "READ")

    with _deny_by_default():
        assert resolve_permission("registered_model", "alpha-1", "alice").permission.can_update
        assert resolve(load_grant_context("alice", bulk=True), "registered_model", "alpha-1").permission.can_update
        assert resolve(load_grant_context("alice", bulk=True), "experiment", "1", name="alpha-1").kind == "group-regex"

        if removal == "remove_user_from_group":
            store.remove_user_from_group("alice", "team")
        else:
            store.set_user_groups("alice", ["other"])

        assert resolve_permission("registered_model", "alpha-1", "alice") == PermissionResult(NO_PERMISSIONS, "fallback")
        ctx = load_grant_context("alice", bulk=True)
        assert resolve(ctx, "registered_model", "alpha-1") == PermissionResult(NO_PERMISSIONS, "fallback")
        assert resolve(ctx, "experiment", "1", name="alpha-1") == PermissionResult(NO_PERMISSIONS, "fallback")


def test_unchanged_membership_sync_keeps_the_context(world):
    """A login that re-syncs the same groups changes nothing, so it flushes nothing (issue #456)."""
    store, _ = world
    store.create_user("alice", "Alice")
    store.populate_groups(["team"])
    store.set_user_groups("alice", ["team"])
    store.create_group_model_permission("team", "alpha-1", "EDIT")

    with _deny_by_default():
        resolve(load_grant_context("alice", bulk=True), "registered_model", "alpha-1")
        before = _cached_section_keys()
        store.set_user_groups("alice", ["team"])
        assert _cached_section_keys() == before != []


def test_no_permissions_grant_beats_lower_source(world):
    """Pins NO_PERMISSIONS handling within and across sources, as the oracle has it.

    - Across sources the configured order decides: a user grant of NO_PERMISSIONS denies whatever
      the group grants, and a READ user grant is not cut down by a group NO_PERMISSIONS.
    - Within a source NO_PERMISSIONS outranks everything: across groups, and among the patterns
      of the best priority tier. A better-priority pattern still beats a worse-priority denial.
    - A grant of NO_PERMISSIONS is final: the workspace permission never overrides it.
    """
    store, tracking = world
    for user in ("deny-user", "read-user", "groups", "tier", "priority", "ws"):
        store.create_user(user, user)
    store.populate_groups(["managers", "blocked", "readers"])
    store.set_user_groups("deny-user", ["managers"])
    store.set_user_groups("read-user", ["blocked"])
    store.set_user_groups("groups", ["managers", "blocked"])
    store.set_user_groups("tier", ["managers"])
    store.create_group_experiment_permission("managers", "1", "MANAGE")
    store.create_group_experiment_permission("blocked", "1", "NO_PERMISSIONS")
    store.create_experiment_permission("1", "deny-user", "NO_PERMISSIONS")
    store.create_experiment_permission("1", "read-user", "READ")
    store.create_registered_model_regex_permission("^alpha", 1, "MANAGE", "tier")
    store.create_registered_model_regex_permission(".*", 1, "NO_PERMISSIONS", "tier")
    store.create_registered_model_regex_permission("^alpha", 1, "READ", "priority")
    store.create_registered_model_regex_permission(".*", 2, "NO_PERMISSIONS", "priority")
    store.create_experiment_permission("3", "ws", "NO_PERMISSIONS")
    store.create_workspace_permission("default", "ws", "MANAGE")

    cases = [
        ("deny-user", "experiment", "1", NO_PERMISSIONS, "user"),
        ("read-user", "experiment", "1", get_permission("READ"), "user"),
        ("groups", "experiment", "1", NO_PERMISSIONS, "group"),
        ("tier", "registered_model", "alpha-1", NO_PERMISSIONS, "regex"),
        ("priority", "registered_model", "alpha-1", get_permission("READ"), "regex"),
    ]
    with _deny_by_default():
        for user, resource_type, resource_id, permission, kind in cases:
            with as_request(user, None):
                expected = oracle_resolve_permission(store, tracking, resource_type, resource_id, user)
                actual = resolve(load_grant_context(user), resource_type, resource_id)
            assert actual == expected == PermissionResult(permission, kind), user

    with (
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
        as_request("ws", "default"),
    ):
        expected = oracle_resolve_permission(store, tracking, "experiment", "3", "ws")
        actual = resolve(load_grant_context("ws"), "experiment", "3", name="alpha-3", resource_workspace="default")
        # Control: an experiment without a grant of its own does take the workspace MANAGE.
        other = resolve(load_grant_context("ws"), "experiment", "5", name="other", resource_workspace="default")
    assert actual == expected == PermissionResult(NO_PERMISSIONS, "user")
    assert other.kind == "workspace" and other.permission.can_manage


def test_pattern_grant_does_not_cross_into_entity_workspace(world):
    """An entity of another workspace gets nothing, whatever source would match it.

    alice holds a ``.*`` MANAGE pattern for ws-a and a direct grant on the experiment. A request in
    ws-a handed the entity of an experiment in ws-b must not read either for it: grant reads and
    pattern scope belong to the request's workspace.
    """
    from mlflow_oidc_auth.utils.batch_permissions import batch_resolve_experiment_permissions

    store, _ = world
    store.create_user("alice", "Alice")
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True), as_request("admin", "ws-a"):
        store.create_experiment_regex_permission(".*", 1, "MANAGE", "alice")
    store.create_experiment_permission("2", "alice", "MANAGE")
    foreign = SimpleNamespace(experiment_id="2", name="beta-2", workspace="ws-b")
    local = SimpleNamespace(experiment_id="1", name="alpha-1", workspace="ws-a")

    with (
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
        patch("mlflow.utils.workspace_context.get_request_workspace", return_value="ws-a"),
        as_request("alice", "ws-a"),
    ):
        for bulk in (False, True):
            ctx = load_grant_context("alice", bulk=bulk)
            denied = resolve(ctx, "experiment", "2", name="beta-2", resource_workspace="ws-b")
            assert denied == PermissionResult(NO_PERMISSIONS, "workspace-deny"), bulk
            # Control: the same pattern does reach an experiment of the request's workspace.
            assert resolve(ctx, "experiment", "1", name="alpha-1", resource_workspace="ws-a").kind == "regex"
        results = batch_resolve_experiment_permissions("alice", [foreign, local])

    assert results["2"] == PermissionResult(NO_PERMISSIONS, "workspace-deny")
    assert results["1"].kind == "regex" and results["1"].permission.can_manage


def test_entity_workspace_patterns_scope_to_the_entitys_workspace(world):
    """An entity of another workspace the caller can read is judged by that workspace's patterns.

    alice reads ws-b. A pattern scoped to ws-a must not grant on a ws-b experiment, and a ws-b
    NO_PERMISSIONS pattern must deny it despite the READ alice holds on ws-b.
    """
    store, _ = world
    store.create_user("alice", "Alice")
    store.create_workspace_permission("ws-b", "alice", "READ")
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True), as_request("admin", "ws-a"):
        store.create_experiment_regex_permission("^beta", 1, "MANAGE", "alice")
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True), as_request("admin", "ws-b"):
        store.create_experiment_regex_permission("^gamma", 1, "NO_PERMISSIONS", "alice")

    with (
        patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True),
        patch.object(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS"),
        patch("mlflow.utils.workspace_context.get_request_workspace", return_value="ws-a"),
        as_request("alice", "ws-a"),
    ):
        for bulk in (False, True):
            ctx = load_grant_context("alice", bulk=bulk)
            # The ws-a pattern matches the name but belongs to another workspace: ws-b's READ applies.
            beta = resolve(ctx, "experiment", "7", name="beta-7", resource_workspace="ws-b")
            assert beta.kind == "workspace" and beta.permission.name == "READ", bulk
            # The ws-b denial pattern outranks the READ alice holds on ws-b.
            gamma = resolve(ctx, "experiment", "8", name="gamma-8", resource_workspace="ws-b")
            assert gamma == PermissionResult(NO_PERMISSIONS, "regex"), bulk


def test_a_pattern_match_never_logs_the_resource_name(caplog):
    """The matcher's debug line names the pattern, never the resource (a gateway secret's name)."""
    import logging

    from mlflow_oidc_auth.utils.grant_context import best_matching_regex, logger

    rule = SimpleNamespace(id=42, regex="^prod-", priority=1, permission="USE", workspace="*")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        assert best_matching_regex([rule], "prod-openai-key", "gateway name", "*") is rule
    assert "prod-openai-key" not in caplog.text
    assert "42" in caplog.text


@pytest.mark.parametrize("delete", ["delete_user", "delete_user_with_hook"])
def test_deleted_user_grants_do_not_reach_a_recreated_account(world, delete):
    """A user re-created under a deleted user's name within the TTL starts with no grants."""
    from mlflow_oidc_auth.utils.permissions import resolve_permission

    store, _ = world
    store.create_user("alice", "Alice")
    store.populate_groups(["team"])
    store.set_user_groups("alice", ["team"])
    store.create_group_model_permission("team", "alpha-1", "MANAGE")
    store.create_registered_model_regex_permission("^beta", 1, "MANAGE", "alice")

    with _deny_by_default():
        ctx = load_grant_context("alice", bulk=True)
        assert resolve(ctx, "registered_model", "alpha-1").permission.can_manage
        assert resolve_permission("registered_model", "beta-2", "alice").permission.can_manage
        assert _cached_section_keys(), "precondition: alice's grants are cached"

        if delete == "delete_user":
            store.delete_user("alice", admin_override=True)
        else:
            store.delete_user_with_hook("alice", lambda session, user: None, admin_override=True)
        store.create_user("alice", "Alice again")

        assert resolve(load_grant_context("alice", bulk=True), "registered_model", "alpha-1") == PermissionResult(NO_PERMISSIONS, "fallback")
        assert resolve_permission("registered_model", "beta-2", "alice") == PermissionResult(NO_PERMISSIONS, "fallback")


@pytest.mark.parametrize("delete", ["delete_user", "delete_user_with_hook"])
def test_deleted_user_workspace_grant_does_not_reach_a_recreated_account(world, delete):
    """alice's cached MANAGE on ``finance`` is gone the moment alice is deleted and re-created."""
    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    store, _ = world
    store.create_user("alice", "Alice")
    store.create_workspace_permission("finance", "alice", "MANAGE")
    with patch.object(config, "MLFLOW_ENABLE_WORKSPACES", True):
        assert get_workspace_permission_cached("alice", "finance").can_manage, "precondition: the grant is cached"

        if delete == "delete_user":
            store.delete_user("alice", admin_override=True)
        else:
            store.delete_user_with_hook("alice", lambda session, user: None, admin_override=True)
        store.create_user("alice", "Alice again")

        assert get_workspace_permission_cached("alice", "finance") is None
        with as_request("alice", "finance"):
            ctx = load_grant_context("alice", bulk=True)
            assert resolve(ctx, "registered_model", "alpha-1") == PermissionResult(NO_PERMISSIONS, "workspace-deny")
