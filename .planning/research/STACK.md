# Stack Research

**Domain:** Multi-tenant organization/workspace support for MLflow OIDC Auth plugin
**Researched:** 2026-03-23
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

These are **additions and changes** to the existing stack. The existing stack (Python 3.12, FastAPI, Flask, SQLAlchemy, React 19, etc.) remains unchanged — see `.planning/codebase/STACK.md` for the full current stack.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| MLflow | >=3.10.0, <4 | Upstream workspace API provider | 3.10 introduced workspace support via 5 new protobuf RPCs. This is the minimum version that exposes `CreateWorkspace`, `ListWorkspaces`, `GetWorkspace`, `UpdateWorkspace`, `DeleteWorkspace` in `MlflowService`. Confidence: HIGH (verified in `service.proto`). |
| SQLAlchemy | >=2.0.46, <3 | ORM for new workspace permission tables | Already in use. New `workspace_permissions` table and `workspace` column on `registered_model_permissions` follow existing patterns. No version bump needed. Confidence: HIGH. |
| Alembic | <2, !=1.18.4 | Schema migration for workspace tables | Already in use. New migration(s) needed for workspace permission table and workspace column additions. Confidence: HIGH. |
| authlib | <2 | OIDC JWT claim extraction (org/tenant claim) | Already in use. Supports custom claim extraction from ID tokens and access tokens via standard JWT parsing. No new library needed for OIDC org claim mapping. Confidence: HIGH. |
| cachetools | >=5.0 | TTL cache for workspace-to-resource mapping | MLflow upstream uses `TTLCache` from `cachetools` for `_RESOURCE_WORKSPACE_CACHE` in the auth module. The plugin should use the same caching pattern for workspace resolution to avoid repeated DB lookups. Confidence: HIGH (verified in upstream `mlflow/server/auth/__init__.py`). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cachetools | >=5.0 | `TTLCache` for workspace→resource cache and workspace permission cache | Always — workspace resolution on every request needs caching. MLflow upstream uses `workspace_cache_max_size=10000` and `workspace_cache_ttl_seconds=3600` as defaults. Match these. |

**No other new Python libraries are needed.** The existing stack handles everything:
- `authlib` — JWT/OIDC claim extraction (already used)
- `sqlalchemy` — ORM for new tables (already used)
- `alembic` — Migrations (already used)
- `fastapi` — New workspace management routers (already used)
- `flask` — Hook registration for new workspace protobuf classes (already used)

### Development Tools

No new development tools needed. The existing toolchain (pytest, tox, Vitest, Playwright, pre-commit, black, eslint) is sufficient.

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Test workspace permission logic | Add workspace-aware test fixtures. Existing `conftest.py` patterns apply. |
| Alembic CLI | Generate migration for workspace tables | `alembic revision --autogenerate -m "add workspace permissions"` |

## Installation

```bash
# New dependency to add to pyproject.toml
# Under [project] dependencies:
cachetools>=5.0

# No other new dependencies needed
```

**pyproject.toml change:**

