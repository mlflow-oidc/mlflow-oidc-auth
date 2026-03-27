---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Workspace Management
status: Bug fixing and workspace audit
stopped_at: Trash/webhook workspace investigation complete
last_updated: "2026-03-27"
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 8
  completed_plans: 8
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Multi-tenant resource isolation — organizations share an MLflow instance while each tenant sees only their own resources
**Current focus:** Post-implementation bug fixing and workspace scoping audit

## Current Position

Phase: Post-implementation (bug fixing / audit)
Plan: Ad-hoc — verifying workspace scoping of trash and webhooks

## Performance Metrics

**Velocity:**

- Total plans completed: 1 (v1.1)
- Average duration: ~5min
- Total execution time: ~5min

*Updated after each plan completion*

## Accumulated Context

### Decisions

All v1.0 decisions logged in PROJECT.md Key Decisions table (15 entries).
v1.1 roadmap decisions:

- Regex permissions before CRUD: complete permission resolution chain needed for MANAGE delegation
- WSOIDC-04 grouped with CRUD backend: workspace auto-create is creation-path logic
- Coarse granularity: 4 phases (backend-first, frontend last)
- [Phase 05]: Workspace regex entities extend RegexPermissionBase (unlike standalone workspace entities) for consistency with all other regex types
- [Phase 05]: Used alias WorkspaceGroupRegexPermRepo in repository/__init__.py; direct module imports in sqlalchemy_store.py use the full name
- [Phase 05]: Router is admin-only — regex permissions are infrastructure-level, not end-user self-service
- [Phase 05]: Full cache flush on regex CUD (D-09) because regex changes affect any user+workspace combination
- [Phase 05]: Source-order-driven permission resolution via PERMISSION_SOURCE_ORDER config (user, group, regex, group-regex)
- [Phase 06-workspace-crud-backend]: Reused _extract_workspace_name_from_path from validators.workspace via lazy import in before_request instead of duplicating
- [Phase 06-workspace-crud-backend]: Used status_code < 300 as success guard in after-request handlers for robustness
- [Phase 06]: Path params named {workspace} to match dependency parameter names in check_workspace_*_permission
- [Phase 06]: Feature-flag gated router: exported in __all__ but NOT in get_all_routers(), registered conditionally in app.py
- [Phase 07]: Proto experiments/models lack workspace field — re-fetch from tracking_store/model_registry_store; build ws_map dict for batch lookup
- [Phase 08]: Workspace CRUD modals follow webhook modal pattern (Modal + useToast + local isSubmitting); DNS-safe validation (2-63 chars, lowercase alphanum + hyphens, "default" reserved)
- [Phase 08]: Module-level getter/setter (getActiveWorkspace/setActiveWorkspace) bridges React context to plain http.ts module without prop-drilling
- [Phase 08]: BulkAssignModal uses sequential grant calls for individual result tracking; admin-only via useUser().is_admin
- [Bug fix]: Trash router needs no changes — MLflow's WorkspaceAwareSqlAlchemyStore handles workspace scoping transparently
- [Bug fix]: useWebhooks refactored to use useApi for workspace reactivity — manual useCallback/useEffect pattern was missing workspace deps

### Pending Todos

None — all trash/webhook workspace audit items resolved.

### Blockers/Concerns

- Upstream workspace API stability: MLflow workspace endpoints are `PUBLIC_UNDOCUMENTED` (API v3.0)
- `cachetools` is transitive dependency only — needs pinning as direct dependency (Phase 5)
- ENTITY-02 (GatewayBudgetPolicy) deferred — protos not present in MLflow 3.10.1
- Phase 7 research flag: verify experiment→workspace mapping in `SearchExperiments.Response` proto
- Phase 6 research flag: resolve CRUD proxy implementation approach (httpx vs WSGI bridge vs tracking store)

## Bug Fix History (Post-Implementation)

| # | Commit | Description | Root Cause |
|---|--------|-------------|------------|
| 1 | `2c4cf0f` | Permission audit bug fixes + ARCHITECTURE.md workspace enforcement docs | Multiple enforcement gaps |
| 2 | `c669f60` | Documentation audit — update all docs for workspace support | Stale docs |
| 3 | `02a8c2a` | Batch permission resolver workspace fallback (Bug 2) | Missing workspace fallback in batch resolver |
| 4 | `1772386` | Synchronous workspace state update (Bug 1) | React effect execution order race condition |
| 5 | `02263be` | Workspace permissions as resource-level fallback docs | Missing documentation |
| 6 | `67326d8` | Workspace-aware model registry store for webhooks | Wrong store class for workspace-enabled DBs |
| 7 | (uncommitted) | useWebhooks workspace reactivity fix | Hook not using useApi, missing workspace deps |

## Session Continuity

Last session: 2026-03-27
Stopped at: Trash/webhook workspace investigation complete, useWebhooks fix applied (uncommitted)
Resume file: None
