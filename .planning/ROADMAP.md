# Roadmap: MLflow OIDC Auth — Workspace Support

## Overview

This roadmap delivers multi-tenant workspace support to the MLflow OIDC Auth plugin in 4 phases. We start by refactoring the existing permission resolution debt and laying the workspace data foundation (feature flag, DB migration, context propagation). Then we build the security core — workspace permission model and auth enforcement that prevents cross-tenant leakage. Next we expose management APIs (user + group workspace permissions, OIDC claim mapping, and new entity coverage). Finally we deliver the React management UI. Each phase produces a coherent, verifiable capability that unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Refactoring & Workspace Foundation** - Eliminate permission resolution debt and establish workspace data layer (feature flag, DB migration, context propagation) (completed 2026-03-23)
- [x] **Phase 2: Workspace Auth Enforcement** - Workspace permission model and security boundary in the permission resolution chain (completed 2026-03-23)
- [ ] **Phase 3: Management API, OIDC & Entity Coverage** - Workspace permission CRUD endpoints, OIDC claim mapping, and new entity auth handlers
- [ ] **Phase 4: Workspace Management UI** - React workspace management feature module with list, detail, member management, and workspace switcher

## Phase Details

### Phase 1: Refactoring & Workspace Foundation
**Goal**: The codebase has a generic permission resolution abstraction and all workspace plumbing exists (feature flag, DB table, context propagation, default workspace) — ready for auth enforcement
**Depends on**: Nothing (first phase)
**Requirements**: REFAC-01, REFAC-02, WSFND-01, WSFND-02, WSFND-03, WSFND-04, WSFND-05, WSFND-06
**Success Criteria** (what must be TRUE):
  1. Permission resolution for all 7 existing resource types uses a single generic `resolve_permission()` function instead of 8 copy-paste functions — all existing tests pass
  2. `MLFLOW_ENABLE_WORKSPACES=false` (default) produces zero behavioral changes — existing deployments unaffected
  3. `workspace_permissions` table exists after Alembic migration with `(workspace, user_id, permission)` composite primary key
  4. Existing permissions are assigned to a "default" workspace during migration — no data loss or permission breakage
  5. `get_request_workspace()` bridge function returns the workspace from `X-MLFLOW-WORKSPACE` header when workspaces are enabled
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Permission resolution refactoring (registry + resolve_permission)
- [x] 01-02-PLAN.md — Repository base class refactoring (4 generic base classes for 28 repos)
- [x] 01-03-PLAN.md — Workspace foundation plumbing (feature flag, AuthContext, middleware, migration, seeding)

### Phase 2: Workspace Auth Enforcement
**Goal**: Workspace boundaries are enforced in the permission resolution chain — users can only access resources in workspaces they have permission for, with no cross-tenant data leakage
**Depends on**: Phase 1
**Requirements**: WSAUTH-01, WSAUTH-02, WSAUTH-03, WSAUTH-04, WSAUTH-05
**Success Criteria** (what must be TRUE):
  1. before_request handlers intercept all 5 workspace protobuf RPCs — CreateWorkspace/UpdateWorkspace/DeleteWorkspace require admin, GetWorkspace checks workspace permission, ListWorkspaces returns filtered results
  2. Users with workspace-level READ/USE/EDIT/MANAGE permissions can access resources in that workspace; users without workspace permission get NO_PERMISSIONS (hard deny, not fallback to default_permission)
  3. CreateExperiment and CreateRegisteredModel require MANAGE permission on the target workspace (not just after_request auto-grant)
  4. Permission resolution chain with workspaces enabled follows: resource-level (user→group→regex→group-regex) → workspace-level → NO_PERMISSIONS
  5. Workspace permission lookups are cached via TTLCache — configurable `workspace_cache_max_size` and `workspace_cache_ttl_seconds`
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Workspace permission data layer (entities, standalone repos, ORM model updates, store methods, TTLCache)
- [x] 02-02-PLAN.md — Workspace auth enforcement (resolve_permission fallback, validators, hook registration, creation gating, ListWorkspaces filtering)

### Phase 3: Management API, OIDC & Entity Coverage
**Goal**: Workspace permissions are manageable via API (user + group), OIDC login auto-assigns workspace membership, and new MLflow 3.10 entities are covered by auth handlers
**Depends on**: Phase 2
**Requirements**: WSMGMT-01, WSMGMT-02, WSMGMT-03, WSOIDC-01, WSOIDC-02, WSOIDC-03, ENTITY-01, ENTITY-02
**Success Criteria** (what must be TRUE):
  1. Admin or workspace MANAGE user can list/create/update/delete workspace-user and workspace-group permissions via FastAPI CRUD endpoints
  2. Users with MANAGE on a workspace can grant/revoke permissions for other users within that workspace without requiring global admin
  3. OIDC login with a workspace claim in the JWT token auto-creates workspace membership with configurable default permission level
  4. Custom workspace resolution logic can be plugged in via `OIDC_WORKSPACE_DETECTION_PLUGIN` (following existing group detection plugin pattern)
  5. Prompt Optimization Job and Gateway Budget Policy protobuf RPCs are intercepted by before_request handlers with appropriate permission checks
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Workspace Management UI
**Goal**: Users can manage workspace membership and permissions through the React admin UI with workspace-scoped views
**Depends on**: Phase 3
**Requirements**: WSMGMT-04, WSMGMT-05, WSMGMT-06
**Success Criteria** (what must be TRUE):
  1. Workspace list view shows all workspaces the current user has access to, with workspace detail view showing members (users + groups) and their permission levels
  2. Workspace switcher component in the admin UI navigation allows switching between workspace-scoped permission views
  3. Admin users can manually assign/remove users to/from workspaces via the UI — serves as fallback when OIDC provider doesn't send workspace claims
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 04-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Refactoring & Workspace Foundation | 3/3 | Complete   | 2026-03-23 |
| 2. Workspace Auth Enforcement | 2/2 | Complete   | 2026-03-23 |
| 3. Management API, OIDC & Entity Coverage | 0/3 | Not started | - |
| 4. Workspace Management UI | 0/1 | Not started | - |
