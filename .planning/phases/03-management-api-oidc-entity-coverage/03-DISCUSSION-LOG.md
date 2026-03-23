# Phase 3: Management API, OIDC & Entity Coverage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 03-management-api-oidc-entity-coverage
**Areas discussed:** Workspace permission API design, OIDC workspace claim mapping, New entity auth coverage, Cache invalidation on permission changes

---

## Workspace Permission API Design

### Router structure and URL prefix

| Option | Description | Selected |
|--------|-------------|----------|
| Single router at v3.0 | One workspace permissions router using `_get_rest_path(version=3)`, consistent with scorers pattern | ✓ |
| Split user/group routers | Separate routers for workspace-user and workspace-group permissions | |
| Reuse existing routers | Add workspace endpoints to existing experiment_permissions or user_permissions routers | |

**User's choice:** Single router at v3.0 — `/api/3.0/mlflow/permissions/workspaces`
**Notes:** Consistent with scorers router prefix pattern. Workspaces are a 3.10 feature so v3.0 makes sense.

### Endpoint style

| Option | Description | Selected |
|--------|-------------|----------|
| REST resource style | `/{workspace}/users`, `/{workspace}/groups` with standard HTTP verbs | ✓ |
| Action-based | `/workspace/grant`, `/workspace/revoke` style endpoints | |
| Query parameter style | Single endpoint with `?type=user&action=create` parameters | |

**User's choice:** REST resource style with PATCH for updates (not PUT)
**Notes:** Full endpoint list: GET/POST for list/create, PATCH for update, DELETE for delete — both for users and groups under workspace path.

### Permission dependency for delegation

| Option | Description | Selected |
|--------|-------------|----------|
| New workspace MANAGE dependency | `check_workspace_manage_permission()` — global admin OR workspace MANAGE | ✓ |
| Admin-only | Only global admins can manage workspace permissions | |
| Workspace READ for all | Any workspace member can view and modify permissions | |

**User's choice:** New `check_workspace_manage_permission()` FastAPI dependency. List endpoints require workspace READ.
**Notes:** Enables non-admin delegation — users with MANAGE on a workspace can grant permissions to others.

### Privilege ceiling for delegation

| Option | Description | Selected |
|--------|-------------|----------|
| Cap at MANAGE | Workspace MANAGE users can grant up to and including MANAGE | ✓ |
| Cap below MANAGE | MANAGE users can only grant up to EDIT (not MANAGE) | |
| No ceiling | Any permission level can be granted by any manager | |

**User's choice:** No privilege ceiling beyond MANAGE — MANAGE users can grant MANAGE to others.
**Notes:** MANAGE is already the highest level, so no escalation risk.

### Pydantic models

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated workspace models | New `WorkspaceUserPermissionRequest`, `WorkspaceGroupPermissionRequest`, `WorkspacePermissionResponse` | ✓ |
| Reuse existing models | Extend existing permission request models with workspace field | |

**User's choice:** Dedicated Pydantic models for workspace permissions.
**Notes:** Keeps workspace permission API self-contained.

---

## OIDC Workspace Claim Mapping

### Workspace detection mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| JWT claim + plugin hook | Default JWT claim extraction + `OIDC_WORKSPACE_DETECTION_PLUGIN` mirroring group detection pattern | ✓ |
| JWT claim only | Simple claim extraction, no plugin extensibility | |
| Plugin only | Require plugin for all workspace detection | |

**User's choice:** Layered approach — plugin first (if configured), JWT claim fallback (if no plugin). Mirrors group detection exactly.
**Notes:** `OIDC_WORKSPACE_CLAIM_NAME` config (default: `'workspace'`). `OIDC_WORKSPACE_DETECTION_PLUGIN` follows `importlib.import_module().get_user_workspaces(access_token)` pattern.

### Default permission for auto-created memberships

| Option | Description | Selected |
|--------|-------------|----------|
| NO_PERMISSIONS | Users get associated but no access until explicitly granted | ✓ |
| READ | Users can read workspace resources by default | |
| Configurable default | Admin sets the default via config | |

**User's choice:** `NO_PERMISSIONS` as the default — most secure option. Configurable via `OIDC_WORKSPACE_DEFAULT_PERMISSION` config.
**Notes:** Users are associated with the workspace during OIDC login but have no access until a workspace MANAGE user or admin explicitly grants permissions.

