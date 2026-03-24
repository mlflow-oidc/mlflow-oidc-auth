# Technology Stack — v1.1 Workspace Management

**Project:** MLflow OIDC Auth — Workspace CRUD, Scoped Search, Regex Permissions, Global Picker
**Researched:** 2026-03-24
**Scope:** Additions/changes only — existing stack validated in v1.0 research
**Confidence:** HIGH

## Executive Summary

**No new Python or JavaScript libraries are needed for v1.1.** The existing stack has every capability required. The workspace CRUD "proxy" doesn't require `httpx` forwarding — MLflow's Flask app already handles `/api/3.0/mlflow/workspaces/*` routes, and they pass through the plugin's `before_request`/`after_request` hooks via the AuthAwareWSGIMiddleware bridge. The only stack change is pinning `cachetools` explicitly (currently transitive-only).

## Recommended Stack Changes

### New Direct Dependency

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `cachetools` | >=5.5.0 | TTLCache for workspace permission lookups | **Already used** in `workspace_cache.py` but only available as transitive dependency via MLflow. PROJECT.md explicitly flags this as a known gap: "cachetools is transitive dependency only — not pinned in pyproject.toml." Pin it to avoid breakage if MLflow changes its dependency tree. v5.5.0+ required for Python 3.12 compatibility. Confidence: HIGH (verified installed v7.0.5, used in production code). |

### No Changes Needed

| Technology | Current Version | Why No Change |
|------------|----------------|---------------|
| `httpx` | >=0.28.1 | **NOT needed for workspace CRUD proxy.** MLflow's workspace endpoints (`/api/3.0/mlflow/workspaces/*`) are Flask routes served by MLflow's app, mounted at `/` via `AuthAwareWSGIMiddleware`. Requests flow: Client → FastAPI → AuthMiddleware → WSGI bridge → Flask → MLflow handlers. The plugin's `before_request_hook()` and `after_request_hook()` already intercept these. No HTTP forwarding required. |
| `sqlalchemy` | >=2.0.46, <3 | New regex workspace permission tables follow identical pattern to existing regex tables (e.g., `SqlExperimentRegexPermission`). No version bump needed. |
| `alembic` | <2, !=1.18.4 | One new migration for regex workspace permission tables. Standard usage. |
| `fastapi` | >=0.132.0 | No new FastAPI patterns needed. Workspace CRUD goes through Flask, not FastAPI routers. |
| React/TypeScript | React 19.1 / TS 5.9 | Global workspace picker uses existing React Context pattern. No new UI libraries needed. |
| TailwindCSS | 4.x | Existing utility classes sufficient for dropdown/picker component. |

## Detailed Analysis Per Feature

### 1. Workspace CRUD Backend (Proxy to MLflow)

**Stack needed:** Nothing new. This is the key insight.

**Architecture clarification:** The word "proxy" in the requirements is misleading. MLflow's Flask app already registers handlers for all 5 workspace RPCs:
- `POST   /api/3.0/mlflow/workspaces` → `CreateWorkspace`
- `GET    /api/3.0/mlflow/workspaces` → `ListWorkspaces`
- `GET    /api/3.0/mlflow/workspaces/<workspace_name>` → `GetWorkspace`
- `PATCH  /api/3.0/mlflow/workspaces/<workspace_name>` → `UpdateWorkspace`
- `DELETE /api/3.0/mlflow/workspaces/<workspace_name>` → `DeleteWorkspace`

These routes are handled by Flask, which is mounted inside FastAPI via `AuthAwareWSGIMiddleware` at `/`. The plugin's `before_request_hook()` already intercepts them (verified: `WORKSPACE_BEFORE_REQUEST_HANDLERS` maps all 5 protobuf classes to validators). The `after_request_hook()` already has `_filter_list_workspaces` for `ListWorkspaces`.

**What's needed for v1.1:**
- Extend `after_request.py` handlers to auto-grant workspace MANAGE on `CreateWorkspace` (same pattern as `_set_can_manage_experiment_permission`)
- Add cascade permission delete on `DeleteWorkspace` (same pattern as `_delete_can_manage_registered_model_permission`)
- These use **only existing imports**: `mlflow.protos.service_pb2`, Flask `Response`, `store`, `get_fastapi_username`

