---
phase: 05-regex-workspace-permissions
verified: 2026-03-24T12:46:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 5: Regex Workspace Permissions Verification Report

**Phase Goal:** Admins can define pattern-based workspace access rules that automatically grant permissions to matching workspaces
**Verified:** 2026-03-24T12:46:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Workspace regex permission tables exist in the database after migration | ✓ VERIFIED | Migration `8a9b0c1de234` creates `workspace_regex_permissions` and `workspace_group_regex_permissions` tables with correct columns, FKs, and unique constraints. `down_revision = "7b8c9d0ef123"` chains correctly. |
| 2 | Admin can create/read/update/delete user regex workspace permissions via store | ✓ VERIFIED | `SqlAlchemyStore` has 6 CRUD methods: `create_workspace_regex_permission`, `get_workspace_regex_permission`, `list_workspace_regex_permissions`, `list_all_workspace_regex_permissions`, `update_workspace_regex_permission`, `delete_workspace_regex_permission`. All delegate to `WorkspaceRegexPermissionRepository`. |
| 3 | Admin can create/read/update/delete group regex workspace permissions via store | ✓ VERIFIED | `SqlAlchemyStore` has 7 CRUD methods: `create_workspace_group_regex_permission`, `get_workspace_group_regex_permission`, `list_workspace_group_regex_permissions`, `list_workspace_group_regex_permissions_for_groups_ids`, `list_all_workspace_group_regex_permissions`, `update_workspace_group_regex_permission`, `delete_workspace_group_regex_permission`. |
| 4 | Workspace regex entities serialize/deserialize correctly | ✓ VERIFIED | 8 entity tests pass: construction, to_json, from_json roundtrip, string ID conversion for both `WorkspaceRegexPermission` and `WorkspaceGroupRegexPermission`. |
| 5 | Admin can create/list/update/delete user regex workspace permissions via REST API | ✓ VERIFIED | Router has POST/GET/PATCH/DELETE at `/user` and `/user/{permission_id}`. All use `Depends(check_admin_permission)`. 20 router tests pass. |
| 6 | Admin can create/list/update/delete group regex workspace permissions via REST API | ✓ VERIFIED | Router has POST/GET/PATCH/DELETE at `/group` and `/group/{permission_id}`. All use `Depends(check_admin_permission)`. Tests verify all operations. |
| 7 | Workspace cache resolves regex and group-regex sources in configured PERMISSION_SOURCE_ORDER | ✓ VERIFIED | `_lookup_workspace_permission()` uses `config.PERMISSION_SOURCE_ORDER` to iterate sources. Four resolvers: `_resolve_user_direct`, `_resolve_group_direct`, `_resolve_user_regex`, `_resolve_group_regex`. Tests verify custom source order and fallthrough. |
| 8 | Full workspace cache is cleared on any regex permission CUD operation | ✓ VERIFIED | `flush_workspace_cache()` calls `cache.clear()`. Called in all 6 CUD endpoints (create/update/delete for user-regex and group-regex). NOT called in list endpoints. 8 specific cache flush tests verify this. |
| 9 | Regex workspace endpoints are not registered when MLFLOW_ENABLE_WORKSPACES is false | ✓ VERIFIED | `workspace_regex_permissions_router` is NOT in `get_all_routers()`. In `app.py`, it is conditionally included only inside `if config.MLFLOW_ENABLE_WORKSPACES:` block (lines 155-162). |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mlflow_oidc_auth/db/models/workspace.py` | SqlWorkspaceRegexPermission and SqlWorkspaceGroupRegexPermission ORM models | ✓ VERIFIED | Both classes present with correct `__tablename__`, columns (id, regex, priority, user_id/group_id, permission), FK constraints, unique constraints, and `to_mlflow_entity()` methods |
| `mlflow_oidc_auth/entities/workspace.py` | WorkspaceRegexPermission and WorkspaceGroupRegexPermission entity classes | ✓ VERIFIED | Both dataclasses extend `RegexPermissionBase` with `__init__`, `to_json()`, `from_json()` |
| `mlflow_oidc_auth/repository/workspace_regex_permission.py` | User regex workspace permission repository | ✓ VERIFIED | `WorkspaceRegexPermissionRepository` extends `BaseRegexPermissionRepository[SqlWorkspaceRegexPermission, WorkspaceRegexPermission]` with `model_class = SqlWorkspaceRegexPermission` |
| `mlflow_oidc_auth/repository/workspace_group_regex_permission.py` | Group regex workspace permission repository | ✓ VERIFIED | `WorkspaceGroupRegexPermissionRepository` extends `BaseGroupRegexPermissionRepository[SqlWorkspaceGroupRegexPermission, WorkspaceGroupRegexPermission]` with `model_class = SqlWorkspaceGroupRegexPermission` |
| `mlflow_oidc_auth/db/migrations/versions/8a9b0c1de234_add_workspace_regex_permissions.py` | Alembic migration for both tables | ✓ VERIFIED | Creates `workspace_regex_permissions` and `workspace_group_regex_permissions` tables with FK constraints, unique constraints, auto-increment PKs. `down_revision = "7b8c9d0ef123"`. Downgrade drops both. |
| `mlflow_oidc_auth/routers/workspace_regex_permissions.py` | FastAPI router with 8 CRUD endpoints | ✓ VERIFIED | 8 endpoints (4 user-regex, 4 group-regex) at correct paths. All admin-only via `Depends(check_admin_permission)`. All CUD ops call `flush_workspace_cache()`. |
| `mlflow_oidc_auth/models/workspace.py` | Pydantic request/response models for regex workspace permissions | ✓ VERIFIED | 4 models: `WorkspaceRegexPermissionRequest`, `WorkspaceGroupRegexPermissionRequest`, `WorkspaceRegexPermissionResponse`, `WorkspaceGroupRegexPermissionResponse` |
| `mlflow_oidc_auth/utils/workspace_cache.py` | Updated cache with regex and group-regex source resolution | ✓ VERIFIED | Contains `flush_workspace_cache()`, `_match_workspace_regex_permission()`, `_resolve_user_regex()`, `_resolve_group_regex()`. Uses `config.PERMISSION_SOURCE_ORDER`. |
| `mlflow_oidc_auth/routers/_prefix.py` | WORKSPACE_REGEX_PERMISSIONS_ROUTER_PREFIX | ✓ VERIFIED | `WORKSPACE_REGEX_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/workspaces/regex", version=3)` |
| `pyproject.toml` | cachetools>=5.5.0 pinned | ✓ VERIFIED | `"cachetools>=5.5.0"` in dependencies list |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `workspace_regex_permissions.py` (router) | `workspace_cache.py` | `flush_workspace_cache()` | ✓ WIRED | Imported at line 24, called in 6 CUD endpoints (lines 61, 108, 130, 148, 195, 217) |
| `workspace_cache.py` | `sqlalchemy_store.py` | `store.list_workspace_regex_permissions` and `store.list_workspace_group_regex_permissions_for_groups_ids` | ✓ WIRED | Called in `_resolve_user_regex()` (line 137) and `_resolve_group_regex()` (lines 152, 155) |
| `routers/__init__.py` | `workspace_regex_permissions.py` | import + `__all__` export (NOT in `get_all_routers`) | ✓ WIRED | Imported at line 38-40, in `__all__` at line 59. Correctly excluded from `get_all_routers()` return list. |
| `app.py` | `workspace_regex_permissions.py` | Feature-flag gated inclusion | ✓ WIRED | Conditionally imported and included via `oidc_app.include_router()` inside `if config.MLFLOW_ENABLE_WORKSPACES:` block (lines 155-162) |
| `workspace_regex_permission.py` (repo) | `db/models/workspace.py` | `model_class = SqlWorkspaceRegexPermission` | ✓ WIRED | Direct class assignment at line 11 |
| `sqlalchemy_store.py` | `workspace_regex_permission.py` (repo) | Store delegates to repo | ✓ WIRED | Import at line 66-67, repo init at line 179, 6+ methods delegate to `workspace_regex_permission_repo` |
| `db/models/__init__.py` | Both new SQL models | Export in `__all__` | ✓ WIRED | Both `SqlWorkspaceRegexPermission` and `SqlWorkspaceGroupRegexPermission` imported and in `__all__` |
| `entities/__init__.py` | Both new entity classes | Export in `__all__` | ✓ WIRED | Both `WorkspaceRegexPermission` and `WorkspaceGroupRegexPermission` imported and in `__all__` |
| `models/__init__.py` | 4 new Pydantic models | Export in `__all__` | ✓ WIRED | All 4 regex Pydantic models imported and in `__all__` |
| `repository/__init__.py` | Both new repo classes | Export in `__all__` | ✓ WIRED | Both imported (group repo aliased as `WorkspaceGroupRegexPermRepo`), both in `__all__` |
| `tests/routers/conftest.py` | New router store mock | Patch entry | ✓ WIRED | `mlflow_oidc_auth.routers.workspace_regex_permissions.store` patched at line 384 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `workspace_cache.py` → `_resolve_user_regex` | `regexes` | `store.list_workspace_regex_permissions(username)` | Yes — delegates to `WorkspaceRegexPermissionRepository.list_regex_for_user()` which queries `SqlWorkspaceRegexPermission` via base class | ✓ FLOWING |
| `workspace_cache.py` → `_resolve_group_regex` | `group_ids`, `regexes` | `store.get_groups_ids_for_user(username)` + `store.list_workspace_group_regex_permissions_for_groups_ids(group_ids)` | Yes — real DB queries through repository layer | ✓ FLOWING |
| `workspace_regex_permissions.py` → CUD endpoints | store return values | `store.create/update/delete_workspace_regex_permission()` | Yes — delegates to repository CRUD methods | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase 5 test files importable and pass | `python -m pytest ... -x -v` | 69 tests passed in 1.11s | ✓ PASS |
| DB models importable from package | `python -c "from mlflow_oidc_auth.db.models import SqlWorkspaceRegexPermission, SqlWorkspaceGroupRegexPermission"` | Success | ✓ PASS |
| Entities importable from package | `python -c "from mlflow_oidc_auth.entities import WorkspaceRegexPermission, WorkspaceGroupRegexPermission"` | Success | ✓ PASS |
| Repos importable from package | `python -c "from mlflow_oidc_auth.repository import WorkspaceRegexPermissionRepository, WorkspaceGroupRegexPermRepo"` | Success | ✓ PASS |
| Router importable from package | `python -c "from mlflow_oidc_auth.routers.workspace_regex_permissions import workspace_regex_permissions_router"` | Success | ✓ PASS |
| Cache functions importable | `python -c "from mlflow_oidc_auth.utils.workspace_cache import flush_workspace_cache, _match_workspace_regex_permission"` | Success | ✓ PASS |
| Router NOT in get_all_routers() | Python assertion | `workspace_regex_permissions_router not in get_all_routers()` = True | ✓ PASS |
| cachetools pinned in pyproject.toml | Python tomllib check | `['cachetools>=5.5.0']` found | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WSREG-01 | 05-01, 05-02 | Admin can create user regex workspace permission (pattern + priority + permission level) | ✓ SATISFIED | Store method `create_workspace_regex_permission()`, POST `/user` endpoint with admin auth, Pydantic model with regex/priority/permission/username fields |
| WSREG-02 | 05-01, 05-02 | Admin can list, update, and delete user regex workspace permissions | ✓ SATISFIED | Store methods for list/update/delete, GET/PATCH/DELETE endpoints at `/user` and `/user/{permission_id}` |
| WSREG-03 | 05-01, 05-02 | Admin can create group regex workspace permission (pattern + priority + permission level) | ✓ SATISFIED | Store method `create_workspace_group_regex_permission()`, POST `/group` endpoint with admin auth, Pydantic model with regex/priority/permission/group_name fields |
| WSREG-04 | 05-01, 05-02 | Admin can list, update, and delete group regex workspace permissions | ✓ SATISFIED | Store methods for list/update/delete, GET/PATCH/DELETE endpoints at `/group` and `/group/{permission_id}` |
| WSREG-05 | 05-02 | Workspace permission cache resolves regex and group-regex sources in configured resolution order | ✓ SATISFIED | `_lookup_workspace_permission()` iterates `config.PERMISSION_SOURCE_ORDER` with `_resolve_user_regex` and `_resolve_group_regex` resolvers. Tests verify custom order respected. |
| WSREG-06 | 05-02 | Full workspace cache is flushed on any regex permission create/update/delete operation | ✓ SATISFIED | `flush_workspace_cache()` calls `cache.clear()`. All 6 CUD endpoints call it. Tests verify list endpoints do NOT flush. |
| WSREG-07 | 05-01 | Alembic migration adds `workspace_regex_permissions` and `workspace_group_regex_permissions` tables | ✓ SATISFIED | Migration `8a9b0c1de234` creates both tables with columns, FKs, unique constraints. Downgrade drops both. |

