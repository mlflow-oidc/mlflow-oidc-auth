---
phase: 01-refactoring-workspace-foundation
plan: 02
subsystem: auth
tags: [repository, generics, refactoring, python, sqlalchemy, type-vars]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Registry-driven resolve_permission() — establishes pattern of generic abstraction over per-type duplicates"
provides:
  - "BaseUserPermissionRepository generic base class for user-level permission CRUD"
  - "BaseGroupPermissionRepository generic base class for group-level permission CRUD"
  - "BaseRegexPermissionRepository generic base class for regex-based user permission CRUD"
  - "BaseGroupRegexPermissionRepository generic base class for regex-based group permission CRUD"
  - "All 28 repository subclasses refactored to extend base classes with ~60% code reduction"
affects: [01-03, 02-workspace-permission-layer, 03-management-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Generic base repository with TypeVar[ModelT, EntityT] for type-safe inheritance"
    - "Class attribute configuration (model_class, entity_class, resource_id_attr) for declarative subclass setup"
    - "Mixin-style method delegation: subclasses set 3 class attrs, get 7+ CRUD methods free"

key-files:
  created:
    - "mlflow_oidc_auth/repository/_base.py"
  modified:
    - "mlflow_oidc_auth/repository/__init__.py"
    - "mlflow_oidc_auth/repository/experiment_permission.py"
    - "mlflow_oidc_auth/repository/registered_model_permission.py"
    - "mlflow_oidc_auth/repository/gateway_endpoint_permissions.py"
    - "mlflow_oidc_auth/repository/scorer_permission.py"
    - "mlflow_oidc_auth/repository/experiment_permission_group.py"
    - "mlflow_oidc_auth/repository/experiment_permission_regex.py"
    - "mlflow_oidc_auth/repository/experiment_permission_regex_group.py"
    - "(and 18 more repository subclass files)"

key-decisions:
  - "Base class uses class attributes (model_class, entity_class, resource_id_attr) rather than constructor params for cleaner subclass definitions"
  - "Scorer 2-part key (experiment_id + scorer_name) handled by overriding all key methods in subclass rather than adding complexity to base"
  - "Gateway repos keep rename()/wipe() as subclass-only methods — not generalized into base since only 3 of 28 repos need them"
  - "Test patch targets updated to _base module path since methods now resolve from base class module"
  - "RegisteredModelPermissionRegex prompt=False parameter handled via method overrides, not base class generalization"

patterns-established:
  - "Generic base repository pattern: subclass sets model_class + entity_class + resource_id_attr, inherits full CRUD"
  - "4-tier repository hierarchy: User → Group → Regex → GroupRegex base classes"
  - "Test patching convention: patch at _base module path for inherited methods, subclass module for overridden methods"

requirements-completed: [REFAC-02]

# Metrics
duration: 25min
completed: 2026-03-23
---

# Phase 01 Plan 02: Repository Base Class Refactoring Summary

**4 generic base repository classes (BaseUserPermissionRepository, BaseGroupPermissionRepository, BaseRegexPermissionRepository, BaseGroupRegexPermissionRepository) eliminating ~1360 lines of duplicated CRUD across 28 permission repository subclasses**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-23T16:10:00Z
- **Completed:** 2026-03-23T16:35:09Z
- **Tasks:** 2
- **Files modified:** 37 (1 created, 26 repos modified, 10 test files updated)

## Accomplishments
- Created 4 generic base classes in `repository/_base.py` (835 lines) with full type-safe Generic[ModelT, EntityT] parameterization
- Refactored all 28 repository subclasses to extend the appropriate base class — standard repos reduced from ~80-125 lines to ~10-30 lines each
- Net code reduction: -1360 lines (2433 deleted, 1073 added across 36 files)
- Updated 10 test files to patch base class module paths and use new internal method names — all 287 repository tests pass with zero regressions
- Full backward compatibility: all public method names and signatures unchanged; `sqlalchemy_store.py` requires zero changes

## Task Commits

Each task was committed atomically:

1. **Task 1: Create generic base repository classes in _base.py** - `ca07337` (refactor)
2. **Task 2: Refactor 28 repository subclasses to extend base classes** - `e955f38` (refactor)

## Files Created/Modified
- `mlflow_oidc_auth/repository/_base.py` - NEW: 4 generic base classes (BaseUserPermissionRepository, BaseGroupPermissionRepository, BaseRegexPermissionRepository, BaseGroupRegexPermissionRepository) with common CRUD operations
- `mlflow_oidc_auth/repository/__init__.py` - Added base class exports to `__all__`
- `mlflow_oidc_auth/repository/experiment_permission.py` - Extends BaseUserPermissionRepository, removed all duplicated CRUD methods
- `mlflow_oidc_auth/repository/experiment_permission_group.py` - Extends BaseGroupPermissionRepository
- `mlflow_oidc_auth/repository/experiment_permission_regex.py` - Extends BaseRegexPermissionRepository
- `mlflow_oidc_auth/repository/experiment_permission_regex_group.py` - Extends BaseGroupRegexPermissionRepository
- `mlflow_oidc_auth/repository/registered_model_permission.py` - Extends BaseUserPermissionRepository with resource_id_attr="name", keeps rename()/wipe()
- `mlflow_oidc_auth/repository/registered_model_permission_group.py` - Extends BaseGroupPermissionRepository
- `mlflow_oidc_auth/repository/registered_model_permission_regex.py` - Extends BaseRegexPermissionRepository with prompt=False overrides
- `mlflow_oidc_auth/repository/registered_model_permission_regex_group.py` - Extends BaseGroupRegexPermissionRepository
- `mlflow_oidc_auth/repository/gateway_endpoint_permissions.py` - Extends BaseUserPermissionRepository, keeps rename()/wipe()
- `mlflow_oidc_auth/repository/gateway_endpoint_group_permissions.py` - Extends BaseGroupPermissionRepository
- `mlflow_oidc_auth/repository/gateway_endpoint_regex_permissions.py` - Extends BaseRegexPermissionRepository
- `mlflow_oidc_auth/repository/gateway_endpoint_group_regex_permissions.py` - Extends BaseGroupRegexPermissionRepository
- `mlflow_oidc_auth/repository/gateway_secret_permissions.py` - Extends BaseUserPermissionRepository, keeps rename()/wipe()
- `mlflow_oidc_auth/repository/gateway_secret_group_permissions.py` - Extends BaseGroupPermissionRepository
- `mlflow_oidc_auth/repository/gateway_secret_regex_permissions.py` - Extends BaseRegexPermissionRepository
- `mlflow_oidc_auth/repository/gateway_secret_group_regex_permissions.py` - Extends BaseGroupRegexPermissionRepository
- `mlflow_oidc_auth/repository/gateway_model_definition_permissions.py` - Extends BaseUserPermissionRepository, keeps rename()/wipe()
- `mlflow_oidc_auth/repository/gateway_model_definition_group_permissions.py` - Extends BaseGroupPermissionRepository
- `mlflow_oidc_auth/repository/gateway_model_definition_regex_permissions.py` - Extends BaseRegexPermissionRepository
- `mlflow_oidc_auth/repository/gateway_model_definition_group_regex_permissions.py` - Extends BaseGroupRegexPermissionRepository
- `mlflow_oidc_auth/repository/prompt_permission_group.py` - Extends BaseGroupPermissionRepository
- `mlflow_oidc_auth/repository/scorer_permission.py` - Extends BaseUserPermissionRepository with 2-part key overrides (experiment_id + scorer_name)
- `mlflow_oidc_auth/repository/scorer_permission_group.py` - Extends BaseGroupPermissionRepository
- `mlflow_oidc_auth/repository/scorer_permission_regex.py` - Extends BaseRegexPermissionRepository
- `mlflow_oidc_auth/repository/scorer_permission_regex_group.py` - Extends BaseGroupRegexPermissionRepository
- `mlflow_oidc_auth/tests/repository/test_experiment_permission.py` - Patch targets updated to _base module
- `mlflow_oidc_auth/tests/repository/test_experiment_permission_group.py` - Patch targets updated to _base module
- `mlflow_oidc_auth/tests/repository/test_experiment_permission_regex.py` - Patch targets and method names updated
- `mlflow_oidc_auth/tests/repository/test_experiment_permission_regex_group.py` - Patch targets and method names updated
- `mlflow_oidc_auth/tests/repository/test_gateway_endpoint_permissions.py` - Patch targets updated to _base module
- `mlflow_oidc_auth/tests/repository/test_gateway_endpoint_group_permissions.py` - Patch targets updated to _base module
- `mlflow_oidc_auth/tests/repository/test_gateway_endpoint_regex_permissions.py` - Hybrid _base/_mod patching for overridden methods
- `mlflow_oidc_auth/tests/repository/test_gateway_endpoint_group_regex_permissions.py` - Patch targets updated to _base module
- `mlflow_oidc_auth/tests/repository/test_registered_model_permission.py` - Patch targets updated to _base module
- `mlflow_oidc_auth/tests/repository/test_registered_model_permission_group.py` - Patch targets updated to _base module

## Decisions Made
- **Class attribute configuration over constructor params:** Subclasses set `model_class`, `entity_class`, `resource_id_attr` as class-level attributes rather than passing them to `__init__()`. This gives the cleanest subclass definitions (3 lines of configuration).
- **Scorer keeps full method overrides:** Rather than adding a complex composite-key abstraction to the base class (which only 1 of 28 repos needs), scorer overrides all key CRUD methods directly. Simpler and more explicit.
- **Gateway rename()/wipe() stays in subclasses:** Only 3 of 28 repos need these methods. Adding them to the base would pollute the interface for the 25 repos that don't need them.
- **Test patch convention documented:** Inherited methods patch at `mlflow_oidc_auth.repository._base.*`, overridden methods patch at `mlflow_oidc_auth.repository.<subclass_module>.*`. This hybrid approach is necessary because Python's name resolution for `patch()` looks up the name in the module where it was imported.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test patch targets for base class method resolution**
- **Found during:** Task 2 (refactoring subclasses)
- **Issue:** Tests used `patch("mlflow_oidc_auth.repository.experiment_permission.get_user")` but after refactoring, `get_user` is only imported in `_base.py`, not in subclass modules
- **Fix:** Changed all test patch paths to reference `mlflow_oidc_auth.repository._base.*` for inherited utilities (`get_user`, `get_group`, `_validate_permission`, `validate_regex`)
- **Files modified:** All 10 test files listed above
- **Verification:** All 287 repository tests pass
- **Committed in:** `e955f38` (part of Task 2 commit)

**2. [Rule 1 - Bug] Updated test references to renamed internal methods**
- **Found during:** Task 2 (refactoring subclasses)
- **Issue:** Tests called `repo._get_experiment_permission()` but base class renames this to `repo._get_permission()`. Similarly `_get_experiment_group_permission` → `_get_group_permission`, `_get_endpoint_regex_permission` → `_get_regex_permission`, etc.
- **Fix:** Updated all test method references to use generic base class names
- **Files modified:** All 10 test files
- **Verification:** All 287 repository tests pass
- **Committed in:** `e955f38` (part of Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs — expected consequences of refactoring internal names)
**Impact on plan:** Both fixes are inherent to the refactoring approach. The plan noted tests must pass but didn't specify the exact patch target changes needed. No scope creep.

## Issues Encountered
- **Test patching complexity:** The biggest challenge was understanding Python's mock `patch()` name resolution — it patches the name in the module where it's looked up, not where it's defined. This required a systematic hybrid patching approach: `_base` module for inherited methods, subclass module for overridden methods.
- **Gateway regex repos have mixed delegation:** Gateway regex repos override `get`/`update`/`revoke` (importing `get_user`, `_validate_permission`, `validate_regex` locally) but delegate `grant`/`list_regex_for_user` to the base class. This required `_MOD` vs `_BASE` patch path constants in tests.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all code is fully functional, no placeholder or TODO patterns.

## Next Phase Readiness
- All 28 repository classes now use the generic base pattern — adding a new workspace permission repository (Phase 2) requires only ~10 lines: set `model_class`, `entity_class`, `resource_id_attr`
- The 4-tier base class hierarchy (User/Group/Regex/GroupRegex) matches the existing permission model exactly — workspace permissions will follow the same pattern
- Plan 01-03 (workspace foundation plumbing) can proceed without any dependency on this plan's internal details

## Self-Check: PASSED

- All key files exist on disk (_base.py, SUMMARY.md)
- Both task commits found in git log (ca07337, e955f38)
- All 4 base classes importable (BaseUserPermissionRepository, BaseGroupPermissionRepository, BaseRegexPermissionRepository, BaseGroupRegexPermissionRepository)
- All 287 repository tests pass (2.97s)

---
*Phase: 01-refactoring-workspace-foundation*
*Completed: 2026-03-23*
