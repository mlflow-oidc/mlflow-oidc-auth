---
phase: 05-regex-workspace-permissions
plan: 02
subsystem: api
tags: [fastapi, router, regex-permissions, workspace, cache, pydantic, cachetools, rbac]

# Dependency graph
requires:
  - phase: 05-regex-workspace-permissions plan 01
    provides: "ORM models, entities, repositories, and 12 CRUD store methods for workspace regex permissions"
provides:
  - "workspace_regex_permissions_router with 8 admin-only CRUD endpoints (user-regex + group-regex)"
  - "Pydantic request/response models for workspace regex permissions"
  - "flush_workspace_cache() for full cache invalidation on regex CUD operations"
  - "_match_workspace_regex_permission() with priority-aware matching and tie-breaking"
  - "Source-order-driven _lookup_workspace_permission() resolving user, group, regex, group-regex via PERMISSION_SOURCE_ORDER"
  - "list_all_workspace_group_regex_permissions() store method for admin listing"
  - "Feature-flag gated router inclusion (MLFLOW_ENABLE_WORKSPACES)"
  - "cachetools>=5.5.0 pinned as direct dependency"
affects: [06-workspace-crud, 07-enforcement, 08-ui]

# Tech tracking
tech-stack:
  added: ["cachetools>=5.5.0 (pinned as direct dependency)"]
  patterns:
    - "Feature-flag gated router: conditionally included in app.py, NOT in get_all_routers()"
    - "Full cache flush on regex CUD (vs per-entry invalidation for direct permissions)"
    - "Source-order-driven permission resolution via config.PERMISSION_SOURCE_ORDER"
    - "Priority-aware regex matching: lower number = higher priority, same-priority tie-break by most permissive"

key-files:
  created:
    - "mlflow_oidc_auth/routers/workspace_regex_permissions.py"
    - "mlflow_oidc_auth/tests/routers/test_workspace_regex_permissions.py"
  modified:
    - "mlflow_oidc_auth/models/workspace.py"
    - "mlflow_oidc_auth/models/__init__.py"
    - "mlflow_oidc_auth/routers/_prefix.py"
    - "mlflow_oidc_auth/routers/__init__.py"
    - "mlflow_oidc_auth/app.py"
    - "pyproject.toml"
    - "mlflow_oidc_auth/sqlalchemy_store.py"
    - "mlflow_oidc_auth/utils/workspace_cache.py"
    - "mlflow_oidc_auth/tests/utils/test_workspace_cache.py"
    - "mlflow_oidc_auth/tests/routers/conftest.py"

key-decisions:
  - "Router is admin-only (all endpoints use Depends(check_admin_permission)) — regex permissions are infrastructure-level, not end-user self-service"
  - "Full cache flush on regex CUD (D-09) rather than targeted invalidation because regex changes can affect any user+workspace combination"
  - "list_all_workspace_group_regex_permissions() added as store method by direct query since BaseGroupRegexPermissionRepository lacks a list() method"
  - "Source resolvers use bare except Exception to gracefully degrade — store exceptions return None and fall through to next source"

patterns-established:
  - "Feature-flag gated routers: include in app.py create_app() inside if config.MLFLOW_ENABLE_WORKSPACES block, NOT in get_all_routers()"
  - "Cache integration: flush_workspace_cache() for regex CUD, invalidate_workspace_permission() for direct CUD"
  - "PERMISSION_SOURCE_ORDER drives resolution: dict of source_name -> lambda resolver, iterated in config order"

requirements-completed: [WSREG-01, WSREG-02, WSREG-03, WSREG-04, WSREG-05, WSREG-06]

# Metrics
duration: ~11min
completed: 2026-03-24
---

# Phase 05 Plan 02: Workspace Regex Permissions Router & Cache Integration Summary

**Admin-only REST API with 8 CRUD endpoints for user-regex and group-regex workspace permissions, plus priority-aware cache resolution using configurable PERMISSION_SOURCE_ORDER**

## Performance

- **Duration:** ~11 min (across continuation session)
- **Started:** 2026-03-24T16:29:43Z
- **Completed:** 2026-03-24T16:41:27Z
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments
- 8 admin-only CRUD endpoints: create/list/update/delete for both user-regex and group-regex workspace permissions
- 4 Pydantic request/response models with regex, priority, permission fields
- Full workspace cache refactored to source-order-driven resolution with 4 sources: user-direct, group-direct, user-regex, group-regex
- Priority-aware regex matching: lower priority number wins (D-07), same-priority tie-break by most permissive (D-08)
- All 6 CUD operations flush full cache (D-09); list operations do not
- Router conditionally included only when MLFLOW_ENABLE_WORKSPACES is true
- cachetools>=5.5.0 pinned as direct dependency
- 49 tests passing (20 router + 29 cache)

