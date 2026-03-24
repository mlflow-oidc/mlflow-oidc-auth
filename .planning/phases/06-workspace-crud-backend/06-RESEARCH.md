# Phase 6: Workspace CRUD Backend — Research

**Researched:** 2026-03-24
**Phase:** 06-workspace-crud-backend
**Requirement IDs:** WSCRUD-01, WSCRUD-02, WSCRUD-03, WSCRUD-04, WSCRUD-05, WSCRUD-06, WSCRUD-07, WSCRUD-08, WSOIDC-04

## Key Finding: MLflow Already Handles Workspace CRUD

**This is NOT a proxy implementation.** MLflow 3.10.1 natively registers workspace CRUD as Flask routes:

```
/api/3.0/mlflow/workspaces       GET    → _list_workspaces_handler
/api/3.0/mlflow/workspaces       POST   → _create_workspace_handler
/api/3.0/mlflow/workspaces/<name> GET    → _get_workspace_handler
/api/3.0/mlflow/workspaces/<name> PATCH  → _update_workspace_handler
/api/3.0/mlflow/workspaces/<name> DELETE → _delete_workspace_handler
```

These routes are registered on the Flask app that is mounted inside our FastAPI app via `AuthAwareWSGIMiddleware`. Our plugin already intercepts these via:
- **before_request hooks**: `WORKSPACE_BEFORE_REQUEST_VALIDATORS` (validates auth/permissions)
- **after_request hooks**: `ListWorkspaces → _filter_list_workspaces` (filters by user permission)

**Architecture: Our plugin WRAPS the MLflow workspace API with auth hooks, not proxy it.**

## MLflow Workspace Proto Fields

```
Workspace:          name, description, default_artifact_root
CreateWorkspace:    name, description, default_artifact_root
GetWorkspace:       workspace_name
ListWorkspaces:     (no fields)
UpdateWorkspace:    workspace_name, description, default_artifact_root
DeleteWorkspace:    workspace_name (+ query param ?mode=RESTRICT|CASCADE|SET_DEFAULT)
```

## MLflow Workspace Name Validation

`WorkspaceNameValidator` in `mlflow.server.handlers`:
- Pattern: `^(?!.*--)[a-z0-9]([-a-z0-9]*[a-z0-9])?$` (DNS-safe)
- Length: 2-63 characters
- Reserved names: `workspaces`, `api`, `ajax-api`, `static-files`
- Default workspace "default" cannot be deleted

**Implication for WSCRUD-07**: MLflow handles validation internally. Our plugin should also validate client-side BEFORE the request reaches MLflow, but MLflow will catch anything we miss. We should add workspace name validation to the FastAPI router endpoints as well.

## MLflow Workspace Deletion Modes

`WorkspaceDeletionMode` enum: `SET_DEFAULT`, `CASCADE`, `RESTRICT`
- `RESTRICT` (default): Fails if workspace has resources
- `CASCADE`: Deletes all resources in the workspace
- `SET_DEFAULT`: Moves resources to default workspace

**Implication for WSCRUD-05**: We should always use RESTRICT mode from our CRUD endpoints (workspace must be empty). The mode is passed as a query parameter `?mode=RESTRICT`.

## What Already Exists (Phase 2-5 Foundation)

### Before-Request Validators (in `validators/workspace.py`)
| Operation | Current Logic | Needs Update? |
|-----------|--------------|---------------|
| `validate_can_create_workspace` | Admin-only | ✓ No change needed (WSCRUD-01: admin creates) |
| `validate_can_read_workspace` | Admin OR user has any workspace permission | ✓ No change needed (WSCRUD-03) |
| `validate_can_update_workspace` | Admin-only | ⚠ Needs update for WSCRUD-04: MANAGE users too |
| `validate_can_delete_workspace` | Admin-only | ⚠ Needs update for WSCRUD-05: MANAGE users too |
| `validate_can_list_workspaces` | All authenticated users (filtered in after_request) | ✓ No change needed (WSCRUD-02) |

### After-Request Handlers (in `hooks/after_request.py`)
| Operation | Current Logic | Needs Update? |
|-----------|--------------|---------------|
| `ListWorkspaces → _filter_list_workspaces` | Filters by workspace cache permission | ✓ No change needed (WSCRUD-02) |
| `CreateWorkspace → ???` | **MISSING** — no auto-grant MANAGE | ⚠ Needs new handler (WSCRUD-01) |
| `DeleteWorkspace → ???` | **MISSING** — no cascade-delete permissions | ⚠ Needs new handler (WSCRUD-06) |

### Store Methods (in `sqlalchemy_store.py`)
- All workspace permission CRUD exists (user + group + regex + group-regex)
- **MISSING**: `wipe_workspace_permissions(workspace)` — bulk delete all permissions for a workspace
- **MISSING**: `list_workspace_regex_permissions_for_workspace(workspace)` — list regex perms matching a workspace (for cascade)

