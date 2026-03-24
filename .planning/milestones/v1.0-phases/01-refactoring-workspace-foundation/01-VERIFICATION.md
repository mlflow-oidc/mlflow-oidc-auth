---
phase: 01-refactoring-workspace-foundation
verified: 2026-03-23T17:01:38Z
status: gaps_found
score: 4/5 success criteria verified
gaps:
  - truth: "Existing permissions are assigned to a 'default' workspace during migration — no data loss or permission breakage"
    status: partial
    reason: "The _seed_default_workspace() function in app.py exists and runs at startup when MLFLOW_ENABLE_WORKSPACES=true, but it only logs readiness — it does NOT insert any workspace permission rows. The migration creates empty workspace_permissions/workspace_group_permissions tables but does NOT assign existing permissions to a default workspace. This was explicitly deferred to Phase 2 in the plan (01-03-PLAN.md Step 3 notes: 'In Phase 1 we do NOT create actual workspace permission rows'). WSFND-04 in REQUIREMENTS.md says 'all existing resources assigned to default workspace for backward compatibility' and ROADMAP SC4 says 'Existing permissions are assigned to a default workspace during migration' — neither is satisfied."
    artifacts:
      - path: "mlflow_oidc_auth/app.py"
        issue: "_seed_default_workspace() is log-only — does not insert workspace permission rows (lines 104-107)"
      - path: "mlflow_oidc_auth/db/migrations/versions/7b8c9d0ef123_add_workspace_permissions.py"
        issue: "Migration creates empty tables only — no data seeding of existing permissions into default workspace"
    missing:
      - "Actual workspace permission rows created for default workspace (either in migration or at startup)"
      - "Existing permissions assigned to default workspace for backward compatibility"
---

# Phase 01: Refactoring & Workspace Foundation Verification Report

**Phase Goal:** The codebase has a generic permission resolution abstraction and all workspace plumbing exists (feature flag, DB table, context propagation, default workspace) — ready for auth enforcement
**Verified:** 2026-03-23T17:01:38Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Permission resolution for all 7 existing resource types uses a single generic `resolve_permission()` function instead of 8 copy-paste functions — all existing tests pass | ✓ VERIFIED | `PERMISSION_REGISTRY` has 7 entries. `resolve_permission()` exists at line 290. Old `_permission_*_sources_config` functions are completely removed (0 matches). 2169 tests pass. |
| 2 | `MLFLOW_ENABLE_WORKSPACES=false` (default) produces zero behavioral changes — existing deployments unaffected | ✓ VERIFIED | `config.MLFLOW_ENABLE_WORKSPACES == False` confirmed. Workspace header extraction gated by `if config.MLFLOW_ENABLE_WORKSPACES:` in auth_middleware.py:242. `_seed_default_workspace()` only called when flag is true (app.py:155). All 2169 existing tests pass with flag disabled. |
| 3 | `workspace_permissions` table exists after Alembic migration with `(workspace, user_id, permission)` composite primary key | ✓ VERIFIED | Migration file `7b8c9d0ef123_add_workspace_permissions.py` creates `workspace_permissions` with `PrimaryKeyConstraint("workspace", "user_id")` and `workspace_group_permissions` with `PrimaryKeyConstraint("workspace", "group_id")`. ORM models `SqlWorkspacePermission` and `SqlWorkspaceGroupPermission` match. FKs to users.id and groups.id present. `down_revision = "6a7b8c9def01"` (correct chain). |
| 4 | Existing permissions are assigned to a "default" workspace during migration — no data loss or permission breakage | ⚠️ PARTIAL | The `_seed_default_workspace()` function exists in app.py and is called at startup when flag enabled, but it only **logs readiness** (lines 105-107) — it does NOT insert any workspace permission rows. The migration creates empty tables. No existing permissions are assigned to the default workspace. Plan explicitly deferred this to Phase 2 (WSAUTH-02). |
| 5 | `get_request_workspace()` bridge function returns the workspace from `X-MLFLOW-WORKSPACE` header when workspaces are enabled | ✓ VERIFIED | `get_request_workspace()` defined in bridge/user.py:69-78, delegates to `get_auth_context().workspace`. AuthMiddleware extracts `x-mlflow-workspace` header (auth_middleware.py:243) only when `config.MLFLOW_ENABLE_WORKSPACES` is true. AuthContext carries workspace through ASGI scope → WSGI environ → bridge. |

