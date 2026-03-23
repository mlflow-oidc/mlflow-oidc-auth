---
phase: 03-management-api-oidc-entity-coverage
plan: 02
subsystem: oidc-workspace-detection, entity-auth-coverage
tags: [oidc, workspace, config, before-request, prompt-optimization-job]
dependency_graph:
  requires: []
  provides:
    - OIDC workspace detection in callback (plugin + JWT claim fallback)
    - 3 new config entries for OIDC workspace integration
    - 5 PromptOptimizationJob before_request handlers
  affects:
    - mlflow_oidc_auth/config.py
    - mlflow_oidc_auth/routers/auth.py
    - mlflow_oidc_auth/hooks/before_request.py
tech_stack:
  added: []
  patterns:
    - Plugin detection pattern (mirrors OIDC_GROUP_DETECTION_PLUGIN)
    - JWT claim fallback with string-to-list normalization
    - Proto-to-validator mapping in BEFORE_REQUEST_HANDLERS
key_files:
  created:
    - mlflow_oidc_auth/tests/test_oidc_workspace_detection.py
    - mlflow_oidc_auth/tests/hooks/test_prompt_optimization_job.py
  modified:
    - mlflow_oidc_auth/config.py
    - mlflow_oidc_auth/routers/auth.py
    - mlflow_oidc_auth/hooks/before_request.py
decisions:
  - "OIDC workspace detection uses layered approach: plugin first, JWT claim fallback, auto-assign"
  - "OIDC_WORKSPACE_DEFAULT_PERMISSION defaults to NO_PERMISSIONS (most secure)"
  - "PromptOptimizationJob uses experiment-scoped validators (reuses existing validate_can_*_experiment)"
  - "ENTITY-02 (GatewayBudgetPolicy) explicitly NOT implemented — deferred per D-12"
metrics:
  completed: "2026-03-23"
---

# Phase 03 Plan 02: OIDC Workspace Detection + PromptOptimizationJob Entity Coverage Summary

OIDC login auto-detects workspace membership via configurable plugin or JWT claim fallback, and 5 PromptOptimizationJob RPCs secured behind experiment-scoped permission checks.

## Tasks Completed

### Task 1: OIDC workspace config + callback detection + auto-assign

**Config entries added to `mlflow_oidc_auth/config.py`:**
- `OIDC_WORKSPACE_CLAIM_NAME` — defaults to `"workspace"` (D-06)
- `OIDC_WORKSPACE_DETECTION_PLUGIN` — defaults to `None` (D-07)
- `OIDC_WORKSPACE_DEFAULT_PERMISSION` — defaults to `"NO_PERMISSIONS"` (D-08, most secure)

**Workspace detection in `_process_oidc_callback_fastapi()` (`mlflow_oidc_auth/routers/auth.py`):**
- Layered approach: plugin first → JWT claim fallback → auto-assign
- Plugin mirrors existing `OIDC_GROUP_DETECTION_PLUGIN` pattern exactly: `importlib.import_module(plugin).get_user_workspaces(access_token)`
- JWT claim fallback normalizes string to list, extracts from `userinfo[OIDC_WORKSPACE_CLAIM_NAME]`
- Auto-assign creates workspace membership via `store.create_workspace_permission(ws_name, email, default_permission)`
- Plugin errors logged as warning (not fatal — login continues)
- Duplicate permissions (re-login) silently ignored (idempotent)
- Only active when `MLFLOW_ENABLE_WORKSPACES=True`

**Tests (`mlflow_oidc_auth/tests/test_oidc_workspace_detection.py`):**
- 14 tests covering: disabled state, plugin detection, JWT claim fallback (string/list/custom claim/missing/empty), auto-assign with configurable permission, idempotent handling, plugin error resilience, config entry defaults

### Task 2: PromptOptimizationJob before_request handlers

**Proto imports added to `mlflow_oidc_auth/hooks/before_request.py`:**
- `CreatePromptOptimizationJob`, `GetPromptOptimizationJob`, `SearchPromptOptimizationJobs`, `DeletePromptOptimizationJob`, `CancelPromptOptimizationJob`

**5 handler entries in `BEFORE_REQUEST_HANDLERS` dict:**
- `CreatePromptOptimizationJob` → `validate_can_update_experiment` (EDIT, same as CreateRun)
- `GetPromptOptimizationJob` → `validate_can_read_experiment` (READ)
- `SearchPromptOptimizationJobs` → `validate_can_read_experiment` (READ)
- `DeletePromptOptimizationJob` → `validate_can_delete_experiment` (DELETE)
- `CancelPromptOptimizationJob` → `validate_can_update_experiment` (EDIT, like cancelling a run)

**Tests (`mlflow_oidc_auth/tests/hooks/test_prompt_optimization_job.py`):**
- 6 tests verifying correct proto→validator identity mapping and full set presence

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

| Check | Result |
|-------|--------|
| Config `OIDC_WORKSPACE_CLAIM_NAME == 'workspace'` | ✅ PASSED |
| Config `OIDC_WORKSPACE_DETECTION_PLUGIN is None` | ✅ PASSED |
| Config `OIDC_WORKSPACE_DEFAULT_PERMISSION == 'NO_PERMISSIONS'` | ✅ PASSED |
| `OIDC_WORKSPACE_DETECTION_PLUGIN` in `routers/auth.py` | ✅ PASSED |
| `CreatePromptOptimizationJob` in `BEFORE_REQUEST_HANDLERS` | ✅ PASSED |
| All 5 PromptOptimizationJob protos registered | ✅ PASSED |
| `test_oidc_workspace_detection.py` — 14/14 tests pass | ✅ PASSED |
| `test_prompt_optimization_job.py` — 6/6 tests pass | ✅ PASSED |
| Existing test regression check — 64/64 tests pass | ✅ PASSED |

## Deferred Items

- **ENTITY-02 (GatewayBudgetPolicy)** — Protos don't exist in MLflow 3.10.1. Expected in MLflow 3.11. Deferred per D-12.

## Known Stubs

None — all code paths are fully wired.

## Self-Check: PASSED
