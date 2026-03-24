---
phase: 06-workspace-crud-backend
verified: 2026-03-24T17:35:23Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 6: Workspace CRUD Backend Verification Report

**Phase Goal:** Users can create, list, view, update, and delete workspaces through the plugin's API with proper authorization and automatic permission management
**Verified:** 2026-03-24T17:35:23Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Admin can create a workspace and automatically receives MANAGE permission on it | ✓ VERIFIED | `after_request.py:462-489` — `_auto_grant_workspace_manage_permission` calls `store.create_workspace_permission(workspace_name, auth_context.username, MANAGE.name)` after successful CreateWorkspace. Registered in `AFTER_REQUEST_PATH_HANDLERS` at line 558. 8 tests in `test_workspace_hooks.py::TestAutoGrantWorkspaceManagePermission` pass. |
| 2 | Non-admin user listing workspaces sees only workspaces they have permission to access (including regex-granted access) | ✓ VERIFIED | Two paths: (a) Flask hook `_filter_list_workspaces` at line 515-534 filters by `get_workspace_permission_cached` (includes regex). (b) FastAPI `workspace_crud.py:84-105` — `list_workspaces` filters via `get_workspace_permission_cached(username, ws.name)` for non-admins. Both tested. |
| 3 | User with MANAGE permission can update a workspace's description and delete it (if empty), while unprivileged users get 403 | ✓ VERIFIED | `validators/workspace.py:48-73` — both `validate_can_update_workspace` and `validate_can_delete_workspace` check `perm.can_manage` via `get_workspace_permission_cached`. FastAPI router uses `Depends(check_workspace_manage_permission)` for PATCH and DELETE. 8 validator tests pass (`TestValidateCanUpdateWorkspaceManage`, `TestValidateCanDeleteWorkspaceManage`). |
| 4 | Deleting a workspace cascade-deletes all associated user and group permission rows | ✓ VERIFIED | `after_request.py:492-512` — `_cascade_delete_workspace_permissions` calls `store.wipe_workspace_permissions(name)`. `sqlalchemy_store.py:1363-1378` — `wipe_workspace_permissions` delegates to both `workspace_permission_repo.delete_all_for_workspace` and `workspace_group_permission_repo.delete_all_for_workspace`. Repo methods at `workspace_permission.py:181-197` and `workspace_group_permission.py:183-199` confirmed with bulk DELETE queries. 5 cascade-delete tests pass. |
| 5 | Workspace CRUD endpoints do not exist when MLFLOW_ENABLE_WORKSPACES=false | ✓ VERIFIED | `app.py:164-167` — `workspace_crud_router` imported and included inside `if config.MLFLOW_ENABLE_WORKSPACES:` block. `routers/__init__.py:65-89` — `get_all_routers()` does NOT include `workspace_crud_router`. Runtime verified: `python -c` confirmed 'workspace crud' not in router tags. Test `TestRouterConfiguration::test_router_not_in_get_all_routers` passes. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mlflow_oidc_auth/hooks/after_request.py` | Auto-grant MANAGE on create, cascade-delete on delete | ✓ VERIFIED | Contains `_auto_grant_workspace_manage_permission` (line 462), `_cascade_delete_workspace_permissions` (line 492), both registered in `AFTER_REQUEST_PATH_HANDLERS` (lines 558-559). Imports `flush_workspace_cache` (line 57). 578 lines, substantive. |
| `mlflow_oidc_auth/validators/workspace.py` | MANAGE-based delegation for update/delete | ✓ VERIFIED | `validate_can_update_workspace` (line 48) and `validate_can_delete_workspace` (line 62) both check `get_workspace_permission_cached` + `perm.can_manage`. 78 lines, substantive. |
| `mlflow_oidc_auth/sqlalchemy_store.py` | `wipe_workspace_permissions` method | ✓ VERIFIED | Method at line 1363 — delegates to both `workspace_permission_repo.delete_all_for_workspace` and `workspace_group_permission_repo.delete_all_for_workspace`. Returns combined count. 1474 lines total. |
| `mlflow_oidc_auth/repository/workspace_permission.py` | `delete_all_for_workspace` method | ✓ VERIFIED | Method at line 181 — bulk DELETE query on `SqlWorkspacePermission` filtered by workspace name. Returns count. 197 lines. |
| `mlflow_oidc_auth/repository/workspace_group_permission.py` | `delete_all_for_workspace` method | ✓ VERIFIED | Method at line 183 — bulk DELETE query on `SqlWorkspaceGroupPermission` filtered by workspace name. Returns count. 245 lines. |
| `mlflow_oidc_auth/routers/workspace_crud.py` | FastAPI CRUD router with 5 endpoints | ✓ VERIFIED | 5 routes: POST (create, admin-only), GET list (filtered), GET `/{workspace}` (read perm), PATCH `/{workspace}` (manage perm), DELETE `/{workspace}` (manage perm, RESTRICT mode, blocks "default"). 201 lines, fully implemented. |
| `mlflow_oidc_auth/models/workspace.py` | Pydantic CRUD models with validation | ✓ VERIFIED | Contains `WorkspaceCrudCreateRequest` with `WORKSPACE_NAME_PATTERN` DNS-safe regex, `field_validator`, min/max length, reserved names. `WorkspaceCrudUpdateRequest`, `WorkspaceCrudResponse`. 148 lines. |
| `mlflow_oidc_auth/app.py` | Feature-flag gated router registration | ✓ VERIFIED | Lines 164-167 — `workspace_crud_router` imported and registered inside `if config.MLFLOW_ENABLE_WORKSPACES:` block. 179 lines. |
| `mlflow_oidc_auth/routers/auth.py` | OIDC auto-create workspace | ✓ VERIFIED | Lines 492-543 — workspace auto-create via `_get_workspace_store().create_workspace()` before permission assignment. Wrapped in try/except — failures don't block login. |
| `mlflow_oidc_auth/routers/__init__.py` | Exports workspace_crud_router but NOT in get_all_routers() | ✓ VERIFIED | Line 41: imported. Line 61: in `__all__`. Lines 72-89: NOT in `get_all_routers()`. |
| `mlflow_oidc_auth/routers/_prefix.py` | WORKSPACE_CRUD_ROUTER_PREFIX constant | ✓ VERIFIED | Line 30: `WORKSPACE_CRUD_ROUTER_PREFIX = _get_rest_path("/mlflow/workspaces/crud", version=3)`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `hooks/after_request.py` | `store.py` | `store.create_workspace_permission()` and `store.wipe_workspace_permissions()` | ✓ WIRED | Line 482: `store.create_workspace_permission(...)`, Line 507: `store.wipe_workspace_permissions(name)`. Store imported at line 45. |
| `validators/workspace.py` | `utils/workspace_cache.py` | `get_workspace_permission_cached` for MANAGE check | ✓ WIRED | Lines 56-57 and 70-71: `perm = get_workspace_permission_cached(...)` → `if perm is not None and perm.can_manage`. Imported at line 7. |
| `hooks/after_request.py` | `AFTER_REQUEST_PATH_HANDLERS` | `CreateWorkspace` and `DeleteWorkspace` mapped | ✓ WIRED | Line 558: `CreateWorkspace: _auto_grant_workspace_manage_permission`, Line 559: `DeleteWorkspace: _cascade_delete_workspace_permissions`. |
| `routers/workspace_crud.py` | `mlflow.server.handlers._get_workspace_store` | Direct calls for CRUD | ✓ WIRED | Imported at line 11. Used in all 5 endpoints (lines 55, 91, 119, 146, 179). |
| `routers/workspace_crud.py` | `dependencies.py` | FastAPI dependency injection | ✓ WIRED | Lines 13-17: imports `check_admin_permission`, `check_workspace_manage_permission`, `check_workspace_read_permission`. Used via `Depends()` in all route signatures. |
| `app.py` | `routers/workspace_crud.py` | Conditional include_router | ✓ WIRED | Lines 164-167: inside `if config.MLFLOW_ENABLE_WORKSPACES:` block, imports and includes the router. |
| `routers/auth.py` | `mlflow.server.handlers._get_workspace_store` | Auto-create workspace in OIDC callback | ✓ WIRED | Lines 494-496: `_get_workspace_store()` imported and called. Lines 513-527: `get_workspace()` + `create_workspace()` pattern for auto-create. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `workspace_crud.py::list_workspaces` | `all_workspaces` | `_get_workspace_store().list_workspaces()` | Yes — MLflow native store query | ✓ FLOWING |
| `workspace_crud.py::get_workspace` | `ws` | `_get_workspace_store().get_workspace(workspace)` | Yes — MLflow native store query | ✓ FLOWING |
| `workspace_crud.py::create_workspace` | `workspace` | `_get_workspace_store().create_workspace(...)` | Yes — MLflow native store create | ✓ FLOWING |
| `after_request.py::_filter_list_workspaces` | `data["workspaces"]` | Flask response JSON | Yes — MLflow response data filtered | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 2383 tests pass | `python -m pytest mlflow_oidc_auth/tests/ -q --ignore=.../test_ui.py` | 2383 passed in 97.68s | ✓ PASS |
| 103 workspace-specific tests pass | `python -m pytest ...test_workspace_hooks.py ...test_workspace_permission.py ...test_workspace_crud.py ...test_auth_workspace_autocreate.py -v` | 103 passed in 1.62s | ✓ PASS |
| Feature flag gating runtime check | `python -c "from mlflow_oidc_auth.routers import get_all_routers; ..."` | workspace_crud_router NOT in get_all_routers() | ✓ PASS |
| Workspace CRUD router has 5 routes | Test `TestRouterConfiguration::test_router_has_five_routes` | Passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WSCRUD-01 | 06-01 | Admin can create workspace with auto-granted MANAGE permission | ✓ SATISFIED | `_auto_grant_workspace_manage_permission` after-hook + `create_workspace` endpoint admin-only |
| WSCRUD-02 | 06-01 | Authenticated user can list workspaces filtered by permissions | ✓ SATISFIED | `_filter_list_workspaces` (Flask) + `list_workspaces` (FastAPI) both filter non-admins via `get_workspace_permission_cached` |
| WSCRUD-03 | 06-01 | User with workspace permission can get workspace details | ✓ SATISFIED | `validate_can_read_workspace` (Flask) + `check_workspace_read_permission` dependency (FastAPI) |
| WSCRUD-04 | 06-01 | User with MANAGE can update workspace description | ✓ SATISFIED | `validate_can_update_workspace` checks `perm.can_manage` + FastAPI `Depends(check_workspace_manage_permission)` |
| WSCRUD-05 | 06-01 | User with MANAGE can delete workspace (RESTRICT mode) | ✓ SATISFIED | `validate_can_delete_workspace` checks `perm.can_manage` + FastAPI uses RESTRICT mode + blocks "default" |
| WSCRUD-06 | 06-01 | Cascade-delete all permission rows on workspace delete | ✓ SATISFIED | `_cascade_delete_workspace_permissions` → `store.wipe_workspace_permissions()` → both repo `delete_all_for_workspace()` |
| WSCRUD-07 | 06-02 | Workspace CRUD proxy validates names and handles errors | ✓ SATISFIED | `WorkspaceCrudCreateRequest` with DNS-safe regex, min/max length, reserved names. Router catches MLflow exceptions and maps to HTTP status codes. |
| WSCRUD-08 | 06-02 | Workspace CRUD endpoints not registered when disabled | ✓ SATISFIED | Router in `app.py` inside `if config.MLFLOW_ENABLE_WORKSPACES:` block. NOT in `get_all_routers()`. Runtime verified. |
| WSOIDC-04 | 06-02 | OIDC login auto-creates non-existent workspaces | ✓ SATISFIED | `auth.py:492-527` — `_get_workspace_store().get_workspace(ws_name)` → `create_workspace()` if not found. Failures don't block login. 4 tests pass. |

**All 9 requirements SATISFIED. No orphaned requirements.**

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No anti-patterns detected | — | — |

No TODOs, FIXMEs, placeholders, empty returns, or console-only handlers found in phase files.

### Human Verification Required

### 1. End-to-End CRUD via Live Server

**Test:** Start MLflow with `MLFLOW_ENABLE_WORKSPACES=true`, create a workspace as admin via FastAPI endpoint, verify MANAGE permission auto-granted, then update description and delete.
**Expected:** Full CRUD lifecycle works. After delete, workspace permissions table has zero rows for that workspace.
**Why human:** Requires live MLflow server with workspace store configured — can't verify store integration without running server.

### 2. Feature Flag Disabling

**Test:** Start MLflow with `MLFLOW_ENABLE_WORKSPACES=false`, attempt to access `/api/3.0/mlflow/workspaces/crud`.
**Expected:** 404 Not Found — router not registered.
**Why human:** Requires running server with specific config to verify HTTP-level behavior.

### 3. OIDC Auto-Create in Real Login Flow

**Test:** Configure OIDC with workspace claim pointing to a non-existent workspace, perform login.
**Expected:** Workspace auto-created in MLflow, user gets permission assigned.
**Why human:** Requires real OIDC provider and MLflow workspace store integration.

### Gaps Summary

No gaps found. All 5 observable truths verified. All 9 requirements satisfied. All artifacts exist, are substantive, wired, and have real data flow. 103 workspace-specific tests and 2383 total tests pass. No anti-patterns detected.

---

_Verified: 2026-03-24T17:35:23Z_
_Verifier: the agent (gsd-verifier)_
