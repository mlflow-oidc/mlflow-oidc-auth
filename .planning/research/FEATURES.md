# Feature Landscape

**Domain:** Multi-tenant organization/workspace support for MLflow OIDC auth plugin
**Researched:** 2026-03-23

## Context: What MLflow 3.10 Actually Ships

MLflow 3.10 (released 2026-02-20) introduced **Workspaces** — not "organizations" in the IdP sense, but logical resource isolation units within a single tracking server. Key upstream facts:

### Upstream Workspace Model (HIGH confidence — verified from source code)

| Aspect | Upstream Implementation |
|--------|------------------------|
| **Entity** | `Workspace` with full CRUD (create/get/list/update/delete) via protobuf |
| **DB Schema** | `workspace_id` FK added to all major tables (experiments, models, traces, endpoints); `workspace_permissions` table with `(workspace, user_id, permission)` PK |
| **Context propagation** | `X-MLFLOW-WORKSPACE` HTTP header; `mlflow.set_workspace()` client API; `workspace_context.get_request_workspace()` server-side |
| **Permission model** | Workspace-level permissions (READ/USE/EDIT/MANAGE/NO_PERMISSIONS) per user. Falls back: resource-level → workspace-level → NO_PERMISSIONS (when workspaces enabled, `default_permission` is NOT used — isolation by default) |
| **Auth enforcement** | `_workspace_permission_for_experiment()`, `_workspace_permission_for_registered_model()`, etc. — each resource check has a workspace fallback lambda |
| **Resource creation** | `CreateExperiment` and `CreateRegisteredModel` require MANAGE permission on the workspace |
| **Artifact isolation** | Per-workspace artifact root override |
| **Feature flag** | `MLFLOW_ENABLE_WORKSPACES` env var — disabled by default |
| **Config options** | `grant_default_workspace_access` — implicit access to default workspace; `workspace_cache_max_size`, `workspace_cache_ttl_seconds` |
| **Workspace permissions API** | `LIST_WORKSPACE_PERMISSIONS` (per workspace), `LIST_USER_WORKSPACE_PERMISSIONS` (per user) — REST v3 endpoints |
| **Permission delegation** | Users with MANAGE on a workspace can grant/revoke permissions for other users in that workspace (self-service) |

### Upstream Auth Routes for Workspaces (HIGH confidence — from routes.py)

```
/api/3.0/mlflow/workspaces/<workspace_name>/permissions  (LIST_WORKSPACE_PERMISSIONS)
/api/3.0/mlflow/workspace-permissions                     (LIST_USER_WORKSPACE_PERMISSIONS)
```

### Upstream Protobuf Handlers for Workspaces (HIGH confidence — from __init__.py)

| Protobuf Class | Upstream Validator |
|---------------|-------------------|
| `CreateWorkspace` | `sender_is_admin` |
| `GetWorkspace` | `validate_can_view_workspace` |
| `ListWorkspaces` | (always allowed — filtered by accessible workspaces) |
| `UpdateWorkspace` | `sender_is_admin` |
| `DeleteWorkspace` | `sender_is_admin` |
| `CreateExperiment` | `validate_can_create_experiment` (workspace MANAGE check) |
| `CreateRegisteredModel` | `validate_can_create_registered_model` (workspace MANAGE check) |
| `SearchExperiments` | Result filtering by workspace access |
| `SearchRegisteredModels` | Result filtering by workspace access |

### What Upstream Basic-Auth Does NOT Have (that our plugin has)

- **Groups** — upstream is user-only; our plugin has group-level permissions
- **Regex permissions** — upstream lacks pattern-based permission rules
- **Group-regex permissions** — our unique feature
- **Prompt-specific permissions** — upstream treats prompts as registered models
- **Gateway permissions at group level** — upstream is user-only
- **OIDC integration** — upstream is basic-auth only

## Entities/Endpoints Our Plugin Does NOT Cover Yet

### Missing from before_request.py (HIGH confidence — verified from code diff)

