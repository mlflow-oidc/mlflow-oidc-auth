# Roadmap: MLflow OIDC Auth — Workspace Support

## Milestones

- ✅ **v1.0 Workspace Support** — Phases 1-4 (shipped 2026-03-23)
- 🚧 **v1.1 Workspace Management** — Phases 5-8 (in progress)

## Phases

<details>
<summary>✅ v1.0 Workspace Support (Phases 1-4) — SHIPPED 2026-03-23</summary>

- [x] Phase 1: Refactoring & Workspace Foundation (3/3 plans) — completed 2026-03-23
- [x] Phase 2: Workspace Auth Enforcement (3/3 plans) — completed 2026-03-23
- [x] Phase 3: Management API, OIDC & Entity Coverage (2/2 plans) — completed 2026-03-23
- [x] Phase 4: Workspace Management UI (2/2 plans) — completed 2026-03-23

</details>

### 🚧 v1.1 Workspace Management (In Progress)

**Milestone Goal:** Add full workspace lifecycle management — CRUD proxy, regex permissions, workspace-scoped search filtering, admin UI with global picker.

- [ ] **Phase 5: Regex Workspace Permissions** - Pattern-based workspace access rules with cache integration
- [ ] **Phase 6: Workspace CRUD Backend** - FastAPI proxy to MLflow workspace API with permission cascade and OIDC auto-create
- [ ] **Phase 7: Workspace-Scoped Search Filtering** - Security-critical after_request hooks preventing cross-tenant data leakage
- [ ] **Phase 8: Workspace Management UI & Global Picker** - Admin CRUD forms, member counts, bulk ops, header dropdown with search and keyboard shortcut

## Phase Details

### Phase 5: Regex Workspace Permissions
**Goal**: Admins can define pattern-based workspace access rules that automatically grant permissions to matching workspaces
**Depends on**: Phase 4 (v1.0 workspace foundation)
**Requirements**: WSREG-01, WSREG-02, WSREG-03, WSREG-04, WSREG-05, WSREG-06, WSREG-07
**Success Criteria** (what must be TRUE):
  1. Admin can create a user regex permission (e.g., `team-.*` → READ) and users matching the pattern gain workspace access without explicit per-workspace grants
  2. Admin can create a group regex permission and group members matching the pattern gain workspace access
  3. Workspace permission cache returns correct permission level when regex and group-regex sources are part of the configured resolution order
  4. Modifying any regex permission immediately invalidates the full workspace cache (no stale access)
**Plans:** 2 plans
Plans:
- [x] 05-01-PLAN.md — Data layer: DB models, entities, repositories, Alembic migration, store wiring
- [ ] 05-02-PLAN.md — Router + cache: CRUD endpoints, workspace cache regex integration, feature-flag gating, cachetools pin

### Phase 6: Workspace CRUD Backend
**Goal**: Users can create, list, view, update, and delete workspaces through the plugin's API with proper authorization and automatic permission management
**Depends on**: Phase 5 (complete permission resolution chain including regex)
**Requirements**: WSCRUD-01, WSCRUD-02, WSCRUD-03, WSCRUD-04, WSCRUD-05, WSCRUD-06, WSCRUD-07, WSCRUD-08, WSOIDC-04
**Success Criteria** (what must be TRUE):
  1. Admin can create a workspace and automatically receives MANAGE permission on it
  2. Non-admin user listing workspaces sees only workspaces they have permission to access (including regex-granted access)
  3. User with MANAGE permission can update a workspace's description and delete it (if empty), while unprivileged users get 403
  4. Deleting a workspace cascade-deletes all associated user and group permission rows
  5. Workspace CRUD endpoints do not exist when `MLFLOW_ENABLE_WORKSPACES=false`
**Plans**: TBD

### Phase 7: Workspace-Scoped Search Filtering
**Goal**: Search results only contain resources from workspaces the user has permission to access, preventing cross-tenant data leakage
**Depends on**: Phase 5 (workspace cache with regex for permission checks)
**Requirements**: WSSEC-01, WSSEC-02, WSSEC-03, WSSEC-04, WSSEC-05, WSSEC-06
**Success Criteria** (what must be TRUE):
  1. User searching experiments sees only experiments belonging to workspaces they have access to (not experiments from other tenants)
  2. User searching registered models and logged models sees only results from accessible workspaces
  3. Resources in the default workspace remain visible when `GRANT_DEFAULT_WORKSPACE_ACCESS` is true, and pre-workspace-era resources (no workspace) remain visible to authorized users
  4. Admin users bypass all workspace-scoped filtering and see all resources
**Plans**: TBD

### Phase 8: Workspace Management UI & Global Picker
**Goal**: Admins can manage workspace lifecycle through the UI, and all users can scope their view to a specific workspace via a header dropdown
**Depends on**: Phase 6 (CRUD backend), Phase 7 (search filtering)
**Requirements**: WSUI-01, WSUI-02, WSUI-03, WSUI-04, WSUI-05, WSPICK-01, WSPICK-02, WSPICK-03, WSPICK-04, WSPICK-05, WSPICK-06
**Success Criteria** (what must be TRUE):
  1. Admin can create, edit, and delete workspaces via modal forms with real-time name validation and confirmation dialogs
  2. Workspace list page shows member count (users + groups) per workspace, and admin can bulk-assign permissions
  3. Header dropdown shows accessible workspaces, selecting one sends `X-MLFLOW-WORKSPACE` header on all subsequent API requests
  4. Workspace selection persists across page refreshes, "All Workspaces" option removes scoping
  5. Picker includes search/filter for many-workspace deployments and keyboard shortcut for quick switching
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7 → 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Refactoring & Workspace Foundation | v1.0 | 3/3 | Complete | 2026-03-23 |
| 2. Workspace Auth Enforcement | v1.0 | 3/3 | Complete | 2026-03-23 |
| 3. Management API, OIDC & Entity Coverage | v1.0 | 2/2 | Complete | 2026-03-23 |
| 4. Workspace Management UI | v1.0 | 2/2 | Complete | 2026-03-23 |
| 5. Regex Workspace Permissions | v1.1 | 0/0 | Not started | - |
| 6. Workspace CRUD Backend | v1.1 | 0/0 | Not started | - |
| 7. Workspace-Scoped Search Filtering | v1.1 | 0/0 | Not started | - |
| 8. Workspace Management UI & Global Picker | v1.1 | 0/0 | Not started | - |
