# Phase 2: Workspace Auth Enforcement - Research

**Researched:** 2026-03-23
**Domain:** MLflow plugin authorization — workspace-level RBAC enforcement
**Confidence:** HIGH

## Summary

Phase 2 adds the security enforcement layer for workspaces on top of Phase 1's foundation (ORM models, middleware, feature flags). The core work is: (1) intercepting workspace protobuf RPCs via before_request hooks using regex path matching, (2) creating standalone workspace permission repositories with entity classes, (3) modifying `resolve_permission()` to add a workspace-level fallback that replaces `DEFAULT_MLFLOW_PERMISSION` when workspaces are enabled, (4) gating `CreateExperiment`/`CreateRegisteredModel` on workspace MANAGE permission, and (5) adding a TTLCache for workspace permission lookups on the hot path.

All patterns needed already exist in the codebase — workspace hooks follow the logged model hook pattern exactly, workspace repos follow existing repo conventions (but standalone per decision WSAUTH-B), and the permission resolution chain is well-structured for the workspace fallback insertion point. The `cachetools` library is already available as a transitive dependency.

**Primary recommendation:** Follow existing codebase patterns exactly — the logged model hook registration, standalone repository classes, and `resolve_permission()` wrapper approach are all proven patterns that minimize risk. The only novel design is the implicit default workspace access (code-level check instead of seeded DB rows).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **WSAUTH-A**: Regex pattern matching for workspace hook registration — following logged model pattern. `WORKSPACE_BEFORE_REQUEST_HANDLERS` dict + `WORKSPACE_BEFORE_REQUEST_VALIDATORS` via `_re_compile_path()`. `_find_validator()` updated for `/mlflow/workspaces` paths.
- **WSAUTH-B**: Standalone workspace permission repositories — NOT extending `BaseUserPermissionRepository` / `BaseGroupPermissionRepository`. Workspace is a tenant boundary, not a resource.
- **WSAUTH-C**: Wrap `resolve_permission()` for workspace fallback — `get_permission_from_store_or_default()` unchanged. When result.kind == "fallback" and workspaces enabled → workspace lookup → NO_PERMISSIONS if not found.
- **WSAUTH-D**: Code-level implicit default workspace access — no seeded rows. `'default'` workspace + `GRANT_DEFAULT_WORKSPACE_ACCESS=True` → implicit MANAGE permission without DB row.
- **WSAUTH-E**: Module-level TTLCache in `utils/workspace_cache.py` — `cachetools.TTLCache` with `(username, workspace)` key. Config: `WORKSPACE_CACHE_MAX_SIZE` (1024), `WORKSPACE_CACHE_TTL_SECONDS` (300). TTL-based invalidation only.
- **WSAUTH-F**: Conditional wrapper in `before_request_hook()` for CreateExperiment/CreateRegisteredModel workspace MANAGE gating — centralized check, not in individual validators.

### Agent's Discretion
- Exact workspace validator function names (e.g., `validate_can_create_workspace`, `validate_can_read_workspace`)
- Whether workspace validators live in `validators/workspace.py` or existing modules
- Exact entity class field names and property patterns
- Exact cache key format (tuple vs string)
- Whether workspace MANAGE check is inline or extracted to a helper
- Exact implicit permission level for `GRANT_DEFAULT_WORKSPACE_ACCESS` (MANAGE vs READ) — MANAGE recommended
- ListWorkspaces after_request filtering implementation details

