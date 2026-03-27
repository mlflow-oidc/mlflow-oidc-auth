# Phase 2: Workspace Auth Enforcement - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase builds the workspace security boundary on top of Phase 1's foundation. After this phase:
- Workspace protobuf RPCs (Create/Get/List/Update/Delete) are intercepted by before_request handlers
- Workspace-level user and group permissions exist with full CRUD via store methods
- CreateExperiment and CreateRegisteredModel require workspace MANAGE permission when workspaces are enabled
- Permission resolution chain includes workspace-level fallback: resource-level → workspace-level → NO_PERMISSIONS (no DEFAULT_MLFLOW_PERMISSION when workspaces enabled)
- Workspace permission lookups are cached via TTLCache for hot-path performance
- Default workspace is implicitly accessible to all users (code-level check, no seeded rows)
- Workspaces disabled (default) still produces zero behavioral changes

**Requirements:** WSAUTH-01, WSAUTH-02, WSAUTH-03, WSAUTH-04, WSAUTH-05
**Carries forward from Phase 1:** WSFND-04 (default workspace seeding gap — resolved via implicit access approach)

</domain>

<decisions>
## Implementation Decisions

### WSAUTH-A: Workspace Hook Registration (WSAUTH-01)

- **Regex pattern matching** — Following the logged model pattern exactly. Create `WORKSPACE_BEFORE_REQUEST_HANDLERS` dict mapping protobuf classes to validators. Build `WORKSPACE_BEFORE_REQUEST_VALIDATORS` using `_re_compile_path()` (already exists in `before_request.py`). Update `_find_validator()` to check workspace validators for `/mlflow/workspaces` paths.
- Workspace endpoints use API v3.0 path-parameterized routes:
  - `POST /api/3.0/mlflow/workspaces` → CreateWorkspace (admin only)
  - `GET /api/3.0/mlflow/workspaces/<workspace_name>` → GetWorkspace (workspace view check)
  - `GET /api/3.0/mlflow/workspaces` → ListWorkspaces (always allowed, filtered in after_request)
  - `PATCH /api/3.0/mlflow/workspaces/<workspace_name>` → UpdateWorkspace (admin only)
  - `DELETE /api/3.0/mlflow/workspaces/<workspace_name>` → DeleteWorkspace (admin only)
- Both `/api/3.0/` and `/ajax-api/3.0/` prefixed endpoints are registered (10 total paths).
- ListWorkspaces passes through before_request (all authenticated users can list) and is filtered in after_request to only return workspaces the user has permissions for.

### WSAUTH-B: Workspace Permission Repository Design (WSAUTH-02)

- **Standalone repositories** — Create `WorkspacePermissionRepository` and `WorkspaceGroupPermissionRepository` as standalone classes, NOT extending `BaseUserPermissionRepository` / `BaseGroupPermissionRepository`.
- Rationale: "workspace" is not a typical resource — it's a tenant boundary. The base classes assume a resource_id column pattern that maps awkwardly to workspace semantics. Standalone repos allow workspace-specific methods like `get_user_workspace_permission(workspace, username)`, `list_workspaces_for_user(username)`, `get_user_highest_workspace_permission(workspace, username)` (across groups).
- Repos are created in `repository/workspace_permission.py` and `repository/workspace_group_permission.py`.
- Entity classes created in `entities/workspace.py`: `WorkspacePermission` and `WorkspaceGroupPermission`.
- ORM models already exist: `SqlWorkspacePermission`, `SqlWorkspaceGroupPermission` (from Phase 1 migration).
- `to_mlflow_entity()` methods added to ORM models.
- Store methods added to `SqlAlchemyStore`: workspace_permission_repo and workspace_group_permission_repo instantiated in `init_db()`.

### WSAUTH-C: Permission Resolution Workspace Fallback (WSAUTH-04)

