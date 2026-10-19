"""One grant resolver for permission checks and list filtering (issue #460).

Before this module, permission resolution was implemented three times: per resource in
``utils/permissions.py`` (one store round trip per source, per resource), in the FastAPI batch
path (``utils/batch_permissions.py``, with its own source walk and its own workspace fallback),
and for workspaces in ``utils/workspace_cache.py``. Every MLflow search filter used the
per-resource path once per scanned row. This module is now the single implementation of the
decision; the three call sites are thin wrappers over it.

The model:

* A :class:`GrantContext` belongs to one user and one request (or one batch). It holds the request
  workspace (for the workspace fallback) and the grant workspace (for name-keyed grants and pattern
  scope).
* **Patterns** (the user's and the user's groups' regex grants) are read once per resource type, on
  first use, and matched in memory.
* **Direct grants** (the user's own, and the folded grants of the user's groups) are read in one of
  two ways. A *single-resource* context looks each one up with the same indexed per-resource query
  as before, so a check never reads a user's whole grant set. A *bulk* context (list filters,
  batch endpoints) reads all of the user's direct grants on the type once and matches names in
  memory — but only on databases whose ``=`` compares names exactly (SQLite, PostgreSQL). Where
  ``=`` ignores case, accents or trailing spaces (MySQL, MariaDB, SQL Server, ...), names are never
  matched in Python: every direct grant is looked up in SQL, with the database's own semantics.
* Both reads are cached across requests per ``(user, grant scope, resource type)`` in their own
  namespace, for ``PERMISSION_CACHE_TTL_SECONDS``. Every store wrapper that flushes the permission
  cache flushes them too (see ``permissions.flush_permission_cache``), behind the shared
  invalidation generation guard (``cache/generation.py``): a load racing an invalidation is used
  for its own request but never cached. A failed load raises and caches nothing. Each read records
  when it was made, so a decision derived from it is never cached past the read's own expiry.
* :func:`resolve` applies the semantics once: ``PERMISSION_SOURCE_ORDER`` first match, the
  strongest grant within a source, ``DEFAULT_MLFLOW_PERMISSION`` as the fallback, and the
  workspace fallback including the experiment-in-request-workspace check.

Nothing here runs in ``AuthMiddleware``: a context is only loaded by the hooks and routers that
resolve permissions, so the authentication path's statement budget is unchanged.
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.cache import CacheBackend, get_cache_backend
from mlflow_oidc_auth.cache.generation import GenerationGuard, key_part, make_key
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, compare_permissions, get_permission, in_regex_grant_order
from mlflow_oidc_auth.utils.grant_workspace import EVERY_WORKSPACE, current_grant_workspace, pattern_in_scope

logger = get_logger()

# ---------------------------------------------------------------------------
# Resource types
# ---------------------------------------------------------------------------

# The names come from the one place grant kinds are defined (``permission_kinds``, #472).
EXPERIMENT = permission_kinds.EXPERIMENT.name
REGISTERED_MODEL = permission_kinds.REGISTERED_MODEL.name
PROMPT = permission_kinds.PROMPT.name
SCORER = permission_kinds.SCORER.name
GATEWAY_ENDPOINT = permission_kinds.GATEWAY_ENDPOINT.name
GATEWAY_SECRET = permission_kinds.GATEWAY_VAULT.name
GATEWAY_MODEL_DEFINITION = permission_kinds.GATEWAY_MODEL_DEFINITION.name
MCP_SERVER = permission_kinds.MCP_SERVER.name

#: Every source name ``PERMISSION_SOURCE_ORDER`` may hold. A resource type without one of them
#: (MCP servers have no pattern sources) skips it silently; only an unknown name is a misconfiguration.
KNOWN_PERMISSION_SOURCES = frozenset(("user", "group", "regex", "group-regex"))

# Resource types whose grants are keyed by an experiment id. MLflow keeps those ids unique across
# workspaces, so the workspace a request names says nothing about the experiment: the workspace
# fallback must first establish that the experiment is in the request's workspace.
_EXPERIMENT_KEYED = frozenset((EXPERIMENT, SCORER))


def source_label(source_name: str) -> str:
    """The plugin's own name for a configured permission source, safe to log.

    ``PERMISSION_SOURCE_ORDER`` can be read from a secret store, so a configured value is never
    written to the log as such; the matching constant is.

    Parameters:
        source_name: A configured permission source.

    Returns:
        The known source it names, or ``"unrecognized"``.
    """
    return next((known for known in KNOWN_PERMISSION_SOURCES if known == source_name), "unrecognized")


# ---------------------------------------------------------------------------
# The pattern matcher (one for every resource type and for workspaces)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pattern:
    """A pattern grant with its regex compiled once, for the life of the cached section.

    Carries the attributes the matcher and ``pattern_in_scope`` read off a pattern entity.
    """

    id: Any
    regex: str
    priority: int
    permission: str
    workspace: Optional[str]
    compiled: Optional[re.Pattern]


def _compile_pattern(rule: Any) -> _Pattern:
    """Precompile one pattern grant. A pattern that does not compile is kept uncompiled.

    Patterns are validated when created, so this does not happen in practice; if it does, the
    matcher's ``re.match`` raises on it exactly where the per-resource path used to, rather than
    the whole context failing to load.
    """
    try:
        compiled: Optional[re.Pattern] = re.compile(rule.regex)
    except (re.error, TypeError):
        compiled = None
    workspace = getattr(rule, "workspace", None)
    return _Pattern(
        id=rule.id,
        regex=rule.regex,
        priority=rule.priority,
        permission=rule.permission,
        workspace=workspace if isinstance(workspace, str) else None,
        compiled=compiled,
    )


def _pattern_matches(rule: Any, name: str) -> bool:
    compiled = getattr(rule, "compiled", None)
    if isinstance(compiled, re.Pattern):
        return compiled.match(name) is not None
    return re.match(rule.regex, name) is not None


def best_matching_regex(regexes: Sequence[Any], name: str, label: str, workspace: str | None = None) -> Optional[Any]:
    """The pattern that decides ``name``'s permission, or None when none matches.

    Only in-scope patterns that match ``name`` count — in scope meaning they apply in the resource's
    workspace, ``workspace``, or the request's grant workspace when omitted (see
    ``utils/grant_workspace.pattern_in_scope``).

    - **Priority decides first.** Only matches in the best (lowest-number) priority tier count.
    - **Within that tier, permission rank decides**, by the same ``compare_permissions`` rule
      direct group grants fold with, so the two cannot drift. ``NO_PERMISSIONS`` ranks highest, so
      any ``NO_PERMISSIONS`` match in the tier wins; otherwise the most capable
      (MANAGE > EDIT > USE > READ).
    - Patterns are walked in ``(priority, id)`` order (``permissions.regex_grant_order``), so of
      equally ranked matches the lowest id is the one returned and logged.

    Parameters:
        regexes: Pattern grants with ``regex``, ``permission``, ``priority`` and ``id``; a
            precompiled pattern from a grant context is matched without recompiling.
        name: The resource name to match.
        label: What ``name`` is (e.g. ``"model name"``), for the debug log. The name itself is
            not logged.
        workspace: The resource's workspace; the request's grant workspace when omitted.

    Returns:
        The deciding pattern, or ``None`` when none matches.
    """
    best = None
    for regex in in_regex_grant_order(regexes):
        if best is not None and regex.priority > best.priority:
            break  # past the best tier
        if not pattern_in_scope(regex, workspace) or not _pattern_matches(regex, name):
            continue
        # compare_permissions(a, b) is True when b ranks at least as high as a: replace only on a
        # strictly higher rank, so equal ranks keep the lower id.
        if best is None or not compare_permissions(regex.permission, best.permission):
            best = regex
    if best is not None:
        # The resource name is never logged: for a gateway secret it is the secret's name.
        logger.debug("Regex permission found for a %s: %s from pattern %s (priority %s)", label, best.permission, getattr(best, "id", None), best.priority)
    return best


# ---------------------------------------------------------------------------
# Resource type specs: what each source of each type is loaded from
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TypeSpec:
    """Where one resource type's grants come from.

    The kind facts — the name, which tables it shares, which key column a pattern matches —
    come from ``permission_kinds``; this adds only how the store reads them.

    Attributes:
        kind: The grant kind (``permission_kinds``).
        label: What a pattern is matched against, for the debug log.
        user: Lists the user's direct grants (``store, username``), in precedence order, for bulk contexts.
        group: Lists the grants of the user's groups (``store, username``), one JOIN, for bulk contexts.
        regex: Lists the user's patterns (``store, username``), or None when the type has none.
        group_regex: Lists the patterns of the user's groups (``store, group_ids``), or None.
        key: The resource key of a direct grant, as :func:`resolve` looks it up.
        user_one: The user's direct grant on one resource (``store, resource id, name, username``),
            the indexed per-resource query; raises ``RESOURCE_DOES_NOT_EXIST`` when there is none.
        group_one: The strongest grant of the user's groups on one resource, likewise.
    """

    kind: permission_kinds.GrantKind
    label: str
    user: Callable[[Any, str], list]
    group: Callable[[Any, str], list]
    regex: Optional[Callable[[Any, str], list]]
    group_regex: Optional[Callable[[Any, List[int]], list]]
    key: Callable[[Any], Any]
    user_one: Callable[[Any, str, Optional[str], str], str]
    group_one: Callable[[Any, str, Optional[str], str], str]

    @property
    def name(self) -> str:
        """The resource type."""
        return self.kind.name

    @property
    def direct_table(self) -> str:
        """The kind owning the direct-grant tables; kinds that share them (prompts and registered
        models) share one read and one cache entry of them."""
        return self.kind.shares_tables_of or self.kind.name


_TYPE_SPECS: Dict[str, TypeSpec] = {
    EXPERIMENT: TypeSpec(
        kind=permission_kinds.EXPERIMENT,
        label="experiment",
        user=lambda s, u: s.list_user_grants(EXPERIMENT, u),
        group=lambda s, u: s.list_user_groups_grants(EXPERIMENT, u),
        regex=lambda s, u: s.list_experiment_regex_permissions(u),
        group_regex=lambda s, ids: s.list_group_experiment_regex_permissions_for_groups_ids(ids),
        key=lambda p: str(p.experiment_id),
        user_one=lambda s, r, n, u: s.get_experiment_permission(r, u).permission,
        group_one=lambda s, r, n, u: s.get_user_groups_experiment_permission(r, u).permission,
    ),
    REGISTERED_MODEL: TypeSpec(
        kind=permission_kinds.REGISTERED_MODEL,
        label="model name",
        user=lambda s, u: s.list_user_grants(REGISTERED_MODEL, u),
        group=lambda s, u: s.list_user_groups_grants(REGISTERED_MODEL, u),
        regex=lambda s, u: s.list_registered_model_regex_permissions(u),
        group_regex=lambda s, ids: s.list_group_registered_model_regex_permissions_for_groups_ids(ids),
        key=lambda p: p.name,
        user_one=lambda s, r, n, u: s.get_registered_model_permission(r, u).permission,
        group_one=lambda s, r, n, u: s.get_user_groups_registered_model_permission(r, u).permission,
    ),
    # Prompts are registered models: their direct grants are the registered-model grants. Only
    # their patterns are their own.
    PROMPT: TypeSpec(
        kind=permission_kinds.PROMPT,
        label="prompt name",
        user=lambda s, u: s.list_user_grants(REGISTERED_MODEL, u),
        group=lambda s, u: s.list_user_groups_grants(REGISTERED_MODEL, u),
        regex=lambda s, u: s.list_prompt_regex_permissions(u),
        group_regex=lambda s, ids: s.list_group_prompt_regex_permissions_for_groups_ids(ids),
        key=lambda p: p.name,
        user_one=lambda s, r, n, u: s.get_registered_model_permission(r, u).permission,
        group_one=lambda s, r, n, u: s.get_user_groups_registered_model_permission(r, u).permission,
    ),
    SCORER: TypeSpec(
        kind=permission_kinds.SCORER,
        label="scorer name",
        user=lambda s, u: s.list_user_grants(SCORER, u),
        group=lambda s, u: s.list_user_groups_grants(SCORER, u),
        regex=lambda s, u: s.list_scorer_regex_permissions(u),
        group_regex=lambda s, ids: s.list_group_scorer_regex_permissions_for_groups_ids(ids),
        key=lambda p: (str(p.experiment_id), p.scorer_name),
        user_one=lambda s, r, n, u: s.get_scorer_permission(r, n, u).permission,
        group_one=lambda s, r, n, u: s.get_user_groups_scorer_permission(r, n, u).permission,
    ),
    GATEWAY_ENDPOINT: TypeSpec(
        kind=permission_kinds.GATEWAY_ENDPOINT,
        label="gateway name",
        user=lambda s, u: s.list_user_grants(GATEWAY_ENDPOINT, u),
        group=lambda s, u: s.list_user_groups_grants(GATEWAY_ENDPOINT, u),
        regex=lambda s, u: s.list_gateway_endpoint_regex_permissions(u),
        group_regex=lambda s, ids: s.list_group_gateway_endpoint_regex_permissions_for_groups_ids(ids),
        key=lambda p: p.endpoint_id,
        user_one=lambda s, r, n, u: s.get_gateway_endpoint_permission(r, u).permission,
        group_one=lambda s, r, n, u: s.get_user_gateway_endpoint_group_permission(r, u).permission,
    ),
    GATEWAY_SECRET: TypeSpec(
        kind=permission_kinds.GATEWAY_VAULT,
        label="gateway name",
        user=lambda s, u: s.list_user_grants(GATEWAY_SECRET, u),
        group=lambda s, u: s.list_user_groups_grants(GATEWAY_SECRET, u),
        regex=lambda s, u: s.list_gateway_secret_regex_permissions(u),
        group_regex=lambda s, ids: s.list_group_gateway_secret_regex_permissions_for_groups_ids(ids),
        key=lambda p: p.secret_id,
        user_one=lambda s, r, n, u: s.get_gateway_secret_permission(r, u).permission,
        group_one=lambda s, r, n, u: s.get_user_gateway_secret_group_permission(r, u).permission,
    ),
    GATEWAY_MODEL_DEFINITION: TypeSpec(
        kind=permission_kinds.GATEWAY_MODEL_DEFINITION,
        label="gateway name",
        user=lambda s, u: s.list_user_grants(GATEWAY_MODEL_DEFINITION, u),
        group=lambda s, u: s.list_user_groups_grants(GATEWAY_MODEL_DEFINITION, u),
        regex=lambda s, u: s.list_gateway_model_definition_regex_permissions(u),
        group_regex=lambda s, ids: s.list_group_gateway_model_definition_regex_permissions_for_groups_ids(ids),
        key=lambda p: p.model_definition_id,
        user_one=lambda s, r, n, u: s.get_gateway_model_definition_permission(r, u).permission,
        group_one=lambda s, r, n, u: s.get_user_gateway_model_definition_group_permission(r, u).permission,
    ),
    # MCP servers have no pattern grants: no regex / group-regex sources.
    MCP_SERVER: TypeSpec(
        kind=permission_kinds.MCP_SERVER,
        label="MCP server name",
        user=lambda s, u: s.list_user_grants(MCP_SERVER, u),
        group=lambda s, u: s.list_user_groups_grants(MCP_SERVER, u),
        regex=None,
        group_regex=None,
        key=lambda p: p.name,
        user_one=lambda s, r, n, u: s.get_mcp_server_permission(r, u).permission,
        group_one=lambda s, r, n, u: s.get_user_mcp_server_group_permission(r, u).permission,
    ),
}

#: Every resource kind ``permission_kinds`` resolves per resource, and how its grants are read. A
#: kind without a spec fails here, at import; a spec without a kind is never reachable
#: (``tests/test_permission_kinds.py``).
PERMISSION_REGISTRY: Dict[str, TypeSpec] = {kind.name: _TYPE_SPECS[kind.name] for kind in permission_kinds.resource_kinds()}


def _store() -> Any:
    """The store singleton, read at call time so a test that swaps it is honored."""
    import mlflow_oidc_auth.store as store_module

    return store_module.store


# ---------------------------------------------------------------------------
# Sections: one resource type's grants for one user in one grant scope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DirectGrants:
    """All of one user's direct grants on one resource type in one grant scope (bulk contexts).

    Attributes:
        user: Resource key -> the user's direct grant.
        group: Resource key -> the strongest grant of any of the user's groups.
        loaded_at: When it was read (``time.time()``).
    """

    user: Mapping[Any, str]
    group: Mapping[Any, str]
    loaded_at: float


@dataclass(frozen=True)
class _Patterns:
    """One user's pattern grants on one resource type.

    Attributes:
        regex: The user's patterns, in ``(priority, id)`` order, precompiled.
        group_regex: The user's groups' patterns, in ``(priority, id)`` order, precompiled.
        loaded_at: When they were read (``time.time()``).
    """

    regex: Tuple[_Pattern, ...]
    group_regex: Tuple[_Pattern, ...]
    loaded_at: float


#: SQL dialects whose ``=`` on a name column compares exactly (byte for byte, case and accents
#: included) under their default collation. Only on these are names matched in Python.
_EXACT_MATCH_DIALECTS = frozenset(("sqlite", "postgresql"))


def _names_match_exactly(store: Any) -> bool:
    """Whether the auth database's ``=`` compares resource names exactly.

    MySQL and MariaDB (case-, accent- and trailing-space-insensitive by default), SQL Server
    (case-insensitive by default) and any unknown backend answer no: there, a direct grant is
    always looked up in SQL, so it matches exactly what the per-resource query matched before —
    including an explicit ``NO_PERMISSIONS`` written in another case.
    """
    try:
        return getattr(store.engine.dialect, "name", None) in _EXACT_MATCH_DIALECTS
    except Exception:
        return False


def _fold_group_grants(rows: Sequence[Any], key: Callable[[Any], Any]) -> Dict[Any, str]:
    """The strongest grant per resource across the user's groups.

    The same ``compare_permissions`` fold as the per-resource group lookup
    (``BaseGroupPermissionRepository.get_group_permission_for_user_resource``): a later grant
    replaces the current one when it ranks at least as high, so ``NO_PERMISSIONS`` (rank 100)
    outranks every other grant, and the result does not depend on row order (issue #253).
    """
    folded: Dict[Any, str] = {}
    for row in rows:
        resource = key(row)
        current = folded.get(resource)
        if current is None or compare_permissions(current, row.permission):
            folded[resource] = row.permission
    return folded


def _direct_user_grants(rows: Sequence[Any], key: Callable[[Any], Any]) -> Dict[Any, str]:
    """The user's direct grant per resource: the first row of each, the store's precedence order.

    ``store.list_user_grants`` returns rows in the order the per-resource lookup decides between
    duplicates by (``_GrantWorkspaceScope._precedence``: the ``default`` grant, else the oldest),
    so taking the first row of each resource applies exactly that lookup's rule.
    """
    grants: Dict[Any, str] = {}
    for row in rows:
        grants.setdefault(key(row), row.permission)
    return grants


def _load_direct(spec: TypeSpec, username: str) -> _DirectGrants:
    """Read all of ``username``'s direct grants on one type: two statements. Errors propagate."""
    store = _store()
    loaded_at = time.time()
    return _DirectGrants(
        user=_direct_user_grants(spec.user(store, username), spec.key),
        group=_fold_group_grants(spec.group(store, username), spec.key),
        loaded_at=loaded_at,
    )


def _load_patterns(spec: TypeSpec, username: str, group_ids: Callable[[], List[int]]) -> _Patterns:
    """Read ``username``'s patterns on one type: two statements, plus the group ids if not known yet."""
    store = _store()
    loaded_at = time.time()
    regex: Tuple[_Pattern, ...] = ()
    group_regex: Tuple[_Pattern, ...] = ()
    if spec.regex is not None:
        regex = tuple(_compile_pattern(r) for r in in_regex_grant_order(list(spec.regex(store, username))))
    if spec.group_regex is not None:
        ids = group_ids()
        if ids:
            group_regex = tuple(_compile_pattern(r) for r in in_regex_grant_order(list(spec.group_regex(store, ids))))
    return _Patterns(regex=regex, group_regex=group_regex, loaded_at=loaded_at)


# ---------------------------------------------------------------------------
# Cache of grant reads, with the shared invalidation generation guard
# ---------------------------------------------------------------------------

_PERMISSION_CACHE_DEFAULT_TTL = 30

# Grant scope of a deployment with workspaces disabled. MLflow's workspace names cannot contain ":".
_WORKSPACES_OFF_SCOPE = "::workspaces-off"

_section_cache: CacheBackend | None = None


def permission_cache_ttl() -> int:
    """``PERMISSION_CACHE_TTL_SECONDS``: how long grant reads (and decisions) are cached."""
    return getattr(config, "PERMISSION_CACHE_TTL_SECONDS", _PERMISSION_CACHE_DEFAULT_TTL)


#: The invalidation generation of the grant reads and of the decisions built from them.
GUARD = GenerationGuard("grant_context_generation", permission_cache_ttl)


def _get_section_cache() -> CacheBackend:
    """The cross-request cache of grant reads (lazy init).

    Its own namespace: neither the permission cache's nor the workspace caches' clear or prefix
    delete reaches into it, nor its into theirs. "_v2": entries changed shape in this release.
    """
    global _section_cache
    if _section_cache is None:
        _section_cache = get_cache_backend("grant_context_v2", maxsize=config.PERMISSION_CACHE_MAX_SIZE, ttl=permission_cache_ttl())
    return _section_cache


def _section_key(username: str, scope: str, resource_type: str, part: str) -> str:
    """``user:scope:type:part``, every component percent-encoded."""
    return make_key(username, scope, resource_type, part)


def flush_grant_contexts() -> None:
    """Drop every cached grant read of every user (full-flush semantics for grant changes).

    Called from ``permissions.flush_permission_cache``, so every store wrapper that flushes the
    permission cache flushes this too, and a membership sync flushes it only when the membership
    actually changed.
    """
    with GUARD.invalidating():
        _get_section_cache().clear()
    logger.debug("Grant context cache fully flushed")


def invalidate_user_grant_contexts(username: str) -> None:
    """Drop every cached grant read of one user, in every grant scope."""
    with GUARD.invalidating():
        _get_section_cache().delete_prefix(f"{key_part(username)}:")


def _cached(key: str, kind: type, load: Callable[[], Any], generation: Any) -> Any:
    """A grant read from the cache, reading and caching it on a miss.

    ``generation`` is the invalidation generation read before the context read anything. A read
    that fails raises and caches nothing; one that an invalidation overlapped answers this
    request but is not left cached: see ``GenerationGuard.store_unless_raced``.
    """
    cache = _get_section_cache()
    cached = cache.get(key)
    if isinstance(cached, kind):
        return cached
    value = load()
    GUARD.store_unless_raced(cache, key, value, generation, check_before_write=False)
    return value


# ---------------------------------------------------------------------------
# The grant context
# ---------------------------------------------------------------------------

_REQUEST = object()
_UNREAD = object()


def _grant_scope() -> Tuple[str, str]:
    """The grant workspace of the current request, and the cache scope its grants are read in.

    Direct grants on name-keyed resources are read for the request's grant workspace (with
    workspaces disabled, ``default``'s and unassigned ones), so a read is only valid for the
    scope it was made in; the scope is part of its cache key.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return DEFAULT_WORKSPACE_NAME, _WORKSPACES_OFF_SCOPE
    workspace = current_grant_workspace()
    return workspace, workspace


def _request_workspace() -> str | None:
    """The workspace the request names, None for a header-less request or with workspaces off."""
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return None
    from mlflow_oidc_auth.bridge.user import get_request_workspace

    return get_request_workspace()


class GrantContext:
    """One user's grants for one request (or batch), resolved in memory where that is exact.

    Build it with :func:`load_grant_context`. It is cheap to create: nothing is read until a
    resource is resolved. It is not shared between requests; only its grant reads are, through the
    section cache.

    Attributes:
        username: The user the grants are for.
        request_workspace: The workspace the workspace fallback uses; None skips it.
        grant_workspace: The workspace name-keyed grants and patterns are read in.
        bulk: Whether direct grants are read in full (lists) rather than one by one (checks).
    """

    def __init__(self, username: str, request_workspace: str | None, grant_workspace: str, scope: str, bulk: bool = False) -> None:
        self.username = username
        self.request_workspace = request_workspace
        self.grant_workspace = grant_workspace
        self.bulk = bulk
        self._scope = scope
        self._direct: Dict[str, _DirectGrants] = {}
        self._patterns: Dict[str, _Patterns] = {}
        self._in_memory_names: Optional[bool] = None
        self._group_ids: Optional[List[int]] = None
        self._workspace_permissions: Dict[str, Optional[Permission]] = {}
        self._experiment_names: Dict[str, str] = {}
        self._experiment_hints: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
        self._decisions: Dict[Tuple[str, str, Optional[str], Optional[str]], PermissionResult] = {}
        self._generation: Any = _UNREAD
        self.oldest_read: Optional[float] = None

    def generation(self) -> Any:
        """The invalidation generation, read once — before this context reads any grant.

        Every cache write the context makes (its grant reads, and the decision
        ``resolve_permission`` caches) is checked against it after the write, so one generation
        read serves the whole context.
        """
        if self._generation is _UNREAD:
            self._generation = GUARD.current()
        return self._generation

    def _check_scope(self) -> None:
        # The repositories read name-keyed grants in the grant workspace current at read time; the
        # cache key must name that same scope, or one workspace's grants would be cached (and, on
        # Redis, shared) as another's. Refuse rather than mislabel.
        if _grant_scope() != (self.grant_workspace, self._scope):
            raise RuntimeError("The request's grant workspace changed after its grant context was built")

    def _note_read(self, loaded_at: float) -> None:
        self.oldest_read = loaded_at if self.oldest_read is None else min(self.oldest_read, loaded_at)

    def group_ids(self) -> List[int]:
        """The ids of the user's groups, read once per context."""
        if self._group_ids is None:
            self._group_ids = list(_store().get_groups_ids_for_user(self.username))
        return self._group_ids

    def names_in_memory(self) -> bool:
        """Whether direct grants are matched in memory: a bulk context on an exact-``=`` database."""
        if self._in_memory_names is None:
            self._in_memory_names = self.bulk and _names_match_exactly(_store())
        return self._in_memory_names

    def direct(self, resource_type: str) -> _DirectGrants:
        """All of the user's direct grants on ``resource_type``'s grant table (bulk, exact-``=`` contexts)."""
        spec = PERMISSION_REGISTRY[resource_type]
        grants = self._direct.get(spec.direct_table)
        if grants is None:
            self._check_scope()
            generation = self.generation()
            key = _section_key(self.username, self._scope, spec.direct_table, "direct")
            grants = _cached(key, _DirectGrants, lambda: _load_direct(spec, self.username), generation)
            self._direct[spec.direct_table] = grants
            self._note_read(grants.loaded_at)
        return grants

    def patterns(self, resource_type: str) -> _Patterns:
        """The user's (and the user's groups') patterns on ``resource_type``."""
        patterns = self._patterns.get(resource_type)
        if patterns is None:
            spec = PERMISSION_REGISTRY[resource_type]
            self._check_scope()
            generation = self.generation()
            key = _section_key(self.username, self._scope, spec.name, "patterns")
            patterns = _cached(key, _Patterns, lambda: _load_patterns(spec, self.username, self.group_ids), generation)
            self._patterns[resource_type] = patterns
            self._note_read(patterns.loaded_at)
        return patterns

    def workspace_permission(self, workspace: str) -> Optional[Permission]:
        """The user's permission on ``workspace``, memoized for this context.

        Read through ``workspace_cache.get_workspace_permission_cached``, which keeps its own
        grant and denial caches and never caches a failed lookup (it returns None, fail closed).
        """
        if workspace not in self._workspace_permissions:
            from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

            self._workspace_permissions[workspace] = get_workspace_permission_cached(self.username, workspace)
        return self._workspace_permissions[workspace]

    def note_experiment(self, experiment_id: str, name: str | None = None, workspace: str | None = None) -> None:
        """Record what the caller already knows of an experiment, from an MLflow entity it holds.

        A name spares the tracking-store lookup a pattern match needs; a workspace spares the one
        the workspace fallback needs to confirm the experiment is in the request's workspace. Only
        values taken from MLflow's own entities belong here, never request input.
        """
        self._experiment_hints[str(experiment_id)] = (name or None, workspace or None)

    def experiment_hint(self, experiment_id: str) -> Tuple[Optional[str], Optional[str]]:
        """``(name, workspace)`` noted for an experiment, ``(None, None)`` when nothing was."""
        return self._experiment_hints.get(str(experiment_id), (None, None))

    def experiment_name(self, experiment_id: str) -> str:
        """The experiment's name, looked up once per context.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` when MLflow does not find the experiment;
                pattern sources then have nothing to match.
        """
        experiment_id = str(experiment_id)
        name = self._experiment_names.get(experiment_id) or self.experiment_hint(experiment_id)[0]
        if name is None:
            from mlflow_oidc_auth.utils import permissions

            name = permissions._get_tracking_store().get_experiment(experiment_id).name
        self._experiment_names[experiment_id] = name
        return name


def load_grant_context(username: str, workspace: Any = _REQUEST, *, bulk: bool = False) -> GrantContext:
    """A grant context for ``username`` in the current request.

    Nothing is read until a resource is resolved.

    Parameters:
        username: The user whose grants to resolve.
        workspace: The workspace the workspace fallback applies in. Omitted, the workspace the
            request names (None for a header-less request, or with workspaces disabled).
        bulk: For resolving many resources (list filters, batch endpoints): direct grants are
            read once per type and matched in memory where the database's ``=`` is exact.
            Leave it off for a single check, which then reads only the grants it needs.

    Returns:
        The context.
    """
    grant_workspace, scope = _grant_scope()
    request_workspace = _request_workspace() if workspace is _REQUEST else workspace
    return GrantContext(username, request_workspace, grant_workspace, scope, bulk=bulk)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def walk_sources(
    lookups: Mapping[str, Callable[[], Optional[str]]],
    source_order: Sequence[str],
    default_permission: str,
    to_permission: Callable[[str], Permission] = get_permission,
) -> PermissionResult:
    """``PERMISSION_SOURCE_ORDER`` first match: the one source walk.

    Parameters:
        lookups: Source name -> a lookup returning the grant's permission name, or None (or
            raising ``RESOURCE_DOES_NOT_EXIST``) when the source holds none. Any other error
            propagates — a source that failed is never skipped to reach a lower one.
        source_order: The configured source order.
        default_permission: ``DEFAULT_MLFLOW_PERMISSION``.
        to_permission: Turns a permission name into a ``Permission``.

    Returns:
        The first source's grant, else the default as ``fallback``.
    """
    for source_name in source_order:
        lookup = lookups.get(source_name)
        if lookup is None:
            if source_name not in KNOWN_PERMISSION_SOURCES:
                logger.warning("Invalid permission source configured in PERMISSION_SOURCE_ORDER; it is ignored")
            continue
        try:
            permission = lookup()
        except MlflowException as e:
            if e.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                raise
            permission = None
        if permission is not None:
            logger.debug("Permission found using source: %s", source_label(source_name))
            return PermissionResult(to_permission(permission), source_name)
        # Not the resource: it may be a gateway secret's name, which is not for the log.
        logger.debug("Permission not found using source: %s", source_label(source_name))
    logger.debug("Default permission used")
    return PermissionResult(to_permission(default_permission), "fallback")


def _lookups(
    ctx: GrantContext, resource_type: str, resource_id: str, name: str | None, pattern_workspace: str | None = None
) -> Dict[str, Callable[[], Optional[str]]]:
    """The source lookups of one resource. Each reads only when the walk reaches it.

    Patterns apply in ``pattern_workspace``: the context's grant workspace unless the resource is
    known to live in another one.
    """
    spec = PERMISSION_REGISTRY[resource_type]
    # The key columns and which of them a pattern matches come from the kind (``permission_kinds``):
    # a scorer is (experiment id, scorer name) and its patterns match the scorer name; an
    # experiment's patterns match its name, which only the tracking store knows.
    kind = spec.kind
    if len(kind.key_columns) > 1:
        if name is None:
            raise ValueError(f"A {kind.name} is resolved by its {' and '.join(kind.key_columns)}")
        key: Any = (str(resource_id), name)
    elif resource_type in _EXPERIMENT_KEYED:
        key = str(resource_id)
    else:
        key = resource_id
    if kind.regex_key_index is None:
        pattern_name: Callable[[], str] = (lambda: name) if name is not None else (lambda: ctx.experiment_name(resource_id))  # noqa: E731
    elif kind.regex_key_index == 0:
        pattern_name = lambda: resource_id  # noqa: E731
    else:
        pattern_name = lambda: name  # noqa: E731

    def direct(source: str) -> Callable[[], Optional[str]]:
        if ctx.names_in_memory():
            grants = ctx.direct(resource_type)
            table = grants.user if source == "user" else grants.group
            return lambda: table.get(key)
        one = spec.user_one if source == "user" else spec.group_one
        # The indexed per-resource query, with the database's own name comparison; a miss raises
        # RESOURCE_DOES_NOT_EXIST, which the walk reads as "no grant".
        return lambda: one(_store(), str(resource_id) if resource_type in _EXPERIMENT_KEYED else resource_id, name, ctx.username)

    def match(group: bool) -> Optional[str]:
        patterns = ctx.patterns(resource_type)
        rules = patterns.group_regex if group else patterns.regex
        if not rules:
            return None
        rule = best_matching_regex(rules, pattern_name(), spec.label, pattern_workspace or ctx.grant_workspace)
        return rule.permission if rule is not None else None

    lookups: Dict[str, Callable[[], Optional[str]]] = {"user": direct("user"), "group": direct("group")}
    if spec.regex is not None:
        lookups["regex"] = lambda: match(False)
    if spec.group_regex is not None:
        lookups["group-regex"] = lambda: match(True)
    return lookups


def workspace_fallback(
    result: PermissionResult,
    *,
    enabled: bool,
    request_workspace: str | None,
    resource_type: str | None,
    in_request_workspace: Callable[[], bool],
    workspace_permission: Callable[[str], Optional[Permission]],
) -> PermissionResult:
    """Defer a generic ``fallback`` result to the user's workspace permission (WSAUTH-C/WSAUTH-04).

    When workspaces are enabled and no resource-level grant was found, the user's permission on the
    request workspace replaces the global default; a user with none is denied (``workspace-deny``).
    A header-less request (no workspace) keeps the global default. An experiment, or a scorer of
    one, that is not in the request's workspace gets nothing: experiment ids are unique across
    workspaces, so a permission on workspace B must not reach an experiment of workspace A.

    Parameters:
        result: The resource-level result.
        enabled: Whether workspaces are enabled.
        request_workspace: The workspace the request names, or None.
        resource_type: The resource type, or None for a resource being created.
        in_request_workspace: Whether the (experiment-keyed) resource is in the request workspace.
        workspace_permission: The user's permission on a workspace, None when there is none.

    Returns:
        ``result`` unchanged, or the workspace-derived result.
    """
    if result.kind != "fallback" or not enabled or not request_workspace:
        return result
    if resource_type in _EXPERIMENT_KEYED and not in_request_workspace():
        return PermissionResult(NO_PERMISSIONS, "workspace-deny")
    ws_perm = workspace_permission(request_workspace)
    if ws_perm is not None:
        return PermissionResult(ws_perm, "workspace")
    return PermissionResult(NO_PERMISSIONS, "workspace-deny")


def _in_request_workspace(resource_id: str, resource_workspace: str | None, request_workspace: str) -> bool:
    """Whether an experiment is in the request workspace: from its entity when known, else MLflow."""
    if resource_workspace is not None:
        return resource_workspace == request_workspace
    from mlflow_oidc_auth.utils import permissions

    return permissions._experiment_in_request_workspace(resource_id)


def resolve(ctx: GrantContext, resource_type: str, resource_id: str, *, name: str | None = None, resource_workspace: str | None = None) -> PermissionResult:
    """The user's effective permission on one resource, resolved in memory against ``ctx``.

    ``PERMISSION_SOURCE_ORDER`` first match (user, group, regex, group-regex by default), the
    strongest grant within a source, ``DEFAULT_MLFLOW_PERMISSION`` when no source holds one, then
    the workspace fallback, including the experiment-in-request-workspace check.

    Parameters:
        ctx: The user's grant context.
        resource_type: One of :data:`PERMISSION_REGISTRY`.
        resource_id: The experiment id (experiments, scorers) or the resource name.
        name: For an experiment, its name when the caller has it (else looked up when a pattern
            source is reached); for a scorer, the scorer name (required).
        resource_workspace: The experiment's workspace when the caller has its entity. With
            workspaces enabled, one of another workspace than the one the request is served from
            is judged in its own workspace: only if the caller may access that workspace, with
            patterns scoped to it and its workspace permission as the fallback — never with the
            request workspace's patterns or permission. Omitted, the workspace fallback asks
            MLflow whether the experiment is in the request's workspace.

    Returns:
        The decision and the source it came from.

    Raises:
        KeyError: For an unknown resource type.
    """
    memo_key = (resource_type, str(resource_id), name, resource_workspace)
    known = ctx._decisions.get(memo_key)
    if known is not None:
        return known
    enabled = bool(config.MLFLOW_ENABLE_WORKSPACES)
    serving = ctx.request_workspace or ctx.grant_workspace
    if enabled and resource_type in _EXPERIMENT_KEYED and resource_workspace is not None and resource_workspace != serving:
        result = _resolve_in_entity_workspace(ctx, resource_type, resource_id, name, resource_workspace)
    else:
        result = walk_sources(_lookups(ctx, resource_type, resource_id, name), config.PERMISSION_SOURCE_ORDER, config.DEFAULT_MLFLOW_PERMISSION)
        request_workspace = ctx.request_workspace
        result = workspace_fallback(
            result,
            enabled=enabled,
            request_workspace=request_workspace,
            resource_type=resource_type,
            in_request_workspace=lambda: _in_request_workspace(resource_id, resource_workspace, request_workspace),
            workspace_permission=ctx.workspace_permission,
        )
    # Recorded after the workspace fallback, which may already have replaced it with a real
    # decision. A scorer's fallback is not final: effective_scorer_permission hands it to the
    # experiment, whose own resolution records a fallback if the default does decide.
    if result.kind == "fallback" and resource_type != SCORER:
        from mlflow_oidc_auth.utils.permissions import record_permission_fallback

        record_permission_fallback(resource_type, str(resource_id), ctx.username, result.permission)
    ctx._decisions[memo_key] = result
    return result


def _resolve_in_entity_workspace(ctx: GrantContext, resource_type: str, resource_id: str, name: str | None, workspace: str) -> PermissionResult:
    """An experiment (or scorer) the caller holds the entity of, living in another workspace.

    Judged as a request of that workspace would judge it: only a caller who may read that
    workspace gets anything; patterns apply as scoped to that workspace; and the fallback is the
    caller's permission on that workspace. Experiment and scorer grants are keyed by an id MLflow
    keeps unique across workspaces, so their direct grants are the same rows either way.
    """
    access = ctx.workspace_permission(workspace)
    if access is None or not access.can_read:
        return PermissionResult(NO_PERMISSIONS, "workspace-deny")
    result = walk_sources(_lookups(ctx, resource_type, resource_id, name, workspace), config.PERMISSION_SOURCE_ORDER, config.DEFAULT_MLFLOW_PERMISSION)
    return workspace_fallback(
        result,
        enabled=True,
        request_workspace=workspace,
        resource_type=resource_type,
        in_request_workspace=lambda: True,  # its own entity says so
        workspace_permission=ctx.workspace_permission,
    )


#: Kinds of a resolved permission that are not a grant on the resource itself.
NON_EXPLICIT_PERMISSION_KINDS = frozenset({"fallback", "workspace", "workspace-deny"})


def resolve_scorer(ctx: GrantContext, experiment_id: str, scorer_name: str, *, resource_workspace: str | None = None) -> PermissionResult:
    """A scorer's effective permission: its own grant, else its experiment's effective permission.

    Parameters:
        ctx: The user's grant context.
        experiment_id: The scorer's experiment.
        scorer_name: The scorer name.
        resource_workspace: The experiment's workspace when the caller has its entity.

    Returns:
        The scorer's grant, or the experiment's effective permission when there is none.
    """
    result = resolve(ctx, SCORER, experiment_id, name=scorer_name, resource_workspace=resource_workspace)
    if result.kind in NON_EXPLICIT_PERMISSION_KINDS:
        hint_name, hint_workspace = ctx.experiment_hint(experiment_id)
        return resolve(ctx, EXPERIMENT, experiment_id, name=hint_name, resource_workspace=resource_workspace or hint_workspace)
    return result


# ---------------------------------------------------------------------------
# Workspace permissions
# ---------------------------------------------------------------------------


def sanitize_log_value(value: str) -> str:
    """Strip control characters from a value before logging to prevent log injection."""
    return str(value).replace("\n", "").replace("\r", "").replace("\t", "")


def _is_not_found(error: Exception) -> bool:
    """Whether ``error`` is the store saying "no such row" — no grant, not a failure."""
    return isinstance(error, MlflowException) and error.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)