| Protobuf Class | Upstream Has? | Our Plugin? | Gap |
|---------------|:---:|:---:|------|
| `CreateExperiment` | before_request | after_request only | **No auth check on creation** — upstream now requires workspace MANAGE |
| `CreateRegisteredModel` | before_request | after_request only | **No auth check on creation** — upstream now requires workspace MANAGE |
| `CreateWorkspace` | Yes (admin) | Missing | **New entity not handled** |
| `GetWorkspace` | Yes | Missing | **New entity not handled** |
| `ListWorkspaces` | Yes | Missing | **New entity not handled** |
| `UpdateWorkspace` | Yes (admin) | Missing | **New entity not handled** |
| `DeleteWorkspace` | Yes (admin) | Missing | **New entity not handled** |
| `SearchExperiments` | Result filtering | Only in after_request | Already covered differently |
| `SearchRegisteredModels` | Result filtering | Only in after_request | Already covered differently |
| `SearchLoggedModels` | Result filtering | Only in after_request | Already covered differently |
| `CreatePromptOptimizationJob` | Yes | Missing | **New entity not handled** |
| `GetPromptOptimizationJob` | Yes | Missing | **New entity not handled** |
| `SearchPromptOptimizationJobs` | Yes | Missing | **New entity not handled** |
| `DeletePromptOptimizationJob` | Yes | Missing | **New entity not handled** |
| `CancelPromptOptimizationJob` | Yes | Missing | **New entity not handled** |
| `CreateGatewayBudgetPolicy` | Yes | Missing | **New entity not handled** |
| `GetGatewayBudgetPolicy` | Yes | Missing | **New entity not handled** |
| `ListGatewayBudgetPolicies` | Yes | Missing | **New entity not handled** |
| `UpdateGatewayBudgetPolicy` | Yes | Missing | **New entity not handled** |
| `DeleteGatewayBudgetPolicy` | Yes | Missing | **New entity not handled** |
| Workspace permission routes | Yes | Missing | **New permission management routes** |

### Upstream Workspace Permission Routes (must intercept)

The upstream auth plugin adds REST v3 workspace permission endpoints. Our plugin needs to either:
1. Intercept workspace CRUD protobuf handlers in before_request
2. Add workspace permission management routes to our FastAPI routers
3. Forward workspace context header through the middleware chain

## Table Stakes

Features users expect for a workspace/multi-tenant auth plugin. Missing = product is not viable for org support.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Workspace CRUD auth enforcement** | Upstream adds Create/Get/List/Update/DeleteWorkspace protos — must intercept | Medium | Admin-only for create/update/delete; view check for get |
| **Workspace context propagation** | `X-MLFLOW-WORKSPACE` header must flow through FastAPI middleware → Flask hooks | Low-Medium | `AuthAwareWSGIMiddleware` already bridges ASGI→WSGI; add workspace to scope |
| **Workspace-level permissions (user)** | Users need READ/EDIT/MANAGE on a workspace to access any resources within it | High | New DB table, entity, repository, store methods, API endpoints |
| **Workspace-level permissions (group)** | Groups must participate in workspace access — differentiator over upstream | High | Extend workspace permissions with group support (upstream only has user-level) |
| **Resource creation gated on workspace** | CreateExperiment and CreateRegisteredModel must require workspace MANAGE | Medium | Add before_request handlers (currently only after_request for auto-grant) |
| **Workspace permission delegation** | Workspace MANAGERs can grant/revoke within their workspace | Medium | Self-service — users with MANAGE on a workspace don't need global admin |
| **Workspace permission management API** | CRUD endpoints for workspace-user and workspace-group permissions | Medium | FastAPI router analogous to existing experiment/model permission routers |
| **Workspace permission management UI** | Admin UI page for managing who can access which workspace | Medium | React feature module; workspace picker + permission table |
| **Database migration** | Add `workspace_permissions` table (and optionally `workspace_group_permissions`) | Low | Alembic migration; safe additive schema change |
| **Feature flag** | `MLFLOW_ENABLE_WORKSPACES` or equivalent config toggle | Low | Workspace features must be opt-in to not break existing deployments |
| **Default workspace access** | `grant_default_workspace_access` config — existing users get implicit access to default workspace | Low | Prevents breaking existing deployments when workspaces are enabled |

