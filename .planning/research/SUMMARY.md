# Project Research Summary

**Project:** MLflow OIDC Auth — Organization/Workspace Support
**Domain:** Multi-tenant authorization for ML experiment tracking
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

This project adds multi-tenant workspace support to the MLflow OIDC Auth plugin, aligning with MLflow 3.10's new workspace feature. MLflow 3.10 introduced workspace-based resource isolation via protobuf RPCs (`CreateWorkspace`, `ListWorkspaces`, `GetWorkspace`, `UpdateWorkspace`, `DeleteWorkspace`), an `X-MLFLOW-WORKSPACE` HTTP header for context propagation, a `workspace_permissions` table, and a permission resolution chain that falls back from resource-level → workspace-level → `NO_PERMISSIONS` (importantly, `default_permission` is **ignored** when workspaces are enabled). The plugin currently has zero workspace support — no protobuf handler registration, no workspace context propagation, no workspace permission tables. The entire workspace feature is net-new.

The recommended approach is to build workspace support in layers: first refactor the existing permission resolution to eliminate copy-paste debt, then add the data foundation (feature flag, DB migration, workspace context in the middleware bridge), then the permission model (workspace-level permissions with user and group support as a fallback layer), then the management API and UI, and finally OIDC claim-to-workspace mapping. The existing stack (Python/FastAPI/Flask/SQLAlchemy/React) requires no new frameworks — only `cachetools` as a new dependency for TTL-based workspace permission caching (matching upstream MLflow's approach). The plugin's unique value over upstream is group-level workspace permissions, OIDC-driven workspace assignment, and a management UI — features upstream's basic-auth model doesn't provide.

The primary risks are: (1) cross-tenant data leakage through the existing permission fallback chain (current default is `MANAGE`, which would grant access to foreign-workspace resources), (2) the "null workspace" migration problem where existing permissions lose effectiveness, and (3) permission resolution complexity explosion given the existing 466-line `utils/permissions.py` with copy-paste patterns across 8 near-identical functions. Risk #1 is addressed by making the workspace boundary check a hard short-circuit before permission resolution. Risk #2 is addressed by a "default workspace" sentinel migration. Risk #3 strongly recommends a prerequisite refactoring phase before workspace implementation to create generic permission abstractions — without this, the workspace support will be unmaintainable.

## Key Findings

### Recommended Stack

No new frameworks or major libraries are needed. The existing stack handles everything. The only new dependency is `cachetools>=5.0` for `TTLCache`-based workspace permission caching, matching MLflow upstream's pattern (`workspace_cache_max_size=10000`, `workspace_cache_ttl_seconds=3600`). MLflow >=3.10.0 is required as the minimum version since that's when workspace protobuf RPCs were introduced.

**Core technologies:**
- **MLflow >=3.10.0**: Provides workspace CRUD protobuf classes, `X-MLFLOW-WORKSPACE` header convention, and `workspace_context` ContextVar — all at API version 3.0 (`PUBLIC_UNDOCUMENTED` visibility)
- **cachetools >=5.0**: TTLCache for workspace permission caching — matches upstream's caching strategy and avoids per-request DB queries for workspace resolution
- **SQLAlchemy + Alembic (existing)**: New `workspace_permissions` table and optional `workspace` column on `registered_model_permissions` — follows existing patterns exactly
- **authlib (existing)**: OIDC JWT claim extraction for configurable workspace claim mapping via `OIDC_WORKSPACE_CLAIM_NAME`
- **FastAPI + React (existing)**: New workspace management router and workspace management UI feature module following established conventions

**Critical version note:** Workspace protobuf endpoints use `/api/3.0/mlflow/workspaces/*` paths. The plugin's `BEFORE_REQUEST_HANDLERS` dict must be extended with these new protobuf classes.

### Expected Features

**Must have (table stakes):**
- **Feature flag** (`MLFLOW_ENABLE_WORKSPACES`) — opt-in; zero behavioral changes when disabled
- **Workspace context propagation** — `X-MLFLOW-WORKSPACE` header flows through ASGI→WSGI bridge to Flask hooks
- **Database migration** — `workspace_permissions` table with `(workspace, user_id, permission)` composite PK
- **Workspace CRUD auth enforcement** — intercept 5 workspace protobuf handlers (admin-only for create/update/delete)
- **Workspace-level user permissions** — READ/USE/EDIT/MANAGE per user per workspace, as fallback in resolution chain
- **Resource creation gating** — `CreateExperiment`/`CreateRegisteredModel` require MANAGE on workspace (currently only after_request)
- **Default workspace access** — `grant_default_workspace_access` config for existing deployment migration path
- **Workspace permission management API** — CRUD endpoints for workspace-user and workspace-group permissions

**Should have (differentiators over upstream):**
- **Group-level workspace permissions** — assign workspace access to groups, not just users (upstream is user-only)
- **OIDC claims → workspace mapping** — auto-assign users to workspaces based on configurable JWT claim
- **Workspace permission delegation** — users with MANAGE on a workspace can self-service member management
- **Workspace management UI** — React feature module with list, detail, member management, workspace switcher

**Defer (v2+):**
- Regex workspace permissions — wait until group-level workspace permissions are proven
- Prompt optimization job auth — handle after core workspace features
- Gateway budget policy auth — handle alongside prompt optimization jobs
- Workspace-scoped search result filtering — upstream tracking store already filters by workspace_id
- Audit trail for workspace changes — logging infrastructure exists, low priority

### Architecture Approach

The architecture extends the existing middleware → bridge → hooks → validators → store chain with workspace context at each layer. Workspace context enters via `X-MLFLOW-WORKSPACE` header, gets added to `scope["mlflow_oidc_auth"]` alongside `username` and `is_admin`, flows through `AuthAwareWSGIMiddleware` (no code change needed — it copies the dict wholesale), and is accessible via a new `get_request_workspace()` bridge function. Permission resolution gains a new fallback layer: resource-level (user→group→regex→group-regex) → **workspace-level** → global default. All workspace code is gated behind an `ENABLE_WORKSPACES` feature flag.

**Major components:**
1. **Workspace utility module** (`utils/workspace.py`) — feature flag check, workspace extraction from request, `DEFAULT_WORKSPACE_NAME` constant
2. **Bridge extension** (`bridge/user.py`) — `get_request_workspace()` function, following `get_request_username()` pattern
3. **Workspace permission model** (`db/models/`, `entities/`, `repository/`) — `SqlWorkspacePermission` table, entity, repository; mirrors upstream schema
4. **Workspace validators** (`validators/workspace.py`) — workspace access checks, MANAGE enforcement for resource creation
5. **Permission resolution update** (`utils/permissions.py`) — workspace-level fallback between resource-level and global default
6. **Workspace management router** (`routers/workspace.py`) — FastAPI CRUD for workspace permissions
7. **Workspace management UI** (`web-react/src/features/workspaces/`) — React feature module following existing convention

### Critical Pitfalls

1. **Cross-tenant data leakage via permission fallback** — Current default permission is `MANAGE`. With workspaces, the resolution chain must short-circuit with `NO_PERMISSIONS` when a resource's workspace doesn't match the user's workspace access. Workspace boundary is a hard deny, not a priority level.
2. **Migration "null workspace" problem** — Adding workspace columns without assigning existing data to a "default" workspace sentinel breaks all existing permissions. Migration must seed default workspace and populate all existing records.
3. **Permission resolution complexity explosion** — Existing `utils/permissions.py` has 8 near-identical functions. Adding workspace dimension without refactoring first creates 28+ code paths. **Prerequisite refactoring to a generic resolver is strongly recommended.**
4. **OIDC provider org claim inconsistency** — No standard OIDC claim for organization exists. Must use configurable `OIDC_WORKSPACE_CLAIM_NAME` with optional detection plugin hook.
5. **Bridge layer doesn't carry workspace context** — ASGI→WSGI bridge must be updated with typed context and fail-fast assertions before any workspace validators can function.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 0: Permission Resolution Refactoring
**Rationale:** PITFALLS.md and CONCERNS.md both identify the existing 466-line `utils/permissions.py` with 8 copy-paste functions as the #1 maintainability risk. Adding workspace as a new dimension to the current structure would create 28+ code paths. This must come first.
**Delivers:** Generic `resolve_permission(resource_type, resource_id, username, workspace)` function, repository base class for permissions, reduced duplication.
**Addresses:** Pitfall #5 (complexity explosion)
**Avoids:** Unmaintainable workspace code; inconsistent workspace handling across resource types

### Phase 1: Workspace Foundation
**Rationale:** Everything depends on the workspace concept existing in the system. Additive-only — nothing breaks for existing deployments.
**Delivers:** Feature flag, workspace config options, `workspace_permissions` DB table + Alembic migration, bridge extension, workspace utility module, default workspace seeding.
**Addresses:** Feature flag, DB migration, default workspace access, workspace context propagation
**Avoids:** Pitfall #3 (null workspace migration), Pitfall #7 (bridge missing context), Pitfall #10 (backward compatibility)

### Phase 2: Workspace Permission Model & Auth Enforcement
**Rationale:** Permission resolution is the security core. Cross-tenant leakage pitfall must be resolved here before building APIs on top.
**Delivers:** Workspace permission entity/model/repository, workspace-level fallback in resolution chain, workspace access validators, before_request workspace validation, TTLCache for workspace permission lookups, workspace CRUD auth enforcement.
**Addresses:** Workspace-level user permissions, resource creation gating, workspace CRUD auth enforcement
**Avoids:** Pitfall #1 (cross-tenant leakage), Pitfall #2 (post-fetch filtering leaks), Pitfall #9 (admin bypass)

### Phase 3: Workspace Management API & Group Permissions
**Rationale:** With permission model in place, expose management APIs. Include group-level workspace permissions — our core differentiator.
**Delivers:** Workspace permission CRUD router (user + group), workspace permission delegation, after_request workspace-scoped auto-grants.
**Addresses:** Workspace permission management API, group-level workspace permissions, workspace permission delegation
**Avoids:** Pitfall #8 (group-to-org relationship — groups remain independent, permissions are workspace-scoped)

### Phase 4: Workspace Management UI
**Rationale:** Needs backend API (Phase 3) to function. High user-visibility but blocked by backend.
**Delivers:** Workspace management React feature module, workspace context provider, workspace switcher in navigation, workspace-scoped permission views.
**Addresses:** Workspace permission management UI, workspace selector

### Phase 5: OIDC Workspace Integration
**Rationale:** Optional enhancement after core workspace support is stable. Provider-dependent; needs iterative refinement.
**Delivers:** Configurable `OIDC_WORKSPACE_CLAIM_NAME`, workspace detection plugin hook, auto-assignment during OIDC login/callback.
**Addresses:** OIDC claims → workspace mapping (top differentiator)
**Avoids:** Pitfall #4 (OIDC claim inconsistency) via configurable claim + plugin hook

### Phase Ordering Rationale

- **Phase 0 before Phase 1:** Refactoring prevents complexity explosion. Both CONCERNS.md and PITFALLS.md identify this as blocking.
- **Phase 1 before Phase 2:** Permission model and bridge must exist before validators can use them.
- **Phase 2 before Phase 3:** Backend enforcement must work before exposing management APIs.
- **Phase 3 before Phase 4:** Frontend needs backend API endpoints to function.
- **Phase 5 last:** OIDC integration is most provider-dependent and only valuable once core workspace support is stable.
- **Feature dependency chain enforced:** Feature Flag → Context Propagation → Permissions → API → UI → OIDC maps directly to phases 1→2→3→4→5.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 0:** Needs precise measurement of refactoring scope across 8 functions, 28+ repositories, and 2390+ line routers to design the generic abstraction correctly.
- **Phase 2:** Complex permission resolution with workspace fallback — upstream MLflow's `_workspace_permission_for_experiment()` lambda patterns must be understood precisely. Integration with upstream `workspace_context` ContextVar needs verification.
- **Phase 5:** OIDC claim formats vary by provider. Needs testing with at least 2 providers (e.g., Keycloak + Auth0) to validate the configurable claim approach.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Additive DB migration + feature flag + bridge extension — well-documented, existing codebase conventions apply directly.
- **Phase 3:** FastAPI CRUD router — follows existing `experiment_permissions_router`, `model_permissions_router` patterns exactly.
- **Phase 4:** React feature module — follows existing `features/` convention with components, hooks, services.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified from MLflow 3.10 source code. No new major dependencies. Workspace protobuf RPCs confirmed in `service.proto`. |
| Features | HIGH | Comprehensive gap analysis between upstream MLflow 3.10 auth module and current plugin, verified from source code diff. |
| Architecture | HIGH | Extends proven existing patterns (middleware → bridge → hooks → validators → store). Data model mirrors upstream MLflow 3.10 schema. |
| Pitfalls | HIGH | Based on direct code analysis with specific file/line references and established multi-tenancy patterns. All 10 pitfalls grounded in concrete code. |

**Overall confidence:** HIGH

All research is based on direct source code analysis of both upstream MLflow 3.10 and the plugin codebase. No findings rely on blog posts, tutorials, or community hearsay.

### Gaps to Address

- **Upstream workspace API stability:** MLflow workspace endpoints are `PUBLIC_UNDOCUMENTED` (API v3.0). Could change in minor releases. Monitor upstream changelog during implementation.
- **`workspace_context` ContextVar interaction:** Plugin may need to set MLflow's `workspace_context` ContextVar for upstream code paths. Needs verification during Phase 2.
- **GraphQL workspace support:** Plugin monkey-patches MLflow's GraphQL auth middleware. Workspace context propagation through GraphQL path not verified in research.
- **Performance at scale (100+ workspaces):** TTLCache strategy is sound but actual overhead needs measurement during Phase 2.
- **Phase 0 refactoring scope:** Needs its own detailed analysis to determine the best generic abstraction pattern (factory, class hierarchy, or parameterized function).

## Sources

### Primary (HIGH confidence)
- MLflow 3.10 source code: `service.proto`, `mlflow/server/auth/` module (entities.py, routes.py, sqlalchemy_store.py, db/models.py, __init__.py, config.py, permissions.py)
- MLflow workspace utilities: `mlflow/utils/workspace_utils.py`, `mlflow/utils/workspace_context.py`
- MLflow environment variables: `mlflow/environment_variables.py`
- Current plugin codebase: `utils/permissions.py`, `hooks/before_request.py`, `hooks/after_request.py`, `middleware/`, `bridge/user.py`, `config.py`, `routers/`, `db/models/`
- OpenID Connect Core 1.0 specification — standard claims verification, no org claim exists

### Secondary (MEDIUM confidence)
- OIDC provider documentation (Auth0 Organizations, Keycloak Organizations, Azure AD multi-tenant, Okta Organizations) — provider-specific claim formats
- Multi-tenant authorization patterns (row-level security, org-scoped RBAC) — established industry patterns

### Tertiary (needs validation)
- MLflow workspace API stability — `PUBLIC_UNDOCUMENTED` visibility means potential breaking changes
- GraphQL workspace context propagation — not verified, needs testing
- `AuthAwareWSGIMiddleware` dict propagation behavior — inferred from code reading, needs integration test

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