- **Wrap resolve_permission()** — Keep `get_permission_from_store_or_default()` completely unchanged. Modify `resolve_permission()` to add workspace fallback:
  1. Call existing resolution (resource-level user → group → regex → group-regex).
  2. If result source is `'fallback'` AND `config.MLFLOW_ENABLE_WORKSPACES` is True:
     - Look up workspace permission for the user (from `AuthContext.workspace` via bridge).
     - If workspace permission found → return workspace-level permission.
     - If no workspace permission found → return `NO_PERMISSIONS` (hard deny).
  3. If workspaces not enabled, existing fallback to `DEFAULT_MLFLOW_PERMISSION` preserved.
- This is the **core security boundary** — when workspaces are enabled, `DEFAULT_MLFLOW_PERMISSION` is never used as a fallback. Only explicit resource-level or workspace-level permissions grant access.
- `resolve_permission()` signature unchanged — callers unaffected.

### WSAUTH-D: Default Workspace Seeding (WSFND-04 completion)

- **Code-level implicit access** — No workspace_permissions rows seeded for the default workspace. Instead, workspace permission lookup code treats the `'default'` workspace as implicitly accessible to ALL users when `GRANT_DEFAULT_WORKSPACE_ACCESS=True` (config from Phase 1).
- The `_seed_default_workspace()` function in `app.py` is updated to log that implicit access is active (no DB writes needed).
- Runtime behavior: When `resolve_permission()` checks workspace permission for a user in the `'default'` workspace and `GRANT_DEFAULT_WORKSPACE_ACCESS=True`, the workspace lookup returns an implicit permission (configurable level, e.g., MANAGE) without a DB row.
- Operators who want strict default workspace access can set `GRANT_DEFAULT_WORKSPACE_ACCESS=False`, requiring explicit workspace_permissions rows.
- No scaling concern — no O(N) rows to seed per user.

### WSAUTH-E: TTLCache for Workspace Permissions (WSAUTH-05)

- **Module-level TTLCache** in a new `mlflow_oidc_auth/utils/workspace_cache.py` module.
- Key: `(username, workspace)` → `Permission` (the resolved workspace permission level).
- Configuration via `AppConfig`:
  - `WORKSPACE_CACHE_MAX_SIZE` (default: 1024) — max entries in cache
  - `WORKSPACE_CACHE_TTL_SECONDS` (default: 300) — TTL in seconds per entry
- Cache miss → DB query via workspace permission repo → populate cache.
- Invalidation: **TTL-based only** — no explicit invalidation on permission changes. This is acceptable because:
  - Workspace permissions change rarely (admin operation).
  - 5-minute default TTL bounds staleness.
  - Explicit invalidation would require cache coordination across processes in multi-replica deployments.
- `cachetools` 7.0.5 already available as transitive dependency (via MLflow). NOT added to `pyproject.toml` direct dependencies — transitive is sufficient.
- Cache is only active when `MLFLOW_ENABLE_WORKSPACES=True`.
- Helper function: `get_workspace_permission_cached(username, workspace)` → calls cache, falls back to repo on miss.

### WSAUTH-F: Creation Workspace Gating (WSAUTH-03)

- **Conditional wrapper in before_request_hook()** — Add workspace MANAGE check as a pre-check specifically for `CreateExperiment` and `CreateRegisteredModel` protobuf message classes.
- When `MLFLOW_ENABLE_WORKSPACES=True` and the request is for CreateExperiment or CreateRegisteredModel:
  1. Extract workspace from `AuthContext` (via bridge `get_request_workspace()`).
  2. If workspace is present, check user has MANAGE on that workspace (via cached lookup).
  3. If no MANAGE permission → return 403 forbidden response.
  4. If MANAGE permission → proceed to normal before_request validation.
- When workspaces are disabled, no additional check — existing behavior preserved.
- The workspace check happens in `before_request_hook()` itself (not in individual validators), keeping the check centralized and avoiding changes to existing validator functions.
- The after_request auto-grant of MANAGE on created resources remains unchanged.

### Testing