### Deferred Ideas (OUT OF SCOPE)
- Workspace CRUD API (FastAPI routers for workspace-user and workspace-group permissions) — Phase 3
- Workspace permission delegation — Phase 3
- OIDC workspace claim extraction and auto-assignment — Phase 3
- Workspace management UI — Phase 4
- Explicit cache invalidation on workspace permission changes — v2
- Workspace-scoped search result filtering in after_request — v2
- Regex workspace permissions — v2
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WSAUTH-01 | before_request handlers for 5 workspace protobuf RPCs (Create/Get/List/Update/Delete) | Logged model hook pattern in `before_request.py` provides exact template; `_re_compile_path()` and `_find_validator()` ready for extension |
| WSAUTH-02 | Workspace-level user/group permissions with DB model, entity, repository, and store methods | ORM models exist (`SqlWorkspacePermission`, `SqlWorkspaceGroupPermission`); entity pattern in `entities/_base.py`; repo pattern in 28+ existing repos; store facade in `sqlalchemy_store.py` |
| WSAUTH-03 | CreateExperiment/CreateRegisteredModel gated on workspace MANAGE permission | `before_request_hook()` in `before_request.py` is the insertion point; `get_request_workspace()` bridge function ready; cached permission lookup enables hot-path check |
| WSAUTH-04 | Permission resolution with workspace-level fallback | `resolve_permission()` in `utils/permissions.py` returns `PermissionResult` with `.kind` field; "fallback" kind is the insertion point for workspace lookup |
| WSAUTH-05 | TTLCache for workspace permission lookups | `cachetools` 7.0.5 available as transitive dep; `TTLCache` well-suited for module-level singleton with lazy init |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Conventional Commits** required: `^(feat|fix|chore|docs|style|ci|refactor|perf|test|build)(\([\w-]+\))?: .+$`
- **Black** formatter with line-length 160
- **Python 3.12** target
- **Snake_case** for all Python modules, functions, and variables
- **Sql prefix** for ORM models: `SqlWorkspacePermission`, `SqlWorkspaceGroupPermission`
- **No Sql prefix** for entity classes: `WorkspacePermission`, `WorkspaceGroupPermission`
- **`__init__.py`** with explicit `__all__` lists for all packages
- **Type hints** on function signatures for public APIs
- **Module-level logger**: `logger = get_logger()`
- Test files use `test_` prefix under `mlflow_oidc_auth/tests/`

## Standard Stack

### Core (already in project — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cachetools` | 7.0.5 | TTLCache for workspace permission lookups | Already transitive dep via mlflow-skinny; TTLCache is the standard Python solution for bounded time-expiring caches |
| `sqlalchemy` | >=2.0.46, <3 | ORM for workspace permission models | Already core dependency; `Mapped[T]` type annotations used throughout |
| `flask` | <4 | Request context for bridge/validators | Already core dependency; hooks operate in Flask request context |

### Supporting (already in project)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mlflow` | >=3.10.0, <4 | Protobuf classes for workspace RPCs, permissions enum | Import `CreateWorkspace`, `GetWorkspace`, etc. from `mlflow.protos.service_pb2` |
| `authlib` | <2 | JWT validation (unchanged) | Not directly needed in Phase 2 — auth middleware from Phase 1 handles this |

### No New Dependencies

Phase 2 requires **zero new dependencies**. All libraries are already available:
- `cachetools` — transitive via mlflow-skinny (do NOT add to `pyproject.toml` direct deps per decision WSAUTH-E)
- All SQLAlchemy, Flask, FastAPI dependencies already declared

## Architecture Patterns

### Recommended File Structure (new files only)

```
mlflow_oidc_auth/
├── entities/
│   └── workspace.py                          # WorkspacePermission, WorkspaceGroupPermission entities
├── repository/
│   ├── workspace_permission.py               # WorkspacePermissionRepository (standalone)
│   └── workspace_group_permission.py         # WorkspaceGroupPermissionRepository (standalone)
├── validators/
│   └── workspace.py                          # validate_can_create/read/update/delete_workspace
├── utils/
│   └── workspace_cache.py                    # TTLCache module, get_workspace_permission_cached()
└── tests/
    ├── entities/
    │   └── test_workspace.py
    ├── repository/
    │   ├── test_workspace_permission.py
    │   └── test_workspace_group_permission.py
    ├── hooks/
    │   └── test_workspace_hooks.py           # or extend test_before_request.py
    ├── utils/
    │   └── test_workspace_cache.py
    └── validators/
        └── test_workspace.py
```

### Modified files