**Orphaned requirements:** None. All 7 WSREG-* requirements from REQUIREMENTS.md mapped to Phase 5 are claimed by plans and verified.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No anti-patterns found |

No TODOs, FIXMEs, placeholders, empty implementations, or stub patterns detected in any Phase 5 files.

### Human Verification Required

### 1. Feature-flag gating integration test

**Test:** Deploy with `MLFLOW_ENABLE_WORKSPACES=false` and verify regex permission endpoints return 404. Then enable and verify they return proper responses.
**Expected:** Endpoints inaccessible when flag is false, accessible when true.
**Why human:** Requires full app startup with environment variable configuration; can't be tested via static analysis alone.

### 2. Admin-only access enforcement

**Test:** Log in as a non-admin user and attempt to call POST/PATCH/DELETE on workspace regex permission endpoints.
**Expected:** All requests return 403 Forbidden.
**Why human:** Requires full auth middleware stack and OIDC session context; unit tests mock the dependency.

### 3. End-to-end regex permission resolution

**Test:** As admin, create a user regex permission `team-.*` → READ. As a non-admin user in that pattern, verify workspace access is granted via the cache.
**Expected:** User gains READ access to workspaces matching `team-.*` without explicit per-workspace grants.
**Why human:** Requires running server with real database, OIDC auth, and workspace creation.

### Gaps Summary

No gaps found. All 9 must-haves verified. All 7 requirements satisfied. All 69 tests pass. All artifacts exist, are substantive, and are properly wired. No anti-patterns detected.

---

_Verified: 2026-03-24T12:46:00Z_
_Verifier: the agent (gsd-verifier)_
