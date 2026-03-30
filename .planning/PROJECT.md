# MLflow OIDC Auth — Organization Support

## What This Is

An MLflow authentication and authorization plugin (mlflow-oidc-auth) that adds OIDC-based login, RBAC with users/groups, per-resource permission management, and multi-tenant workspace isolation to MLflow tracking servers. Workspace support enables resource isolation across teams or external organizations sharing a single MLflow instance, with feature-flag-gated opt-in behavior and zero impact on existing deployments.

## Core Value

Multi-tenant resource isolation — organizations must be able to share an MLflow instance while each tenant sees only their own experiments, models, and resources, with no accidental data leakage between tenants.

## Requirements

### Validated

- ✓ OIDC authentication (login, logout, callback, session management) — pre-existing
- ✓ Multi-method auth (OIDC, Basic Auth, Bearer Token/JWT, session cookies) — pre-existing
- ✓ User management (create, update, list, admin roles) — pre-existing
- ✓ Group management (create, assign users, group-level permissions) — pre-existing
- ✓ Experiment permissions (user, group, regex, group-regex variants) — pre-existing
- ✓ Registered model permissions (user, group, regex, group-regex variants) — pre-existing
- ✓ Prompt permissions (user, group, regex, group-regex variants) — pre-existing
- ✓ Scorer permissions (user, group, regex, group-regex variants) — pre-existing
- ✓ Gateway endpoint permissions (user, group, regex, group-regex variants) — pre-existing
- ✓ Gateway secret permissions (user, group, regex, group-regex variants) — pre-existing
- ✓ Gateway model definition permissions (user, group, regex, group-regex variants) — pre-existing
- ✓ Configurable permission resolution order (user → group → regex → group-regex) — pre-existing
- ✓ Permission levels (READ, USE, EDIT, MANAGE, NO_PERMISSIONS) — pre-existing
- ✓ Admin bypass for all permission checks — pre-existing
- ✓ Auto-grant MANAGE on resource creation — pre-existing
- ✓ Search result filtering based on user permissions — pre-existing
- ✓ Cascade permission deletes on resource deletion — pre-existing
- ✓ GraphQL authorization middleware — pre-existing
- ✓ Pluggable config providers (AWS, Azure, Vault, K8s, env) — pre-existing
- ✓ React SPA admin UI for managing permissions, users, groups — pre-existing
- ✓ Alembic database migrations — pre-existing
- ✓ MLflow plugin integration (mlflow server --app-name oidc-auth) — pre-existing
- ✓ REFAC-01: Permission resolution consolidated into registry-driven `resolve_permission()` — v1.0
- ✓ REFAC-02: Generic repository base classes (4 bases for 28 repos) — v1.0
- ✓ WSFND-01: Feature flag (`MLFLOW_ENABLE_WORKSPACES`) gates all workspace behavior — v1.0
- ✓ WSFND-02: `X-MLFLOW-WORKSPACE` header propagated through middleware chain — v1.0
- ✓ WSFND-03: Alembic migration adds workspace_permissions tables — v1.0
- ✓ WSFND-04: Default workspace seeded at startup — v1.0
- ✓ WSFND-05: `GRANT_DEFAULT_WORKSPACE_ACCESS` config option — v1.0
- ✓ WSFND-06: AuthContext frozen dataclass replaces individual environ keys — v1.0
- ✓ WSAUTH-01: before_request handlers for 5 workspace protobuf RPCs — v1.0
- ✓ WSAUTH-02: Workspace permission data layer (entities, repos, ORM, store, TTLCache) — v1.0
- ✓ WSAUTH-03: CreateExperiment/CreateRegisteredModel gated on workspace MANAGE — v1.0
- ✓ WSAUTH-04: Permission resolution workspace fallback (resource → workspace → NO_PERMISSIONS) — v1.0
- ✓ WSAUTH-05: TTLCache for workspace permission lookups — v1.0
- ✓ WSMGMT-01: Workspace-user permission CRUD router — v1.0
- ✓ WSMGMT-02: Workspace-group permission CRUD router — v1.0
- ✓ WSMGMT-03: Workspace permission delegation (MANAGE grants sub-admin) — v1.0
- ✓ WSMGMT-04: React workspace management feature module — v1.0
- ✓ WSMGMT-05: Workspace navigation in admin UI sidebar — v1.0
- ✓ WSMGMT-06: Admin-managed workspace-to-user assignment UI — v1.0
- ✓ WSOIDC-01: Configurable OIDC workspace claim extraction — v1.0
- ✓ WSOIDC-02: Workspace detection plugin hook — v1.0
- ✓ WSOIDC-03: Auto-create workspace membership on OIDC login — v1.0
- ✓ ENTITY-01: PromptOptimizationJob before_request handlers — v1.0
- ✓ WSREG-01–07: Regex workspace permissions (user-regex and group-regex, cache integration, feature-flag gated) — v1.1 Phase 5