```
mlflow_oidc_auth/
├── hooks/
│   ├── before_request.py                     # + WORKSPACE_BEFORE_REQUEST_HANDLERS/VALIDATORS, _find_validator() update, creation gating
│   └── after_request.py                      # + ListWorkspaces filtering in after_request_hook()
├── utils/
│   └── permissions.py                        # resolve_permission() workspace fallback
├── db/models/
│   └── workspace.py                          # + to_mlflow_entity() on existing ORM models
├── sqlalchemy_store.py                       # + workspace permission repo instantiation and store methods
├── config.py                                 # + WORKSPACE_CACHE_MAX_SIZE, WORKSPACE_CACHE_TTL_SECONDS
├── app.py                                    # _seed_default_workspace() logging update
└── store.py                                  # + workspace permission store method proxies (if needed)
```

### Pattern 1: Workspace Hook Registration (mirrors logged model pattern)

**What:** Register workspace protobuf RPC handlers using regex path matching, identical to how logged model handlers are registered.

**When to use:** For all 5 workspace RPCs (Create, Get, List, Update, Delete).

**Example:**
```python
# Source: mlflow_oidc_auth/hooks/before_request.py (logged model pattern, lines 267-278)
from mlflow.protos.service_pb2 import CreateWorkspace, GetWorkspace, ListWorkspaces, UpdateWorkspace, DeleteWorkspace

WORKSPACE_BEFORE_REQUEST_HANDLERS = {
    CreateWorkspace: validate_can_create_workspace,
    GetWorkspace: validate_can_read_workspace,
    ListWorkspaces: None,  # Allow all, filter in after_request
    UpdateWorkspace: validate_can_update_workspace,
    DeleteWorkspace: validate_can_delete_workspace,
}

WORKSPACE_BEFORE_REQUEST_VALIDATORS = {
    (_re_compile_path(http_path), method): handler
    for http_path, handler, methods in get_endpoints(
        lambda rc: WORKSPACE_BEFORE_REQUEST_HANDLERS.get(rc)
    )
    for method in methods
    if handler is not None
}
```

**_find_validator() update:**
```python
# In _find_validator(), add workspace check alongside logged model check
def _find_validator(path, method):
    # Check workspace validators for workspace paths
    if "/mlflow/workspaces" in path:
        for (regex, m), handler in WORKSPACE_BEFORE_REQUEST_VALIDATORS.items():
            if method == m and regex.match(path):
                return handler
    # Existing logged model check
    if "/mlflow/logged-models" in path:
        for (regex, m), handler in LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS.items():
            if method == m and regex.match(path):
                return handler
    # Existing exact-match fallback
    return BEFORE_REQUEST_VALIDATORS.get((path, method))
```

### Pattern 2: Standalone Workspace Repository (decision WSAUTH-B)

**What:** Create workspace permission repositories as standalone classes (not extending base classes) because workspace is a tenant boundary.

**When to use:** For `WorkspacePermissionRepository` and `WorkspaceGroupPermissionRepository`.

**Example:**
```python
# Source: follows pattern from existing repos but without base class
# mlflow_oidc_auth/repository/workspace_permission.py
from sqlalchemy.orm import Session
from mlflow_oidc_auth.db.models.workspace import SqlWorkspacePermission
from mlflow_oidc_auth.entities.workspace import WorkspacePermission

class WorkspacePermissionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, workspace: str, user_id: int) -> WorkspacePermission:
        perm = self.session.query(SqlWorkspacePermission).filter(
            SqlWorkspacePermission.workspace == workspace,
            SqlWorkspacePermission.user_id == user_id,
        ).one_or_none()
        if perm is None:
            raise MlflowException(
                f"Workspace permission not found for user {user_id} in workspace {workspace}",
                RESOURCE_DOES_NOT_EXIST,
            )
        return perm.to_mlflow_entity()

    def list_for_user(self, user_id: int) -> list[WorkspacePermission]:
        return [
            p.to_mlflow_entity()
            for p in self.session.query(SqlWorkspacePermission).filter(
                SqlWorkspacePermission.user_id == user_id,
            ).all()
        ]

    def create(self, workspace: str, user_id: int, permission: str) -> WorkspacePermission:
        perm = SqlWorkspacePermission(workspace=workspace, user_id=user_id, permission=permission)
        self.session.add(perm)
        self.session.flush()
        return perm.to_mlflow_entity()

    def update(self, workspace: str, user_id: int, permission: str) -> WorkspacePermission:
        perm = self.session.query(SqlWorkspacePermission).filter(
            SqlWorkspacePermission.workspace == workspace,
            SqlWorkspacePermission.user_id == user_id,
        ).one_or_none()
        if perm is None:
            raise MlflowException(...)
        perm.permission = permission
        self.session.flush()
        return perm.to_mlflow_entity()

    def delete(self, workspace: str, user_id: int) -> None:
        self.session.query(SqlWorkspacePermission).filter(
            SqlWorkspacePermission.workspace == workspace,
            SqlWorkspacePermission.user_id == user_id,
        ).delete()
        self.session.flush()
```

