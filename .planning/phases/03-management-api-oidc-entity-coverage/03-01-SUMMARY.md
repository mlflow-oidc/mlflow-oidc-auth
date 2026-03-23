---
phase: 03-management-api-oidc-entity-coverage
plan: 01
subsystem: workspace-permissions, management-api
tags: [fastapi, workspace, permissions, crud, pydantic, cache]
dependency_graph:
  requires:
    - phase: 02-workspace-auth-enforcement
      provides: workspace permission repositories, workspace cache, workspace entities
  provides:
    - 8 CRUD endpoints for workspace user+group permission management
    - Pydantic request/response models for workspace permissions
    - FastAPI dependencies for workspace MANAGE/READ permission checks
    - Store facade methods for workspace group permission CRUD
    - Cache invalidation for user workspace permission changes
  affects:
    - mlflow_oidc_auth/routers/__init__.py
    - mlflow_oidc_auth/dependencies.py
    - mlflow_oidc_auth/sqlalchemy_store.py
    - mlflow_oidc_auth/utils/workspace_cache.py
tech_stack:
  added: []
  patterns:
    - Workspace permission router follows experiment_permissions/scorers v3 pattern
    - User CUD invalidates cache; group CUD relies on TTL (per D-13/D-14/D-15)
    - check_workspace_manage_permission/check_workspace_read_permission dependency pattern
key_files:
  created:
    - mlflow_oidc_auth/models/workspace.py
    - mlflow_oidc_auth/routers/workspace_permissions.py
    - mlflow_oidc_auth/tests/routers/test_workspace_permissions.py
  modified:
    - mlflow_oidc_auth/models/__init__.py
    - mlflow_oidc_auth/sqlalchemy_store.py
    - mlflow_oidc_auth/utils/workspace_cache.py
    - mlflow_oidc_auth/dependencies.py
    - mlflow_oidc_auth/routers/_prefix.py
    - mlflow_oidc_auth/routers/__init__.py
    - mlflow_oidc_auth/tests/routers/conftest.py
key_decisions:
  - "Workspace permission router at v3.0 path (/api/3.0/mlflow/permissions/workspaces) consistent with scorers"
  - "User permission CUD invalidates cache immediately; group permission CUD relies on TTL expiry per D-15"
  - "check_workspace_manage_permission returns username (enables audit logging); check_workspace_read_permission same pattern"
  - "Store facade methods for group permissions resolve group_name to group_id using repository.utils.get_group()"
patterns_established:
  - "Workspace permission CRUD: 4 user endpoints + 4 group endpoints with separate Pydantic models"
  - "Selective cache invalidation: only user-level permission changes trigger immediate invalidation"
requirements_completed: [WSMGMT-01, WSMGMT-02, WSMGMT-03]
metrics:
  completed: "2026-03-23"
---

# Phase 03 Plan 01: Workspace Permission CRUD API Summary

8-endpoint FastAPI router for workspace user+group permission management with Pydantic models, MANAGE/READ dependency checks, store group facade methods, and selective cache invalidation.

## Tasks Completed

### Task 1: Pydantic models, store group methods, cache invalidation, FastAPI dependencies

**Pydantic models (`mlflow_oidc_auth/models/workspace.py`):**
- `WorkspaceUserPermissionRequest` — username + permission fields for user CUD operations
- `WorkspaceGroupPermissionRequest` — group_name + permission fields for group CUD operations
- `WorkspaceUserPermissionResponse` — workspace + username + permission for API responses
- `WorkspaceGroupPermissionResponse` — workspace + group_name + permission for API responses

**Store facade methods added to `mlflow_oidc_auth/sqlalchemy_store.py`:**
- `get_workspace_group_permission(workspace, group_name)` — resolves group_name → group_id via `get_group()`
- `create_workspace_group_permission(workspace, group_name, permission)`
- `update_workspace_group_permission(workspace, group_name, permission)`
- `delete_workspace_group_permission(workspace, group_name)`
- `list_workspace_group_permissions(workspace)` — returns all group permissions for a workspace

**Cache invalidation (`mlflow_oidc_auth/utils/workspace_cache.py`):**
- `invalidate_workspace_permission(username, workspace)` — removes specific (username, workspace) key from TTLCache
- Called by router after user permission CUD operations (per D-13/D-14)
- Group permission changes rely on TTL expiry only (per D-15)

