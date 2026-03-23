---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to plan
stopped_at: Phase 3 context gathered
last_updated: "2026-03-23T21:12:05.094Z"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Multi-tenant resource isolation — organizations share an MLflow instance while each tenant sees only their own resources
**Current focus:** Phase 02 — workspace-auth-enforcement

## Current Position

Phase: 3
Plan: Not started

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 8min | 2 tasks | 4 files |
| Phase 01 P02 | 25min | 2 tasks | 37 files |
| Phase 01 P03 | 15min | 2 tasks | 18 files |
| Phase 02 P01 | 45min | 2 tasks | 13 files |
| Phase 02 P02 | 11min | 2 tasks | 8 files |
| Phase 02 P03 | 3min | 1 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Research-first approach validated; all findings based on MLflow 3.10 source code analysis
- Prerequisite refactoring mandatory — 8 copy-paste permission functions must be consolidated before adding workspace dimension
- Coarse granularity: 4 phases consolidating research's 6-phase structure
- [Phase 01]: Registry-driven permission resolution: all 7 resource types use PERMISSION_REGISTRY dict and resolve_permission() single entry point
- [Phase 01]: Scorer 2-part key handled via **kwargs to resolve_permission(); prompt sources intentionally share registered_model store methods
- [Phase 01]: Generic base repository pattern: subclasses set model_class + entity_class + resource_id_attr class attributes, inherit full CRUD (4 base classes for 28 repos)
- [Phase 01]: Scorer 2-part key handled via method overrides in subclass rather than base class complexity; gateway rename()/wipe() kept as subclass-only methods
- [Phase 01]: AuthContext is a frozen dataclass (not TypedDict) for immutability and attribute access
- [Phase 01]: Single environ key (environ['mlflow_oidc_auth'] = AuthContext) replaces individual keys for cleaner bridge
- [Phase 01]: Default workspace seeded at app startup (not in migration) — schema vs data separation
- [Phase 02]: Workspace hooks via regex pattern matching (logged model pattern) — WORKSPACE_BEFORE_REQUEST_VALIDATORS
- [Phase 02]: Standalone workspace permission repos (not extending base classes) — workspace is a tenant boundary, not a resource
- [Phase 02]: Wrap resolve_permission() for workspace fallback — get_permission_from_store_or_default() unchanged
- [Phase 02]: Code-level implicit default workspace access — no seeded rows, GRANT_DEFAULT_WORKSPACE_ACCESS controls runtime
- [Phase 02]: Module-level TTLCache in utils/workspace_cache.py — key (username, workspace), TTL-based invalidation only
- [Phase 02]: Conditional workspace MANAGE wrapper in before_request_hook() for CreateExperiment/CreateRegisteredModel
- [Phase 02]: Standalone workspace repos use get_user() from repository.utils for username resolution (not user_repo._get_user)
- [Phase 02]: workspace_cache not exported from utils/__init__.py — callers import directly to avoid circular import issues
- [Phase 02]: Creation gating uses lazy-built path set from get_endpoints() with if-handler-not-None filter
- [Phase 02]: Workspace validators return True/False (matching existing convention), not Flask Response objects
- [Phase 02]: Lazy imports patched at source module in tests — not at consuming module
- [Phase 02]: Handler identity check (handler in (...)) for get_endpoints() filter — truthiness check passes non-protobuf Flask handlers

### Pending Todos

None.

### Blockers/Concerns

- Upstream workspace API stability: MLflow workspace endpoints are `PUBLIC_UNDOCUMENTED` (API v3.0) — could change in minor releases
- cachetools is transitive dependency only (via MLflow) — not pinned in pyproject.toml

## Session Continuity

Last session: 2026-03-23T21:12:05.089Z
Stopped at: Phase 3 context gathered
Resume file: .planning/phases/03-management-api-oidc-entity-coverage/03-CONTEXT.md