### Pattern 3: resolve_permission() Workspace Fallback (decision WSAUTH-C)

**What:** Add workspace fallback to `resolve_permission()` without changing `get_permission_from_store_or_default()`.

**When to use:** In `utils/permissions.py` — the single modification point for the permission chain.

**Example:**
```python
# Source: mlflow_oidc_auth/utils/permissions.py (modify resolve_permission at line ~290)
def resolve_permission(resource_type, resource_id, username, **kwargs) -> PermissionResult:
    builder = PERMISSION_REGISTRY[resource_type]
    sources_config = builder(resource_id, username, **kwargs)
    result = get_permission_from_store_or_default(sources_config)

    # Workspace fallback: when no resource-level permission found
    if result.kind == "fallback" and config.MLFLOW_ENABLE_WORKSPACES:
        workspace = get_request_workspace()
        if workspace:
            ws_perm = get_workspace_permission_cached(username, workspace)
            if ws_perm is not None:
                return PermissionResult(ws_perm, "workspace")
            return PermissionResult(NO_PERMISSIONS, "workspace-deny")

    return result
```

**Critical detail:** The `kind` field on `PermissionResult` is the string `"fallback"` — this is set in `get_permission_from_store_or_default()` when no source matches and it falls back to `DEFAULT_MLFLOW_PERMISSION`. This is the exact insertion point.

### Pattern 4: TTLCache with Lazy Initialization (decision WSAUTH-E)

**What:** Module-level TTLCache that's lazily initialized on first access, reading config values at init time (not import time).

**When to use:** In `utils/workspace_cache.py`.

**Example:**
```python
# mlflow_oidc_auth/utils/workspace_cache.py
from cachetools import TTLCache
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, MANAGE
from mlflow_oidc_auth.store import store

_cache: TTLCache | None = None


def _get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache(
            maxsize=config.WORKSPACE_CACHE_MAX_SIZE,
            ttl=config.WORKSPACE_CACHE_TTL_SECONDS,
        )
    return _cache


def get_workspace_permission_cached(username: str, workspace: str) -> Permission | None:
    """Get the effective workspace permission for a user, with caching.

    Returns None if the user has no workspace permission.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return None

    cache = _get_cache()
    key = (username, workspace)
    if key in cache:
        return cache[key]

    perm = _lookup_workspace_permission(username, workspace)
    if perm is not None:
        cache[key] = perm
    return perm


def _lookup_workspace_permission(username: str, workspace: str) -> Permission | None:
    """Look up workspace permission from DB, with implicit default workspace access."""
    # Implicit access to default workspace
    if workspace == "default" and config.GRANT_DEFAULT_WORKSPACE_ACCESS:
        return MANAGE

    # User-level workspace permission
    try:
        perm = store.get_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except MlflowException:
        pass

    # Group-level workspace permission (highest across user's groups)
    try:
        perm = store.get_user_groups_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except MlflowException:
        pass

    return None
```

### Pattern 5: Creation Gating in before_request_hook() (decision WSAUTH-F)

**What:** Centralized workspace MANAGE check for resource creation, placed in `before_request_hook()` before dispatching to individual validators.

**When to use:** For `CreateExperiment` and `CreateRegisteredModel` only.

