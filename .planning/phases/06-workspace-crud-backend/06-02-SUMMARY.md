---
phase: 06-workspace-crud-backend
plan: 02
subsystem: routers
tags: [workspace, crud, fastapi, pydantic, oidc, feature-flag, auto-create]

requires:
  - phase: 06-workspace-crud-backend-plan-01
    provides: "Workspace auth hooks (auto-grant MANAGE, cascade-delete, validators)"
  - phase: 05-regex-workspace-permissions
    provides: "Workspace permission cache, workspace entities, permission resolution"
provides:
  - "FastAPI workspace CRUD router with 5 endpoints (create, list, get, update, delete)"
  - "DNS-safe workspace name validation via Pydantic field_validator"
  - "Permission-based workspace list filtering (admin sees all, non-admin sees permitted)"
  - "Feature-flag gated router registration (MLFLOW_ENABLE_WORKSPACES)"
  - "OIDC login auto-creates non-existent workspaces before assigning membership (WSOIDC-04)"
affects: [07-frontend-workspace-ui]

tech-stack:
  added: []
  patterns:
    - "Pydantic field_validator for DNS-safe workspace name validation"
    - "Feature-flag gated router: not in get_all_routers(), registered conditionally in app.py"
    - "MLflow workspace store proxy: FastAPI routes delegate to _get_workspace_store() for CRUD"
    - "Lazy import pattern: _get_workspace_store imported inside function body in auth.py"

key-files:
  created:
    - mlflow_oidc_auth/routers/workspace_crud.py
    - mlflow_oidc_auth/tests/routers/test_workspace_crud.py
    - mlflow_oidc_auth/tests/routers/test_auth_workspace_autocreate.py
  modified:
    - mlflow_oidc_auth/models/workspace.py
    - mlflow_oidc_auth/routers/__init__.py
    - mlflow_oidc_auth/routers/_prefix.py
    - mlflow_oidc_auth/app.py
    - mlflow_oidc_auth/routers/auth.py

key-decisions:
  - "Path params named {workspace} to match dependency parameter names in check_workspace_*_permission"
  - "workspace_crud_router exported in __all__ but NOT in get_all_routers() — feature-flag gated in app.py"
  - "Lazy import of _get_workspace_store in auth.py to match existing pattern of deferred imports"
  - "Patch target mlflow.server.handlers._get_workspace_store (not auth module) because import is function-local"

patterns-established:
  - "Feature-flag gated router pattern: export in __all__, register conditionally in app.py"
  - "MLflow store proxy pattern: FastAPI endpoint → _get_workspace_store() → error mapping to HTTPException"

requirements-completed: [WSCRUD-07, WSCRUD-08, WSOIDC-04]

duration: 12min
completed: 2026-03-24
---

# Phase 06 Plan 02: Workspace CRUD Router & OIDC Auto-Create Summary

**One-liner:** FastAPI workspace CRUD router with DNS-safe Pydantic validation proxying to MLflow's native workspace store, plus OIDC login auto-creation of non-existent workspaces

## What Was Done

### Task 1: Workspace CRUD Router (commit `f27ec23`)

Created a full FastAPI workspace CRUD router with 5 endpoints that proxy to MLflow's native workspace store:

1. **Pydantic Models** (`models/workspace.py`):
   - `WorkspaceCrudCreateRequest` with DNS-safe name validation (`WORKSPACE_NAME_PATTERN`, `field_validator`)
   - `WorkspaceCrudUpdateRequest` for description updates
   - `WorkspaceCrudResponse` for structured responses
   - Constants: `WORKSPACE_NAME_MIN_LENGTH=2`, `WORKSPACE_NAME_MAX_LENGTH=63`, `WORKSPACE_RESERVED_NAMES`

2. **Router** (`routers/workspace_crud.py`):
   - `POST /` — Create workspace (admin only), returns 201
   - `GET /` — List workspaces (admin sees all, non-admin sees only permitted)
   - `GET /{workspace}` — Get workspace details (READ permission required)
   - `PATCH /{workspace}` — Update description (MANAGE permission required)
   - `DELETE /{workspace}` — Delete workspace in RESTRICT mode (MANAGE, cannot delete "default")

3. **Feature-Flag Gating**:
   - Router exported in `__all__` but NOT in `get_all_routers()`
   - Registered conditionally in `app.py` inside `if config.MLFLOW_ENABLE_WORKSPACES:` block
   - Prefix constant `WORKSPACE_CRUD_ROUTER_PREFIX` added to `_prefix.py`

4. **Tests** (`test_workspace_crud.py`): 33 tests covering:
   - 14 Pydantic validation tests (valid names, invalid names, reserved names, description limits)
   - 6 router configuration tests (prefix, tags, route count, feature flag gating, exports)
   - 2 create tests (success, duplicate 409)
   - 2 list tests (admin sees all, non-admin filtered)
   - 2 get tests (success, not found 404)
   - 2 update tests (success, not found 404)
   - 4 delete tests (success, default blocked 400, not found 404, not empty 409)
   - 1 feature flag integration test

### Task 2: OIDC Workspace Auto-Create (commit `7850a03`)

Modified the OIDC callback in `auth.py` to auto-create workspaces that don't exist before assigning membership:

1. **Implementation** (`routers/auth.py` lines 492-527):
   - Before the permission assignment loop, gets MLflow workspace store via `_get_workspace_store()`
   - For each workspace, checks existence via `get_workspace()`, auto-creates via `create_workspace(name, description="")` if not found
   - Wrapped in nested try/except: store access failure logged but doesn't block, individual auto-create failure logged but doesn't block
   - Permission assignment continues regardless of auto-create outcome

2. **Tests** (`test_auth_workspace_autocreate.py`): 4 tests covering:
   - Non-existent workspace is auto-created before permission assignment
   - Existing workspace skips creation (idempotent)
   - Auto-create failure doesn't block login
   - Workspaces disabled skips all auto-create logic

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock patch targets for lazy imports**
- **Found during:** Task 2 test implementation
- **Issue:** Tests initially patched `mlflow_oidc_auth.routers.auth._get_workspace_store` and `mlflow_oidc_auth.routers.auth.store`, but both are imported lazily inside the function body (not at module level), so these patch targets don't exist
- **Fix:** Changed patch targets to `mlflow.server.handlers._get_workspace_store` (source) and `mlflow_oidc_auth.store.store` (source module)
- **Files modified:** `mlflow_oidc_auth/tests/routers/test_auth_workspace_autocreate.py`
- **Commit:** `7850a03`

## Deferred Issues

- **Pre-existing test failure:** `test_ui.py::TestServeSPAConfig::test_serve_spa_config_authenticated` fails because mock config's `MLFLOW_ENABLE_WORKSPACES` attribute is a MagicMock (not JSON-serializable). Confirmed pre-existing — not introduced by this plan. Needs mock config to set `MLFLOW_ENABLE_WORKSPACES = True` explicitly.

## Known Stubs

None — all endpoints are fully wired to MLflow's workspace store via `_get_workspace_store()`.

## Verification Results

```
mlflow_oidc_auth/tests/routers/test_workspace_crud.py: 33 passed
mlflow_oidc_auth/tests/routers/test_workspace_permissions.py: 28 passed
mlflow_oidc_auth/tests/routers/test_auth_workspace_autocreate.py: 4 passed
mlflow_oidc_auth/tests/routers/test_auth.py: 31 passed
Full suite (excluding pre-existing failure): 1022 passed
```

## Self-Check: PASSED

All created/modified files verified present. Both task commits (f27ec23, 7850a03) verified in git log.