## Differentiators

Features that set our plugin apart from upstream basic-auth. Not expected by upstream, but valued by OIDC-auth users.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **OIDC claims → workspace mapping** | Automatically assign users to workspaces based on OIDC token claims (e.g., `org`, `team`, `department`) | High | Map OIDC claims to workspace names during login/callback; auto-create workspace membership |
| **Group-level workspace permissions** | Assign workspace access to groups, not just individual users (upstream is user-only) | Medium | Our group infrastructure already exists; extend it to workspace permissions |
| **Regex workspace permissions** | Pattern-based workspace access rules (e.g., `team-*` for all team workspaces) | Medium | Follows existing regex permission pattern for experiments/models |
| **Workspace + group permission resolution** | Combine workspace boundaries with existing group/regex permission hierarchy | High | Must define resolution order: workspace-level → then user/group/regex within workspace |
| **Org-level admin role** | Workspace admin role separate from global admin — can manage workspace membership and resources but not other workspaces | Medium | Delegation model; MANAGE on workspace grants admin within that workspace scope |
| **Workspace selector in auth UI** | Dropdown/switcher in React admin UI to manage permissions per-workspace | Medium | UX improvement over workspace-unaware permission management |
| **Prompt optimization job auth** | Handle `CreatePromptOptimizationJob` and related protobuf classes | Low-Medium | Upstream covers this; we should too since we handle all other protobuf classes |
| **Gateway budget policy auth** | Handle `CreateGatewayBudgetPolicy` and related protobuf classes | Low-Medium | New upstream resource type we don't cover |
| **Workspace-scoped search result filtering** | after_request filter results to only workspace-accessible resources | Medium | Extend existing search filtering to check workspace membership |
| **Audit trail for workspace access** | Log workspace permission changes for compliance | Low | Logging already exists; extend to workspace permission events |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Per-workspace artifact store management** | Artifact storage config is MLflow core responsibility, not auth plugin | Document how to configure upstream `--artifact-root` per workspace |
| **Workspace CRUD (create/update/delete workspace entity)** | Workspace lifecycle is managed by MLflow core; auth plugin only controls access | Intercept protobuf handlers for auth checks; delegate workspace CRUD to upstream store |
| **Per-workspace billing/metering** | Not an auth concern; no infrastructure for cost tracking | Out of scope — use external tools if needed |
| **Cross-workspace resource sharing** | Breaks isolation model; too complex permission model | Resources belong to one workspace; cross-ref via naming conventions or external cataloging |
| **Per-workspace OIDC provider configuration** | Different IdPs per workspace adds massive complexity | Single OIDC provider per deployment; workspace mapping via claims within that IdP |
| **Hierarchical workspaces (nesting)** | Upstream model is flat; nesting adds exponential complexity to permission resolution | Keep flat workspace model; use naming conventions for logical grouping (e.g., `team-a/project-1`) |
| **Hard workspace boundary enforcement at DB level** | Requires modifying MLflow's DB queries (out of plugin scope) | Enforce via auth hooks (before_request) and result filtering (after_request) — soft boundary |
| **Workspace entity model definition** | Our plugin doesn't own workspace lifecycle — MLflow does | Only add workspace_permissions and auth checks; use upstream workspace store |

## Feature Dependencies

```
Feature Flag (MLFLOW_ENABLE_WORKSPACES) → All workspace features

Workspace Context Propagation → Workspace-level permissions
                              → Resource creation gating
                              → Workspace-scoped search filtering

DB Migration (workspace_permissions) → Workspace-level permissions (user)
                                     → Workspace-level permissions (group)
                                     → Workspace permission management API
                                     → Workspace permission management UI

Workspace-level permissions (user) → Workspace permission delegation
                                   → Workspace permission management API

Workspace-level permissions (group) → Group-level workspace permissions
                                    → Regex workspace permissions

Workspace permission management API → Workspace permission management UI
                                    → Workspace selector in auth UI

OIDC claims → workspace mapping → Group-level workspace permissions (needs groups to exist)
                                → Workspace-level permissions (needs workspace table)

Resource creation gating → Workspace CRUD auth enforcement
                        → Prompt optimization job auth
                        → Gateway budget policy auth
```

