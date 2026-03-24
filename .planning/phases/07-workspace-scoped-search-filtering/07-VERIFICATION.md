---
phase: 07-workspace-scoped-search-filtering
verified: 2026-03-24T18:59:15Z
status: passed
score: 7/7 must-haves verified
---

# Phase 7: Workspace-Scoped Search Filtering Verification Report

**Phase Goal:** Search results only contain resources from workspaces the user has permission to access, preventing cross-tenant data leakage
**Verified:** 2026-03-24T18:59:15Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Non-admin user searching experiments sees only experiments from workspaces they have permission to access | ✓ VERIFIED | `_filter_search_experiments` calls `_can_access_workspace` on both initial page (line 144) and refetch path (line 171); tests `TestFilterSearchExperimentsWorkspace` confirm filtering |
| 2 | Non-admin user searching registered models sees only models from workspaces they have permission to access | ✓ VERIFIED | `_filter_search_registered_models` calls `_can_access_workspace` on both initial page (line 211) and refetch path (line 238); tests `TestFilterSearchRegisteredModelsWorkspace` confirm filtering |
| 3 | Non-admin user searching logged models sees only models from experiments in accessible workspaces | ✓ VERIFIED | `_filter_search_logged_models` calls `_can_access_workspace` via experiment lookup on both initial page (line 283) and refetch path (line 334); tests `TestFilterSearchLoggedModelsWorkspace` confirm filtering |
| 4 | Experiments in default workspace are visible when GRANT_DEFAULT_WORKSPACE_ACCESS is true | ✓ VERIFIED | `_can_access_workspace` line 112: `if workspace == "default" and config.GRANT_DEFAULT_WORKSPACE_ACCESS: return True`; test `test_returns_true_for_default_workspace_when_grant_enabled` and cross-cutting test confirm |
| 5 | Experiments with no workspace (pre-workspace-era) are visible to authorized users | ✓ VERIFIED | `_can_access_workspace` line 110-111: `if not workspace: return True`; handles both `None` and empty string; tests `test_returns_true_when_workspace_is_none` and `test_returns_true_when_workspace_is_empty_string` confirm |
| 6 | Admin users see all results regardless of workspace | ✓ VERIFIED | All three filter functions (`_filter_search_experiments` line 118, `_filter_search_registered_models` line 185, `_filter_search_logged_models` line 255) return early when `get_fastapi_admin_status()` is True; admin bypass tests in all three test classes confirm |
| 7 | Filtering is a no-op when MLFLOW_ENABLE_WORKSPACES is false | ✓ VERIFIED | `_can_access_workspace` line 108: `if not config.MLFLOW_ENABLE_WORKSPACES: return True`; workspace filtering blocks in all three filters are gated by `if config.MLFLOW_ENABLE_WORKSPACES:`; `test_no_workspace_filtering_when_disabled` tests in all three classes confirm |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mlflow_oidc_auth/hooks/after_request.py` | `_can_access_workspace` helper + workspace filtering in 3 search functions | ✓ VERIFIED | 660 lines, contains `_can_access_workspace` (line 99), workspace filtering in `_filter_search_experiments` (lines 132-145, 171), `_filter_search_registered_models` (lines 199-212, 238), `_filter_search_logged_models` (lines 269-286, 324-335) |
| `mlflow_oidc_auth/tests/hooks/test_workspace_search_filtering.py` | Comprehensive test coverage (min 200 lines) | ✓ VERIFIED | 1116 lines, 24 test functions across 5 test classes covering all requirements |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `after_request.py` | `workspace_cache.py` | `get_workspace_permission_cached` import | ✓ WIRED | Line 58 imports, line 114 uses in `_can_access_workspace` |
| `after_request.py` | `config.py` | `config.MLFLOW_ENABLE_WORKSPACES` / `config.GRANT_DEFAULT_WORKSPACE_ACCESS` | ✓ WIRED | Config import at line 42, `MLFLOW_ENABLE_WORKSPACES` used at lines 108, 133, 200, 271, 325; `GRANT_DEFAULT_WORKSPACE_ACCESS` used at line 112 |
| `after_request.py` | `_get_tracking_store` / `_get_model_registry_store` | Workspace lookup via `.get_experiment().workspace` / `.get_registered_model().workspace` | ✓ WIRED | Tracking store used for experiments (lines 134, 138-140) and logged models (lines 272, 277-279); model registry store used for registered models (lines 201, 205-206) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `after_request.py::_can_access_workspace` | `workspace` param | `tracking_store.get_experiment(eid).workspace` / `model_registry_store.get_registered_model(name).workspace` | Yes — queries MLflow tracking/model store | ✓ FLOWING |
| `after_request.py::_can_access_workspace` | Permission check | `get_workspace_permission_cached(username, workspace)` | Yes — resolves via workspace cache (user, group, regex, group-regex sources) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 24 workspace filtering tests pass | `pytest mlflow_oidc_auth/tests/hooks/test_workspace_search_filtering.py -q` | 24 passed | ✓ PASS |
| All 2407 tests pass (no regressions) | `pytest mlflow_oidc_auth/tests/ -q --ignore=mlflow_oidc_auth/tests/routers/test_ui.py` | 2407 passed, 0 failed | ✓ PASS |
| after_request.py compiles cleanly | `python -m py_compile mlflow_oidc_auth/hooks/after_request.py` | exit 0 | ✓ PASS |
| No TODO/placeholder/stub patterns | `rg -n "TODO\|FIXME\|PLACEHOLDER" after_request.py` | No output | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WSSEC-01 | 07-01-PLAN.md | After-request search filtering verifies each experiment's actual workspace against user's workspace permissions | ✓ SATISFIED | `_filter_search_experiments` lines 132-145 (initial page) and line 171 (refetch path) |
| WSSEC-02 | 07-01-PLAN.md | After-request search filtering verifies each registered model's actual workspace against user's workspace permissions | ✓ SATISFIED | `_filter_search_registered_models` lines 199-212 (initial page) and line 238 (refetch path) |
| WSSEC-03 | 07-01-PLAN.md | After-request search filtering verifies each logged model's experiment workspace against user's workspace permissions | ✓ SATISFIED | `_filter_search_logged_models` lines 269-286 (initial page) and lines 324-335 (refetch path); derives workspace from experiment_id |
| WSSEC-04 | 07-01-PLAN.md | Default workspace resources remain visible when GRANT_DEFAULT_WORKSPACE_ACCESS is true | ✓ SATISFIED | `_can_access_workspace` line 112: `if workspace == "default" and config.GRANT_DEFAULT_WORKSPACE_ACCESS: return True` |
| WSSEC-05 | 07-01-PLAN.md | Pre-workspace-era resources (no workspace assignment) remain visible to authorized users | ✓ SATISFIED | `_can_access_workspace` lines 110-111: `if not workspace: return True` (handles None and empty string) |
| WSSEC-06 | 07-01-PLAN.md | Admin users bypass all workspace-scoped filtering | ✓ SATISFIED | Admin early-return in all three filter functions (lines 118-119, 185-186, 255-256) |

**Orphaned requirements:** None — all 6 WSSEC requirements mapped in REQUIREMENTS.md to Phase 7 are covered by 07-01-PLAN.md.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

No TODOs, FIXMEs, placeholders, stubs, or empty implementations detected in modified files.

### Human Verification Required

### 1. Cross-Tenant Data Leakage End-to-End Test

**Test:** With workspaces enabled, create two workspaces (ws-A, ws-B), assign user-1 to ws-A only, create experiments in both workspaces, then search experiments as user-1.
**Expected:** user-1 sees only ws-A experiments; no ws-B experiments leak through.
**Why human:** Requires a running MLflow server with workspace-enabled configuration and actual workspace/experiment data — cannot verify with unit tests alone.

### 2. Pagination Correctness Under Workspace Filtering

**Test:** Create 50 experiments across 2 workspaces, set max_results=10, and paginate through all results as a user with access to only one workspace.
**Expected:** Pagination tokens work correctly, all accessible experiments are eventually returned, no duplicates, no missing results.
**Why human:** Complex pagination behavior with refetch loop requires end-to-end integration testing with real MLflow tracking store.

### Gaps Summary

No gaps found. All 7 observable truths verified, all 6 WSSEC requirements satisfied, all artifacts exist and are substantive with real implementations, all key links are wired, all 2407 tests pass with zero regressions, and no anti-patterns detected.

---

_Verified: 2026-03-24T18:59:15Z_
_Verifier: the agent (gsd-verifier)_
