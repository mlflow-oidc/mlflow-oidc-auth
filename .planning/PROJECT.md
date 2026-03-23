# MLflow OIDC Auth — Organization Support

## What This Is

An MLflow authentication and authorization plugin (mlflow-oidc-auth) that adds OIDC-based login, RBAC with users/groups, and per-resource permission management to MLflow tracking servers. The project is adding multi-tenant organization support, aligning with MLflow 3.10's new organization features, to enable resource isolation across teams or external organizations sharing a single MLflow instance.

## Core Value

Multi-tenant resource isolation — organizations must be able to share an MLflow instance while each tenant sees only their own experiments, models, and resources, with no accidental data leakage between tenants.

## Requirements

### Validated

- ✓ OIDC authentication (login, logout, callback, session management) — existing
- ✓ Multi-method auth (OIDC, Basic Auth, Bearer Token/JWT, session cookies) — existing
- ✓ User management (create, update, list, admin roles) — existing
- ✓ Group management (create, assign users, group-level permissions) — existing
- ✓ Experiment permissions (user, group, regex, group-regex variants) — existing
- ✓ Registered model permissions (user, group, regex, group-regex variants) — existing
- ✓ Prompt permissions (user, group, regex, group-regex variants) — existing
- ✓ Scorer permissions (user, group, regex, group-regex variants) — existing
- ✓ Gateway endpoint permissions (user, group, regex, group-regex variants) — existing
- ✓ Gateway secret permissions (user, group, regex, group-regex variants) — existing
- ✓ Gateway model definition permissions (user, group, regex, group-regex variants) — existing
- ✓ Configurable permission resolution order (user → group → regex → group-regex) — existing
- ✓ Permission levels (READ, USE, EDIT, MANAGE, NO_PERMISSIONS) — existing
- ✓ Admin bypass for all permission checks — existing
- ✓ Auto-grant MANAGE on resource creation — existing
- ✓ Search result filtering based on user permissions — existing
- ✓ Cascade permission deletes on resource deletion — existing
- ✓ GraphQL authorization middleware — existing
- ✓ Pluggable config providers (AWS, Azure, Vault, K8s, env) — existing
- ✓ React SPA admin UI for managing permissions, users, groups — existing
- ✓ Alembic database migrations — existing
- ✓ MLflow plugin integration (mlflow server --app-name oidc-auth) — existing

### Active

- [ ] Implement workspace management API — CRUD endpoints, OIDC claim mapping, new entity auth handlers
- [ ] Implement workspace management UI — React workspace module with list, detail, member management, workspace switcher

### Validated in Phase 2: Workspace Auth Enforcement

- ✓ WSAUTH-01: before_request handlers intercept all 5 workspace protobuf RPCs with correct access levels (admin for CUD, perm check for Get, filtered for List)
- ✓ WSAUTH-02: Workspace permission data layer — entities, standalone repos, ORM models, store facade, TTLCache with configurable size/TTL
- ✓ WSAUTH-03: CreateExperiment and CreateRegisteredModel gated on workspace MANAGE permission
- ✓ WSAUTH-04: resolve_permission() workspace fallback — resource-level → workspace-level → NO_PERMISSIONS (hard deny)
- ✓ WSAUTH-05: Cached workspace permission lookups with implicit default workspace MANAGE access

### Validated in Phase 1: Refactoring & Workspace Foundation

- ✓ REFAC-01: Permission resolution refactored into generic `resolve_permission()` with `PERMISSION_REGISTRY` — 7 resource types, single entry point
- ✓ REFAC-02: Repository base classes — 4 generic bases (`BaseUserPermissionRepository`, `BaseGroupPermissionRepository`, `BaseRegexPermissionRepository`, `BaseGroupRegexPermissionRepository`) for 28 repos
- ✓ WSFND-01: `MLFLOW_ENABLE_WORKSPACES` feature flag gates all workspace behavior, disabled by default
- ✓ WSFND-02: `X-MLFLOW-WORKSPACE` header propagated through middleware chain (AuthMiddleware → ASGI scope → WSGI environ → Flask bridge)
- ✓ WSFND-03: Alembic migration adds `workspace_permissions` and `workspace_group_permissions` tables with composite PKs
- ⚠ WSFND-04: Default workspace seeding plumbing exists (function + call site), actual data insertion deferred to Phase 2
- ✓ WSFND-05: `GRANT_DEFAULT_WORKSPACE_ACCESS` config option, defaults to true
- ✓ WSFND-06: `AuthContext` frozen dataclass replaces individual environ keys; `get_auth_context()`, `get_request_workspace()` bridge functions

### Out of Scope