**FastAPI dependencies (`mlflow_oidc_auth/dependencies.py`):**
- `check_workspace_manage_permission(workspace, request)` — admin OR workspace MANAGE permission required; returns username
- `check_workspace_read_permission(workspace, request)` — admin OR workspace READ permission required; returns username
- Both check `config.MLFLOW_ENABLE_WORKSPACES` flag, use `get_workspace_permission_cached()` for non-admin users

### Task 2: Workspace permissions router, registration, and tests

**Router prefix (`mlflow_oidc_auth/routers/_prefix.py`):**
- `WORKSPACE_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/workspaces", version=3)` → `/api/3.0/mlflow/permissions/workspaces`

**Router (`mlflow_oidc_auth/routers/workspace_permissions.py`) — 8 endpoints:**

| Method | Path | Function | Permission | Cache |
|--------|------|----------|------------|-------|
| GET | `/{workspace}/users` | `list_workspace_users` | READ | — |
| GET | `/{workspace}/groups` | `list_workspace_groups` | READ | — |
| POST | `/{workspace}/users` | `create_workspace_user_permission` | MANAGE | invalidate |
| POST | `/{workspace}/groups` | `create_workspace_group_permission` | MANAGE | TTL only |
| PATCH | `/{workspace}/users/{username}` | `update_workspace_user_permission` | MANAGE | invalidate |
| PATCH | `/{workspace}/groups/{group_name}` | `update_workspace_group_permission` | MANAGE | TTL only |
| DELETE | `/{workspace}/users/{username}` | `delete_workspace_user_permission` | MANAGE | invalidate |
| DELETE | `/{workspace}/groups/{group_name}` | `delete_workspace_group_permission` | MANAGE | TTL only |

**Registration (`mlflow_oidc_auth/routers/__init__.py`):**
- `workspace_permissions_router` imported, added to `__all__`, added to `get_all_routers()` return list

**Test fixture (`mlflow_oidc_auth/tests/routers/conftest.py`):**
- Added `workspace_permissions.store` to `_patch_router_stores` autouse fixture

**Tests (`mlflow_oidc_auth/tests/routers/test_workspace_permissions.py`) — 28 tests:**
- Router configuration: prefix, tags, responses, route count, path constants
- User endpoints: list (populated + empty + fallback), create, update, delete
- Group endpoints: list (populated + fallback), create, update, delete
- Cache invalidation: user CUD calls `invalidate_workspace_permission`; group CUD does NOT
- Response models: field validation for all 4 Pydantic models

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed workspace_cache.py file corruption**
- **Found during:** Task 1
- **Issue:** Edit tool accidentally replaced content in middle of `get_workspace_permission_cached` instead of appending at end, causing indentation error and duplicated code
- **Fix:** Rewrote entire `workspace_cache.py` preserving original functions plus new `invalidate_workspace_permission`
- **Files modified:** `mlflow_oidc_auth/utils/workspace_cache.py`

**2. [Rule 3 - Blocking] Added store mock to test conftest**
- **Found during:** Task 2
- **Issue:** `_patch_router_stores` autouse fixture in `conftest.py` didn't include `workspace_permissions.store`, causing test failures
- **Fix:** Added `"mlflow_oidc_auth.routers.workspace_permissions.store"` to the patch list
- **Files modified:** `mlflow_oidc_auth/tests/routers/conftest.py`

## Verification Results

| Check | Result |
|-------|--------|
| 4 Pydantic models importable from `models.workspace` | ✅ PASSED |
| `check_workspace_manage_permission` importable from `dependencies` | ✅ PASSED |
| `check_workspace_read_permission` importable from `dependencies` | ✅ PASSED |
| 5 store facade group methods present on `SqlAlchemyStore` | ✅ PASSED |
| `invalidate_workspace_permission` importable from `workspace_cache` | ✅ PASSED |
| Router has 8 routes | ✅ PASSED |
| Router registered in `get_all_routers()` (16 total routers) | ✅ PASSED |
| `invalidate_workspace_permission` in user CUD endpoints (3 calls) | ✅ PASSED |
| `invalidate_workspace_permission` NOT in group CUD endpoints | ✅ PASSED |
| `test_workspace_permissions.py` — 28/28 tests pass | ✅ PASSED |
| Existing router tests — 580 collected, no failures | ✅ PASSED |

## Deferred Items

None.

## Known Stubs

None — all code paths are fully wired.

## Self-Check: PASSED

All 4 created files verified present on disk. All 11 verification checks passed. No commits created (per instructions — code changes only).
