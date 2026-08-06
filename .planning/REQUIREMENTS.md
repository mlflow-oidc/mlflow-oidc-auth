# Requirements: MLflow OIDC Auth — Workspace Management

**Defined:** 2026-03-24
**Core Value:** Multi-tenant resource isolation — organizations must be able to share an MLflow instance while each tenant sees only their own experiments, models, and resources, with no accidental data leakage between tenants.

## v1.1 Requirements

Requirements for workspace management milestone. Each maps to roadmap phases.

### Workspace Backend

- [x] **WSCRUD-01**: Admin can create a workspace via FastAPI proxy endpoint with auto-granted MANAGE permission
- [x] **WSCRUD-02**: Authenticated user can list workspaces (filtered to accessible workspaces for non-admins)
- [x] **WSCRUD-03**: User with workspace permission can get workspace details by name
- [x] **WSCRUD-04**: User with MANAGE permission can update workspace description
- [x] **WSCRUD-05**: User with MANAGE permission can delete a workspace (RESTRICT mode — workspace must be empty)
- [x] **WSCRUD-06**: When a workspace is deleted, all associated permission rows (user and group) are cascade-deleted
- [x] **WSCRUD-07**: Workspace CRUD proxy validates workspace names client-side and handles MLflow validation errors gracefully
- [x] **WSCRUD-08**: Workspace CRUD endpoints are not registered when `MLFLOW_ENABLE_WORKSPACES=false`

### Regex Workspace Permissions

- [x] **WSREG-01**: Admin can create user regex workspace permission (pattern + priority + permission level)
- [x] **WSREG-02**: Admin can list, update, and delete user regex workspace permissions
- [x] **WSREG-03**: Admin can create group regex workspace permission (pattern + priority + permission level)
- [x] **WSREG-04**: Admin can list, update, and delete group regex workspace permissions
- [x] **WSREG-05**: Workspace permission cache resolves regex and group-regex sources in configured resolution order
- [x] **WSREG-06**: Full workspace cache is flushed on any regex permission create/update/delete operation
- [x] **WSREG-07**: Alembic migration adds `workspace_regex_permissions` and `workspace_group_regex_permissions` tables

### Workspace Security

- [x] **WSSEC-01**: After-request search filtering verifies each experiment's actual workspace against user's workspace permissions
- [x] **WSSEC-02**: After-request search filtering verifies each registered model's actual workspace against user's workspace permissions
- [x] **WSSEC-03**: After-request search filtering verifies each logged model's experiment workspace against user's workspace permissions
- [x] **WSSEC-04**: Default workspace resources remain visible when `GRANT_DEFAULT_WORKSPACE_ACCESS` is true
- [x] **WSSEC-05**: Pre-workspace-era resources (no workspace assignment) remain visible to authorized users
- [x] **WSSEC-06**: Admin users bypass all workspace-scoped filtering

### Workspace UI — Management

- [ ] **WSUI-01**: Admin can create a workspace via modal form with real-time name validation (DNS-safe pattern, 2-63 chars, reserved name check)
- [ ] **WSUI-02**: Admin can edit workspace description via modal form
- [ ] **WSUI-03**: Admin can delete a workspace via confirmation dialog with safety warning
- [ ] **WSUI-04**: Workspace list page shows member count (users + groups with permissions) per workspace
- [x] **WSUI-05**: Admin can assign permissions to multiple users/groups at once via bulk operations

### Workspace UI — Global Picker

- [x] **WSPICK-01**: Header dropdown shows accessible workspaces when `workspacesEnabled` is true in runtime config
- [x] **WSPICK-02**: Selecting a workspace sends `X-MLFLOW-WORKSPACE` header on all subsequent API requests
- [x] **WSPICK-03**: Workspace selection persists across page refreshes via localStorage
- [x] **WSPICK-04**: "All Workspaces" option removes workspace scoping (no header sent)
- [x] **WSPICK-05**: Picker includes search/filter input for deployments with many workspaces
- [x] **WSPICK-06**: Keyboard shortcut enables quick workspace switching without mouse interaction

### OIDC Integration

- [x] **WSOIDC-04**: When OIDC login maps to a workspace that does not exist, the workspace is auto-created before assigning membership

## v1.2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Workspace UI Enhancements

- **WSUI-06**: Workspace list shows resource counts (experiments, models) per workspace
- **WSPICK-07**: Workspace picker in sidebar as alternative placement option

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Per-workspace artifact store management UI | MLflow core responsibility; `default_artifact_root` set on create only |
| Workspace hierarchy / nesting | MLflow model is flat; nesting adds exponential permission complexity |
| Cross-workspace resource moving | Not supported by MLflow — experiments/models must be recreated |
| Per-workspace RBAC rule redefinitions | Permission model already complex; use READ/USE/EDIT/MANAGE consistently |
| Workspace templates (pre-configured setups) | Manual setup per workspace; scriptable via API |
| Workspace usage analytics/dashboard | Not an auth concern; use MLflow's built-in UI |
| Direct workspace store access (bypass MLflow) | Always proxy through MLflow API to preserve validation and constraints |
| Mobile app | Web-first approach |
| Multi-cluster/multi-instance federation | Single instance scope only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WSREG-01 | Phase 5 | Complete |
| WSREG-02 | Phase 5 | Complete |
| WSREG-03 | Phase 5 | Complete |
| WSREG-04 | Phase 5 | Complete |
| WSREG-05 | Phase 5 | Complete |
| WSREG-06 | Phase 5 | Complete |
| WSREG-07 | Phase 5 | Complete |
| WSCRUD-01 | Phase 6 | Complete |
| WSCRUD-02 | Phase 6 | Complete |
| WSCRUD-03 | Phase 6 | Complete |
| WSCRUD-04 | Phase 6 | Complete |
| WSCRUD-05 | Phase 6 | Complete |
| WSCRUD-06 | Phase 6 | Complete |
| WSCRUD-07 | Phase 6 | Complete |
| WSCRUD-08 | Phase 6 | Complete |
| WSOIDC-04 | Phase 6 | Complete |
| WSSEC-01 | Phase 7 | Complete |
| WSSEC-02 | Phase 7 | Complete |
| WSSEC-03 | Phase 7 | Complete |
| WSSEC-04 | Phase 7 | Complete |
| WSSEC-05 | Phase 7 | Complete |
| WSSEC-06 | Phase 7 | Complete |
| WSUI-01 | Phase 8 | Pending |
| WSUI-02 | Phase 8 | Pending |
| WSUI-03 | Phase 8 | Pending |
| WSUI-04 | Phase 8 | Pending |
| WSUI-05 | Phase 8 | Complete |
| WSPICK-01 | Phase 8 | Complete |
| WSPICK-02 | Phase 8 | Complete |
| WSPICK-03 | Phase 8 | Complete |
| WSPICK-04 | Phase 8 | Complete |
| WSPICK-05 | Phase 8 | Complete |
| WSPICK-06 | Phase 8 | Complete |

**Coverage:**
- v1.1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after roadmap creation (33/33 mapped)*