### Group-to-workspace mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to Phase 4 | Backend hooks only in this phase; UI mapping in Phase 4 | ✓ |
| Include in this phase | Build full group-to-workspace mapping config + UI now | |

**User's choice:** Deferred to Phase 4.
**Notes:** This phase delivers the plugin hook extensibility point. A built-in group-mapping plugin could ship alongside the Phase 4 UI.

---

## New Entity Auth Coverage

### PromptOptimizationJob handler placement

| Option | Description | Selected |
|--------|-------------|----------|
| Main BEFORE_REQUEST_HANDLERS | Add to the main handler dict alongside experiments, runs, models | ✓ |
| Separate handler group | Create PROMPT_OPT_JOB_HANDLERS similar to WORKSPACE_BEFORE_REQUEST_VALIDATORS | |

**User's choice:** Main `BEFORE_REQUEST_HANDLERS` dict — same pattern as experiments, runs, models.
**Notes:** All 5 RPCs confirmed present in MLflow 3.10.1: Create, Get, Search, Delete, Cancel.

### Permission model for PromptOptimizationJob

| Option | Description | Selected |
|--------|-------------|----------|
| Experiment-scoped | Reuse experiment permission validators (READ/EDIT mapped to job operations) | ✓ |
| Dedicated permissions | New PromptOptimizationJob permission type | |

**User's choice:** Experiment-scoped permissions — reuse existing experiment validators.
**Notes:** Mapping: Create→EDIT (like CreateRun), Get/Search→READ, Delete→EDIT or DELETE, Cancel→EDIT (like cancelling a run).

### ENTITY-02 (GatewayBudgetPolicy)

| Option | Description | Selected |
|--------|-------------|----------|
| Defer | Protos don't exist in 3.10.1; defer to future phase | ✓ |
| Stub handlers | Create placeholder handlers that will be activated when protos arrive | |

**User's choice:** Defer entirely — expected in MLflow 3.11.0.
**Notes:** No stubs, no placeholders. Will be a future phase task when MLflow version target is updated.

---

## Cache Invalidation on Permission Changes

### Invalidation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Targeted local cache.pop() | Invalidate specific (username, workspace) entry on user permission changes | ✓ |
| Full cache clear | Clear entire workspace permission cache on any change | |
| No invalidation | Rely entirely on TTL for all changes | |

**User's choice:** Targeted local invalidation via `cache.pop((username, workspace))`.
**Notes:** Single-process only — TTL still handles cross-replica staleness.

### Where invalidation lives

| Option | Description | Selected |
|--------|-------------|----------|
| Router layer | Workspace permission router calls cache invalidation after store operations | ✓ |
| Store layer | Store methods automatically invalidate cache on write | |
| Middleware | Middleware intercepts permission-modifying responses | |

**User's choice:** Router layer — store doesn't know about cache.
**Notes:** Keep cache concerns in the API layer, not the data access layer.

### Scope of invalidation triggers

| Option | Description | Selected |
|--------|-------------|----------|
| User changes only | Only user permission CRUD triggers invalidation; groups rely on TTL | ✓ |
| All permission changes | Both user and group permission changes trigger invalidation | |

**User's choice:** User permission changes only. Group changes rely on TTL-based expiry.
**Notes:** Group membership changes are rarer and tracing affected users is expensive. Pragmatic — group changes propagate within TTL window.

---

## Agent's Discretion

- Exact Pydantic model field names and response structure
- Exact validator function names for PromptOptimizationJob (reuse existing or create dedicated wrappers)
- How workspace claim extraction integrates into `_process_oidc_callback()` flow
- Error response format for permission delegation failures
- Whether `invalidate_workspace_permission()` is a new function or inline in the router
- New config variables added to `AppConfig` — exact naming conventions

## Deferred Ideas

- **ENTITY-02: GatewayBudgetPolicy** — Protobuf RPCs not present in MLflow 3.10.1. Expected in 3.11.0.
- **Group-to-workspace mapping UI** — Phase 4 scope alongside workspace management UI (WSMGMT-06).
- **Cross-replica cache invalidation** — Redis pub/sub or similar. Remains deferred from Phase 2.
- **Regex workspace permissions** — Deferred from Phase 2.
- **Workspace-scoped search result filtering in after_request** — Deferred from Phase 2.

---

*Phase: 03-management-api-oidc-entity-coverage*
*Discussion log generated: 2026-03-23*