**What's NOT needed:**
- No `httpx.AsyncClient` for forwarding requests to MLflow's backend
- No new FastAPI router for workspace CRUD
- No separate HTTP proxy middleware

Confidence: HIGH (verified by tracing request flow through `app.py` → `AuthAwareWSGIMiddleware` → Flask → `before_request_hook` → `after_request_hook`)

### 2. Workspace-Scoped Search Result Filtering

**Stack needed:** Nothing new.

**Current state:** `after_request.py` already filters:
- `SearchExperiments` → `_filter_search_experiments()` using `can_read_experiment()`
- `SearchRegisteredModels` → `_filter_search_registered_models()` using `can_read_registered_model()`
- `SearchLoggedModels` → `_filter_search_logged_models()` using `can_read_experiment()`
- `ListWorkspaces` → `_filter_list_workspaces()` using `get_workspace_permission_cached()`

**What's needed for v1.1:**
- When `MLFLOW_ENABLE_WORKSPACES` is true AND `AuthContext.workspace` is set, add workspace membership check to experiment/model search filters
- Use existing `get_workspace_permission_cached()` (from `workspace_cache.py`) alongside existing `can_read_experiment()`/`can_read_registered_model()`
- Pattern: Check if experiment/model belongs to the workspace context, then check user has workspace access
- Uses only existing imports: `config.MLFLOW_ENABLE_WORKSPACES`, `get_auth_context()`, `get_workspace_permission_cached()`

**Important limitation:** The plugin cannot know which experiments/models belong to which workspace without querying MLflow's tracking store. MLflow's `Experiment` proto has a `workspace` field (added in 3.10). The filter functions already access `response_message.experiments` — they just need to read the workspace field from each experiment proto.

Confidence: HIGH (verified `after_request.py` patterns and `SearchExperiments.Response` protobuf fields)

### 3. Regex Workspace Permissions

**Stack needed:** Nothing new (follows established pattern exactly).

**Established pattern (verified in codebase):**

| Layer | Existing Example | Workspace Equivalent |
|-------|-----------------|---------------------|
| ORM Model | `SqlExperimentRegexPermission` (4 columns: id, regex, priority, user_id, permission) | `SqlWorkspaceRegexPermission` (same columns) |
| ORM Model | `SqlExperimentGroupRegexPermission` (4 columns: id, regex, priority, group_id, permission) | `SqlWorkspaceGroupRegexPermission` (same columns) |
| Entity | `ExperimentRegexPermission` (in `entities/`) | `WorkspaceRegexPermission` |
| Repository | `ExperimentPermissionRegexRepository(BaseRegexPermissionRepository)` — 18 lines | `WorkspaceRegexPermissionRepository` — standalone (per WSAUTH-B decision) |
| Migration | Standard `op.create_table()` with FK constraints | Same pattern as `7b8c9d0ef123_add_workspace_permissions.py` |
| Store methods | `store.create_experiment_regex_permission()` | `store.create_workspace_regex_permission()` |
| Cache integration | N/A for experiments | Extend `_lookup_workspace_permission()` in `workspace_cache.py` to check regex after user+group |

**Decision: Standalone vs Base class repos?**

Per existing decision WSAUTH-B, workspace repos are standalone (not extending base classes). This should continue for regex workspace repos. Reason: Workspace is a tenant boundary, not a resource. The regex matching pattern is the same, but the query patterns and access semantics differ.

However, the implementation can still **delegate to the same utility functions** from `repository/utils.py` (`get_user`, `get_group`, `validate_regex`, `list_user_groups`).

**Alembic migration:** One migration adds 2 tables:
- `workspace_regex_permissions` (id, regex, priority, user_id FK, permission) with unique constraint on (regex, user_id)
- `workspace_group_regex_permissions` (id, regex, priority, group_id FK, permission) with unique constraint on (regex, group_id)

Confidence: HIGH (verified pattern across 8+ existing regex permission implementations)

### 4. Global Workspace Picker UI

**Stack needed:** Nothing new.