- Per-org billing or usage metering — not an auth concern
- Multi-cluster/multi-instance federation — single instance scope only
- Org-specific MLflow configuration (e.g., artifact store per org) — MLflow core concern, not auth plugin

## Context

**Upstream trigger:** MLflow 3.10 (https://github.com/mlflow/mlflow/releases/tag/v3.10.0) introduced Organization Support. The upstream MLflow auth module at https://github.com/mlflow/mlflow/tree/master/mlflow/server/auth needs investigation to understand what hooks, models, and APIs were added.

**Existing architecture:** FastAPI wraps MLflow's Flask app via AuthAwareWSGIMiddleware. RBAC is enforced in Flask before_request hooks that map MLflow protobuf request classes to validator functions. Permission management is via FastAPI routers. The plugin has 7 resource types, each with 4 permission variants (user, group, regex, group-regex). Permission resolution is now consolidated into a single `resolve_permission()` function via `PERMISSION_REGISTRY`. All 28 repository classes extend generic base classes. Workspace plumbing (feature flag, AuthContext, middleware, DB tables) is in place.

**Current state:** Phase 2 complete — workspace auth enforcement done. The permission resolution chain includes workspace-level fallback (resource → workspace → NO_PERMISSIONS). All 5 workspace protobuf RPCs are intercepted. CreateExperiment/CreateRegisteredModel are gated on workspace MANAGE. ListWorkspaces is filtered per user permissions. TTLCache provides cached workspace permission lookups. All behavior gated by MLFLOW_ENABLE_WORKSPACES feature flag. Ready for Phase 3: Management API, OIDC & Entity Coverage.

**Production deployments:** The plugin has existing production deployments with established users, groups, and permissions. Backward compatibility is important but breaking changes are acceptable with a major version bump.

**Research-first approach:** The exact scope of implementation depends on research findings. Key unknowns include what MLflow 3.10 actually exposes for orgs, what entities the current plugin doesn't intercept, and how orgs should integrate with the existing group/permission hierarchy.

**Multi-tenancy model:** Flexible — must support both internal teams and external organizations depending on deployment scenario.

## Constraints

- **Compatibility**: Must target MLflow >=3.10.0 — org features require 3.10 baseline
- **Production impact**: Existing deployments must have a clear migration path, even if major version bump
- **Tech stack**: Python/FastAPI/Flask/SQLAlchemy backend, React/TypeScript frontend — no new frameworks
- **Plugin boundary**: Can only control auth/authz — cannot modify MLflow core behavior
- **Research dependency**: Implementation scope gated on research findings about MLflow 3.10 internals

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Research-first approach before implementation | Too many unknowns about MLflow 3.10 org model | ✓ Completed — MLflow uses "Workspaces" |
| Breaking changes OK with major version | Production deployments exist but org support is transformative enough to justify it | ✓ Confirmed — WSGI bridge now uses AuthContext |
| Flexible tenancy model (internal + external) | Different deployments have different needs; don't lock into one model | ✓ Aligned — feature flag allows opt-in |
| Deep dive upstream MLflow code + docs | Release notes alone won't reveal integration points for the auth plugin | ✓ Completed — 5 protobuf RPCs, X-MLFLOW-WORKSPACE header, workspace_permissions table identified |
| REFAC-01: Registry-driven permission resolution | 8 copy-paste functions → single resolve_permission() | ✓ Implemented in Phase 1 |
| REFAC-02: Generic repository base classes | 28 repos with duplicated CRUD → 4 generic bases | ✓ Implemented in Phase 1 |
| WSFND-06: AuthContext replaces individual environ keys | Single frozen dataclass for auth state propagation | ✓ Implemented in Phase 1 |
| WSFND-04: Default workspace seeding deferred to Phase 2 | Store methods needed for actual data insertion | ✓ Resolved — workspace store methods + implicit default workspace MANAGE via TTLCache |

| WSAUTH-B: Standalone workspace repos (not extending base classes) | Workspace is a tenant boundary, not a resource — different access patterns | ✓ Implemented in Phase 2 |
| WSAUTH-C: Wrap resolve_permission() for workspace fallback | get_permission_from_store_or_default() unchanged, workspace check only on fallback | ✓ Implemented in Phase 2 |
| WSAUTH-D: Implicit default workspace MANAGE via TTLCache | GRANT_DEFAULT_WORKSPACE_ACCESS=True grants MANAGE on "default" workspace | ✓ Implemented in Phase 2 |
| WSAUTH-E: Module-level TTLCache with lazy init | Avoids import-time config reads, configurable size/TTL | ✓ Implemented in Phase 2 |
| WSAUTH-F: Conditional creation gating in before_request_hook() | CreateExperiment/CreateRegisteredModel require workspace MANAGE | ✓ Implemented in Phase 2 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-23 after Phase 2 completion*
