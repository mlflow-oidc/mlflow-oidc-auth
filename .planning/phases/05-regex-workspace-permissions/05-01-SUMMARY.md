---
phase: 05-regex-workspace-permissions
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, regex-permissions, workspace, repository-pattern]

# Dependency graph
requires:
  - phase: v1.0 (prior milestone)
    provides: "Base regex permission infrastructure (RegexPermissionBase, BaseRegexPermissionRepository, BaseGroupRegexPermissionRepository)"
provides:
  - "SqlWorkspaceRegexPermission and SqlWorkspaceGroupRegexPermission ORM models"
  - "WorkspaceRegexPermission and WorkspaceGroupRegexPermission entity classes"
  - "WorkspaceRegexPermissionRepository and WorkspaceGroupRegexPermissionRepository"
  - "12 CRUD facade methods on SqlAlchemyStore for workspace regex permissions"
  - "Alembic migration 8a9b0c1de234 creating workspace_regex_permissions and workspace_group_regex_permissions tables"
affects: [05-02 router-and-cache, 06-workspace-crud, 07-enforcement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Workspace regex permissions follow identical patterns to experiment/model/scorer/gateway regex permissions"

key-files:
  created:
    - "mlflow_oidc_auth/db/migrations/versions/8a9b0c1de234_add_workspace_regex_permissions.py"
    - "mlflow_oidc_auth/repository/workspace_regex_permission.py"
    - "mlflow_oidc_auth/repository/workspace_group_regex_permission.py"
    - "mlflow_oidc_auth/tests/entities/test_workspace.py (new test classes added)"
    - "mlflow_oidc_auth/tests/repository/test_workspace_regex_permission.py"
    - "mlflow_oidc_auth/tests/repository/test_workspace_group_regex_permission.py"
  modified:
    - "mlflow_oidc_auth/db/models/workspace.py"
    - "mlflow_oidc_auth/db/models/__init__.py"
    - "mlflow_oidc_auth/entities/workspace.py"
    - "mlflow_oidc_auth/entities/__init__.py"
    - "mlflow_oidc_auth/repository/__init__.py"
    - "mlflow_oidc_auth/sqlalchemy_store.py"

key-decisions:
  - "Used alias WorkspaceGroupRegexPermRepo in repository/__init__.py to keep __all__ list manageable (full name is 42 chars)"
  - "Workspace regex entities extend RegexPermissionBase (unlike standalone workspace entities) for consistency with all other regex types"

patterns-established:
  - "Workspace regex pattern: identical structure to experiment/model regex permissions — extends base classes, ~18-line repos"
  - "Store facade: 6 methods per regex type (create, get, list_for_user/group, list_all, update, delete)"

requirements-completed: [WSREG-01, WSREG-02, WSREG-03, WSREG-04, WSREG-07]

# Metrics
duration: ~25min
completed: 2026-03-24
---

# Phase 05 Plan 01: Workspace Regex Permissions Data Layer Summary

**Workspace regex permission DB models, entities, repos, and store facade with Alembic migration creating two new tables (workspace_regex_permissions, workspace_group_regex_permissions)**

## Performance

- **Duration:** ~25 min (across two sessions)
- **Started:** 2026-03-24T16:00:00Z
- **Completed:** 2026-03-24T16:26:41Z
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments
- Two new ORM models (SqlWorkspaceRegexPermission, SqlWorkspaceGroupRegexPermission) with FK constraints and unique constraints
- Two new entity classes extending RegexPermissionBase with full serialization/deserialization
- Two new repository classes (~18 lines each) extending base classes with backward-compatible aliases
- Alembic migration 8a9b0c1de234 creating both tables (down_revision chains from workspace permissions migration)
- 12 CRUD facade methods on SqlAlchemyStore (6 user regex, 6 group regex)
- 20 new tests (16 entity + 4 repository) — all passing

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: DB models, entities, and Alembic migration** — `b125781` (test: RED), `ebc03e1` (feat: GREEN)
2. **Task 2: Repository classes and store integration** — `a10ec3c` (test: RED), `b54bde6` (feat: GREEN)

_TDD tasks had separate RED (failing test) and GREEN (implementation) commits._

## Files Created/Modified
- `mlflow_oidc_auth/db/models/workspace.py` — Added SqlWorkspaceRegexPermission and SqlWorkspaceGroupRegexPermission ORM models
- `mlflow_oidc_auth/db/models/__init__.py` — Added exports for new models
- `mlflow_oidc_auth/entities/workspace.py` — Added WorkspaceRegexPermission and WorkspaceGroupRegexPermission entity classes
- `mlflow_oidc_auth/entities/__init__.py` — Added exports for new entities
- `mlflow_oidc_auth/db/migrations/versions/8a9b0c1de234_add_workspace_regex_permissions.py` — Alembic migration for both tables
- `mlflow_oidc_auth/repository/workspace_regex_permission.py` — User regex workspace permission repository
- `mlflow_oidc_auth/repository/workspace_group_regex_permission.py` — Group regex workspace permission repository
- `mlflow_oidc_auth/repository/__init__.py` — Added exports for new repos
- `mlflow_oidc_auth/sqlalchemy_store.py` — Added imports, repo init, and 12 CRUD facade methods
- `mlflow_oidc_auth/tests/entities/test_workspace.py` — 8 new entity tests (construction, to_json, from_json roundtrip, string id conversion)
- `mlflow_oidc_auth/tests/repository/test_workspace_regex_permission.py` — 2 repo wiring tests
- `mlflow_oidc_auth/tests/repository/test_workspace_group_regex_permission.py` — 2 repo wiring tests

## Decisions Made
- Used alias `WorkspaceGroupRegexPermRepo` in `repository/__init__.py` because the full name `WorkspaceGroupRegexPermissionRepository` is 42 characters; direct module imports in `sqlalchemy_store.py` use the full name
- Workspace regex entities extend `RegexPermissionBase` (unlike standalone workspace entities which are standalone), consistent with all 7 other regex resource types
- SqlAlchemyStore imports repos directly from their modules (not via `__init__.py`) following the existing pattern in the codebase

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — all implementations are complete and wired to the data layer.

## Next Phase Readiness
- Data layer complete: ORM models, entities, repos, store facade all in place
- Ready for Plan 02 (router and cache integration): routers can now call store CRUD methods
- Alembic migration chain: 7b8c9d0ef123 → 8a9b0c1de234 (workspace regex permissions)

## Self-Check: PASSED

All 12 files verified as present. All 4 task commits verified in git log. 2309/2311 tests pass (2 pre-existing failures in test_ui.py unrelated to this plan).

---
*Phase: 05-regex-workspace-permissions*
*Completed: 2026-03-24*