**Score:** 4/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mlflow_oidc_auth/utils/permissions.py` | PERMISSION_REGISTRY + resolve_permission() | ✓ VERIFIED | 534 lines. PERMISSION_REGISTRY has 7 entries (line 279-287). resolve_permission() at line 290. 7 `_build_*_sources` builders. All `effective_*` and `can_*` wrappers preserved. `get_permission_from_store_or_default()` core loop unchanged (lines 488-534). |
| `mlflow_oidc_auth/repository/_base.py` | 4 generic base classes | ✓ VERIFIED | 835 lines. `BaseUserPermissionRepository(Generic[ModelT, EntityT])` at line 34. `BaseGroupPermissionRepository` at line 204. `BaseRegexPermissionRepository` at line 498. `BaseGroupRegexPermissionRepository` at line 644. All use `model_class`, `resource_id_attr` class attributes. |
| `mlflow_oidc_auth/entities/auth_context.py` | AuthContext frozen dataclass | ✓ VERIFIED | 27 lines. `@dataclass(frozen=True)` with `username: str`, `is_admin: bool`, `workspace: str | None = None`. Frozen (immutable) confirmed programmatically. |
| `mlflow_oidc_auth/config.py` | MLFLOW_ENABLE_WORKSPACES + GRANT_DEFAULT_WORKSPACE_ACCESS | ✓ VERIFIED | Lines 127-131. `MLFLOW_ENABLE_WORKSPACES = config_manager.get_bool("MLFLOW_ENABLE_WORKSPACES", default=False)`. `GRANT_DEFAULT_WORKSPACE_ACCESS = config_manager.get_bool("GRANT_DEFAULT_WORKSPACE_ACCESS", default=True)`. Defaults confirmed programmatically. |
| `mlflow_oidc_auth/bridge/user.py` | get_auth_context(), get_request_workspace(), backward-compat functions | ✓ VERIFIED | 78 lines. `get_auth_context()` at line 14. `get_request_workspace()` at line 69. `get_fastapi_username()` delegates to `get_auth_context().username` (line 49). `get_fastapi_admin_status()` delegates to `get_auth_context().is_admin` (line 64). All exported in `bridge/__init__.py`. |
| `mlflow_oidc_auth/db/models/workspace.py` | SqlWorkspacePermission + SqlWorkspaceGroupPermission | ✓ VERIFIED | 26 lines. `SqlWorkspacePermission(Base)` with `__tablename__ = "workspace_permissions"`, composite PK `(workspace, user_id)`. `SqlWorkspaceGroupPermission(Base)` with `__tablename__ = "workspace_group_permissions"`, composite PK `(workspace, group_id)`. Both exported in `db/models/__init__.py`. |
| `mlflow_oidc_auth/db/migrations/versions/7b8c9d0ef123_add_workspace_permissions.py` | Alembic migration for workspace tables | ✓ VERIFIED | 49 lines. Creates both tables with FKs and composite PKs. `down_revision = "6a7b8c9def01"` (correct chain). `downgrade()` drops tables in reverse order. |
| `mlflow_oidc_auth/middleware/auth_middleware.py` | AuthContext creation + workspace header extraction | ✓ VERIFIED | AuthContext import at line 18. `AuthContext(username=..., is_admin=..., workspace=...)` at line 245-249. Workspace header gated by `config.MLFLOW_ENABLE_WORKSPACES` at line 242. |
| `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py` | AuthContext bridging to WSGI environ | ✓ VERIFIED | AuthContext import at line 13. `isinstance(auth_context, AuthContext)` check at line 36. `environ["mlflow_oidc_auth"] = auth_context` at line 41. Old individual keys (`environ["mlflow_oidc_auth.username"]`) completely removed (0 matches in codebase). |
| `mlflow_oidc_auth/app.py` | Default workspace seeding at startup | ⚠️ PARTIAL | `_seed_default_workspace()` at line 74. Called when `config.MLFLOW_ENABLE_WORKSPACES` (line 155). But function is log-only — does not insert actual workspace permission rows. Documented as intentional Phase 1 deferral. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `utils/permissions.py` | `store.py` | store singleton in builder lambdas | ✓ WIRED | `store.get_experiment_permission`, `store.get_user_groups_experiment_permission`, etc. called within builder functions |
| `utils/permissions.py` | `permissions.py` | `get_permission()` in core loop | ✓ WIRED | `get_permission(perm)` at line 523 in `get_permission_from_store_or_default()` |
| `repository/_base.py` | `db/models/__init__.py` | SqlUser, SqlGroup imports | ✓ WIRED | `from mlflow_oidc_auth.db.models import SqlGroup, SqlUser` at line 21 |
| `repository/experiment_permission.py` | `repository/_base.py` | class inheritance | ✓ WIRED | `ExperimentPermissionRepository(BaseUserPermissionRepository[SqlExperimentPermission, ExperimentPermission])` confirmed |
| `middleware/auth_middleware.py` | `entities/auth_context.py` | AuthContext instantiated | ✓ WIRED | `AuthContext(username=..., is_admin=..., workspace=...)` at line 245-249 |
| `middleware/auth_aware_wsgi_middleware.py` | `bridge/user.py` | AuthContext stored in environ, read by bridge | ✓ WIRED | `environ["mlflow_oidc_auth"] = auth_context` in WSGI middleware (line 41). Bridge reads via `request.environ.get("mlflow_oidc_auth")` (line 27). |
| `middleware/auth_middleware.py` | `config.py` | MLFLOW_ENABLE_WORKSPACES check | ✓ WIRED | `config.MLFLOW_ENABLE_WORKSPACES` at line 242 |
| `app.py` | `config.py` | Default workspace seeding gated by flag | ✓ WIRED | `if config.MLFLOW_ENABLE_WORKSPACES:` at line 155 → `_seed_default_workspace()` |
| `repository/__init__.py` | `repository/_base.py` | Base classes exported | ✓ WIRED | All 4 base classes imported and listed in `__all__` |
| `entities/__init__.py` | `entities/auth_context.py` | AuthContext exported | ✓ WIRED | `AuthContext` in `__all__` list |
| `db/models/__init__.py` | `db/models/workspace.py` | Workspace models exported | ✓ WIRED | `SqlWorkspacePermission` and `SqlWorkspaceGroupPermission` in `__all__` |
| `bridge/__init__.py` | `bridge/user.py` | All bridge functions exported | ✓ WIRED | `get_auth_context`, `get_fastapi_admin_status`, `get_fastapi_username`, `get_request_workspace` all in `__all__` |

### Data-Flow Trace (Level 4)

Not applicable for this phase — artifacts are configuration, middleware, and database schema (not data-rendering components).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| PERMISSION_REGISTRY has 7 entries | `python -c "from mlflow_oidc_auth.utils.permissions import PERMISSION_REGISTRY; assert len(PERMISSION_REGISTRY)==7"` | 7 entries confirmed | ✓ PASS |
| Old _sources_config functions removed | `python -c "import mlflow_oidc_auth.utils.permissions as p; assert not [n for n in dir(p) if '_sources_config' in n]"` | 0 old functions | ✓ PASS |
| Config flags have correct defaults | `python -c "from mlflow_oidc_auth.config import config; assert config.MLFLOW_ENABLE_WORKSPACES==False; assert config.GRANT_DEFAULT_WORKSPACE_ACCESS==True"` | Both correct | ✓ PASS |
| AuthContext is frozen | `python -c "from mlflow_oidc_auth.entities.auth_context import AuthContext; c=AuthContext('t',False); c.username='x'" # FrozenInstanceError` | FrozenInstanceError raised | ✓ PASS |
| All bridge functions importable | `python -c "from mlflow_oidc_auth.bridge import get_auth_context, get_fastapi_username, get_fastapi_admin_status, get_request_workspace"` | All imported OK | ✓ PASS |
| All 4 base repo classes importable | `python -c "from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository, BaseGroupPermissionRepository, BaseRegexPermissionRepository, BaseGroupRegexPermissionRepository"` | All imported OK | ✓ PASS |
| Full test suite passes | `python -m pytest mlflow_oidc_auth/tests/ -x --ignore=mlflow_oidc_auth/tests/integration -q` | 2169 passed, 0 failed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REFAC-01 | 01-01 | Permission resolution refactored into generic `resolve_permission()` | ✓ SATISFIED | `PERMISSION_REGISTRY` with 7 entries, `resolve_permission()` function, old 8 copy-paste functions removed. All 2169 tests pass. |
| REFAC-02 | 01-02 | Repository base class for permissions | ✓ SATISFIED | 4 generic base classes in `_base.py` (835 lines). All 28 repository subclasses refactored. Exported in `__init__.py`. |
| WSFND-01 | 01-03 | Feature flag gates all workspace behavior — disabled by default | ✓ SATISFIED | `config.MLFLOW_ENABLE_WORKSPACES` defaults to `False`. Header extraction, workspace seeding, all gated by flag. |
| WSFND-02 | 01-03 | X-MLFLOW-WORKSPACE header propagated through middleware chain | ✓ SATISFIED | Header extracted in AuthMiddleware (line 243), stored in AuthContext, propagated through ASGI scope → WSGI environ → bridge. Only when flag enabled. |
| WSFND-03 | 01-03 | Alembic migration adds workspace_permissions table | ✓ SATISFIED | Migration `7b8c9d0ef123` creates `workspace_permissions` with `(workspace, user_id)` composite PK and `workspace_group_permissions` with `(workspace, group_id)` composite PK. FK constraints to users/groups. |
| WSFND-04 | 01-03 | Default workspace seeded — all existing resources assigned to default workspace | ⚠️ PARTIAL | `_seed_default_workspace()` function exists and is called at startup when flag enabled, but it is log-only — does NOT insert permission rows. No existing permissions are assigned to a default workspace. Plan explicitly deferred actual seeding to Phase 2. |
| WSFND-05 | 01-03 | `grant_default_workspace_access` config option | ✓ SATISFIED | `config.GRANT_DEFAULT_WORKSPACE_ACCESS` defaults to `True`. Available for Phase 2 to use. |
| WSFND-06 | 01-03 | Bridge extension with `get_request_workspace()` | ✓ SATISFIED | `get_request_workspace()` in bridge/user.py. `get_auth_context()` returns full AuthContext. Backward-compat: `get_fastapi_username()` and `get_fastapi_admin_status()` preserved with unchanged signatures. All exported in `bridge/__init__.py`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `mlflow_oidc_auth/utils/permissions.py` | 487 | `# TODO: check if str can be replaced by Permission in function signature` | ℹ️ Info | Pre-existing TODO in the unchanged `get_permission_from_store_or_default()` function. Not introduced by this phase. |
| `mlflow_oidc_auth/app.py` | 104-107 | `_seed_default_workspace()` is log-only — no actual data insertion | ⚠️ Warning | Known stub per 01-03-SUMMARY.md. Phase 2 will wire up actual seeding. WSFND-04 partially unsatisfied. |

