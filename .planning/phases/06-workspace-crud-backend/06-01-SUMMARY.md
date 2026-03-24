---
phase: 06-workspace-crud-backend
plan: 01
subsystem: auth
tags: [workspace, rbac, hooks, flask, cascade-delete, manage-permission]

requires:
  - phase: 05-regex-workspace-permissions
    provides: "Workspace permission cache, workspace entities, workspace regex repos, permission resolution chain"
provides:
  - "Auto-grant MANAGE permission to workspace creator via after_request hook"
  - "Cascade-delete all workspace permission rows (user + group) on workspace delete"
  - "MANAGE-based delegation for workspace update and delete validators"
  - "Workspace name stashing in Flask g for delete cascade pattern"
  - "wipe_workspace_permissions store facade method"
affects: [06-workspace-crud-backend-plan-02, 07-frontend-workspace-ui]

tech-stack:
  added: []
  patterns:
    - "Stash-and-cascade pattern for workspace delete (mirrors gateway pattern)"
    - "MANAGE delegation in validators via get_workspace_permission_cached + can_manage"

key-files:
  created: []
  modified:
    - mlflow_oidc_auth/hooks/after_request.py
    - mlflow_oidc_auth/hooks/before_request.py
    - mlflow_oidc_auth/validators/workspace.py
    - mlflow_oidc_auth/sqlalchemy_store.py
    - mlflow_oidc_auth/repository/workspace_permission.py
    - mlflow_oidc_auth/repository/workspace_group_permission.py
    - mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py
    - mlflow_oidc_auth/tests/repository/test_workspace_permission.py
    - mlflow_oidc_auth/tests/repository/test_workspace_group_permission.py

key-decisions:
  - "Reused _extract_workspace_name_from_path from validators.workspace instead of duplicating in before_request"
  - "Auto-grant handler checks resp.status_code < 300 (not just 200/201) for broader success range"
  - "Cascade-delete handler uses same status_code < 300 guard for consistency"

patterns-established:
  - "Workspace stash-and-cascade: stash g._deleting_workspace_name in _find_validator, consume in _cascade_delete_workspace_permissions"
  - "MANAGE delegation pattern: admin check first, then workspace_permission_cached + can_manage check"

requirements-completed: [WSCRUD-01, WSCRUD-02, WSCRUD-03, WSCRUD-04, WSCRUD-05, WSCRUD-06]

duration: 10min
completed: 2026-03-24
---

# Phase 6 Plan 1: Workspace CRUD Auth Hooks Summary

**Workspace CRUD auth enforcement via before/after request hooks: auto-grant MANAGE on create, cascade-delete on delete, MANAGE delegation for update/delete validators**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-24T17:03:00Z
- **Completed:** 2026-03-24T17:12:56Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Added `delete_all_for_workspace()` to both workspace permission repositories and `wipe_workspace_permissions()` to SqlAlchemyStore for bulk-delete on cascade
- Wired `_auto_grant_workspace_manage_permission` after-request handler for CreateWorkspace — creator gets MANAGE permission + cache flush
- Wired `_cascade_delete_workspace_permissions` after-request handler for DeleteWorkspace — wipes all user and group permission rows + cache flush
- Updated `validate_can_update_workspace` and `validate_can_delete_workspace` to allow MANAGE permission holders (not just admins)
- Added workspace name stashing in `_find_validator()` for DELETE requests (mirrors gateway stash pattern)
- 148 workspace-related tests pass (44 hook tests + 10 repo wipe tests + existing tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Repository wipe methods and store facade** - `234719e` (feat)
2. **Task 2: After-request hooks and validator MANAGE delegation** - `af37106` (feat)

## Files Created/Modified
- `mlflow_oidc_auth/repository/workspace_permission.py` - Added `delete_all_for_workspace()` bulk-delete method
- `mlflow_oidc_auth/repository/workspace_group_permission.py` - Added `delete_all_for_workspace()` bulk-delete method
- `mlflow_oidc_auth/sqlalchemy_store.py` - Added `wipe_workspace_permissions()` facade delegating to both repos
- `mlflow_oidc_auth/hooks/after_request.py` - Added auto-grant and cascade-delete handlers, registered in AFTER_REQUEST_PATH_HANDLERS
- `mlflow_oidc_auth/hooks/before_request.py` - Added workspace name stashing in `_find_validator()` for DELETE
- `mlflow_oidc_auth/validators/workspace.py` - Updated update/delete validators with MANAGE permission check
- `mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py` - Added 20 new tests (auto-grant, cascade-delete, stash, MANAGE validators)
- `mlflow_oidc_auth/tests/repository/test_workspace_permission.py` - Added `TestDeleteAllForWorkspace` test class
- `mlflow_oidc_auth/tests/repository/test_workspace_group_permission.py` - Added `TestDeleteAllForWorkspace` test class

## Decisions Made
- Reused `_extract_workspace_name_from_path` from `validators.workspace` (lazy import) instead of duplicating the path extraction logic in `before_request.py` — keeps single source of truth for workspace path parsing
- Used `resp.status_code < 300` as success guard in both auto-grant and cascade-delete handlers rather than checking explicit 200/201/204 codes — more robust against MLflow response code changes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failure in `test_ui.py::TestServeSPAConfig::test_serve_spa_config_authenticated` (MagicMock not JSON-serializable for `MLFLOW_ENABLE_WORKSPACES`) — unrelated to this plan's changes, not addressed

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functions are fully implemented with real logic.

## Next Phase Readiness
- Workspace CRUD auth enforcement is complete — all 6 WSCRUD requirements satisfied
- Ready for Plan 2 (workspace CRUD proxy/passthrough if applicable) or Phase 7 (frontend workspace UI)
- Gateway cascade-delete pattern successfully replicated for workspaces

## Self-Check: PASSED

- All 10 key files verified present on disk
- Commit `234719e` (Task 1) verified in git log
- Commit `af37106` (Task 2) verified in git log

---
*Phase: 06-workspace-crud-backend*
*Completed: 2026-03-24*