**Example:**
```python
# In before_request_hook(), after finding the validator, before calling it:
_WORKSPACE_GATED_CREATION_CLASSES = frozenset({CreateExperiment, CreateRegisteredModel})

# Inside before_request_hook():
if config.MLFLOW_ENABLE_WORKSPACES and not is_admin:
    # Check if this request is a workspace-gated creation
    for cls in _WORKSPACE_GATED_CREATION_CLASSES:
        if _matches_request_class(request_class, cls):
            workspace = get_request_workspace()
            if workspace:
                ws_perm = get_workspace_permission_cached(username, workspace)
                if ws_perm is None or ws_perm < MANAGE:
                    return make_forbidden_response()
            break
```

### Anti-Patterns to Avoid

- **Don't modify `get_permission_from_store_or_default()`** — This function is the inner resolution engine used for all resource types. The workspace fallback belongs in `resolve_permission()` which is the outer wrapper. Changing the inner function risks breaking all existing permission checks.

- **Don't extend base repository classes for workspace repos** — The `BaseUserPermissionRepository` assumes a `resource_id` column pattern. Workspace is a tenant boundary with different semantics. Forcing it into the base pattern creates awkward abstractions.

- **Don't add `cachetools` to `pyproject.toml` direct deps** — It's already a transitive dependency via mlflow-skinny. Adding it directly creates a version constraint conflict risk and maintenance burden.

- **Don't put workspace checks in individual validators** — The creation gating (WSAUTH-03) belongs in `before_request_hook()` centrally, not scattered across `validate_can_create_experiment()` and `validate_can_create_registered_model()`. Individual validators don't know about workspaces.

- **Don't seed workspace permission rows for default workspace** — The code-level implicit access approach (WSAUTH-D) avoids O(N) rows and the user-exists-before-permission-row timing problem.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TTL cache | Custom dict with timestamp tracking | `cachetools.TTLCache` | Thread-safe, handles eviction, LRU on capacity overflow, well-tested |
| Regex path matching | Custom regex builder | `_re_compile_path()` (already exists) | Handles API v3.0 path parameterization, both `/api/3.0/` and `/ajax-api/3.0/` prefix expansion |
| Permission comparison | String comparison of permission levels | `Permission` dataclass with `__lt__`/`__gt__` operators | Priority-based comparison already handles READ < USE < EDIT < MANAGE ordering |
| Endpoint discovery | Hardcoded path strings | `get_endpoints()` with protobuf class lambda | Automatically resolves HTTP paths from MLflow's protobuf service definitions, handles dual-prefix expansion |

**Key insight:** Every pattern needed for Phase 2 already exists in the codebase. The work is applying existing patterns to workspace-specific code, not inventing new infrastructure.

## Common Pitfalls

### Pitfall 1: PermissionResult.kind String Mismatch

**What goes wrong:** The workspace fallback in `resolve_permission()` checks `result.kind == "fallback"` but the string could be different.
**Why it happens:** `PermissionResult` is a `NamedTuple` with a string `kind` field. If the string doesn't match exactly, the workspace fallback never triggers.
**How to avoid:** Verify the exact string in `get_permission_from_store_or_default()`. It is `"fallback"` — confirmed by reading `utils/permissions.py` where the function returns `PermissionResult(permission=default_permission, kind="fallback")`.
**Warning signs:** Tests pass for workspace-disabled but workspace-enabled fallback doesn't trigger.

### Pitfall 2: Import Cycle with Lazy Cache Init

**What goes wrong:** `workspace_cache.py` imports from `store.py` which imports from `sqlalchemy_store.py` which may import from modules that import `workspace_cache.py`.
**Why it happens:** Module-level imports create circular dependency chains in Python.
**How to avoid:** Use lazy imports inside `_lookup_workspace_permission()` if needed, or ensure `workspace_cache.py` only imports from `store` (the singleton module, not the class) and `config`. The `store` module is a thin singleton wrapper with no heavy imports — this is the safe import target.
**Warning signs:** `ImportError` at startup or during first cache miss.

### Pitfall 3: None vs Missing in Cache

**What goes wrong:** If `None` is cached for "no permission found", the cache returns `None` on hit but the code treats cache hit as "permission exists".
**Why it happens:** `TTLCache` stores any value including `None`. `key in cache` returns True even if value is `None`.
**How to avoid:** Only cache non-None permission values. On cache miss (key not in cache), do the DB lookup. If DB lookup returns None, do NOT cache it — let subsequent requests re-check. This means "no permission" is always a cache miss, which is acceptable because denied users don't generate sustained traffic on a single workspace.
**Warning signs:** User granted workspace permission but still denied because `None` was cached.