### Human Verification Required

### 1. Workspace Header Propagation End-to-End

**Test:** Start the server with `MLFLOW_ENABLE_WORKSPACES=true`, send a request with `X-MLFLOW-WORKSPACE: my-workspace` header, verify `get_request_workspace()` returns `"my-workspace"` in a Flask hook.
**Expected:** The workspace value flows from HTTP header → AuthMiddleware → ASGI scope → WSGI environ → bridge function.
**Why human:** Requires a running server with OIDC configured and an authenticated request.

### 2. Backward Compatibility with Flag Disabled

**Test:** Start the server with default config (workspaces disabled), send requests with and without `X-MLFLOW-WORKSPACE` header.
**Expected:** Zero behavioral changes. No workspace extracted. `get_request_workspace()` returns `None`. All existing API calls work identically.
**Why human:** Requires full server with real auth flow to confirm no regressions.

### 3. Alembic Migration Applies Cleanly

**Test:** Run `alembic upgrade head` on a fresh database and on a database at revision `6a7b8c9def01`.
**Expected:** Both workspace tables created successfully. `alembic downgrade` removes them cleanly.
**Why human:** Requires actual database execution to verify migration applies without errors.

## Gaps Summary

**1 gap found, affecting 1 of 5 success criteria:**

**WSFND-04 / SC4 — Default workspace seeding is log-only.** The `_seed_default_workspace()` function in `app.py` exists and runs when `MLFLOW_ENABLE_WORKSPACES=true`, but it only logs readiness — it does not insert actual workspace permission rows. The Alembic migration creates empty `workspace_permissions` and `workspace_group_permissions` tables but does not assign existing permissions to a default workspace. REQUIREMENTS.md WSFND-04 states "all existing resources assigned to default workspace for backward compatibility" and ROADMAP SC4 states "Existing permissions are assigned to a 'default' workspace during migration." Neither is satisfied.

**Mitigating context:** This was an explicit, documented design decision. The 01-03-PLAN.md states: "In Phase 1 we do NOT create actual workspace permission rows (that's Phase 2's WSAUTH-02 store methods)." The 01-03-SUMMARY.md documents it as a "Known Stub." The phase goal says "ready for auth enforcement" — the plumbing (function, call site, table existence check) IS ready. The actual data operations depend on workspace permission CRUD store methods that are Phase 2 scope (WSAUTH-02).

**Recommendation:** This gap may be acceptable if the team considers WSFND-04 as partially met ("plumbing exists, data seeding deferred to Phase 2"). If strict requirement compliance is needed, the gap must be closed before Phase 1 can be marked complete. The fix requires either: (a) inserting a sentinel row for the default workspace in the startup seeder, or (b) reclassifying WSFND-04 as spanning Phases 1+2.

---

_Verified: 2026-03-23T17:01:38Z_
_Verifier: the agent (gsd-verifier)_