### Workspace Cache (in `utils/workspace_cache.py`)
- `get_workspace_permission_cached()` — full chain resolution (user, group, regex, group-regex)
- `invalidate_workspace_permission()` — per-entry invalidation
- `flush_workspace_cache()` — full cache flush
- All ready to use for permission checks and cache invalidation

## Implementation Approach

### Plan 1: After-Request Hooks + Store Methods + Validator Updates

**1a. Auto-grant MANAGE on workspace create (WSCRUD-01)**
Add `_auto_grant_workspace_manage_permission()` to `after_request.py`:
- Map `CreateWorkspace → _auto_grant_workspace_manage_permission`
- Extract workspace name from response body
- Call `store.create_workspace_permission(workspace, username, "MANAGE")`
- Flush workspace cache

**1b. Cascade-delete permissions on workspace delete (WSCRUD-06)**
Add `_cascade_delete_workspace_permissions()` to `after_request.py`:
- Map `DeleteWorkspace → _cascade_delete_workspace_permissions`
- Need to stash workspace name in `g` before delete (in before_request, like gateway pattern)
- Add `wipe_workspace_permissions(workspace)` to store — deletes all user + group permission rows
- Flush workspace cache

**1c. Update validators for MANAGE delegation (WSCRUD-04, WSCRUD-05)**
- `validate_can_update_workspace`: Admin OR MANAGE permission
- `validate_can_delete_workspace`: Admin OR MANAGE permission

**1d. Store: Add wipe method (WSCRUD-06)**
- `wipe_workspace_permissions(workspace: str)` — delete all `SqlWorkspacePermission` and `SqlWorkspaceGroupPermission` where workspace=name

### Plan 2: FastAPI CRUD Router + OIDC Auto-Create + Feature Flag

**2a. FastAPI workspace CRUD router (WSCRUD-07, WSCRUD-08)**
A NEW FastAPI router that provides enhanced workspace CRUD with:
- Name validation (using MLflow's `WorkspaceNameValidator` plus our own Pydantic validation)
- Proper Pydantic request/response models
- Permission-based access control via FastAPI dependencies
- Feature flag gating (not registered when `MLFLOW_ENABLE_WORKSPACES=false`)

This router DOES NOT replace MLflow's Flask routes — it provides a parallel, permission-enriched API that the frontend can use. The Flask routes still work for direct MLflow API consumers.

Why both? The Flask routes go through before/after request hooks (coarse validation). The FastAPI router provides fine-grained error messages, proper Pydantic validation, and permission-aware responses that the React UI needs.

**FastAPI endpoints:**
```
POST   /api/3.0/mlflow/workspaces/crud          → create (admin-only)
GET    /api/3.0/mlflow/workspaces/crud          → list (filtered by permissions)
GET    /api/3.0/mlflow/workspaces/crud/{name}   → get (permission-checked)
PATCH  /api/3.0/mlflow/workspaces/crud/{name}   → update (admin or MANAGE)
DELETE /api/3.0/mlflow/workspaces/crud/{name}   → delete (admin or MANAGE, RESTRICT mode)
```

**Implementation**: The FastAPI router makes internal calls to the same MLflow tracking store that Flask uses. We can use `from mlflow.server.handlers import _get_workspace_store` to get the workspace store, then call its methods directly.

**2b. OIDC auto-create workspace (WSOIDC-04)**
In `routers/auth.py` `_process_oidc_callback_fastapi()`, the workspace detection block currently calls `store.create_workspace_permission()` but does NOT create the workspace itself. Need to add:
- Before assigning membership, check if workspace exists
- If not, create it via the tracking store
- Then assign permission

**2c. Feature flag gating (WSCRUD-08)**
- New router only registered in `create_app()` inside `if config.MLFLOW_ENABLE_WORKSPACES:` block
- Same pattern as `workspace_regex_permissions_router`

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| MLflow workspace store API may differ across backends | Use `_get_workspace_store()` which returns the configured store |
| `_get_workspace_store()` is a private MLflow function | It's the same pattern used by all MLflow handlers; no alternative exists |
| Race condition on auto-create (two OIDC logins create same workspace) | MLflow handles uniqueness constraint; catch and ignore |
| Workspace delete while users still have permissions | RESTRICT mode prevents deletion with resources; permission cascade in after_request handles cleanup |

## Dependencies

- **Phase 5 complete**: All workspace permission infrastructure in place ✓
- **MLflow 3.10.1**: Workspace API available ✓
- **No new libraries needed**: Uses existing MLflow APIs and our store infrastructure

## Test Strategy

- Unit tests for store `wipe_workspace_permissions()` method
- Unit tests for after_request handlers (auto-grant, cascade-delete)
- Unit tests for updated validators
- Unit tests for new FastAPI workspace CRUD router
- Unit tests for OIDC auto-create in auth callback

---
*Research completed: 2026-03-24*