**Existing infrastructure:**
- `RuntimeConfig` type already has `workspaces_enabled: boolean` (verified in `runtime-config.ts`)
- `useAllWorkspaces()` hook already fetches from `/api/3.0/mlflow/workspaces` (verified in `use-all-workspaces.ts`)
- `WorkspaceListItem` type already defined with `name`, `description`, `default_artifact_root` (verified in `entity.ts`)
- `WorkspaceListResponse` type already wraps the array (verified)
- Sidebar already conditionally renders Workspaces link when `workspacesEnabled` (verified in `sidebar-data.ts`)
- Header component has a `<div className="flex z-4">` section between logo and nav that's the natural place for a picker

**What's needed for v1.1:**
- New React Context: `WorkspaceContext` (provides `selectedWorkspace`, `setSelectedWorkspace`)
- New component: `workspace-picker.tsx` (dropdown in header, uses `useAllWorkspaces`)
- Context value propagated to all API calls via `X-MLFLOW-WORKSPACE` header
- Modify `http.ts` service to include workspace header when set
- Store selected workspace in `localStorage` for persistence across sessions

**React patterns to use:**
- `createContext()` + custom hook (existing pattern: `RuntimeConfigContext` in `use-runtime-config.ts`)
- TailwindCSS dropdown styling (existing utility classes, no UI library needed)
- FontAwesome icon (already available: `faBuilding` used in sidebar-data.ts)

**Why NOT add a UI component library (e.g., Headless UI, Radix):**
- The entire existing UI uses raw TailwindCSS with custom components
- A dropdown picker is simple enough to build without a library
- Adding a component library would be inconsistent with the existing codebase
- All existing dropdowns/modals in the app use custom implementations

Confidence: HIGH (verified all existing UI patterns and infrastructure)

## What NOT to Add

| Don't Add | Why | Use Instead |
|-----------|-----|-------------|
| `httpx` for workspace CRUD proxy | MLflow's Flask app handles workspace routes natively. The plugin already intercepts them via hooks. Adding HTTP forwarding would create a second request path with different auth semantics. | Existing Flask hook interception (before_request + after_request) |
| `starlette.responses.StreamingResponse` for proxy | No streaming needed — workspace CRUD responses are small JSON (workspace list, single workspace). | Existing Flask response handling in after_request hooks |
| Headless UI / Radix UI / shadcn/ui | The codebase uses raw TailwindCSS + custom components. A dropdown picker doesn't justify introducing a component library. | Custom TailwindCSS dropdown component |
| `zustand` / `jotai` / `@tanstack/react-query` | The codebase uses React Context + custom `useApi` hook for state. No complex state management needed for workspace picker. | `React.createContext()` + `useAllWorkspaces()` hook (existing) |
| `redis` / external cache | `cachetools.TTLCache` is already working for workspace permissions. In-process cache is sufficient for this workload. | Existing `workspace_cache.py` with `TTLCache` |
| Separate workspace permission API version | Workspace permission CRUD already uses `/api/3.0/` prefix (verified in `_prefix.py`). Regex endpoints should use the same version. | `/api/3.0/mlflow/permissions/workspaces/` prefix (existing) |

## pyproject.toml Change

```toml
# BEFORE (current):
dependencies = [
  "mlflow<4,>=3.10.0",
  # ... existing deps ...
  "httpx>=0.28.1"
]

# AFTER (v1.1):
dependencies = [
  "mlflow<4,>=3.10.0",
  # ... existing deps ...
  "httpx>=0.28.1",
  "cachetools>=5.5.0",  # TTL cache for workspace permissions (was transitive-only)
]
```

**No package.json changes needed.** The frontend uses only existing React 19 APIs and existing custom hooks.

## Integration Points

### Backend Integration Map