### Pitfall 4: Missing Both `/api/3.0/` and `/ajax-api/3.0/` Prefixes

**What goes wrong:** Workspace hook registration only covers one prefix, leaving the other prefix unprotected.
**Why it happens:** MLflow registers endpoints under both prefixes. `get_endpoints()` with `_re_compile_path()` handles this automatically, but only if you use it correctly.
**How to avoid:** Use `get_endpoints()` for path discovery — it returns all prefix variants. Do NOT hardcode paths.
**Warning signs:** Hooks work via one prefix but not the other.

### Pitfall 5: before_request_hook() Order of Operations for Creation Gating

**What goes wrong:** The workspace MANAGE check runs after the admin check, so admins are correctly bypassed, but the check runs before the validator is found, so it can't determine which protobuf class the request maps to.
**Why it happens:** The creation gating needs to know the request class (CreateExperiment, CreateRegisteredModel) but this is determined by validator lookup which happens earlier in the function.
**How to avoid:** Place the workspace creation gating AFTER the validator lookup (which identifies the request class) but BEFORE calling the validator. The existing `before_request_hook()` flow is: find validator → admin bypass → call validator. Insert workspace check between admin bypass and call validator.
**Warning signs:** Workspace check doesn't trigger because it can't identify creation requests.

### Pitfall 6: `_find_validator()` Returning None for ListWorkspaces

**What goes wrong:** `ListWorkspaces` has `None` handler in `WORKSPACE_BEFORE_REQUEST_HANDLERS`, so it's excluded from `WORKSPACE_BEFORE_REQUEST_VALIDATORS`. If `_find_validator()` returns `None` for a ListWorkspaces path, the `before_request_hook()` may treat it as "no handler = allow" or "no handler = deny" depending on the default behavior.
**Why it happens:** The current `before_request_hook()` returns 403 when no validator is found for a recognized path. ListWorkspaces needs explicit allow-through.
**How to avoid:** Either: (a) give ListWorkspaces a no-op validator that always returns True, or (b) ensure `_find_validator()` returns a sentinel that `before_request_hook()` recognizes as "allow". Option (a) is simpler and consistent with the pattern.
**Warning signs:** Authenticated users get 403 on ListWorkspaces.

## Code Examples

### Entity Classes

```python
# mlflow_oidc_auth/entities/workspace.py
from mlflow_oidc_auth.permissions import Permission, get_permission


class WorkspacePermission:
    def __init__(self, workspace: str, user_id: int, permission: str, username: str | None = None):
        self._workspace = workspace
        self._user_id = user_id
        self._permission = permission
        self._username = username

    @property
    def workspace(self) -> str:
        return self._workspace

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def permission(self) -> str:
        return self._permission

    @property
    def username(self) -> str | None:
        return self._username

    def to_json(self) -> dict:
        return {
            "workspace": self.workspace,
            "user_id": self.user_id,
            "permission": self.permission,
            "username": self.username,
        }


class WorkspaceGroupPermission:
    def __init__(self, workspace: str, group_id: int, permission: str, group_name: str | None = None):
        self._workspace = workspace
        self._group_id = group_id
        self._permission = permission
        self._group_name = group_name

    @property
    def workspace(self) -> str:
        return self._workspace

    @property
    def group_id(self) -> int:
        return self._group_id

    @property
    def permission(self) -> str:
        return self._permission

    @property
    def group_name(self) -> str | None:
        return self._group_name

    def to_json(self) -> dict:
        return {
            "workspace": self.workspace,
            "group_id": self.group_id,
            "permission": self.permission,
            "group_name": self.group_name,
        }
```

### ORM Model to_mlflow_entity()