```toml
# Add to dependencies list:
"cachetools>=5.0",

# Update MLflow minimum:
"mlflow>=3.10.0,<4",  # Already at this level
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `cachetools.TTLCache` for workspace cache | `functools.lru_cache` | Never for this use case — `lru_cache` has no TTL, stale workspace mappings would persist until eviction by size. `TTLCache` matches upstream MLflow's approach. |
| Configurable OIDC claim name (`OIDC_ORG_CLAIM_NAME` env var) | Hardcoded claim like `org_id` | Never — OIDC providers use different claim names (Keycloak: custom, Azure AD: `tid`, Okta: `org_id`, Auth0: `org_id`/`org_name`). Must be configurable. |
| SQLAlchemy table for workspace permissions | Separate microservice for workspace management | Never — the plugin is a single-process MLflow plugin. Adding a separate service would break the deployment model entirely. |
| Align with MLflow's "workspace" terminology | Use "organization" terminology | Never — MLflow 3.10 consistently uses "workspace" everywhere (protobuf, routes, DB models, env vars, headers). Using different terminology would cause confusion and maintenance burden. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Custom workspace protobuf definitions | MLflow already defines all workspace messages in `service.proto`. The plugin should import these, not redefine them. | Import from `mlflow.protos.service_pb2`: `CreateWorkspace`, `ListWorkspaces`, `GetWorkspace`, `UpdateWorkspace`, `DeleteWorkspace` |
| `MLFLOW_WORKSPACE_STORE_URI` env var | This is for MLflow's upstream auth module store, not the plugin's store. The plugin has its own `OIDC_USERS_DB_URI`. | Use the plugin's existing `OIDC_USERS_DB_URI` for workspace permission storage |
| MLflow's built-in `SqlAlchemyStore` for workspaces | The plugin overrides MLflow's auth module entirely. Using MLflow's store alongside the plugin's store would create dual-write and consistency issues. | Use the plugin's own `SqlAlchemyStore` with new workspace methods |
| Universal "organization" OIDC claim assumption | There is NO standard OIDC claim for organizations. OpenID Connect Core 1.0 defines `sub`, `name`, `email`, `groups` etc. but nothing for org/tenant. Assuming any single claim name will break for some IdP. | Configurable claim mapping: `OIDC_WORKSPACE_CLAIM_NAME` env var (default: none/disabled) |
| `redis` or external cache for workspace resolution | Adds operational complexity for a cache that's request-scoped and tolerant of stale data. MLflow upstream uses in-process `TTLCache`. | `cachetools.TTLCache` — in-process, zero-dependency (beyond the library), matches upstream |

## Stack Patterns by Variant

**If workspace support is DISABLED (`MLFLOW_ENABLE_WORKSPACES=false`):**
- No behavioral changes. All workspace code paths are gated.
- Existing permission resolution (`default_permission` fallback) continues to work.
- This is the default — workspace support is opt-in.
- Because: Backward compatibility with existing deployments is critical.

**If workspace support is ENABLED (`MLFLOW_ENABLE_WORKSPACES=true`):**
- `default_permission` config is IGNORED (MLflow upstream enforces this for isolation).
- Permission resolution changes: `_workspace_permission()` provides fallback instead.
- `X-MLFLOW-WORKSPACE` header must be extracted and propagated through ASGI→WSGI bridge.
- `grant_default_workspace_access` config controls whether authenticated users get implicit access to "default" workspace.
- Because: Workspace-enabled mode fundamentally changes permission semantics for tenant isolation.

**If OIDC workspace claim mapping is CONFIGURED (`OIDC_WORKSPACE_CLAIM_NAME` is set):**
- On OIDC login, extract the configured claim from the ID token.
- Auto-assign workspace permissions based on claim value.
- Because: Enables automatic workspace assignment from IdP without manual admin setup.

**If OIDC workspace claim mapping is NOT configured:**
- Workspace assignment is fully admin-managed via API/UI.
- No automatic workspace membership from OIDC tokens.
- Because: Some deployments manage workspace membership independently of IdP org structure.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| mlflow >=3.10.0 | cachetools >=5.0 | MLflow 3.10 uses cachetools internally for workspace cache. No conflict. |
| mlflow >=3.10.0 | sqlalchemy >=2.0.46 | Already compatible per current stack. |
| mlflow >=3.10.0 | authlib <2 | Already compatible per current stack. |
| cachetools >=5.0 | Python >=3.10 | cachetools 5.x supports Python 3.7+. No issue. |
| mlflow >=3.10.0 | fastapi >=0.132.0 | Already compatible per current stack. |

**Critical compatibility note:** The MLflow 3.10 workspace protobuf classes (`CreateWorkspace`, `ListWorkspaces`, etc.) are `PUBLIC_UNDOCUMENTED` visibility at API version 3.0. The plugin currently handles API version 2.0 endpoints. The workspace endpoints use `/api/3.0/mlflow/workspaces/*` paths. The plugin's `BEFORE_REQUEST_HANDLERS` dict must be extended with these new protobuf classes.

## MLflow 3.10 Workspace API Reference

### Protobuf RPCs (from `service.proto`)

| RPC | Method | Path | Visibility |
|-----|--------|------|------------|
| `CreateWorkspace` | POST | `/api/3.0/mlflow/workspaces` | PUBLIC_UNDOCUMENTED |
| `ListWorkspaces` | GET | `/api/3.0/mlflow/workspaces` | PUBLIC_UNDOCUMENTED |
| `GetWorkspace` | GET | `/api/3.0/mlflow/workspaces/{workspace_name}` | PUBLIC_UNDOCUMENTED |
| `UpdateWorkspace` | PATCH | `/api/3.0/mlflow/workspaces/{workspace_name}` | PUBLIC_UNDOCUMENTED |
| `DeleteWorkspace` | DELETE | `/api/3.0/mlflow/workspaces/{workspace_name}` | PUBLIC_UNDOCUMENTED |

### Auth Module Routes (from `routes.py`)

| Route | Purpose |
|-------|---------|
| `/api/3.0/mlflow/workspaces/<workspace_name>/permissions` | List permissions for a workspace |
| `/api/3.0/mlflow/workspace-permissions` | List current user's workspace permissions |

### Auth Module Entities

| Entity | Fields | Table |
|--------|--------|-------|
| `WorkspacePermission` | `workspace`, `user_id`, `permission` | `workspace_permissions` |
| `SqlWorkspacePermission` | Composite PK `(workspace, user_id)`, indexed on both columns | `workspace_permissions` |

### Auth Module Store Methods

| Method | Purpose |
|--------|---------|
| `list_workspace_permissions(workspace)` | Get all permissions for a workspace |
| `list_user_workspace_permissions(user_id)` | Get all workspace permissions for a user |
| `set_workspace_permission(workspace, user_id, permission)` | Create/update a workspace permission |
| `delete_workspace_permission(workspace, user_id)` | Remove a workspace permission |
| `list_accessible_workspace_names(user_id)` | Get workspace names a user can access |
| `get_workspace_permission(workspace, user_id)` | Get specific permission |
| `delete_workspace_permissions_for_workspace(workspace)` | Cascade delete on workspace removal |

### Environment Variables

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `MLFLOW_ENABLE_WORKSPACES` | bool | `False` | Feature flag for workspace support |
| `MLFLOW_WORKSPACE` | str | — | Set workspace context for CLI operations |
| `MLFLOW_WORKSPACE_STORE_URI` | str | — | Separate store URI for workspace data (upstream only) |

### Auth Config Additions

| Config Key | Type | Default | Purpose |
|------------|------|---------|---------|
| `grant_default_workspace_access` | bool | — | Whether authenticated users get implicit access to "default" workspace |
| `workspace_cache_max_size` | int | 10000 | Max entries in workspace-to-resource TTL cache |
| `workspace_cache_ttl_seconds` | int | 3600 | TTL for workspace-to-resource cache entries |

### HTTP Header

| Header | Purpose |
|--------|---------|
| `X-MLFLOW-WORKSPACE` | Identifies the workspace for a request. Read by `workspace_utils.get_workspace()`. |

### Workspace Context

- `mlflow.utils.workspace_context` provides `ContextVar`-based workspace scoping
- `DEFAULT_WORKSPACE_NAME` constant (value: `"default"`)
- Workspace resolved from: header → env var → default

## OIDC Organization Claim Landscape

OpenID Connect Core 1.0 defines **no standard claim for organization/tenant identity**. This is critical context for the plugin's design.

| OIDC Provider | Claim Name | Claim Value | Notes |
|---------------|------------|-------------|-------|
| Keycloak | Custom (varies) | Realm-based or custom attribute | Often mapped via protocol mappers. No standard claim. |
| Azure AD (Entra ID) | `tid` | Tenant ID (GUID) | Standard in Azure tokens. Also `tenant_ctry`. |
| Okta | `org_id` | Organization ID | Available with Okta Organizations feature. |
| Auth0 | `org_id`, `org_name` | Organization ID/name | Available with Auth0 Organizations. |
| Google Workspace | `hd` | Hosted domain | Domain-based, not org-based. |
| Generic | — | — | No universal claim exists. |

**Recommendation:** The plugin should provide `OIDC_WORKSPACE_CLAIM_NAME` configuration (env var or config provider) that specifies which JWT claim to read for workspace assignment. Default: not set (disabled, workspace assignment is admin-managed only). Confidence: HIGH.

## Sources

- MLflow `service.proto` (GitHub master branch) — Workspace RPC definitions verified. Confidence: HIGH.
- MLflow `mlflow/server/auth/entities.py` — `WorkspacePermission` entity verified. Confidence: HIGH.
- MLflow `mlflow/server/auth/routes.py` — Workspace permission routes verified. Confidence: HIGH.
- MLflow `mlflow/server/auth/sqlalchemy_store.py` — All workspace store methods verified. Confidence: HIGH.
- MLflow `mlflow/server/auth/__init__.py` — Workspace permission resolution, validators, feature gating verified. Confidence: HIGH.
- MLflow `mlflow/server/auth/db/models.py` — `SqlWorkspacePermission` model verified. Confidence: HIGH.
- MLflow `mlflow/server/auth/config.py` — Workspace config options verified. Confidence: HIGH.
- MLflow `mlflow/server/auth/permissions.py` — Permission model (`READ`/`USE`/`EDIT`/`MANAGE`/`NO_PERMISSIONS`) verified. Confidence: HIGH.
- MLflow `mlflow/utils/workspace_utils.py` — `X-MLFLOW-WORKSPACE` header, `DEFAULT_WORKSPACE_NAME` verified. Confidence: HIGH.
- MLflow `mlflow/utils/workspace_context.py` — `ContextVar`-based workspace scoping verified. Confidence: HIGH.
- MLflow `mlflow/environment_variables.py` — `MLFLOW_ENABLE_WORKSPACES`, `MLFLOW_WORKSPACE`, `MLFLOW_WORKSPACE_STORE_URI` verified. Confidence: HIGH.
- MLflow 3.10 Release Notes (https://github.com/mlflow/mlflow/releases/tag/v3.10.0) — Confirmed "Organization Support" maps to workspace implementation. Confidence: HIGH.
- OpenID Connect Core 1.0 (https://openid.net/specs/openid-connect-core-1_0.html) — Standard claims verified, no org claim exists. Confidence: HIGH.
- Current plugin codebase (grep for workspace/Workspace/WORKSPACE) — Zero references confirmed, no existing workspace support. Confidence: HIGH.

---
*Stack research for: MLflow OIDC Auth — Organization/Workspace Support*
*Researched: 2026-03-23*
