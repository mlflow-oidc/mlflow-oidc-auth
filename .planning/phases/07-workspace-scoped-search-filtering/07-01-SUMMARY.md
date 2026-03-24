---
phase: 07-workspace-scoped-search-filtering
plan: 01
subsystem: hooks/after_request
tags: [security, workspace, search-filtering, tenant-isolation]
dependency_graph:
  requires: [05-workspace-regex-permissions, 06-workspace-crud-backend]
  provides: [workspace-scoped-search-experiments, workspace-scoped-search-models, workspace-scoped-search-logged-models]
  affects: [after_request.py, search-api-responses]
tech_stack:
  added: []
  patterns: [workspace-gated-filtering, exp-ws-map-caching, feature-flag-gated-noop]
key_files:
  created:
    - mlflow_oidc_auth/tests/hooks/test_workspace_search_filtering.py
  modified:
    - mlflow_oidc_auth/hooks/after_request.py
decisions:
  - "Proto experiments/models lack workspace field — must re-fetch from tracking_store/model_registry_store to get workspace"
  - "LoggedModel has no workspace — derive from experiment_id via tracking_store.get_experiment(exp_id).workspace"
  - "Build ws_map dict before filtering to avoid N individual lookups; cache across initial page and refetch"
  - "Workspace filtering gated by config.MLFLOW_ENABLE_WORKSPACES — no-op when disabled, zero regression risk"
metrics:
  duration: "~3 minutes"
  completed: "2026-03-24"
  tasks_completed: 3
  tasks_total: 3
  tests_added: 24
  tests_total_pass: 150
requirements_completed: [WSSEC-01, WSSEC-02, WSSEC-03, WSSEC-04, WSSEC-05, WSSEC-06]
---

# Phase 07 Plan 01: Workspace-Scoped Search Filtering Summary

**One-liner:** Workspace-scoped search filtering in all three after_request search hooks using `_can_access_workspace` helper with feature-flag gating, default-workspace bypass, and pre-workspace-era resource visibility.

## What Was Done

### Task 1: `_can_access_workspace` helper + `_filter_search_experiments` workspace filtering
- Added `_can_access_workspace(username, workspace)` helper function that encapsulates workspace access logic:
  - Returns `True` when `MLFLOW_ENABLE_WORKSPACES` is `False` (no-op)
  - Returns `True` for `None`/empty workspace (pre-workspace-era resources, WSSEC-05)
  - Returns `True` for `"default"` workspace when `GRANT_DEFAULT_WORKSPACE_ACCESS` is `True` (WSSEC-04)
  - Otherwise checks `get_workspace_permission_cached(username, workspace)` is not `None`
- Modified `_filter_search_experiments`:
  - **Initial page:** After existing `can_read_experiment` filter, builds `ws_map` dict via `tracking_store.get_experiment(eid).workspace`, then filters experiments by workspace access
  - **Refetch path:** Added `_can_access_workspace(username, e.workspace)` to list comprehension alongside existing `can_read_experiment` check
- **Commit:** `a04d540`

### Task 2: `_filter_search_registered_models` + `_filter_search_logged_models` workspace filtering
- Modified `_filter_search_registered_models`:
  - **Initial page:** After existing `can_read_registered_model` filter, builds `ws_map` via `model_registry_store.get_registered_model(name).workspace`, then filters by workspace
  - **Refetch path:** Added `_can_access_workspace(username, rm.workspace)` to list comprehension
- Modified `_filter_search_logged_models`:
  - **Initial page:** After existing `can_read_experiment` filter, builds `exp_ws_map` via `tracking_store.get_experiment(exp_id).workspace`, then filters by workspace (LoggedModel has no `.workspace` — uses experiment_id to derive)
  - **Refetch loop:** Added workspace check using `exp_ws_map` cache (reused across initial page + refetch)
- **Commit:** `5cd1477`

### Task 3: Regression verification
- All 43 existing `test_after_request.py` tests pass ✅
- All 44 existing `test_workspace_hooks.py` tests pass ✅
- All 24 new `test_workspace_search_filtering.py` tests pass ✅
- Full hooks suite: **150 passed, 0 failed** ✅
- Broader suite: 1046 passed, 1 pre-existing failure (unrelated `test_ui.py` mock serialization issue) ✅
- `py_compile after_request.py` passes ✅

## Test Coverage

| Test Class | Tests | Status |
|---|---|---|
| `TestCanAccessWorkspace` | 7 | ✅ All pass |
| `TestFilterSearchExperimentsWorkspace` | 5 | ✅ All pass |
| `TestFilterSearchRegisteredModelsWorkspace` | 5 | ✅ All pass |
| `TestFilterSearchLoggedModelsWorkspace` | 5 | ✅ All pass |
| `TestWorkspaceFilteringCrossCutting` | 2 | ✅ All pass |
| **Total new tests** | **24** | ✅ |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all workspace filtering paths are fully wired to `get_workspace_permission_cached` and `config` flags.

## Security Requirements Met

| Req | Description | Status |
|---|---|---|
| WSSEC-01 | SearchExperiments filtered by workspace permission | ✅ |
| WSSEC-02 | SearchRegisteredModels filtered by workspace permission | ✅ |
| WSSEC-03 | SearchLoggedModels filtered by experiment workspace permission | ✅ |
| WSSEC-04 | Default workspace visible when GRANT_DEFAULT_WORKSPACE_ACCESS=True | ✅ |
| WSSEC-05 | Pre-workspace-era resources (workspace=None/empty) visible | ✅ |
| WSSEC-06 | Admin users bypass all workspace filtering | ✅ |

## Self-Check: PASSED

- ✅ `mlflow_oidc_auth/hooks/after_request.py` exists
- ✅ `mlflow_oidc_auth/tests/hooks/test_workspace_search_filtering.py` exists
- ✅ `07-01-SUMMARY.md` exists
- ✅ Commit `a04d540` found
- ✅ Commit `5cd1477` found
