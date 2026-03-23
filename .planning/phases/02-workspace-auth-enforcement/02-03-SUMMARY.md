---
phase: 02-workspace-auth-enforcement
plan: 03
subsystem: auth
tags: [workspace, rbac, hooks, creation-gating, bug-fix, gap-closure]

# Dependency graph
requires:
  - phase: 02-workspace-auth-enforcement/02-02
    provides: "Workspace creation gating via _get_workspace_gated_creation_paths() and _is_workspace_gated_creation()"
provides:
  - "Fixed _get_workspace_gated_creation_paths() filter — only CreateExperiment and CreateRegisteredModel paths included"
  - "Regression tests for /graphql, /server-info, /gateway/*, /scorer/* not being workspace-gated"
  - "Path count assertion: exactly 4 creation paths (2 endpoints x 2 API prefixes)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Handler identity check (handler in (Class1, Class2)) instead of truthiness check (handler is not None) for protobuf-filtered get_endpoints() results"

key-files:
  created: []
  modified:
    - mlflow_oidc_auth/hooks/before_request.py
    - mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py

key-decisions:
  - "Use handler identity check instead of truthiness — get_endpoints() returns non-None Flask handlers for non-protobuf routes"

patterns-established:
  - "Autouse fixture to reset module-level lazy caches (_WORKSPACE_GATED_CREATION_PATHS) between tests"

requirements-completed: [WSAUTH-03]

# Metrics
duration: 3min
completed: 2026-03-23
---

# Phase 02 Plan 03: Fix Over-inclusive Workspace Creation Gating Summary

**Fixed _get_workspace_gated_creation_paths() filter from truthiness check to handler identity check, preventing /graphql, /server-info, and 15 other non-creation paths from being incorrectly workspace-gated**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T19:20:08Z
- **Completed:** 2026-03-23T19:23:22Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Fixed security-impacting bug: non-creation paths (/graphql, /server-info, /gateway/*, /scorer/*) were incorrectly included in workspace creation gating set
- Changed filter from `if handler is not None` to `if handler in (CreateExperiment, CreateRegisteredModel)` — only 4 paths now returned (was 21)
- Added 2 regression tests: graphql/server-info/gateway rejection test + exact path count assertion
- Added autouse fixture to reset lazy-cached creation paths between tests
- Full test suite passes: 2251 tests, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix _get_workspace_gated_creation_paths() filter and add regression tests** - `1e97803` (fix)

## Files Created/Modified
- `mlflow_oidc_auth/hooks/before_request.py` — Changed line 382 filter from truthiness to identity check
- `mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py` — Added autouse cache reset fixture, 2 regression tests (graphql/server-info rejection + path count)

## Decisions Made
- Use handler identity check `handler in (CreateExperiment, CreateRegisteredModel)` instead of `handler is not None` — the lambda in get_endpoints() returns the protobuf class for matches but get_endpoints() also yields non-protobuf endpoints where the handler is the actual Flask handler function (not None)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## Known Stubs
None — bug fix only, no new features.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 02 gap closure complete — WSAUTH-03 now fully satisfied
- All workspace creation gating paths verified: exactly 4 (CreateExperiment + CreateRegisteredModel x 2 API prefixes)
- Non-creation paths confirmed excluded from gating set
- No blockers

---
*Phase: 02-workspace-auth-enforcement*
*Completed: 2026-03-23*

## Self-Check: PASSED

- All 2 key files verified present
- SUMMARY.md verified present
- Commit 1e97803 (Task 1) verified
