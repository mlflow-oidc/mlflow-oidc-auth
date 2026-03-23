---
phase: 01-refactoring-workspace-foundation
plan: 03
subsystem: auth
tags: [workspace, feature-flag, dataclass, middleware, alembic, migration, bridge, auth-context]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Registry-driven resolve_permission() — establishes middleware pattern this plan extends with workspace context"
  - phase: 01-02
    provides: "Generic base repository classes — workspace repos in Phase 2 will extend these bases"
provides:
  - "MLFLOW_ENABLE_WORKSPACES and GRANT_DEFAULT_WORKSPACE_ACCESS feature flags in AppConfig"
  - "AuthContext frozen dataclass for typed auth state propagation through middleware chain"
  - "X-MLFLOW-WORKSPACE header extraction in AuthMiddleware (gated by feature flag)"
  - "AuthContext propagation: AuthMiddleware → ASGI scope → AuthAwareWSGIMiddleware → Flask environ → bridge functions"
  - "get_auth_context() and get_request_workspace() bridge functions"
  - "workspace_permissions and workspace_group_permissions DB tables via Alembic migration"
  - "Default workspace seeding at app startup when workspaces enabled"
affects: [02-workspace-auth-enforcement, 03-management-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Feature flag gating: config.MLFLOW_ENABLE_WORKSPACES checked before any workspace behavior"
    - "Typed middleware context: frozen dataclass (AuthContext) instead of plain dict for ASGI→WSGI bridge"
    - "Single environ key: environ['mlflow_oidc_auth'] holds AuthContext object (replaces individual keys)"
    - "Startup seeding pattern: _seed_default_workspace() in create_app() with table existence check"

key-files:
  created:
    - "mlflow_oidc_auth/entities/auth_context.py"
    - "mlflow_oidc_auth/db/models/workspace.py"
    - "mlflow_oidc_auth/db/migrations/versions/7b8c9d0ef123_add_workspace_permissions.py"
    - "mlflow_oidc_auth/tests/entities/__init__.py"
    - "mlflow_oidc_auth/tests/entities/test_auth_context.py"
    - "mlflow_oidc_auth/tests/middleware/test_auth_middleware_workspace.py"
  modified:
    - "mlflow_oidc_auth/config.py"
    - "mlflow_oidc_auth/entities/__init__.py"
    - "mlflow_oidc_auth/bridge/user.py"
    - "mlflow_oidc_auth/bridge/__init__.py"
    - "mlflow_oidc_auth/middleware/auth_middleware.py"
    - "mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py"
    - "mlflow_oidc_auth/db/models/__init__.py"
    - "mlflow_oidc_auth/app.py"
    - "mlflow_oidc_auth/tests/bridge/test_user.py"
    - "mlflow_oidc_auth/tests/middleware/test_auth_aware_wsgi_middleware.py"
    - "mlflow_oidc_auth/tests/middleware/test_auth_middleware.py"
    - "mlflow_oidc_auth/tests/test_config.py"

key-decisions:
  - "AuthContext is a frozen dataclass rather than a TypedDict — provides immutability guarantees and attribute access instead of dict key access"
  - "Single environ key (environ['mlflow_oidc_auth'] = AuthContext) replaces two individual keys (mlflow_oidc_auth.username, mlflow_oidc_auth.is_admin) — cleaner and extensible"
  - "Default workspace seeding at startup (not in migration) — migrations should only create schema; seeding is app-level concern"
  - "Seeding function checks table existence before querying — handles case where migration hasn't run yet"
  - "Phase 1 seeding logs readiness but doesn't insert permission rows — actual user grants are Phase 2"

patterns-established:
  - "Feature flag gating pattern: if config.MLFLOW_ENABLE_WORKSPACES before any workspace behavior"
  - "AuthContext propagation chain: AuthMiddleware creates → scope stores → WSGI middleware bridges → Flask environ holds → bridge functions read"
  - "Workspace header extraction: request.headers.get('x-mlflow-workspace') only when flag enabled"
  - "Bridge delegation: get_fastapi_username() and get_fastapi_admin_status() delegate to get_auth_context() for DRY"

requirements-completed: [WSFND-01, WSFND-02, WSFND-03, WSFND-04, WSFND-05, WSFND-06]

# Metrics
duration: 15min
completed: 2026-03-23
---

# Phase 01 Plan 03: Workspace Foundation Plumbing Summary

**Feature-flag-gated workspace plumbing: AuthContext frozen dataclass propagated through FastAPI→ASGI→WSGI→Flask bridge, workspace_permissions/workspace_group_permissions Alembic tables, X-MLFLOW-WORKSPACE header extraction, and default workspace startup seeding**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-23T16:40:00Z
- **Completed:** 2026-03-23T16:54:08Z
- **Tasks:** 2
- **Files modified:** 18 (6 created, 12 modified)

## Accomplishments
- Full workspace context propagation chain: feature flag → header extraction → AuthContext → ASGI scope → WSGI environ → bridge functions — all gated by `MLFLOW_ENABLE_WORKSPACES=false` default
- AuthContext frozen dataclass replaces plain dict for typed, immutable auth state through the middleware chain (username, is_admin, workspace)
- workspace_permissions and workspace_group_permissions tables created via Alembic migration with composite PKs and foreign keys to users/groups
- Bridge refactored: `get_fastapi_username()` and `get_fastapi_admin_status()` preserved with unchanged signatures, now delegate to `get_auth_context()`
- 2169 tests pass with zero regressions — existing tests updated for AuthContext pattern, new tests cover workspace header extraction, config flags, and entity immutability

## Task Commits

Each task was committed atomically:

1. **Task 1: Feature flags, AuthContext dataclass, bridge refactoring, and middleware updates** - `3c831bf` (feat)
2. **Task 2: Database migration, ORM models, default workspace seeding, and tests** - `ef63609` (feat)

## Files Created/Modified
- `mlflow_oidc_auth/config.py` - Added MLFLOW_ENABLE_WORKSPACES (default=False) and GRANT_DEFAULT_WORKSPACE_ACCESS (default=True) feature flags
- `mlflow_oidc_auth/entities/auth_context.py` - NEW: AuthContext frozen dataclass with username, is_admin, workspace fields
- `mlflow_oidc_auth/entities/__init__.py` - Added AuthContext export
- `mlflow_oidc_auth/bridge/user.py` - Refactored to use AuthContext; added get_auth_context() and get_request_workspace()
- `mlflow_oidc_auth/bridge/__init__.py` - Updated exports for 4 bridge functions
- `mlflow_oidc_auth/middleware/auth_middleware.py` - Creates AuthContext instead of dict, extracts X-MLFLOW-WORKSPACE header when flag enabled
- `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py` - Passes single AuthContext object in environ instead of individual keys
- `mlflow_oidc_auth/db/models/workspace.py` - NEW: SqlWorkspacePermission and SqlWorkspaceGroupPermission ORM models
- `mlflow_oidc_auth/db/models/__init__.py` - Added workspace model exports
- `mlflow_oidc_auth/db/migrations/versions/7b8c9d0ef123_add_workspace_permissions.py` - NEW: Alembic migration for workspace tables (down_revision=6a7b8c9def01)
- `mlflow_oidc_auth/app.py` - Added _seed_default_workspace() and startup call when workspaces enabled
- `mlflow_oidc_auth/tests/entities/test_auth_context.py` - NEW: AuthContext construction, immutability, defaults tests
- `mlflow_oidc_auth/tests/bridge/test_user.py` - Rewritten for AuthContext pattern; added get_auth_context and get_request_workspace tests
- `mlflow_oidc_auth/tests/middleware/test_auth_middleware_workspace.py` - NEW: Workspace header extraction tests (enabled/disabled/no-header/always-has-fields)
- `mlflow_oidc_auth/tests/middleware/test_auth_aware_wsgi_middleware.py` - Rewritten for AuthContext object pattern
- `mlflow_oidc_auth/tests/middleware/test_auth_middleware.py` - Fixed scope assertions for AuthContext attribute access
- `mlflow_oidc_auth/tests/test_config.py` - Added MLFLOW_ENABLE_WORKSPACES and GRANT_DEFAULT_WORKSPACE_ACCESS tests

## Decisions Made
- **AuthContext as frozen dataclass:** Provides immutability (can't accidentally modify auth state mid-request) and attribute access (`.username` vs `["username"]`). TypedDict was considered but frozen dataclass gives stronger guarantees.
- **Single environ key pattern:** `environ["mlflow_oidc_auth"] = AuthContext(...)` replaces `environ["mlflow_oidc_auth.username"]` + `environ["mlflow_oidc_auth.is_admin"]`. Cleaner, extensible (workspace is just another field), and avoids key proliferation.
- **Startup seeding over migration seeding:** Default workspace is seeded in `create_app()` not in the Alembic migration. Migrations create schema; data seeding is an app-level concern that may depend on runtime configuration.
- **Phase 1 seeding is log-only:** The `_seed_default_workspace()` function verifies the table exists and logs readiness but doesn't insert actual permission rows — those are Phase 2's responsibility (WSAUTH-02 store methods).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed workspace middleware tests to use dispatch pattern instead of raw ASGI**
- **Found during:** Task 2 (test creation)
- **Issue:** Initial workspace middleware tests called `middleware(scope, AsyncMock(), AsyncMock())` directly as raw ASGI, but `AuthMiddleware` extends `BaseHTTPMiddleware` which requires the `dispatch(request, call_next)` pattern. Tests failed with "No response returned" error from starlette.
- **Fix:** Rewrote all 4 workspace tests to use the same `dispatch` pattern with `create_mock_request` fixture and `mock_store` from conftest, matching the existing test infrastructure in `test_auth_middleware.py`.
- **Files modified:** `mlflow_oidc_auth/tests/middleware/test_auth_middleware_workspace.py`
- **Verification:** All 4 workspace tests pass; full suite 2169 passed
- **Committed in:** `ef63609` (part of Task 2 commit)

**2. [Rule 1 - Bug] Fixed auth middleware scope assertion tests for AuthContext attribute access**
- **Found during:** Task 2 (test verification)
- **Issue:** Existing tests in `test_auth_middleware.py` (lines 800-801, 808-809) used dict subscript access `req.scope["mlflow_oidc_auth"]["username"]` but scope now holds AuthContext object, not a dict.
- **Fix:** Changed to attribute access `.username` and `.is_admin` on the AuthContext object.
- **Files modified:** `mlflow_oidc_auth/tests/middleware/test_auth_middleware.py`
- **Verification:** Full test suite passes with 2169 tests
- **Committed in:** `ef63609` (part of Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs — test compatibility with AuthContext refactoring)
**Impact on plan:** Both fixes are direct consequences of the AuthContext refactoring. No scope creep.

## Issues Encountered
- **Auth middleware reformatted since plan was written:** The plan referenced scope injection at line 221 as a single-line dict, but the file had already been reformatted (multi-line dict at lines 240-243). The correct location was found and updated to AuthContext pattern.
- **Pre-existing LSP import errors:** All LSP warnings about unresolved imports (fastapi, flask, dotenv, starlette, pytest) are pre-existing runtime dependencies not available in the LSP environment — not related to this plan's changes.

## User Setup Required

None - no external service configuration required. The feature flags default to `MLFLOW_ENABLE_WORKSPACES=false` (no behavioral change) and `GRANT_DEFAULT_WORKSPACE_ACCESS=true`. Set `MLFLOW_ENABLE_WORKSPACES=true` to enable workspace behavior in Phase 2+.

## Known Stubs

**1. `_seed_default_workspace()` in `mlflow_oidc_auth/app.py`**
- **Line:** ~27-48 (function definition)
- **Reason:** Intentionally log-only in Phase 1. The function verifies the workspace_permissions table exists and logs readiness, but does NOT insert actual workspace permission rows. Phase 2 (WSAUTH-02) will add workspace permission store methods and grant logic.
- **Resolution plan:** Phase 2 plan 02-01 will wire up actual workspace permission CRUD via store methods.

## Next Phase Readiness
- **Full workspace data path ready:** Feature flag → header extraction → AuthContext → ASGI scope → WSGI environ → bridge functions — Phase 2 plugs workspace permission resolution into this chain
- **DB tables ready:** workspace_permissions and workspace_group_permissions exist with proper composite PKs and FKs — Phase 2 adds repository classes and store methods using the base classes from Plan 01-02
- **Phase 1 complete:** All 3 plans (permission resolution refactoring, repository base classes, workspace foundation plumbing) delivered — ready for Phase 2 workspace auth enforcement

## Self-Check: PASSED

- All 6 key created files exist on disk
- Both task commits found in git log (3c831bf, ef63609)
- Full test suite: 2169 passed, 0 failures

---
*Phase: 01-refactoring-workspace-foundation*
*Completed: 2026-03-23*