- Unit tests for:
  - Workspace before_request handler registration and validator matching (regex paths)
  - WorkspacePermissionRepository and WorkspaceGroupPermissionRepository CRUD
  - Workspace entity classes and ORM model `to_mlflow_entity()` methods
  - `resolve_permission()` workspace fallback (resource-level found → no workspace check; fallback + workspaces enabled → workspace-level; fallback + no workspace perm → NO_PERMISSIONS)
  - Default workspace implicit access (GRANT_DEFAULT_WORKSPACE_ACCESS true/false)
  - TTLCache hit/miss/expiry behavior
  - CreateExperiment/CreateRegisteredModel workspace MANAGE gating
  - All tests with MLFLOW_ENABLE_WORKSPACES=False confirm zero behavioral changes
- Existing test suite must pass unchanged (regression).

### Agent's Discretion

- Exact workspace validator function names (e.g., `validate_can_create_workspace`, `validate_can_read_workspace`)
- Whether workspace validators live in `validators/workspace.py` or are added to existing validator modules
- Exact entity class field names and property patterns
- Exact cache key format (tuple vs string)
- Whether workspace MANAGE check for CreateExperiment is in before_request_hook() body or extracted to a helper function
- Exact implicit permission level for GRANT_DEFAULT_WORKSPACE_ACCESS (MANAGE vs READ) — recommend MANAGE for backward compatibility
- ListWorkspaces after_request filtering implementation details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Workspace Protobuf RPCs
- `mlflow.protos.service_pb2` — `CreateWorkspace`, `GetWorkspace`, `ListWorkspaces`, `UpdateWorkspace`, `DeleteWorkspace`, `Workspace`
- API paths: `/api/3.0/mlflow/workspaces` (POST, GET) and `/api/3.0/mlflow/workspaces/<workspace_name>` (GET, PATCH, DELETE)
- Fields: CreateWorkspace(name, description, default_artifact_root), GetWorkspace(workspace_name), ListWorkspaces(), UpdateWorkspace(workspace_name, description, default_artifact_root), DeleteWorkspace(workspace_name)

### Hook Registration Pattern (logged model precedent)
- `mlflow_oidc_auth/hooks/before_request.py` — `LOGGED_MODEL_BEFORE_REQUEST_HANDLERS`, `LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS`, `_re_compile_path()`, `_find_validator()` (lines 282-340)
- `mlflow_oidc_auth/hooks/after_request.py` — `AFTER_REQUEST_PATH_HANDLERS`, `AFTER_REQUEST_HANDLERS`, `after_request_hook()` (lines 388-426)

### Permission Resolution
- `mlflow_oidc_auth/utils/permissions.py` — `resolve_permission()` (line 290), `get_permission_from_store_or_default()` (line 488), `PERMISSION_REGISTRY` (line 279)
- `mlflow_oidc_auth/permissions.py` — `Permission` dataclass, `NO_PERMISSIONS`, `MANAGE`, `get_permission()`

### Workspace Foundation (Phase 1 output)
- `mlflow_oidc_auth/db/models/workspace.py` — `SqlWorkspacePermission`, `SqlWorkspaceGroupPermission`
- `mlflow_oidc_auth/entities/auth_context.py` — `AuthContext(username, is_admin, workspace)`
- `mlflow_oidc_auth/bridge/user.py` — `get_auth_context()`, `get_request_workspace()`, `get_fastapi_username()`
- `mlflow_oidc_auth/config.py` — `MLFLOW_ENABLE_WORKSPACES`, `GRANT_DEFAULT_WORKSPACE_ACCESS`
- `mlflow_oidc_auth/app.py` — `_seed_default_workspace()` (line 74)
- `mlflow_oidc_auth/middleware/auth_middleware.py` — Where AuthContext is created with workspace

### Repository Pattern
- `mlflow_oidc_auth/repository/_base.py` — 4 generic base classes (for reference, NOT to extend for workspace repos)
- `mlflow_oidc_auth/repository/` — 28 existing repo classes (naming/structure convention)
- `mlflow_oidc_auth/sqlalchemy_store.py` — Store facade, repo instantiation in `init_db()` (line 55-97)

### Configuration
- `mlflow_oidc_auth/config.py` — `AppConfig` class for adding WORKSPACE_CACHE_MAX_SIZE, WORKSPACE_CACHE_TTL_SECONDS

