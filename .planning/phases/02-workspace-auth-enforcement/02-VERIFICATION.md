---
phase: 02-workspace-auth-enforcement
verified: 2026-03-23T22:28:00Z
status: passed
score: 5/5 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "CreateExperiment and CreateRegisteredModel require MANAGE permission on the target workspace (not just after_request auto-grant) — over-inclusive creation gating fixed"
  gaps_remaining: []
  regressions: []
---

# Phase 2: Workspace Auth Enforcement Verification Report

**Phase Goal:** Workspace boundaries are enforced in the permission resolution chain — users can only access resources in workspaces they have permission for, with no cross-tenant data leakage
**Verified:** 2026-03-23T22:28:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (Plan 02-03 fixed over-inclusive creation gating)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | before_request handlers intercept all 5 workspace protobuf RPCs — CreateWorkspace/UpdateWorkspace/DeleteWorkspace require admin, GetWorkspace checks workspace permission, ListWorkspaces returns filtered results | ✓ VERIFIED | `WORKSPACE_BEFORE_REQUEST_HANDLERS` maps all 5 protobuf classes. Runtime verification confirms: `CreateWorkspace→validate_can_create_workspace`, `GetWorkspace→validate_can_read_workspace`, `ListWorkspaces→validate_can_list_workspaces`, `UpdateWorkspace→validate_can_update_workspace`, `DeleteWorkspace→validate_can_delete_workspace`. Regex validators register both /api/3.0/ and /ajax-api/3.0/ prefixes (10 workspace entries). `_find_validator()` correctly dispatches workspace paths. `_filter_list_workspaces` registered in after_request for ListWorkspaces filtering. |
| 2 | Users with workspace-level READ/USE/EDIT/MANAGE permissions can access resources in that workspace; users without workspace permission get NO_PERMISSIONS (hard deny, not fallback to default_permission) | ✓ VERIFIED | `resolve_permission()` checks `result.kind == "fallback" and config.MLFLOW_ENABLE_WORKSPACES`, returns `PermissionResult(ws_perm, "workspace")` when cached permission exists, returns `PermissionResult(NO_PERMISSIONS, "workspace-deny")` when no permission. `get_permission_from_store_or_default()` remains completely unchanged — it still returns `PermissionResult(get_permission(perm), "fallback")` at the end. TTLCache in `workspace_cache.py` resolves user→group→None chain. |
| 3 | CreateExperiment and CreateRegisteredModel require MANAGE permission on the target workspace (not just after_request auto-grant) | ✓ VERIFIED | **Gap closed by Plan 02-03 (commit 1e97803).** `_get_workspace_gated_creation_paths()` at line 382 now uses `if handler in (CreateExperiment, CreateRegisteredModel)` instead of the buggy `if handler is not None`. Runtime verification confirms exactly 4 paths returned: `/api/2.0/mlflow/experiments/create POST`, `/ajax-api/2.0/mlflow/experiments/create POST`, `/api/2.0/mlflow/registered-models/create POST`, `/ajax-api/2.0/mlflow/registered-models/create POST`. Non-creation paths (`/graphql`, `/server-info`, `/gateway/*`, `/scorer/*`) all return False from `_is_workspace_gated_creation()`. 2 regression tests added: `test_is_workspace_gated_creation_rejects_graphql_and_server_info` and `test_workspace_gated_creation_paths_count`. |
| 4 | Permission resolution chain with workspaces enabled follows: resource-level (user→group→regex→group-regex) → workspace-level → NO_PERMISSIONS | ✓ VERIFIED | `resolve_permission()` calls `get_permission_from_store_or_default()` first (unchanged), which tries user→group→regex→group-regex per `PERMISSION_SOURCE_ORDER` config. Only on `result.kind == "fallback"` does the workspace check engage. `_lookup_workspace_permission()` tries user-level then group-level (highest across groups). Returns NO_PERMISSIONS as hard deny. 5 workspace fallback tests in `TestResolvePermissionWorkspaceFallback` all pass. |
| 5 | Workspace permission lookups are cached via TTLCache — configurable `workspace_cache_max_size` and `workspace_cache_ttl_seconds` | ✓ VERIFIED | `workspace_cache.py` uses `cachetools.TTLCache` with lazy init. `_get_cache()` reads `config.WORKSPACE_CACHE_MAX_SIZE` (default 1024) and `config.WORKSPACE_CACHE_TTL_SECONDS` (default 300). Only non-None values cached. Config verified at lines 134-140 of config.py. 10 cache behavior tests pass including hit/miss, None-not-cached, and implicit default workspace MANAGE. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mlflow_oidc_auth/entities/workspace.py` | WorkspacePermission and WorkspaceGroupPermission entities | ✓ VERIFIED | 82 lines. Both classes with property access and to_json(). |
| `mlflow_oidc_auth/repository/workspace_permission.py` | WorkspacePermissionRepository with CRUD | ✓ VERIFIED | 179 lines. get/create/update/delete/list_for_user/list_for_workspace. |
| `mlflow_oidc_auth/repository/workspace_group_permission.py` | WorkspaceGroupPermissionRepository with get_highest_for_user | ✓ VERIFIED | 227 lines. Full CRUD + get_highest_for_user with user_groups join and compare_permissions. |
| `mlflow_oidc_auth/utils/workspace_cache.py` | TTLCache with get_workspace_permission_cached() | ✓ VERIFIED | 86 lines. Lazy init, non-None caching, implicit default workspace MANAGE, lazy store import. |
| `mlflow_oidc_auth/validators/workspace.py` | 5 workspace validators | ✓ VERIFIED | 66 lines. create/read/update/delete require admin (read checks perm), list is no-op. |
| `mlflow_oidc_auth/hooks/before_request.py` | Workspace handler registration + creation gating | ✓ VERIFIED | WORKSPACE_BEFORE_REQUEST_HANDLERS (5 entries), WORKSPACE_BEFORE_REQUEST_VALIDATORS, creation gating at lines 371-386. **Fixed:** `_get_workspace_gated_creation_paths()` now correctly filters with `handler in (CreateExperiment, CreateRegisteredModel)` — returns exactly 4 paths. |
| `mlflow_oidc_auth/hooks/after_request.py` | ListWorkspaces after_request filtering | ✓ VERIFIED | _filter_list_workspaces at line 413-427. Registered in AFTER_REQUEST_PATH_HANDLERS. Admin bypass, workspace disable check, JSON filtering. |
| `mlflow_oidc_auth/utils/permissions.py` | resolve_permission() workspace fallback | ✓ VERIFIED | Workspace fallback after fallback kind. NO_PERMISSIONS import. get_permission_from_store_or_default unchanged. |
| `mlflow_oidc_auth/db/models/workspace.py` | ORM models with to_mlflow_entity() | ✓ VERIFIED | 50 lines. Both SqlWorkspacePermission and SqlWorkspaceGroupPermission have to_mlflow_entity() + relationship(). |
| `mlflow_oidc_auth/config.py` | WORKSPACE_CACHE_MAX_SIZE and WORKSPACE_CACHE_TTL_SECONDS | ✓ VERIFIED | Lines 134-140. Defaults 1024 and 300 respectively. |
| `mlflow_oidc_auth/sqlalchemy_store.py` | Workspace permission store methods | ✓ VERIFIED | 7 methods. Repo instantiation in init_db. Username→user_id resolution via get_user(). |
| `mlflow_oidc_auth/entities/__init__.py` | Workspace entity exports | ✓ VERIFIED | WorkspacePermission and WorkspaceGroupPermission in __all__. |
| `mlflow_oidc_auth/validators/__init__.py` | Workspace validator exports | ✓ VERIFIED | All 5 workspace validators in __all__. |
| `mlflow_oidc_auth/repository/__init__.py` | Workspace repo exports | ✓ VERIFIED | Both workspace repos in __all__. |
| `mlflow_oidc_auth/tests/hooks/test_workspace_hooks.py` | Workspace hook + creation gating tests including regression tests | ✓ VERIFIED | 552 lines, 24 tests across 5 test classes. **New in 02-03:** autouse `_reset_creation_paths_cache` fixture, `test_is_workspace_gated_creation_rejects_graphql_and_server_info`, `test_workspace_gated_creation_paths_count`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `hooks/before_request.py` | `validators/workspace.py` | WORKSPACE_BEFORE_REQUEST_HANDLERS maps protobuf classes to validator functions | ✓ WIRED | All 5 validators mapped and imported. `_find_validator()` routes workspace paths. |
| `utils/permissions.py` | `utils/workspace_cache.py` | resolve_permission() calls get_workspace_permission_cached() | ✓ WIRED | Lazy import, called on fallback kind. Returns PermissionResult with workspace/workspace-deny kind. |
| `hooks/before_request.py` | `utils/workspace_cache.py` | Creation gating calls get_workspace_permission_cached() | ✓ WIRED | Lazy import, calls get_workspace_permission_cached. Checks ws_perm.can_manage. |
| `hooks/after_request.py` | `utils/workspace_cache.py` | _filter_list_workspaces calls get_workspace_permission_cached() | ✓ WIRED | Import at line 54, called in list comprehension filter. |
| `utils/workspace_cache.py` | `store.py` | _lookup_workspace_permission calls store methods | ✓ WIRED | Lazy import. Calls store.get_workspace_permission and store.get_user_groups_workspace_permission. |
| `sqlalchemy_store.py` | `repository/workspace_permission.py` | init_db() instantiates repos | ✓ WIRED | Both workspace repos imported and instantiated. |
| `db/models/workspace.py` | `entities/workspace.py` | to_mlflow_entity() returns entity instances | ✓ WIRED | Both ORM models have to_mlflow_entity() returning entity instances. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `workspace_cache.py` | Permission result | store.get_workspace_permission → repo.get() → SqlWorkspacePermission query | DB query with .one() on composite PK | ✓ FLOWING |
| `workspace_cache.py` | Group permission | store.get_user_groups_workspace_permission → repo.get_highest_for_user() → JOIN query | DB query joining workspace_group_permissions + user_groups | ✓ FLOWING |
| `after_request.py` _filter_list_workspaces | Workspace list | response.get_json() → filter via get_workspace_permission_cached | Real data from MLflow response, filtered by cached perm lookup | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 5 workspace handlers registered | Python import + len check | 5 handlers, all correct validators | ✓ PASS |
| Workspace regex validators cover both prefixes | Python import + inspection | 10 workspace entries covering /api/3.0/ and /ajax-api/3.0/ | ✓ PASS |
| _find_validator dispatches workspace paths | Python simulation with FakeReq | GET workspaces/my-workspace → validate_can_read_workspace, GET workspaces → validate_can_list_workspaces, POST workspaces → validate_can_create_workspace | ✓ PASS |
| CreateExperiment is creation-gated | Python check _is_workspace_gated_creation | (/api/2.0/mlflow/experiments/create, POST) → True | ✓ PASS |
| CreateRegisteredModel is creation-gated | Python check _is_workspace_gated_creation | (/api/2.0/mlflow/registered-models/create, POST) → True | ✓ PASS |
| **Non-creation paths NOT gated** | Python check _is_workspace_gated_creation | /graphql GET→False, /graphql POST→False, /server-info GET→False, /gateway/supported-providers GET→False, /gateway/supported-models GET→False, /scorer/invoke POST→False | **✓ PASS** (was ✗ FAIL, fixed by 02-03) |
| Exactly 4 creation paths returned | Python _get_workspace_gated_creation_paths() | 4 paths: 2 endpoints × 2 prefixes, all POST | **✓ PASS** (new check) |
| ListWorkspaces after_request registered | Python import check | ListWorkspaces in AFTER_REQUEST_PATH_HANDLERS, 2 (path,method) entries | ✓ PASS |
| resolve_permission has workspace fallback | Source inspection | Contains workspace-deny and workspace kinds | ✓ PASS |
| All 2251 tests pass (24 workspace-specific) | pytest full suite -x | 2251 passed in 105.91s, 0 failures | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| WSAUTH-01 | 02-02 | before_request handlers for 5 workspace protobuf RPCs | ✓ SATISFIED | 5 handlers in WORKSPACE_BEFORE_REQUEST_HANDLERS, regex validators with both path prefixes, _find_validator workspace dispatch |
| WSAUTH-02 | 02-01 | Workspace-level user permissions with DB model, entity, repository, store methods | ✓ SATISFIED | WorkspacePermission entity, SqlWorkspacePermission ORM with to_mlflow_entity(), WorkspacePermissionRepository with full CRUD, 7 SqlAlchemyStore wrapper methods |
| WSAUTH-03 | 02-02, 02-03 | CreateExperiment and CreateRegisteredModel gated on workspace MANAGE | ✓ SATISFIED | **Fixed by 02-03 (commit 1e97803).** `_get_workspace_gated_creation_paths()` returns exactly 4 paths. Non-creation paths excluded. Filter uses `handler in (CreateExperiment, CreateRegisteredModel)`. 2 regression tests added. |
| WSAUTH-04 | 02-02 | Permission resolution with workspace-level fallback: resource→workspace→NO_PERMISSIONS | ✓ SATISFIED | resolve_permission() has workspace fallback block. get_permission_from_store_or_default() unchanged. Returns NO_PERMISSIONS with "workspace-deny" kind when no workspace permission. |
| WSAUTH-05 | 02-01 | TTLCache for workspace permission lookups with configurable size/TTL | ✓ SATISFIED | cachetools.TTLCache with lazy init, WORKSPACE_CACHE_MAX_SIZE (1024), WORKSPACE_CACHE_TTL_SECONDS (300), non-None caching, implicit default workspace MANAGE |

No orphaned requirements — all 5 WSAUTH IDs are mapped in plans and covered.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `mlflow_oidc_auth/utils/permissions.py` | 398 | `TODO: check if str can be replaced by Permission in function signature` | ℹ️ Info | Pre-existing TODO, not introduced by this phase |
| `mlflow_oidc_auth/hooks/before_request.py` | 354-361 | `WORKSPACE_BEFORE_REQUEST_VALIDATORS` includes non-workspace entries from get_endpoints() | ℹ️ Info | Harmless — `_find_validator()` only consults this dict when request path contains `/mlflow/workspaces`. Wasted memory but no functional impact. |

**Note:** The 🛑 Blocker from the initial verification (over-inclusive `_get_workspace_gated_creation_paths()`) has been resolved by Plan 02-03.

### Human Verification Required

### 1. End-to-end workspace permission enforcement

**Test:** Enable `MLFLOW_ENABLE_WORKSPACES=True`, create a workspace, assign a user READ permission. Try accessing experiments in that workspace vs another workspace.
**Expected:** Experiments in the permitted workspace are accessible; experiments in other workspaces return 403 or NO_PERMISSIONS.
**Why human:** Requires running MLflow server with workspace-enabled config, creating actual resources, and testing cross-workspace access patterns.

### 2. Workspace creation gating with real requests

**Test:** With workspaces enabled, send POST to /api/2.0/mlflow/experiments/create with and without workspace MANAGE permission.
**Expected:** Without MANAGE → 403; with MANAGE → experiment created.
**Why human:** Requires running server with auth middleware to verify full request lifecycle.

### 3. ListWorkspaces after_request filtering

**Test:** As non-admin user with permission on workspace A but not B, call ListWorkspaces.
**Expected:** Response only includes workspace A.
**Why human:** Requires MLflow workspace API to return actual workspace data for filtering.

### Gaps Summary

**No gaps remain.** All 5 observable truths verified. The single gap from the initial verification (over-inclusive creation gating in `_get_workspace_gated_creation_paths()`) was fixed by Plan 02-03 (commit 1e97803). The fix changed the filter from `if handler is not None` to `if handler in (CreateExperiment, CreateRegisteredModel)`, reducing the creation-gated path set from 21 paths to exactly 4 (2 endpoints × 2 API prefixes). Regression tests confirm non-creation paths (/graphql, /server-info, /gateway/*, /scorer/*) are excluded. Full test suite of 2251 tests passes with zero regressions.

---

_Verified: 2026-03-23T22:28:00Z_
_Verifier: the agent (gsd-verifier)_
