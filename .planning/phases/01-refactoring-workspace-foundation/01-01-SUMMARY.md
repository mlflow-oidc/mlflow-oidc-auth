---
phase: 01-refactoring-workspace-foundation
plan: 01
subsystem: auth
tags: [permissions, rbac, refactoring, registry-pattern, python]

# Dependency graph
requires: []
provides:
  - "PERMISSION_REGISTRY dict mapping 7 resource types to builder functions"
  - "resolve_permission() single entry point for all permission resolution"
  - "_match_regex_permission() generic regex matcher replacing 10+ duplicated functions"
  - "All existing public API functions preserved as thin wrappers (unchanged signatures)"
affects: [01-02, 02-workspace-permission-layer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Registry pattern for permission resolution (PERMISSION_REGISTRY dict)"
    - "Builder functions returning source config dicts (replacing inline config construction)"
    - "Generic function with label parameter replacing type-specific duplicates"

key-files:
  created: []
  modified:
    - "mlflow_oidc_auth/utils/permissions.py"
    - "mlflow_oidc_auth/tests/utils/test_permissions.py"
    - "mlflow_oidc_auth/tests/utils/test_permissions_scorer.py"
    - "mlflow_oidc_auth/tests/utils/test_permissions_gateway.py"

key-decisions:
  - "Kept experiment-specific regex wrappers since they do experiment_id→name lookup (not just regex matching)"
  - "PERMISSION_REGISTRY populated at module import time — tests must patch the registry dict, not builder functions directly"
  - "Scorer 2-part key (experiment_id + scorer_name) handled via **kwargs to resolve_permission()"
  - "Prompt sources intentionally share registered_model store methods for user/group — preserved exactly"

patterns-established:
  - "Registry-driven permission resolution: all 7 resource types use resolve_permission() → PERMISSION_REGISTRY[type] → builder → get_permission_from_store_or_default()"
  - "Builder function pattern: _build_*_sources(resource_id, username, **kwargs) → Dict[str, Callable[[], str]]"
  - "Generic regex matcher: _match_regex_permission(regexes, name, label) replaces all type-specific regex functions"

requirements-completed: [REFAC-01]

# Metrics
duration: 8min
completed: 2026-03-23
---

# Phase 01 Plan 01: Permission Resolution Refactoring Summary

**Registry-driven resolve_permission() consolidating 8 copy-paste source config functions and 10+ duplicate regex matchers into a single PERMISSION_REGISTRY with 7 resource type builders**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-23T16:05:30Z
- **Completed:** 2026-03-23T16:13:40Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Consolidated 8 `_permission_*_sources_config` functions into 7 `_build_*_sources` builder functions registered in `PERMISSION_REGISTRY`
- Replaced 10+ near-identical regex matching functions with a single generic `_match_regex_permission(regexes, name, label)`
- Created `resolve_permission()` as the single entry point for all permission resolution across all 7 resource types
- Preserved ALL existing public API functions as thin wrappers with unchanged signatures (zero breaking changes)
- Added 5 new tests for `resolve_permission()` and `PERMISSION_REGISTRY` coverage; all 62 permission tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Build permission registry and resolve_permission()** - `fae51e5` (refactor)
2. **Task 2: Update tests for refactored permission resolution** - `1d6d809` (test)

## Files Created/Modified
- `mlflow_oidc_auth/utils/permissions.py` - Refactored from 8 duplicated source config functions to registry-driven architecture with PERMISSION_REGISTRY, resolve_permission(), and _match_regex_permission()
- `mlflow_oidc_auth/tests/utils/test_permissions.py` - Updated imports for renamed internal functions, added TestResolvePermission class with 5 tests
- `mlflow_oidc_auth/tests/utils/test_permissions_scorer.py` - Updated to use _match_regex_permission and _build_scorer_sources
- `mlflow_oidc_auth/tests/utils/test_permissions_gateway.py` - Updated to use _match_regex_permission for all 6 gateway regex functions

## Decisions Made
- **Kept experiment regex wrappers:** `_get_experiment_permission_from_regex` and `_get_experiment_group_permission_from_regex` were kept as thin wrappers (not merged into `_match_regex_permission`) because they perform experiment_id → experiment_name lookup via `_get_tracking_store()` before matching
- **Registry populated at import time:** `PERMISSION_REGISTRY` is a module-level dict built at import. Tests that need to override builder behavior must use `patch.dict("mlflow_oidc_auth.utils.permissions.PERMISSION_REGISTRY", {...})` rather than patching builder functions directly
- **Scorer kwargs pattern:** Scorer's 2-part key (experiment_id + scorer_name) passes through `resolve_permission(SCORER, experiment_id, username, scorer_name=scorer_name)` — the `**kwargs` are forwarded to `_build_scorer_sources` which extracts `scorer_name`
- **Prompt→registered_model sharing preserved:** `_build_prompt_sources` intentionally uses `store.get_registered_model_permission` and `store.get_user_groups_registered_model_permission` for user/group sources (not prompt-specific methods), matching original behavior exactly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- **Pre-existing test failure from parallel agent:** `test_experiment_permission.py::test_grant_permission_success` fails due to repository file changes made by a parallel agent executing plan 01-02 (modifying `experiment_permission.py`, `gateway_endpoint_permissions.py`, etc.). This failure is NOT caused by our permission refactoring and is outside the scope of this plan.
- **PERMISSION_REGISTRY import-time population:** Initial test approach of patching `_build_experiment_sources` directly didn't work because the registry is populated at import time. Resolved by using `patch.dict` on the registry itself.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all code is fully functional, no placeholder or TODO patterns.

## Next Phase Readiness
- Permission resolution is now centralized through `resolve_permission()` and `PERMISSION_REGISTRY`
- Adding workspace-level permission fallback (Phase 2) will require changes in ONE place: add a new source type to the builder functions and update `config.PERMISSION_SOURCE_ORDER`
- The registry pattern makes it trivial to add new resource types in the future
- Plan 01-02 (repository base classes) is being executed in parallel by another agent

## Self-Check: PASSED

- All 4 modified files exist on disk
- Both task commits found in git log (fae51e5, 1d6d809)
- PERMISSION_REGISTRY has 7 entries (verified via import)
- SUMMARY.md created at expected path

---
*Phase: 01-refactoring-workspace-foundation*
*Completed: 2026-03-23*