### Existing Tests
- `tests/` — Test patterns, fixtures, conventions

</canonical_refs>

<specifics>
## Specific Ideas

### Workspace Before Request Handler Registration
```python
# In before_request.py
WORKSPACE_BEFORE_REQUEST_HANDLERS = {
    CreateWorkspace: validate_can_create_workspace,     # admin only
    GetWorkspace: validate_can_read_workspace,           # workspace perm check
    ListWorkspaces: None,                                # always allowed (filtered in after_request)
    UpdateWorkspace: validate_can_update_workspace,      # admin only
    DeleteWorkspace: validate_can_delete_workspace,      # admin only
}

WORKSPACE_BEFORE_REQUEST_VALIDATORS = {
    (_re_compile_path(http_path), method): handler
    for http_path, handler, methods in get_endpoints(
        lambda rc: WORKSPACE_BEFORE_REQUEST_HANDLERS.get(rc)
    )
    for method in methods
    if handler is not None  # skip ListWorkspaces (None handler = allow-all)
}
```

### resolve_permission() Workspace Fallback
```python
def resolve_permission(resource_type, resource_id, username, **kwargs) -> PermissionResult:
    builder = PERMISSION_REGISTRY[resource_type]
    sources_config = builder(resource_id, username, **kwargs)
    result = get_permission_from_store_or_default(sources_config)

    # Workspace fallback when no resource-level permission found
    if result.type == "fallback" and config.MLFLOW_ENABLE_WORKSPACES:
        workspace = get_request_workspace()
        if workspace:
            ws_perm = get_workspace_permission_cached(username, workspace)
            if ws_perm:
                return PermissionResult(ws_perm, "workspace")
            return PermissionResult(get_permission("NO_PERMISSIONS"), "workspace-deny")

    return result
```

### TTLCache Module
```python
# mlflow_oidc_auth/utils/workspace_cache.py
from cachetools import TTLCache
from mlflow_oidc_auth.config import config

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
    cache = _get_cache()
    key = (username, workspace)
    if key in cache:
        return cache[key]
    # DB lookup...
    perm = _lookup_workspace_permission(username, workspace)
    if perm:
        cache[key] = perm
    return perm
```

### Implicit Default Workspace Access
```python
def _lookup_workspace_permission(username: str, workspace: str) -> Permission | None:
    # Implicit access to default workspace
    if workspace == "default" and config.GRANT_DEFAULT_WORKSPACE_ACCESS:
        return MANAGE  # or configurable level

    # Explicit user permission
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

### Workspace MANAGE Gating in before_request_hook()
```python
# In before_request_hook(), after validator lookup and before admin check:
if config.MLFLOW_ENABLE_WORKSPACES and not is_admin:
    _workspace_creation_classes = (CreateExperiment, CreateRegisteredModel)
    # Check if current request maps to a creation protobuf class
    if validator and _is_creation_request(request, _workspace_creation_classes):
        workspace = get_request_workspace()
        if workspace:
            ws_perm = get_workspace_permission_cached(username, workspace)
            if not ws_perm or not ws_perm.can_manage:
                return responses.make_forbidden_response()
```

</specifics>

<deferred>
## Deferred Ideas

- Workspace CRUD API (FastAPI routers for workspace-user and workspace-group permissions) — Phase 3 (WSMGMT-01, WSMGMT-02)
- Workspace permission delegation (MANAGE users can grant within workspace) — Phase 3 (WSMGMT-03)
- OIDC workspace claim extraction and auto-assignment — Phase 3 (WSOIDC-01, WSOIDC-02, WSOIDC-03)
- Workspace management UI — Phase 4 (WSMGMT-04, WSMGMT-05, WSMGMT-06)
- Explicit cache invalidation on workspace permission changes — v2 (TTL-based sufficient for now)
- Workspace-scoped search result filtering in after_request — v2 deferred
- Regex workspace permissions — v2 deferred

</deferred>

---

*Phase: 02-workspace-auth-enforcement*
*Context gathered: 2026-03-23 via discuss-phase*
