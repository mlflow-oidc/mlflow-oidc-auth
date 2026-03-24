# Phase 3: Management API, OIDC & Entity Coverage - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase makes workspace permissions manageable via API, integrates workspace detection into the OIDC login flow, and adds auth handlers for new MLflow 3.10 entities. After this phase:
- Admin or workspace MANAGE users can list/create/update/delete workspace-user and workspace-group permissions via FastAPI CRUD endpoints
- Users with MANAGE on a workspace can delegate permissions to other users within that workspace (without global admin)
- OIDC login with a workspace claim auto-creates workspace membership with a configurable default permission level
- Custom workspace resolution logic can be plugged in via `OIDC_WORKSPACE_DETECTION_PLUGIN`
- PromptOptimizationJob protobuf RPCs are intercepted by before_request handlers with experiment-scoped permission checks
- Workspace permission cache has targeted local invalidation on user permission changes via CRUD API

**Requirements:** WSMGMT-01, WSMGMT-02, WSMGMT-03, WSOIDC-01, WSOIDC-02, WSOIDC-03, ENTITY-01
**Deferred:** ENTITY-02 (GatewayBudgetPolicy — protos don't exist in MLflow 3.10.1, expected in 3.11)

</domain>

<decisions>
## Implementation Decisions

### Workspace Permission API Design (WSMGMT-01, WSMGMT-02, WSMGMT-03)
- **D-01:** Single workspace permissions router at `/api/3.0/mlflow/permissions/workspaces` (v3.0 since workspaces are a 3.10 feature, consistent with scorers router prefix pattern)
- **D-02:** REST resource style endpoints:
  - List users: `GET /{workspace}/users`
  - List groups: `GET /{workspace}/groups`
  - Create user permission: `POST /{workspace}/users`
  - Create group permission: `POST /{workspace}/groups`
  - Update user permission: `PATCH /{workspace}/users/{username}`
  - Update group permission: `PATCH /{workspace}/groups/{group_name}`
  - Delete user permission: `DELETE /{workspace}/users/{username}`
  - Delete group permission: `DELETE /{workspace}/groups/{group_name}`
- **D-03:** New `check_workspace_manage_permission()` FastAPI dependency — verifies global admin OR workspace MANAGE permission. Used on create/update/delete endpoints. List endpoints require at least workspace READ.
- **D-04:** Workspace MANAGE users can grant permissions up to and including MANAGE to other users. No privilege ceiling beyond MANAGE (which is already the highest level).
- **D-05:** Dedicated workspace permission Pydantic models: `WorkspaceUserPermissionRequest(username, permission)`, `WorkspaceGroupPermissionRequest(group_name, permission)`, `WorkspacePermissionResponse(workspace, username/group_name, permission)`.

### OIDC Workspace Claim Mapping (WSOIDC-01, WSOIDC-02, WSOIDC-03)
- **D-06:** New config `OIDC_WORKSPACE_CLAIM_NAME` (default: `'workspace'`) for extracting workspace from JWT claims during login/callback. Default mechanism — simple deployments just set a claim name.
- **D-07:** Plugin hook `OIDC_WORKSPACE_DETECTION_PLUGIN` following exact same pattern as `OIDC_GROUP_DETECTION_PLUGIN`: `importlib.import_module(config.OIDC_WORKSPACE_DETECTION_PLUGIN).get_user_workspaces(access_token)` returns a list of workspace names. Mirrors group plugin interface exactly.
- **D-08:** Auto-create workspace membership during OIDC login when workspace claim/plugin returns workspaces. Default permission level from `OIDC_WORKSPACE_DEFAULT_PERMISSION` config (default: `NO_PERMISSIONS`). Users get associated with the workspace but have no access until explicitly granted by admin or workspace MANAGE user.
- **D-09:** Group-to-workspace mapping UI and configuration is deferred to Phase 4. This phase delivers the backend hooks (JWT claim extraction + plugin) that the UI mapping would eventually use.

### New Entity Auth Coverage (ENTITY-01)
- **D-10:** PromptOptimizationJob handlers added to main `BEFORE_REQUEST_HANDLERS` dict (same pattern as experiments, runs, models — not a separate handler group). The 5 RPCs exist in `mlflow.protos.service_pb2` as confirmed in MLflow 3.10.1.
- **D-11:** Experiment-scoped permission model for PromptOptimizationJob:
  - `CreatePromptOptimizationJob` → `validate_can_update_experiment` (EDIT on experiment, same as CreateRun)
  - `GetPromptOptimizationJob` → `validate_can_read_experiment` (READ on experiment)
  - `SearchPromptOptimizationJobs` → `validate_can_read_experiment` (READ on experiment)
  - `DeletePromptOptimizationJob` → `validate_can_delete_experiment` or experiment EDIT
  - `CancelPromptOptimizationJob` → `validate_can_update_experiment` (EDIT on experiment, like cancelling a run)
- **D-12:** ENTITY-02 (GatewayBudgetPolicy) deferred — protos not present in MLflow 3.10.1, expected in MLflow 3.11. Will be a future phase task.

### Cache Invalidation on Permission Changes
- **D-13:** Targeted local invalidation: when workspace permission CRUD endpoints modify a user permission, call `cache.pop((username, workspace))` to invalidate the specific entry. Single-process only — TTL still handles cross-replica staleness.
- **D-14:** Invalidation lives in the router layer — workspace permission router calls cache invalidation directly after successful store operations. Store layer doesn't know about cache.
- **D-15:** User permission changes only trigger invalidation. Group permission changes rely on TTL-based expiry (group membership changes are rarer and tracing affected users is expensive). This is pragmatic — group changes propagate within TTL window.

### Agent's Discretion
- Exact Pydantic model field names and response structure
- Exact validator function names for PromptOptimizationJob (e.g., whether to reuse existing experiment validators or create dedicated ones)
- How workspace claim extraction integrates into the existing `_process_oidc_callback()` flow
- Error response format for permission delegation failures (e.g., granting above ceiling)
- Whether `invalidate_workspace_permission()` is a new function in `workspace_cache.py` or inline in the router
- New config variables added to `AppConfig` in `config.py` — exact naming for `OIDC_WORKSPACE_CLAIM_NAME`, `OIDC_WORKSPACE_DETECTION_PLUGIN`, `OIDC_WORKSPACE_DEFAULT_PERMISSION`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Workspace Permission API
- `mlflow_oidc_auth/routers/experiment_permissions.py` — Reference router pattern with CRUD endpoints, dependency injection, store delegation
- `mlflow_oidc_auth/routers/__init__.py` — Router registration list (add new workspace permissions router here)
- `mlflow_oidc_auth/routers/_prefix.py` — URL prefix constants (add `WORKSPACE_PERMISSIONS_ROUTER_PREFIX` using `_get_rest_path` with `version=3`)
- `mlflow_oidc_auth/dependencies.py` — Existing permission check dependencies (`check_admin_permission`, `check_experiment_manage_permission`, etc.) — pattern for new `check_workspace_manage_permission`
- `mlflow_oidc_auth/models/` — Existing Pydantic model patterns for request/response validation
- `mlflow_oidc_auth/repository/workspace_permission.py` — Phase 2 standalone workspace permission repository (CRUD methods already exist)
- `mlflow_oidc_auth/repository/workspace_group_permission.py` — Phase 2 standalone workspace group permission repository
- `mlflow_oidc_auth/sqlalchemy_store.py` — Store facade with workspace permission repo references

### OIDC Integration
- `mlflow_oidc_auth/routers/auth.py` lines 380-442 — `_process_oidc_callback()` function where group detection plugin is called and user/groups are created. Workspace detection injects here.
- `mlflow_oidc_auth/config.py` lines 94-103 — `OIDC_GROUP_DETECTION_PLUGIN` config pattern to mirror for workspace detection
- `mlflow_oidc_auth/config.py` lines 127-139 — Existing workspace config entries (add new OIDC workspace configs near here)

### Entity Coverage
- `mlflow_oidc_auth/hooks/before_request.py` lines 179-252 — `BEFORE_REQUEST_HANDLERS` dict (add PromptOptimizationJob entries here)
- `mlflow_oidc_auth/hooks/before_request.py` lines 1-82 — Protobuf imports from `mlflow.protos.service_pb2` (add PromptOptimizationJob imports)
- `mlflow_oidc_auth/validators/experiment.py` — Experiment validators reused for PromptOptimizationJob handlers

### Cache
- `mlflow_oidc_auth/utils/workspace_cache.py` — Phase 2 TTLCache module (add `invalidate_workspace_permission()` or expose cache pop)

### Phase 1/2 Foundation
- `mlflow_oidc_auth/entities/auth_context.py` — `AuthContext(username, is_admin, workspace)`
- `mlflow_oidc_auth/bridge/user.py` — `get_auth_context()`, `get_request_workspace()`
- `mlflow_oidc_auth/config.py` — `MLFLOW_ENABLE_WORKSPACES`, `GRANT_DEFAULT_WORKSPACE_ACCESS`

### Research
- `.planning/research/SUMMARY.md` — Executive summary with architecture context
- `.planning/REQUIREMENTS.md` — Full requirement list with traceability

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `experiment_permissions_router` — Reference implementation for permission CRUD router with FastAPI dependencies, store delegation, response models
- `check_admin_permission()` / `check_experiment_manage_permission()` in `dependencies.py` — Pattern for new `check_workspace_manage_permission()` dependency
- `WorkspacePermissionRepository` / `WorkspaceGroupPermissionRepository` — Phase 2 standalone repos with full CRUD already implemented
- `workspace_cache.py` — Phase 2 TTLCache with `get_workspace_permission_cached()` — add invalidation function here
- `_process_oidc_callback()` in `routers/auth.py` — Injection point for workspace detection (after group detection, before user creation)
- `BEFORE_REQUEST_HANDLERS` dict in `hooks/before_request.py` — Direct addition point for PromptOptimizationJob handlers
- Existing experiment validators — Can be reused directly for PromptOptimizationJob (experiment-scoped)

### Established Patterns
- Router → Dependency → Store → Repository chain for all permission management
- `_get_rest_path()` with `version=3` for v3.0 API prefixes (scorers use this)
- `config_manager.get()` / `config_manager.get_bool()` for new config entries
- `importlib.import_module()` for plugin loading (group detection plugin)
- Main `BEFORE_REQUEST_HANDLERS` dict for proto-based handler registration (as opposed to regex pattern matching used by logged models and workspaces)

### Integration Points
- `mlflow_oidc_auth/routers/__init__.py` — Register new workspace permissions router in `get_all_routers()`
- `mlflow_oidc_auth/routers/_prefix.py` — Add `WORKSPACE_PERMISSIONS_ROUTER_PREFIX`
- `mlflow_oidc_auth/config.py` `AppConfig.__init__()` — Add `OIDC_WORKSPACE_CLAIM_NAME`, `OIDC_WORKSPACE_DETECTION_PLUGIN`, `OIDC_WORKSPACE_DEFAULT_PERMISSION`
- `mlflow_oidc_auth/routers/auth.py` `_process_oidc_callback()` — Add workspace detection after group detection
- `mlflow_oidc_auth/hooks/before_request.py` `BEFORE_REQUEST_HANDLERS` — Add 5 PromptOptimizationJob entries
- `mlflow_oidc_auth/dependencies.py` — Add `check_workspace_manage_permission()`

</code_context>

<specifics>
## Specific Ideas

### Workspace Detection in OIDC Callback
The workspace detection should be a layered approach:
1. **Plugin first** — If `OIDC_WORKSPACE_DETECTION_PLUGIN` is set, call `get_user_workspaces(access_token)` (mirrors group detection exactly)
2. **JWT claim fallback** — If no plugin, extract from `userinfo.get(config.OIDC_WORKSPACE_CLAIM_NAME, [])` (like groups extraction)
3. **Auto-assign** — For each detected workspace, create workspace membership with `OIDC_WORKSPACE_DEFAULT_PERMISSION` (default: `NO_PERMISSIONS` — most secure, explicit grant required)

### Group-to-Workspace Mapping (Future)
User wants ability to configure group-to-workspace mappings (e.g., `team-frontend:workspace-frontend`) via admin UI. This is Phase 4 scope. The plugin hook from this phase provides the extensibility point — a built-in group-mapping plugin could be shipped as a default option alongside the UI.

### Permission Delegation Constraint
Non-admin workspace MANAGE users can grant any permission level up to and including MANAGE. This is safe because MANAGE is already the highest level. The router should validate that the granted permission is a valid permission level.

</specifics>

<deferred>
## Deferred Ideas

- **ENTITY-02: GatewayBudgetPolicy** — Protobuf RPCs don't exist in MLflow 3.10.1. Expected in MLflow 3.11.0. Create as future phase task when MLflow version target is updated.
- **Group-to-workspace mapping UI** — Admin UI for configuring group→workspace mappings. Phase 4 scope alongside workspace management UI (WSMGMT-06).
- **Cross-replica cache invalidation** — Phase 2 deferred; targeted local invalidation added in this phase. Full cross-replica coordination (Redis pub/sub, etc.) remains v2 deferred.
- **Regex workspace permissions** — v2 deferred (per Phase 2 context)
- **Workspace-scoped search result filtering in after_request** — v2 deferred (per Phase 2 context)

</deferred>

---

*Phase: 03-management-api-oidc-entity-coverage*
*Context gathered: 2026-03-23*