## Task Commits

Each task was committed atomically (TDD: combined RED+GREEN):

1. **Task 1: Pydantic models, router, feature-flag gating, and cachetools pin** — `437cb5b` (feat)
2. **Task 2: Workspace cache integration with regex and group-regex source resolution** — `a080c7d` (feat)

## Files Created/Modified
- `mlflow_oidc_auth/routers/workspace_regex_permissions.py` — New router with 8 CRUD endpoints, admin-only, full cache flush on CUD
- `mlflow_oidc_auth/tests/routers/test_workspace_regex_permissions.py` — 20 tests covering all endpoints, cache flush behavior, and configuration
- `mlflow_oidc_auth/models/workspace.py` — Added 4 Pydantic models (WorkspaceRegexPermissionRequest/Response, WorkspaceGroupRegexPermissionRequest/Response)
- `mlflow_oidc_auth/models/__init__.py` — Added imports and __all__ entries for new models
- `mlflow_oidc_auth/routers/_prefix.py` — Added WORKSPACE_REGEX_PERMISSIONS_ROUTER_PREFIX
- `mlflow_oidc_auth/routers/__init__.py` — Added import and __all__ entry (NOT in get_all_routers)
- `mlflow_oidc_auth/app.py` — Added feature-flag gated inclusion of workspace_regex_permissions_router
- `pyproject.toml` — Added cachetools>=5.5.0 as direct dependency
- `mlflow_oidc_auth/sqlalchemy_store.py` — Added list_all_workspace_group_regex_permissions() method
- `mlflow_oidc_auth/utils/workspace_cache.py` — Added flush_workspace_cache(), _match_workspace_regex_permission(), 4 resolver functions, refactored _lookup_workspace_permission() to use PERMISSION_SOURCE_ORDER
- `mlflow_oidc_auth/tests/utils/test_workspace_cache.py` — Added 19 new tests (5 test classes), updated 4 existing tests with PERMISSION_SOURCE_ORDER mock
- `mlflow_oidc_auth/tests/routers/conftest.py` — Added workspace_regex_permissions store patch

## Decisions Made
- Router is admin-only — regex permissions are infrastructure-level configuration, not self-service
- Full cache flush on regex CUD (D-09) because regex changes can affect any user+workspace combination, unlike direct permissions which are scoped to a specific user+workspace pair
- Added `list_all_workspace_group_regex_permissions()` as a direct session query in sqlalchemy_store.py because BaseGroupRegexPermissionRepository lacks a `list()` method (unlike BaseRegexPermissionRepository)
- Source resolvers use bare `except Exception` to gracefully degrade — store exceptions return None and resolution continues to next source

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] list_all_workspace_group_regex_permissions() direct query**
- **Found during:** Task 1 (router implementation)
- **Issue:** Plan referenced `self.workspace_group_regex_permission_repo.list()` but `BaseGroupRegexPermissionRepository` does not have a `list()` method (only `BaseRegexPermissionRepository` has it)
- **Fix:** Implemented `list_all_workspace_group_regex_permissions()` using direct SQLAlchemy query against `SqlWorkspaceGroupRegexPermission` model with `self.ManagedSessionMaker()` session
- **Files modified:** mlflow_oidc_auth/sqlalchemy_store.py
- **Verification:** Router test for GET /group passes, returns expected list
- **Committed in:** 437cb5b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor implementation adjustment, functionally equivalent to planned approach. No scope creep.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — all implementations are complete and wired end-to-end.

## Next Phase Readiness
- Phase 05 complete: full workspace regex permission stack in place (data layer + API + cache integration)
- Ready for Phase 06 (Workspace CRUD Backend): can now check both direct and regex workspace permissions
- Permission resolution chain: user-direct → group-direct → user-regex → group-regex (configurable via PERMISSION_SOURCE_ORDER)
- Cache integration: flush_workspace_cache() available for any operation that broadly affects workspace permissions

## Self-Check: PASSED

All 13 files verified as present. Both task commits (437cb5b, a080c7d) verified in git log. 49 workspace-related tests pass (20 router + 29 cache). 2 pre-existing failures in test_ui.py unrelated to this plan.

---
*Phase: 05-regex-workspace-permissions*
*Completed: 2026-03-24*
