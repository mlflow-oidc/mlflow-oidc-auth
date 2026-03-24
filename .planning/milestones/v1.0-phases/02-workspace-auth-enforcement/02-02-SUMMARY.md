---
phase: 02-workspace-auth-enforcement
plan: 02
subsystem: auth
tags: [workspace, rbac, hooks, permissions, before_request, after_request, validators, creation-gating]

# Dependency graph
requires:
  - phase: 02-workspace-auth-enforcement/02-01
    provides: "Workspace permission entities, repos, store methods, TTLCache, and config flags"
  - phase: 01-refactoring-workspace-foundation
    provides: "resolve_permission() registry, AuthContext bridge, workspace header extraction"
provides:
  - "5 workspace validators (create/read/update/delete/list) in validators/workspace.py"
  - "WORKSPACE_BEFORE_REQUEST_HANDLERS + WORKSPACE_BEFORE_REQUEST_VALIDATORS hook registration"
  - "resolve_permission() workspace fallback (resource→workspace→NO_PERMISSIONS chain)"
  - "Creation gating — CreateExperiment/CreateRegisteredModel require workspace MANAGE"
  - "ListWorkspaces after_request filtering — users only see permitted workspaces"
affects: [03-management-api, 04-workspace-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import pattern for circular dependency avoidance (workspace_cache, bridge.user)"
    - "Regex-based validator dispatch for workspace paths (same pattern as logged-model)"
    - "get_endpoints() with handler-not-None filter for path set construction"

key-files:
  created:
    - mlflow_oidc_auth/validators/workspace.py
    - mlflow_oidc_auth/tests/validators/test_workspace.py
  modified:
    - mlflow_oidc_auth/validators/__init__.py
    - mlflow_oidc_auth/hooks/before_request.py
    - mlflow_oidc_auth/hooks/after_request.py
    - mlflow_oidc_auth/utils/permissions.py
    - mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py
    - mlflow_oidc_auth/tests/utils/test_permissions.py

key-decisions:
  - "Workspace validators return True/False (matching existing convention) — not Flask Response objects"
  - "Creation gating uses lazy-built path set from get_endpoints() with if-handler-not-None filter"
  - "Patch lazy imports at source module (bridge.user, workspace_cache) not at consuming module"

patterns-established:
  - "Workspace path checking before logged-model in _find_validator() — order matters for /mlflow/ prefix overlap"
  - "PermissionResult kind='workspace' and kind='workspace-deny' for workspace fallback tracing"

requirements-completed: [WSAUTH-01, WSAUTH-03, WSAUTH-04]

# Metrics
duration: 11min
completed: 2026-03-23
---

# Phase 02 Plan 02: Workspace Auth Enforcement Summary

**Workspace security boundary wired into permission resolution chain — validators, hook registration, resolve_permission() workspace fallback, CreateExperiment/Model MANAGE gating, and ListWorkspaces filtering**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-23T18:50:21Z
- **Completed:** 2026-03-23T19:01:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- 5 workspace validator functions enforce admin-only for mutations, permission check for reads, and open access for list
- Hook registration maps workspace protobuf RPCs to validators via regex patterns, covering both /api/3.0/ and /ajax-api/3.0/ prefixes
- resolve_permission() workspace fallback returns workspace-level permission when no resource-level match exists, or NO_PERMISSIONS for hard deny
- CreateExperiment and CreateRegisteredModel gated on workspace MANAGE permission before normal validation
- ListWorkspaces after_request handler strips workspaces user lacks permission for, with admin bypass
- 46 new tests across 3 test files, all passing with full suite at 2249 (zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Workspace validators, hook registration, _find_validator extension** - `494e1d5` (feat)
2. **Task 2: resolve_permission() workspace fallback, creation gating, ListWorkspaces filtering** - `7a86349` (feat)

## Files Created/Modified
- `mlflow_oidc_auth/validators/workspace.py` — 5 workspace validators + _extract_workspace_name_from_path() helper
- `mlflow_oidc_auth/validators/__init__.py` — Added workspace validator imports and __all__ exports
- `mlflow_oidc_auth/hooks/before_request.py` — WORKSPACE_BEFORE_REQUEST_HANDLERS/VALIDATORS, _find_validator workspace path, _is_workspace_gated_creation(), creation gating in before_request_hook()
- `mlflow_oidc_auth/hooks/after_request.py` — _filter_list_workspaces() function, ListWorkspaces in AFTER_REQUEST_PATH_HANDLERS
- `mlflow_oidc_auth/utils/permissions.py` — NO_PERMISSIONS import, workspace fallback block in resolve_permission()
- `mlflow_oidc_auth/tests/validators/test_workspace.py` — 17 validator unit tests
- `mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py` — 22 hook tests (9 Task 1 + 12 Task 2 + 1 registration test)
- `mlflow_oidc_auth/tests/utils/test_permissions.py` — 5 workspace fallback tests in TestResolvePermissionWorkspaceFallback

## Decisions Made
- Workspace validators return True/False to match existing validator convention — before_request_hook checks `if not validator(username)`
- Creation gating uses lazy-built set of (path, method) tuples from get_endpoints(), with `if handler is not None` filter to exclude unrelated endpoints
- Lazy imports (get_request_workspace, get_workspace_permission_cached) patched at their source modules in tests, not at the consuming module
- Workspace path matching inserted before logged-model in _find_validator() to prevent /mlflow/ prefix overlap

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _get_workspace_gated_creation_paths() including non-creation endpoints**
- **Found during:** Task 2 (GREEN phase — creation gating tests)
- **Issue:** `get_endpoints()` yields ALL endpoints; the lambda returns None for non-matches but the comprehension didn't filter these out, causing paths like /experiments/get to be included in the gated set
- **Fix:** Added `if handler is not None` guard in the comprehension (matching the same pattern used for WORKSPACE_BEFORE_REQUEST_VALIDATORS)
- **Files modified:** mlflow_oidc_auth/hooks/before_request.py
- **Verification:** test_is_workspace_gated_creation_rejects_non_creation_paths now passes
- **Committed in:** 7a86349

**2. [Rule 1 - Bug] Fixed mock patch paths for lazy imports in tests**
- **Found during:** Task 2 (GREEN phase — before_request_hook integration tests)
- **Issue:** Tests patched `mlflow_oidc_auth.hooks.before_request.get_request_workspace` but the function is lazily imported inside the function body, so it's not a module-level attribute. Same for `get_workspace_permission_cached` in both hooks and permissions test files.
- **Fix:** Changed patch targets to source modules: `mlflow_oidc_auth.bridge.user.get_request_workspace` and `mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached`
- **Files modified:** mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py, mlflow_oidc_auth/tests/utils/test_permissions.py
- **Verification:** All 46 plan tests pass, full suite 2249 passed
- **Committed in:** 7a86349

---

**Total deviations:** 2 auto-fixed (2× Rule 1 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## Known Stubs
None — all features fully wired.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Phase 02 complete — workspace security boundary is fully enforced
- Ready for Phase 03 (Management API, OIDC & Entity Coverage):
  - Workspace permission CRUD API can build on store methods from 02-01
  - OIDC claim mapping can use get_workspace_permission_cached for assignment
  - New entity handlers follow the established before_request/after_request pattern
- No blockers

---
*Phase: 02-workspace-auth-enforcement*
*Completed: 2026-03-23*

## Self-Check: PASSED

- All 9 key files verified present
- Commit 494e1d5 (Task 1) verified
- Commit 7a86349 (Task 2) verified