| New Feature | Touches | Pattern From |
|-------------|---------|-------------|
| CreateWorkspace after_request | `after_request.py`, `AFTER_REQUEST_PATH_HANDLERS` | `_set_can_manage_experiment_permission` |
| DeleteWorkspace after_request | `after_request.py`, `AFTER_REQUEST_PATH_HANDLERS` | `_delete_can_manage_registered_model_permission` |
| Workspace-scoped search filter | `after_request.py`, `_filter_search_experiments`, `_filter_search_registered_models` | Existing filter functions + `get_workspace_permission_cached` |
| Regex workspace models | `db/models/workspace.py` | `db/models/experiment.py` (SqlExperimentRegexPermission) |
| Regex workspace entities | `entities/workspace.py` | `entities/__init__.py` (ExperimentRegexPermission) |
| Regex workspace repos | `repository/` (2 new files) | `repository/experiment_permission_regex.py` (standalone, not base class) |
| Regex workspace store | `sqlalchemy_store.py`, `store.py` | Existing workspace permission store methods |
| Regex workspace router | `routers/workspace_permissions.py` | Existing user/group workspace permission endpoints |
| Regex workspace cache | `utils/workspace_cache.py` → `_lookup_workspace_permission()` | Add regex check after user+group checks |
| Regex workspace migration | `db/migrations/versions/` (1 new file) | `7b8c9d0ef123_add_workspace_permissions.py` |

### Frontend Integration Map

| New Feature | Touches | Pattern From |
|-------------|---------|-------------|
| Workspace picker component | New `shared/components/workspace-picker.tsx` | Sidebar dropdown pattern |
| Workspace context | New `shared/context/workspace-context.tsx` | `runtime-config-provider.tsx` |
| Header integration | `shared/components/header.tsx` | Insert between logo and nav |
| HTTP header injection | `core/services/http.ts` | Add `X-MLFLOW-WORKSPACE` header conditionally |
| API endpoints | `core/configs/api-endpoints.ts` | Add regex workspace permission endpoints |
| Workspace service | `core/services/workspace-service.ts` | Add CRUD and regex permission fetchers |
| Entity types | `shared/types/entity.ts` | Add `WorkspaceRegexPermission` type |

## Version Compatibility

| Package A | Package B | Compatible? | Notes |
|-----------|-----------|-------------|-------|
| cachetools >=5.5.0 | mlflow >=3.10.0 | ✅ YES | MLflow 3.10 uses cachetools internally. Pinning >=5.5.0 won't conflict. |
| cachetools >=5.5.0 | Python 3.12 | ✅ YES | cachetools 5.5+ fully supports Python 3.12. |
| cachetools >=5.5.0 | sqlalchemy >=2.0.46 | ✅ YES | No interaction. |

## Sources

- Plugin codebase analysis: `app.py`, `hooks/after_request.py`, `hooks/before_request.py`, `middleware/auth_middleware.py`, `middleware/auth_aware_wsgi_middleware.py`, `repository/_base.py`, `routers/workspace_permissions.py`, `db/models/workspace.py`, `db/models/experiment.py`, `utils/workspace_cache.py`, `config.py`, `validators/workspace.py`, `entities/auth_context.py`, `permissions.py` — All verified directly. Confidence: HIGH.
- MLflow workspace endpoint registration: `get_endpoints()` returns all 5 workspace RPCs with `/api/3.0/mlflow/workspaces` paths — Verified via runtime introspection. Confidence: HIGH.
- MLflow workspace protobuf availability: `CreateWorkspace`, `GetWorkspace`, `ListWorkspaces`, `UpdateWorkspace`, `DeleteWorkspace` all importable from `mlflow.protos.service_pb2` — Verified at runtime. Confidence: HIGH.
- Frontend codebase: `runtime-config.ts`, `workspace-service.ts`, `use-all-workspaces.ts`, `api-endpoints.ts`, `entity.ts`, `header.tsx`, `sidebar-data.ts` — All verified directly. Confidence: HIGH.
- `cachetools` v7.0.5 installed, used in `workspace_cache.py` line 7 (`from cachetools import TTLCache`) — Verified. Confidence: HIGH.
- `httpx` v0.28.1 installed, used ONLY in `tests/integration/` — Verified via grep. Confidence: HIGH.

---
*Stack research for: MLflow OIDC Auth — v1.1 Workspace Management*
*Researched: 2026-03-24*
*Key finding: Zero new libraries needed. Pin cachetools. "Proxy" is already handled by Flask mount.*