```python
# Addition to mlflow_oidc_auth/db/models/workspace.py
# On SqlWorkspacePermission class:
def to_mlflow_entity(self) -> WorkspacePermission:
    return WorkspacePermission(
        workspace=self.workspace,
        user_id=self.user_id,
        permission=self.permission,
        username=self.user.username if self.user else None,
    )

# On SqlWorkspaceGroupPermission class:
def to_mlflow_entity(self) -> WorkspaceGroupPermission:
    return WorkspaceGroupPermission(
        workspace=self.workspace,
        group_id=self.group_id,
        permission=self.permission,
        group_name=self.group.group_name if self.group else None,
    )
```

### Workspace Validators

```python
# mlflow_oidc_auth/validators/workspace.py
from mlflow_oidc_auth.bridge.user import get_auth_context
from mlflow_oidc_auth.responses.client_error import make_forbidden_response
from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached
from mlflow_oidc_auth.permissions import MANAGE


def validate_can_create_workspace():
    """Only admins can create workspaces."""
    auth_context = get_auth_context()
    if not auth_context.is_admin:
        return make_forbidden_response()


def validate_can_read_workspace():
    """User must have any workspace permission to view workspace details."""
    auth_context = get_auth_context()
    if auth_context.is_admin:
        return None
    # Extract workspace_name from path (regex group)
    workspace_name = _extract_workspace_name_from_path()
    perm = get_workspace_permission_cached(auth_context.username, workspace_name)
    if perm is None:
        return make_forbidden_response()


def validate_can_update_workspace():
    """Only admins can update workspaces."""
    auth_context = get_auth_context()
    if not auth_context.is_admin:
        return make_forbidden_response()


def validate_can_delete_workspace():
    """Only admins can delete workspaces."""
    auth_context = get_auth_context()
    if not auth_context.is_admin:
        return make_forbidden_response()
```

### ListWorkspaces After-Request Filtering

```python
# Addition to mlflow_oidc_auth/hooks/after_request.py
def _filter_list_workspaces(response):
    """Filter ListWorkspaces response to only include workspaces user has permission for."""
    if response.status_code != 200:
        return response
    auth_context = get_auth_context()
    if auth_context.is_admin:
        return response
    data = response.get_json()
    if not data or "workspaces" not in data:
        return response
    filtered = [
        ws for ws in data["workspaces"]
        if get_workspace_permission_cached(auth_context.username, ws.get("name", "")) is not None
    ]
    data["workspaces"] = filtered
    response.set_data(json.dumps(data))
    return response
```

### Store Methods

```python
# Additions to mlflow_oidc_auth/sqlalchemy_store.py

# In init_db():
self.workspace_permission_repo = WorkspacePermissionRepository(self.ManagedSessionMaker)
self.workspace_group_permission_repo = WorkspaceGroupPermissionRepository(self.ManagedSessionMaker)

# Store wrapper methods:
def get_workspace_permission(self, workspace: str, username: str) -> WorkspacePermission:
    with self.ManagedSessionMaker() as session:
        user = self.user_repo.get_user(session, username)
        return self.workspace_permission_repo.get(session, workspace, user.id)

def create_workspace_permission(self, workspace: str, username: str, permission: str) -> WorkspacePermission:
    with self.ManagedSessionMaker() as session:
        user = self.user_repo.get_user(session, username)
        return self.workspace_permission_repo.create(session, workspace, user.id, permission)

def get_user_groups_workspace_permission(self, workspace: str, username: str) -> WorkspaceGroupPermission:
    """Get the highest workspace permission across all groups the user belongs to."""
    with self.ManagedSessionMaker() as session:
        user = self.user_repo.get_user(session, username)
        return self.workspace_group_permission_repo.get_highest_for_user(session, workspace, user.id)
```

### Config Additions