## MVP Recommendation

Prioritize (Phase 1 — Table Stakes):
1. **Workspace context propagation** — must have header flowing through middleware (Low-Medium)
2. **DB migration for workspace_permissions** — foundation for all permission features (Low)
3. **Workspace CRUD auth enforcement** — intercept Create/Get/List/Update/Delete Workspace protos (Medium)
4. **Workspace-level user permissions** — store, repository, entity, validators (High)
5. **Resource creation gating** — CreateExperiment/CreateRegisteredModel require workspace MANAGE (Medium)
6. **Feature flag** — opt-in toggle to not break existing deployments (Low)
7. **Default workspace access** — migration path for existing deployments (Low)

Prioritize (Phase 2 — Differentiators):
1. **Group-level workspace permissions** — extend our group infrastructure to workspaces (Medium)
2. **Workspace permission management API** — FastAPI CRUD router (Medium)
3. **Workspace permission management UI** — React feature module (Medium)
4. **OIDC claims → workspace mapping** — auto-assign during login (High)
5. **Workspace permission delegation** — MANAGE users can self-service (Medium)

Defer:
- **Regex workspace permissions**: Wait until group-level is proven; complexity not justified initially
- **Prompt optimization job auth**: Lower priority — handle after core workspace features
- **Gateway budget policy auth**: New resource type — handle alongside prompt optimization jobs
- **Audit trail**: Nice-to-have; logging infrastructure already exists
- **Workspace-scoped search filtering**: Can wait — upstream tracking store already filters by workspace_id

## Upstream vs Our Plugin: Feature Matrix

| Capability | Upstream Basic Auth | Our OIDC Auth (Current) | Our OIDC Auth (Target) |
|------------|:---:|:---:|:---:|
| Workspace CRUD | Yes (via protobuf) | No | Auth enforcement only |
| Workspace user permissions | Yes | No | Yes |
| Workspace group permissions | No | No | **Yes (differentiator)** |
| Workspace regex permissions | No | No | **Yes (differentiator)** |
| Workspace permission delegation | Yes (MANAGE) | No | Yes |
| OIDC claims → workspace mapping | No | No | **Yes (differentiator)** |
| Resource creation gating | Yes | No | Yes |
| Workspace context propagation | Yes (header) | No | Yes |
| Group-level resource permissions | No | Yes | Yes |
| Regex resource permissions | No | Yes | Yes |
| Multi-method auth (OIDC/JWT/Basic) | Basic only | Yes | Yes |
| Permission resolution chain | Resource only | User→Group→Regex→GroupRegex | Workspace→User→Group→Regex→GroupRegex |

## Sources

- MLflow 3.10.0 Release: https://github.com/mlflow/mlflow/releases/tag/v3.10.0 (HIGH confidence)
- PR #20657 — Workspace feature branch: https://github.com/mlflow/mlflow/pull/20657 (HIGH confidence — merged code)
- PR #20702 — Workspace UI: https://github.com/mlflow/mlflow/pull/20702 (HIGH confidence — merged code)
- `mlflow/server/auth/routes.py` — upstream auth routes (HIGH confidence — raw source)
- `mlflow/server/auth/__init__.py` — upstream auth validators and handlers (HIGH confidence — raw source)
- `mlflow/server/auth/entities.py` — upstream entity definitions including `WorkspacePermission` (HIGH confidence — raw source)
- `mlflow/server/auth/db/models.py` — upstream DB models including `SqlWorkspacePermission` (HIGH confidence — raw source)
- `mlflow/server/auth/sqlalchemy_store.py` — upstream store with workspace methods (HIGH confidence — raw source)
- `mlflow_oidc_auth/hooks/before_request.py` — our plugin's current hook mappings (HIGH confidence — local source)
- `mlflow_oidc_auth/hooks/after_request.py` — our plugin's current after-request handling (HIGH confidence — local source)