### Active

- [ ] Workspace CRUD backend — FastAPI proxy to MLflow's workspace REST API (create, list, get, update, delete) with auth checks
- [ ] Workspace management UI — admin page for creating, viewing, updating, and deleting workspaces
- [ ] Global workspace picker — dropdown in UI header that scopes all admin pages to the selected workspace
- [ ] Workspace-scoped search result filtering in after_request
- ~~Regex workspace permissions~~ → Validated (see below)
- [ ] ENTITY-02: GatewayBudgetPolicy before_request handlers — deferred from v1.0, protos not in MLflow 3.10.1

## Current Milestone: v1.1 Workspace Management

**Goal:** Add full workspace lifecycle management (CRUD) to the plugin — backend proxy to MLflow's workspace API, admin UI with global workspace picker, and workspace-scoped search filtering.

**Target features:**
- Workspace CRUD backend (proxy to MLflow `/api/3.0/mlflow/workspaces`)
- Workspace management UI (create, list, get, update, delete)
- Global workspace picker in UI header (scopes all admin pages)
- Workspace-scoped search result filtering in after_request hooks
- Regex workspace permissions (pattern-based workspace access)
- ENTITY-02: GatewayBudgetPolicy before_request handlers (if protos available)

### Out of Scope

- Per-workspace artifact store management — MLflow core responsibility, not auth plugin
- Workspace CRUD (create/update/delete workspace entity) — workspace lifecycle managed by MLflow core; plugin only controls access
- Per-workspace billing/metering — not an auth concern
- Per-workspace OIDC provider configuration — single provider per deployment
- Hard workspace boundary enforcement at DB level — enforced via hooks and result filtering
- Workspace entity model definition — plugin doesn't own workspace lifecycle
- Mobile app — web-first approach
- Multi-cluster/multi-instance federation — single instance scope only

## Context

**Current state (post-v1.0, v1.1 Phase 5 complete):** Workspace support includes all v1.0 features plus regex-based workspace access rules. Phase 5 added:
- 86 Python files modified, 34 TypeScript/TSX files added/modified
- Net +4,857 lines Python, +1,513 lines TypeScript
- 157 files changed across the milestone (44 commits)
- Full workspace permission chain: resource-level → workspace-level → NO_PERMISSIONS
- TTLCache-backed cached lookups for workspace permissions
- 8-endpoint CRUD API for workspace user+group permission management
- OIDC workspace claim mapping with plugin/JWT/auto-assign detection
- React admin UI with workspace list, detail, and member management pages
- User-regex and group-regex workspace permissions (8 CRUD endpoints, admin-only)
- Configurable permission source order (user → group → regex → group-regex) for workspace cache
- Priority-aware regex matching with tie-break by most permissive
- `cachetools>=5.5.0` pinned as direct dependency

**Tech stack:** Python 3.12 / FastAPI / Flask / SQLAlchemy 2 backend, React 19 / TypeScript / Vite frontend. MLflow >=3.10.0 required for workspace protobuf RPCs.

