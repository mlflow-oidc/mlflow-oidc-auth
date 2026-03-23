# Requirements — v1 Workspace Support

**Project:** MLflow OIDC Auth — Organization/Workspace Support
**Created:** 2026-03-23
**Status:** Active

## v1 Requirements

### Prerequisite Refactoring

- [x] **REFAC-01**: Permission resolution refactored into generic `resolve_permission()` function to eliminate 8 copy-paste functions in `utils/permissions.py`
- [x] **REFAC-02**: Repository base class for permissions to reduce duplication across 28+ repository classes

### Workspace Foundation

- [x] **WSFND-01**: Feature flag (`MLFLOW_ENABLE_WORKSPACES` / `ENABLE_WORKSPACES` config) gates all workspace behavior — disabled by default, zero behavioral changes when off
- [x] **WSFND-02**: `X-MLFLOW-WORKSPACE` header propagated through FastAPI AuthMiddleware → ASGI scope `mlflow_oidc_auth` dict → AuthAwareWSGIMiddleware → Flask request.environ
- [x] **WSFND-03**: Alembic migration adds `workspace_permissions` table with `(workspace, user_id, permission)` composite primary key
- [x] **WSFND-04**: Default workspace seeded on migration — all existing resources assigned to default workspace for backward compatibility
- [x] **WSFND-05**: `grant_default_workspace_access` config option — existing users get implicit access to default workspace when workspaces first enabled
- [x] **WSFND-06**: Bridge extension with `get_request_workspace()` function following existing `get_request_username()` pattern in `bridge/user.py`

### Workspace Auth Enforcement

- [x] **WSAUTH-01**: before_request handlers registered for 5 workspace protobuf RPCs: `CreateWorkspace` (admin), `GetWorkspace` (view check), `ListWorkspaces` (always allowed, filtered), `UpdateWorkspace` (admin), `DeleteWorkspace` (admin)
- [x] **WSAUTH-02**: Workspace-level user permissions (READ/USE/EDIT/MANAGE) with DB model (`SqlWorkspacePermission`), entity, repository, and store methods
- [x] **WSAUTH-03**: `CreateExperiment` and `CreateRegisteredModel` gated on workspace MANAGE permission in before_request (currently only auto-grant in after_request)
- [x] **WSAUTH-04**: Permission resolution updated with workspace-level fallback: resource-level (user→group→regex→group-regex) → workspace-level → NO_PERMISSIONS (when workspaces enabled, `default_permission` is NOT used)
- [x] **WSAUTH-05**: TTLCache for workspace permission lookups (configurable `workspace_cache_max_size`, `workspace_cache_ttl_seconds`) to avoid per-request DB queries

### Workspace Management

- [ ] **WSMGMT-01**: FastAPI CRUD router for workspace-user permissions (list, create, update, delete per workspace)
- [ ] **WSMGMT-02**: FastAPI CRUD router for workspace-group permissions (list, create, update, delete per workspace) — differentiator over upstream
- [ ] **WSMGMT-03**: Workspace permission delegation — users with MANAGE on a workspace can grant/revoke permissions for other users within that workspace without requiring global admin
- [ ] **WSMGMT-04**: React workspace management feature module with workspace list view, workspace detail view, and member management (users + groups)
- [ ] **WSMGMT-05**: Workspace switcher component in admin UI navigation for workspace-scoped permission views
- [ ] **WSMGMT-06**: Admin-managed workspace-to-user assignment UI as fallback when OIDC provider doesn't send workspace claims — manual workspace membership management

### OIDC Workspace Integration

- [ ] **WSOIDC-01**: Configurable `OIDC_WORKSPACE_CLAIM_NAME` environment variable for extracting workspace from OIDC JWT token claims during login/callback
- [ ] **WSOIDC-02**: Workspace detection plugin hook (following existing `OIDC_GROUP_DETECTION_PLUGIN` pattern) for custom workspace resolution logic per deployment
- [ ] **WSOIDC-03**: Auto-create workspace membership during OIDC login when workspace claim is present in token — assign user to workspace with configurable default permission level

### New Entity Coverage

- [ ] **ENTITY-01**: before_request handlers for Prompt Optimization Job protobuf RPCs: `CreatePromptOptimizationJob`, `GetPromptOptimizationJob`, `SearchPromptOptimizationJobs`, `DeletePromptOptimizationJob`, `CancelPromptOptimizationJob`
- [ ] **ENTITY-02**: before_request handlers for Gateway Budget Policy protobuf RPCs: `CreateGatewayBudgetPolicy`, `GetGatewayBudgetPolicy`, `ListGatewayBudgetPolicies`, `UpdateGatewayBudgetPolicy`, `DeleteGatewayBudgetPolicy`

## v2 Requirements (Deferred)

- [ ] Regex workspace permissions — pattern-based workspace access rules (e.g., `team-*`)
- [ ] Workspace-scoped search result filtering in after_request
- [ ] Audit trail for workspace permission changes
- [ ] Cross-workspace resource sharing (explicit grant model)
- [ ] Hierarchical workspace nesting

## Out of Scope

- Per-workspace artifact store management — MLflow core responsibility, not auth plugin
- Workspace CRUD (create/update/delete workspace entity) — workspace lifecycle managed by MLflow core; plugin only controls access
- Per-workspace billing/metering — not an auth concern
- Per-workspace OIDC provider configuration — single provider per deployment
- Hard workspace boundary enforcement at DB level — enforced via hooks (before_request) and result filtering (after_request)
- Workspace entity model definition — plugin doesn't own workspace lifecycle

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| REFAC-01 | Phase 1 | Complete |
| REFAC-02 | Phase 1 | Complete |
| WSFND-01 | Phase 1 | Complete |
| WSFND-02 | Phase 1 | Complete |
| WSFND-03 | Phase 1 | Complete |
| WSFND-04 | Phase 1 | Complete |
| WSFND-05 | Phase 1 | Complete |
| WSFND-06 | Phase 1 | Complete |
| WSAUTH-01 | Phase 2 | Complete |
| WSAUTH-02 | Phase 2 | Complete |
| WSAUTH-03 | Phase 2 | Complete |
| WSAUTH-04 | Phase 2 | Complete |
| WSAUTH-05 | Phase 2 | Complete |
| WSMGMT-01 | Phase 3 | Pending |
| WSMGMT-02 | Phase 3 | Pending |
| WSMGMT-03 | Phase 3 | Pending |
| WSMGMT-04 | Phase 4 | Pending |
| WSMGMT-05 | Phase 4 | Pending |
| WSMGMT-06 | Phase 4 | Pending |
| WSOIDC-01 | Phase 3 | Pending |
| WSOIDC-02 | Phase 3 | Pending |
| WSOIDC-03 | Phase 3 | Pending |
| ENTITY-01 | Phase 3 | Pending |
| ENTITY-02 | Phase 3 | Pending |

---
*Requirements defined: 2026-03-23*
*24 v1 requirements | 5 v2 deferred | 6 out of scope*
*Traceability updated: 2026-03-23 — all 24 v1 requirements mapped to phases*