def match_workspace_pattern(regexes: Sequence[Any], workspace: str) -> Optional[Permission]:
    """The permission the best workspace pattern grants on ``workspace``, or None.

    The same matcher as every resource type: best priority tier, then permission rank
    (``NO_PERMISSIONS`` first, else the most capable). Workspace patterns have no workspace of
    their own, so every one is in scope.
    """
    rule = best_matching_regex(regexes, workspace, "workspace", EVERY_WORKSPACE)
    return get_permission(rule.permission) if rule is not None else None


def resolve_workspace_permission(username: str, workspace: str, source_order: Optional[Sequence[str]] = None) -> Tuple[Optional[Permission], bool]:
    """The user's permission on a workspace, walking ``PERMISSION_SOURCE_ORDER``; reports failures.

    Sources are read lazily in order and the first grant wins. A source that errors before a match
    makes the answer unknown: a lower source's grant may be wider than what the failed one holds,
    so the walk is denied (fail closed) rather than falling through to it.

    Parameters:
        username: The user.
        workspace: The workspace name.
        source_order: The configured source order; ``config.PERMISSION_SOURCE_ORDER`` when omitted.

    Returns:
        ``(permission, errored)``. ``errored`` True means the result must not be cached; the
        permission is then always None.
    """
    store = _store()
    order = config.PERMISSION_SOURCE_ORDER if source_order is None else source_order

    def direct(read: Callable[[], Any]) -> Callable[[], Optional[Permission]]:
        return lambda: get_permission(read().permission)

    def group_patterns() -> Optional[Permission]:
        group_ids = store.get_groups_ids_for_user(username)
        if not group_ids:
            return None
        return match_workspace_pattern(store.list_workspace_group_regex_permissions_for_groups_ids(group_ids) or [], workspace)

    sources: Dict[str, Callable[[], Optional[Permission]]] = {
        "user": direct(lambda: store.get_workspace_permission(workspace, username)),
        "group": direct(lambda: store.get_user_groups_workspace_permission(workspace, username)),
        "regex": lambda: match_workspace_pattern(store.list_workspace_regex_permissions(username) or [], workspace),
        "group-regex": group_patterns,
    }

    logger.debug("Looking up workspace permission for %s@%s", sanitize_log_value(username), sanitize_log_value(workspace))
    for source_name in order:
        lookup = sources.get(source_name)
        if lookup is None:
            logger.warning("Invalid workspace permission source: %s", source_label(source_name))
            continue
        try:
            permission = lookup()
        except Exception as e:
            if _is_not_found(e):
                logger.debug("No %s workspace permission for %s@%s", source_label(source_name), sanitize_log_value(username), sanitize_log_value(workspace))
                continue
            logger.warning(
                "Workspace permission lookup for %s@%s failed in source %s (%s); denying without caching",
                sanitize_log_value(username),
                sanitize_log_value(workspace),
                source_label(source_name),
                type(e).__name__,
            )
            return None, True
        if permission is not None:
            logger.debug(
                "Workspace permission found via source '%s' for %s@%s: %s",
                source_label(source_name),
                sanitize_log_value(username),
                sanitize_log_value(workspace),
                permission.name,
            )
            return permission, False
    logger.warning("No workspace permission found for %s@%s after checking all sources", sanitize_log_value(username), sanitize_log_value(workspace))
    return None, False