**Known gaps:**
- ENTITY-02 (GatewayBudgetPolicy) deferred — protos not present in MLflow 3.10.1
- Upstream workspace API is `PUBLIC_UNDOCUMENTED` (v3.0) — could change in minor releases
- ~~`cachetools` is transitive dependency only~~ — pinned as `cachetools>=5.5.0` in Phase 5

**Production deployments:** Existing deployments upgrade seamlessly — `MLFLOW_ENABLE_WORKSPACES` defaults to false, all workspace behavior is gated behind this flag. Enabling workspaces adds workspace-level permission resolution on top of existing resource-level permissions.

## Constraints

- **Compatibility**: Must target MLflow >=3.10.0 — org features require 3.10 baseline
- **Production impact**: Existing deployments unaffected when workspaces disabled (feature flag default)
- **Tech stack**: Python/FastAPI/Flask/SQLAlchemy backend, React/TypeScript frontend — no new frameworks
- **Plugin boundary**: Can only control auth/authz — cannot modify MLflow core behavior
- **Upstream stability**: Workspace protobuf RPCs are `PUBLIC_UNDOCUMENTED` — monitor for breaking changes
- **Workspace CRUD**: Plugin proxies to MLflow's `/api/3.0/mlflow/workspaces` API — cannot own workspace lifecycle directly
- **MANAGE delegation**: Users with MANAGE permission on a workspace can update/delete it (not admin-only)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Research-first approach before implementation | Too many unknowns about MLflow 3.10 org model | ✓ Good — MLflow uses "Workspaces", 5 protobuf RPCs identified |
| Breaking changes OK with major version | Production deployments exist but org support is transformative | ✓ Good — WSGI bridge uses AuthContext, clean migration path |
| Flexible tenancy model (internal + external) | Different deployments have different needs | ✓ Good — feature flag allows opt-in |
| REFAC-01: Registry-driven permission resolution | 8 copy-paste functions → single resolve_permission() | ✓ Good — enabled workspace fallback insertion |
| REFAC-02: Generic repository base classes | 28 repos with duplicated CRUD → 4 generic bases | ✓ Good — reduced maintenance surface |
| WSFND-06: AuthContext frozen dataclass | Single frozen dataclass for auth state propagation | ✓ Good — cleaner than multiple environ keys |
| WSAUTH-B: Standalone workspace repos | Workspace is tenant boundary, not resource — different access patterns | ✓ Good — simpler than extending generic bases |
| WSAUTH-C: Wrap resolve_permission() for workspace fallback | get_permission_from_store_or_default() unchanged | ✓ Good — minimal diff, backward compatible |
| WSAUTH-D: Implicit default workspace MANAGE via TTLCache | No seeded rows needed for default workspace access | ✓ Good — cleaner than migration-seeded data |
| WSAUTH-F: Conditional creation gating in before_request_hook() | CreateExperiment/CreateRegisteredModel require workspace MANAGE | ✓ Good — prevents unauthorized resource creation |
| Phase 3: Single router for all workspace CRUD | 8 endpoints in one router vs split user/group routers | ✓ Good — follows existing pattern consistency |
| Phase 3: OIDC workspace detection plugin-first | Mirrors OIDC_GROUP_DETECTION_PLUGIN pattern | ✓ Good — consistent with existing extension model |
| Phase 3: ENTITY-02 deferred | GatewayBudgetPolicy protos not in MLflow 3.10.1 | — Pending — revisit when MLflow adds protos |
| Phase 4: Text input for member names | Not dropdown — workspace members are free-form | ✓ Good — avoids loading all users/groups |
| Phase 4: CUD buttons always visible | Backend enforces authorization, UI shows toast on 403 | ✓ Good — consistent UX, proper separation of concerns |

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
*Last updated: 2026-03-24 after v1.1 Phase 8 (Workspace Management UI & Global Picker) complete — Milestone v1.1 Workspace Management COMPLETE*
