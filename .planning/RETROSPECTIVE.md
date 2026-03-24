# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Workspace Support

**Shipped:** 2026-03-23
**Phases:** 4 | **Plans:** 10 | **Tasks:** 19

### What Was Built
- Registry-driven permission resolution (`resolve_permission()` + `PERMISSION_REGISTRY`) replacing 8 copy-paste functions with a single entry point for 7 resource types
- 4 generic repository base classes eliminating ~1,360 lines of duplicated CRUD across 28 permission repository subclasses
- Feature-flag-gated workspace plumbing: `AuthContext` frozen dataclass, middleware chain propagation, Alembic tables, default workspace seeding
- Workspace security boundary in the permission resolution chain: resource-level → workspace-level → NO_PERMISSIONS (hard deny)
- TTLCache-backed workspace permission lookups with configurable size/TTL and implicit default workspace MANAGE access
- 8-endpoint FastAPI CRUD router for workspace user+group permission management
- OIDC workspace claim mapping: plugin-first detection, JWT claim fallback, auto-assign with configurable default permission
- PromptOptimizationJob auth coverage (5 before_request handlers)
- React workspace management UI: list page with search, detail page with member CRUD, sidebar navigation

### What Worked
- **Research-first approach**: Deep-diving MLflow 3.10 source code before planning phases prevented wasted implementation effort. Key discovery that MLflow uses "Workspaces" (not "Organizations") shaped the entire implementation.
- **Prerequisite refactoring**: Phase 1 refactoring (PERMISSION_REGISTRY, base repositories) directly enabled Phase 2's workspace fallback insertion with minimal code changes. The investment paid off immediately.
- **Feature flag gating**: `MLFLOW_ENABLE_WORKSPACES=false` default meant every phase could be merged without affecting existing deployments. Zero risk of breaking production.
- **Plan-level granularity**: 10 plans across 4 phases kept each execution unit focused and verifiable. Phase 2's gap closure plan (02-03) caught a real bug.
- **Existing pattern replication**: Following established patterns (OIDC group detection plugin → workspace detection plugin, experiment_permissions router → workspace_permissions router) reduced design decisions and maintained consistency.

### What Was Inefficient
- **SUMMARY.md format inconsistency**: The `one_liner` field in phase 3 and 4 SUMMARY.md files wasn't parseable by the automated extraction tool. Required manual reading to get accomplishment descriptions.
- **Requirements tracking lag**: Phase 3 requirements were never checked off by the executor — required a fix commit after the fact. The phase transition workflow should enforce requirement checkbox updates.
- **Performance metrics gaps**: STATE.md performance metrics for phases 3-4 lack duration data. Session timing wasn't tracked consistently.
- **ENTITY-02 gap discovered late**: GatewayBudgetPolicy protobuf absence in MLflow 3.10.1 was only discovered during Phase 3 execution, not during research. Research phase should probe proto availability more aggressively.

### Patterns Established
- **AuthContext frozen dataclass**: Replaced multiple individual `request.environ` keys with a single typed object for auth state propagation across the FastAPI→ASGI→WSGI→Flask bridge
- **Standalone repos for tenant boundaries**: Workspace repos don't extend the generic base classes — they have fundamentally different access patterns (tenant boundary vs resource-level)
- **Implicit default access via cache**: Default workspace MANAGE is granted at the cache level (code-level implicit) rather than via seeded database rows
- **Conditional before_request wrapping**: Workspace creation gating wraps specific handlers only when workspaces enabled, using lazy-built path sets with handler identity checks
- **Text input for member management**: Workspace member add/edit uses free-form text input (not dropdown) to avoid loading all users/groups — backend validates

### Key Lessons
1. **Refactoring before feature work compounds**: The ~2 plans spent on permission resolution and repository refactoring saved significantly more time in phases 2-4 than they cost. Always invest in foundation cleanup when adding a new dimension to existing code.
2. **Feature flags make incremental delivery safe**: Every phase was mergeable independently because workspace behavior was gated. This pattern should be standard for any multi-phase feature.
3. **Pattern replication > novel design**: Following existing codebase patterns (plugin hooks, router structure, test patterns) resulted in consistent code that existing maintainers can immediately understand.
4. **Automated tooling needs format enforcement**: SUMMARY.md extraction failed on 4/10 files due to format variations. Templates should be stricter, or extraction should be more robust.
5. **Proto availability should be a research gate**: If a feature depends on upstream protobuf definitions existing, verify their presence in the target version during research — not during execution.

### Cost Observations
- Sessions: Multiple sessions across milestone (exact count not tracked)
- Notable: Phase 1 refactoring plans were fastest (8-25 min), Phase 2 enforcement was most complex (45 min for plan 02-01). Phase 3-4 timing not recorded.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 4 | 10 | Established GSD workflow, research-first approach, feature flag pattern |

### Cumulative Quality

| Milestone | Files Modified | Net LOC | Known Gaps |
|-----------|---------------|---------|------------|
| v1.0 | 157 | +16,817 | ENTITY-02 (deferred) |

### Top Lessons (Verified Across Milestones)

1. Prerequisite refactoring pays forward — invest in foundation before adding feature dimensions
2. Feature flags enable safe incremental delivery for multi-phase features