```python
# In mlflow_oidc_auth/config.py AppConfig class:
WORKSPACE_CACHE_MAX_SIZE: int = int(os.environ.get("WORKSPACE_CACHE_MAX_SIZE", "1024"))
WORKSPACE_CACHE_TTL_SECONDS: int = int(os.environ.get("WORKSPACE_CACHE_TTL_SECONDS", "300"))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Exact path matching only (BEFORE_REQUEST_HANDLERS) | Regex matching for parameterized routes (LOGGED_MODEL_BEFORE_REQUEST_HANDLERS) | Phase 1 / MLflow 3.x logged models | Workspace hooks use the regex pattern exclusively |
| Flat permission model (resource-level only) | Hierarchical: resource → workspace → default | Phase 2 (this phase) | Enables multi-tenant isolation without per-resource permission grants |
| DEFAULT_MLFLOW_PERMISSION as universal fallback | Workspace-level fallback replaces default when workspaces enabled | Phase 2 (this phase) | Critical security change — no implicit access when workspaces enabled |

## Open Questions

1. **Workspace name extraction from regex path**
   - What we know: Logged model paths use regex groups, but the existing code doesn't extract named groups from matched paths for use by validators.
   - What's unclear: How workspace validators get the workspace_name from the URL path. Flask's `request.view_args` may not work for regex-matched paths.
   - Recommendation: Extract workspace_name from `flask.request.path` by splitting on `/mlflow/workspaces/` — simple and reliable. Or use regex named groups in `_re_compile_path()`.

2. **ListWorkspaces None handler in _find_validator()**
   - What we know: ListWorkspaces needs to pass through before_request (all authenticated users) and be filtered in after_request.
   - What's unclear: Whether `_find_validator()` returning None causes before_request_hook() to deny or allow the request.
   - Recommendation: Use a no-op validator (returns None = allow) instead of None handler. This avoids any ambiguity about the allow/deny default.

3. **Session scope for workspace permission repo queries**
   - What we know: Existing repos receive session from `ManagedSessionMaker` context manager in store methods.
   - What's unclear: Whether standalone repos should follow the same session injection pattern or use a different approach.
   - Recommendation: Follow existing pattern exactly — pass `session` to repo methods from store wrapper methods using `with self.ManagedSessionMaker() as session:`.

## Sources

### Primary (HIGH confidence)
- `mlflow_oidc_auth/hooks/before_request.py` — Full hook registration pattern, `_find_validator()`, `_re_compile_path()`, `before_request_hook()` flow
- `mlflow_oidc_auth/hooks/after_request.py` — After-request filtering pattern, `AFTER_REQUEST_PATH_HANDLERS`
- `mlflow_oidc_auth/utils/permissions.py` — `resolve_permission()`, `get_permission_from_store_or_default()`, `PermissionResult.kind` values
- `mlflow_oidc_auth/repository/_base.py` — Base repository classes (for understanding what NOT to extend)
- `mlflow_oidc_auth/db/models/workspace.py` — Existing ORM models (`SqlWorkspacePermission`, `SqlWorkspaceGroupPermission`)
- `mlflow_oidc_auth/entities/_base.py`, `entities/experiment.py` — Entity class patterns
- `mlflow_oidc_auth/config.py` — AppConfig pattern, existing workspace feature flags
- `mlflow_oidc_auth/bridge/user.py` — `get_request_workspace()`, `get_auth_context()`
- `mlflow_oidc_auth/sqlalchemy_store.py` — Store facade pattern, repo instantiation
- `mlflow_oidc_auth/models/permission.py` — `PermissionResult` NamedTuple definition
- `mlflow_oidc_auth/permissions.py` — `Permission` dataclass, `NO_PERMISSIONS`, `MANAGE`, `get_permission()`
- `cachetools` 7.0.5 — TTLCache API (verified available via pip show)

### Secondary (MEDIUM confidence)
- `mlflow_oidc_auth/tests/hooks/test_before_request.py` — Test patterns for hook registration
- `mlflow_oidc_auth/tests/utils/test_permissions.py` — Test patterns for permission resolution

### Tertiary (LOW confidence)
- Workspace protobuf class availability in `mlflow.protos.service_pb2` — assumed based on CONTEXT.md canonical refs, not independently verified against MLflow 3.10 source

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all libraries already in project, versions verified
- Architecture: HIGH — all patterns exist in codebase, new code mirrors existing patterns exactly
- Pitfalls: HIGH — identified from direct code reading, not speculation
- Code Examples: MEDIUM — based on pattern analysis, may need adjustment during implementation

**Research date:** 2026-03-23
**Valid until:** 2026-04-22 (30 days — stable patterns, no external dependency changes expected)
