# Architecture Research

**Domain:** Multi-tenant organization/workspace support for an MLflow OIDC auth plugin
**Researched:** 2026-03-23
**Confidence:** HIGH

## System Overview

### Current Architecture (Before Workspaces)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ASGI Entry (Uvicorn)                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ProxyHeaders │→ │AuthMiddleware│→ │  FastAPI Router Layer     │  │
│  │  Middleware   │  │(Basic/Bearer │  │ (permissions, auth, UI,  │  │
│  │              │  │ /Session)    │  │  users, groups, health)  │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────────┘  │
│                           │                                         │
│          Sets: request.scope["mlflow_oidc_auth"]                    │
│                 = {username, is_admin}                               │
│                           │                                         │
├───────────────────────────┼─────────────────────────────────────────┤
│               AuthAwareWSGIMiddleware                               │
│          Copies scope["mlflow_oidc_auth"] → environ                 │
├───────────────────────────┼─────────────────────────────────────────┤
│                     Flask (MLflow App)                               │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ before_request│→ │ MLflow Core  │→ │    after_request         │  │
│  │  (validators) │  │ (experiments,│  │ (auto-grant, filter,     │  │
│  │              │  │  runs, models)│  │  cascade deletes)        │  │
│  └───────┬───────┘  └──────────────┘  └─────────────────────────┘  │
│          │                                                          │
│  ┌───────┴───────────────────────────────────────────────────────┐  │
│  │  Bridge: get_request_username() → environ["mlflow_oidc_auth"] │  │
│  └───────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                     Permission Resolution                            │
│  Configurable order: [user, group, regex, group-regex]              │
│  First match wins. Admin bypass.                                     │
├─────────────────────────────────────────────────────────────────────┤
│                     SqlAlchemyStore (Facade)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │UserRepo  │  │GroupRepo │  │PermRepos │  │RegexPermRepos    │   │
│  │          │  │          │  │(28 repos)│  │(group-regex, etc)│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                     SQLAlchemy + Alembic                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    SQLite / PostgreSQL                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Target Architecture (With Workspace Support)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ASGI Entry (Uvicorn)                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ProxyHeaders │→ │AuthMiddleware│→ │  FastAPI Router Layer     │  │
│  │  Middleware   │  │(Basic/Bearer │  │ + NEW: workspace_router  │  │
│  │              │  │ /Session)    │  │   (workspace CRUD,       │  │
│  │              │  │ +workspace   │  │    workspace permissions) │  │
│  │              │  │  extraction  │  │                          │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────────┘  │
│                           │                                         │
│          Sets: request.scope["mlflow_oidc_auth"]                    │
│                 = {username, is_admin, workspace}                    │
│                           │                    ▲                     │
│                           │     X-MLFLOW-WORKSPACE header           │
│                           │     or OIDC claim extraction             │
├───────────────────────────┼─────────────────────────────────────────┤
│               AuthAwareWSGIMiddleware                               │
│          Copies scope["mlflow_oidc_auth"] → environ                 │
│          (now includes workspace)                                    │
├───────────────────────────┼─────────────────────────────────────────┤
│                     Flask (MLflow App)                               │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ before_request│→ │ MLflow Core  │→ │    after_request         │  │
│  │ +workspace    │  │ (experiments,│  │ +workspace auto-grant    │  │
│  │  validation   │  │  runs, models)│  │ +workspace scoping      │  │
│  └───────┬───────┘  └──────────────┘  └─────────────────────────┘  │
│          │                                                          │
│  ┌───────┴───────────────────────────────────────────────────────┐  │
│  │  Bridge: get_request_username() + get_request_workspace()      │  │
│  └───────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                     Permission Resolution (UPDATED)                  │
│  OLD: [user, group, regex, group-regex] → first match wins          │
│  NEW: resource-level → workspace-level → default                     │
│       within resource-level: [user, group, regex, group-regex]      │
│       workspace adds a fallback layer before global default          │
├─────────────────────────────────────────────────────────────────────┤
│                     SqlAlchemyStore (Facade) — EXTENDED              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐  │
│  │UserRepo  │ │GroupRepo │ │PermRepos │ │NEW: WorkspaceRepo    │  │
│  │          │ │          │ │(28 repos)│ │WorkspacePermRepo     │  │
│  │          │ │          │ │+workspace│ │WorkspaceGroupRepo    │  │
│  │          │ │          │ │ column   │ │                      │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                     SQLAlchemy + Alembic                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │          SQLite / PostgreSQL                                  │   │
│  │  + workspaces table                                           │   │
│  │  + workspace_permissions table                                │   │
│  │  + workspace column on registered_model_permissions           │   │
│  │  + workspace_groups table (optional: workspace-scoped groups) │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Current Responsibility | Workspace Change |
|-----------|----------------------|------------------|
| AuthMiddleware | Authenticate user, set username + is_admin | Extract workspace from `X-MLFLOW-WORKSPACE` header or OIDC claim; add to auth context |
| AuthAwareWSGIMiddleware | Copy auth context from ASGI scope to WSGI environ | No code change needed — already copies entire `mlflow_oidc_auth` dict |
| Bridge (user.py) | Expose `get_request_username()` and `is_admin()` | Add `get_request_workspace()` function |
| before_request hooks | Map protobuf classes to validators, enforce RBAC | Add workspace validation for resource creation (MANAGE on workspace required) |
| after_request hooks | Auto-grant MANAGE on create, filter search results | Scope auto-grants to workspace; filter by workspace membership |
| Permission resolution | Ordered resolver: user → group → regex → group-regex | Add workspace-level fallback between resource-level and global default |
| SqlAlchemyStore | Facade over 20+ repos | Add workspace CRUD, workspace permission CRUD, workspace-scoped queries |
| Validators | Check user has required permission on resource | Accept workspace context; check workspace permission as fallback |
| GraphQL middleware | Authorize GraphQL queries | Pass workspace context; filter by workspace |
| FastAPI Routers | REST API for permission management | New workspace router; workspace parameter on existing permission endpoints |
| React SPA | Admin UI for users, groups, permissions | New workspace management feature; workspace switcher; workspace-scoped views |

## Recommended Project Structure

### New/Modified Backend Files

```
mlflow_oidc_auth/
├── bridge/
│   └── user.py                          # MODIFY: add get_request_workspace()
├── db/
│   └── models/
│       ├── workspace.py                 # NEW: SqlWorkspace model
│       ├── workspace_permission.py      # NEW: SqlWorkspacePermission model
│       └── registered_model_permission.py  # MODIFY: add workspace column
├── entities/
│   ├── workspace.py                     # NEW: Workspace entity dataclass
│   └── workspace_permission.py          # NEW: WorkspacePermission entity
├── models/
│   └── workspace.py                     # NEW: Pydantic models for workspace API
├── repository/
│   ├── workspace.py                     # NEW: WorkspaceRepository
│   └── workspace_permission.py          # NEW: WorkspacePermissionRepository
├── routers/
│   └── workspace.py                     # NEW: workspace_router (CRUD + permissions)
├── validators/
│   └── workspace.py                     # NEW: workspace access validators
├── hooks/
│   ├── before_request.py                # MODIFY: workspace-gated creation checks
│   └── after_request.py                 # MODIFY: workspace-scoped auto-grants & filters
├── middleware/
│   └── auth_middleware.py               # MODIFY: extract workspace from header/claim
├── utils/
│   ├── permissions.py                   # MODIFY: workspace fallback in resolution chain
│   └── workspace.py                     # NEW: workspace context utilities
├── config.py                            # MODIFY: add ENABLE_WORKSPACES config flag
└── sqlalchemy_store.py                  # MODIFY: add workspace-related store methods
```

### New/Modified Frontend Files

```
web-react/src/
├── features/
│   └── workspaces/                      # NEW: workspace management feature
│       ├── index.tsx
│       ├── components/
│       │   ├── workspace-list.tsx
│       │   ├── workspace-detail.tsx
│       │   ├── workspace-create.tsx
│       │   └── workspace-members.tsx
│       ├── hooks/
│       │   └── use-workspaces.ts
│       └── services/
│           └── workspace-api.ts
├── core/
│   ├── context/
│   │   └── workspace-context.tsx        # NEW: active workspace state
│   ├── components/
│   │   └── workspace-switcher.tsx       # NEW: workspace selector in nav
│   └── configs/
│       └── api-endpoints.ts             # MODIFY: add workspace endpoints
└── app.tsx                              # MODIFY: add workspace routes
```

### Structure Rationale

- **`bridge/user.py` extended (not new file):** Workspace context follows the same pattern as username — extracted from `environ["mlflow_oidc_auth"]`. One file, two concerns, minimal API surface.
- **`db/models/workspace.py` + `workspace_permission.py` as separate files:** Follows existing convention of one model per file. Workspace and workspace permissions are distinct entities.
- **`validators/workspace.py` new file:** Workspace access checks are conceptually separate from resource-level validators. Keeps single responsibility.
- **`utils/workspace.py` new file:** Constants (`DEFAULT_WORKSPACE_NAME`), feature flag checks (`is_workspaces_enabled()`), workspace resolution logic. Reused across middleware, hooks, validators.
- **Frontend `workspaces/` feature:** Follows existing feature-module convention (like `experiments/`, `groups/`). Self-contained with components, hooks, services.
- **Frontend `workspace-context.tsx`:** Global state for active workspace. All API calls include workspace header when context is set.

## Architectural Patterns

### Pattern 1: Feature-Gated Workspace Support

**What:** All workspace behavior is gated behind an `ENABLE_WORKSPACES` config flag (env var `MLFLOW_OIDC_AUTH_ENABLE_WORKSPACES`). When disabled, the system behaves identically to today — zero behavioral changes for existing deployments.

**When to use:** Always. This is the compatibility strategy.

**Trade-offs:**
- Pro: Zero risk to existing deployments; gradual rollout possible; easy to disable if issues arise
- Con: Every workspace code path needs `if workspaces_enabled` guards; slight code complexity increase

**Example:**
```python
# mlflow_oidc_auth/utils/workspace.py
from mlflow_oidc_auth.config import app_config

DEFAULT_WORKSPACE_NAME = "default"
WORKSPACE_HEADER_NAME = "X-MLFLOW-WORKSPACE"

def is_workspaces_enabled() -> bool:
    return app_config.enable_workspaces

def get_workspace_from_request(request) -> str:
    """Extract workspace from request header, defaulting to 'default'."""
    if not is_workspaces_enabled():
        return DEFAULT_WORKSPACE_NAME
    return request.headers.get(WORKSPACE_HEADER_NAME, DEFAULT_WORKSPACE_NAME)
```

### Pattern 2: Workspace as Permission Fallback Layer

**What:** Workspace permissions sit between resource-level permissions and the global default in the permission resolution chain. This matches upstream MLflow 3.10's approach exactly.

**When to use:** For all resource permission checks when workspaces are enabled.

**Trade-offs:**
- Pro: Aligns with upstream MLflow; workspace admins get blanket access without per-resource grants; reduces permission management overhead
- Con: Adds a query to the resolution chain (mitigated by caching); more complex to reason about "what permission does user X have?"

**Example:**
```python
# Conceptual flow in utils/permissions.py
def get_permission(username, resource_type, resource_id, workspace):
    # 1. Try resource-level (existing: user → group → regex → group-regex)
    resource_perm = get_resource_level_permission(username, resource_type, resource_id)
    if resource_perm is not None:
        return resource_perm

    # 2. NEW: Try workspace-level (if workspaces enabled)
    if is_workspaces_enabled() and workspace:
        workspace_perm = get_workspace_permission(username, workspace)
        if workspace_perm is not None:
            return workspace_perm

    # 3. Fall back to configured default
    return get_default_permission()
```

### Pattern 3: Upstream-Compatible Data Model

**What:** Mirror MLflow 3.10's workspace data model in the plugin's own database, using the same entity names and column structures. This ensures the plugin can interoperate with upstream MLflow's workspace features if/when MLflow exposes workspace management APIs.

**When to use:** For all new workspace-related DB schemas.

**Trade-offs:**
- Pro: Future-proof; reduces impedance mismatch if upstream MLflow evolves; familiar to MLflow contributors
- Con: May include columns/fields we don't immediately need; constrains our schema design choices

**Key upstream models to mirror:**

| Upstream MLflow Model | Plugin Equivalent | Notes |
|----------------------|-------------------|-------|
| `SqlWorkspacePermission` (workspace, user_id, permission) | `SqlWorkspacePermission` (workspace, user_id, permission) | Same composite PK |
| `workspace` column on `SqlRegisteredModelPermission` | `workspace` column on plugin's model permission | Nullable, defaults to "default" |
| `DEFAULT_WORKSPACE_NAME = "default"` | Same constant | All existing resources belong to "default" |

### Pattern 4: Header-Based Workspace Propagation (Not URL-Based)

**What:** Workspace context travels via `X-MLFLOW-WORKSPACE` HTTP header, not URL path segments. This matches upstream MLflow 3.10's approach and avoids breaking the MLflow client SDK's URL structure.

**When to use:** All API requests that need workspace scoping.

**Trade-offs:**
- Pro: No URL changes needed; MLflow client SDK remains compatible; middleware can inject header transparently
- Con: Less visible in logs/URLs; requires all clients to set the header; easy to forget

**Why not URL-based:** MLflow's API URLs are defined by protobuf service definitions (e.g., `/api/2.0/mlflow/experiments/create`). The plugin cannot change these URLs without breaking MLflow client compatibility. Header-based scoping is the only viable approach.

## Data Flow

### Request Flow (With Workspaces)

```
Client Request (with X-MLFLOW-WORKSPACE: "team-alpha")
    ↓
ProxyHeadersMiddleware (no change)
    ↓
AuthMiddleware
    → Authenticate user (Basic/Bearer/Session) — existing
    → Extract workspace from X-MLFLOW-WORKSPACE header — NEW
    → Set scope["mlflow_oidc_auth"] = {username, is_admin, workspace} — MODIFIED
    ↓
Route Match?
    ├── FastAPI route → Router handles directly (workspace in request context)
    └── MLflow route → AuthAwareWSGIMiddleware
                           ↓
                       Flask environ["mlflow_oidc_auth"] = {username, is_admin, workspace}
                           ↓
                       before_request hook
                           → get_request_workspace() from environ — NEW
                           → Validator checks:
                              1. Is user admin? → bypass
                              2. Resource-level permission? → allow/deny
                              3. Workspace-level permission? → allow/deny — NEW
                              4. Global default → allow/deny
                           ↓
                       MLflow processes request
                           ↓
                       after_request hook
                           → Auto-grant includes workspace context — NEW
                           → Search filter respects workspace boundaries — NEW
```

### Permission Resolution Flow (Updated)

```
validate_can_read_experiment(experiment_id)
    ↓
username = get_request_username()
workspace = get_request_workspace()  ← NEW
    ↓
┌─ Resource-Level Resolution (existing, unchanged) ─────────┐
│  For resolver in configured_order [user, group, regex, …]: │
│    permission = resolver.check(username, experiment_id)     │
│    if permission found → return permission                  │
└────────────────────────────────────────────────────────────┘
    ↓ (no resource-level permission found)
┌─ Workspace-Level Resolution (NEW) ────────────────────────┐
│  if workspaces_enabled AND workspace != None:              │
│    wp = store.get_workspace_permission(workspace, user_id) │
│    if wp found → return wp.permission                      │
└────────────────────────────────────────────────────────────┘
    ↓ (no workspace-level permission found)
┌─ Global Default ──────────────────────────────────────────┐
│  return app_config.default_permission  (e.g., READ)        │
└────────────────────────────────────────────────────────────┘
```

### Workspace Context Extraction Flow

```
Request arrives
    ↓
┌─ Source 1: X-MLFLOW-WORKSPACE header ─────────────┐
│  Most common. Set by MLflow client SDK or manually. │
│  Direct, explicit.                                   │
└───────────────────────────────────────────────────────┘
    ↓ (header not present)
┌─ Source 2: OIDC claim mapping (optional) ─────────┐
│  Map OIDC "org" or "workspace" claim to workspace. │
│  Configured via MLFLOW_OIDC_AUTH_WORKSPACE_CLAIM.   │
│  Useful for SSO-driven workspace assignment.        │
└───────────────────────────────────────────────────────┘
    ↓ (no claim or no mapping configured)
┌─ Source 3: Default workspace ─────────────────────┐
│  Fall back to "default" workspace.                  │
│  All pre-existing resources live here.              │
└───────────────────────────────────────────────────────┘
```

### Key Data Flows

1. **Workspace creation:** Admin calls `POST /api/2.0/mlflow/workspaces` → FastAPI workspace router → WorkspaceRepository.create() → DB insert. Creator gets MANAGE permission auto-granted.
2. **Resource creation in workspace:** Client sets `X-MLFLOW-WORKSPACE: team-alpha` + `POST /api/2.0/mlflow/experiments/create` → before_request checks user has MANAGE on workspace "team-alpha" → MLflow creates experiment → after_request auto-grants MANAGE scoped to workspace.
3. **Cross-workspace search filtering:** User lists experiments → after_request filter removes experiments from workspaces where user has NO_PERMISSIONS or no workspace access.
4. **Workspace permission grant:** Admin calls workspace permissions API → WorkspacePermissionRepository.create() → User now has fallback permission level for all resources in that workspace.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 workspaces | No special handling. "default" workspace covers single-tenant. All queries fast. |
| 10-100 workspaces | Add DB indexes on workspace columns. Cache workspace memberships in memory (TTLCache, matching upstream pattern). |
| 100+ workspaces | Consider read replicas for permission checks. Workspace permission cache becomes critical. May need workspace-partitioned permission tables. |

### Scaling Priorities

1. **First bottleneck — permission resolution queries:** Adding workspace as a fallback layer means one additional DB query per request when no resource-level permission matches. **Mitigation:** TTLCache on workspace permissions (upstream MLflow uses this exact strategy with `cachetools.TTLCache`). Cache key: `(workspace, user_id)`. TTL: 30-60 seconds.
2. **Second bottleneck — search result filtering:** Filtering results by workspace membership requires knowing which workspaces a user belongs to. **Mitigation:** Cache user's workspace memberships at authentication time (in the auth context dict). Avoids per-result DB lookups.

## Anti-Patterns

### Anti-Pattern 1: Workspace as URL Path Segment

**What people do:** Add `/workspace/{workspace_id}/` prefix to all API URLs (e.g., `/api/2.0/mlflow/workspace/team-alpha/experiments/list`).
**Why it's wrong:** MLflow client SDK generates URLs from protobuf definitions. Changing URL structure breaks all existing MLflow clients. The plugin cannot control client-side URL generation.
**Do this instead:** Use `X-MLFLOW-WORKSPACE` header. Clients set it once; all subsequent calls are scoped. Transparent to MLflow client SDK.

### Anti-Pattern 2: Hard Workspace Isolation (No Cross-Workspace Access)

**What people do:** Treat workspaces as absolute security boundaries where resources can NEVER be accessed from another workspace context.
**Why it's wrong:** Legitimate use cases exist: shared models, cross-team experiments, platform-wide scorers. Hard isolation forces resource duplication.
**Do this instead:** Workspace-level permissions control default access. Resource-level permissions can explicitly grant cross-workspace access. Admin can mark specific resources as "shared" across workspaces.

### Anti-Pattern 3: Duplicating Upstream MLflow's Workspace Store

**What people do:** Create a separate parallel workspace store in the plugin that duplicates MLflow's `_get_workspace_store()` functionality.
**Why it's wrong:** MLflow 3.10 has its own workspace store (`MLFLOW_WORKSPACE_STORE_URI`). Duplicating it creates two sources of truth for workspace→resource mappings.
**Do this instead:** The plugin should manage workspace *permissions* (who can access which workspace) and *metadata* (workspace display names, OIDC claim mappings). Let upstream MLflow manage workspace→resource mappings. The plugin's job is authorization, not resource cataloging.

### Anti-Pattern 4: Workspace-Scoping All 28 Permission Tables

**What people do:** Add a `workspace` column to every single permission table (28 tables × 4 variants = 112 column additions).
**Why it's wrong:** Most resource types (experiments, prompts, scorers) don't have workspace scoping in upstream MLflow. Only registered models have a `workspace` column upstream. Adding workspace to all tables is premature and creates massive migration complexity.
**Do this instead:** Follow upstream MLflow's lead: add `workspace` column only to registered model permissions initially. Use workspace-level permissions as the general fallback mechanism. Expand per-resource workspace scoping later if upstream MLflow adds it.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OIDC Provider | Workspace claim extraction from ID token | Optional. Configure via `MLFLOW_OIDC_AUTH_WORKSPACE_CLAIM` env var. Maps OIDC claim (e.g., `org`, `groups`) to workspace name. |
| MLflow Client SDK | `X-MLFLOW-WORKSPACE` header injection | Clients must be configured to send the header. Python SDK: set via `mlflow.set_workspace()` or env var `MLFLOW_WORKSPACE`. |
| Upstream MLflow Auth | Workspace permission resolution | Plugin replaces upstream's `_get_permission_from_store_or_default` with its own enhanced version that adds group/regex/group-regex resolution. Must preserve upstream's workspace fallback behavior. |
| MLflow Workspace Store | Resource→workspace mapping | Plugin does NOT manage this. Upstream MLflow maps resources to workspaces via `MLFLOW_WORKSPACE_STORE_URI`. Plugin queries this mapping for authorization decisions. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| AuthMiddleware → Bridge | ASGI scope dict → WSGI environ dict | `workspace` field added to existing `mlflow_oidc_auth` dict. AuthAwareWSGIMiddleware copies dict wholesale — no code change needed on the bridge transport. |
| Bridge → Validators | Python function call (`get_request_workspace()`) | New function in `bridge/user.py`. Same pattern as `get_request_username()`. |
| Validators → Permission Resolution | Python function call | `get_permission_from_store_or_default()` gains optional `workspace` parameter. Backward-compatible: defaults to None (no workspace fallback). |
| Permission Resolution → Store | Python function call | New store methods: `get_workspace_permission(workspace, user_id)`, `list_workspace_permissions(workspace)`, `create_workspace_permission(...)`, etc. |
| FastAPI Routers → Store | Python function call | New workspace router calls store directly, same pattern as existing permission routers. |
| Frontend → Backend | HTTP REST API | New endpoints under `/api/2.0/mlflow/workspaces/`. Workspace context sent via header on all requests. |

## Migration Strategy

### Database Migration Plan

**Phase 1 — Additive only (no breaking changes):**

```sql
-- New tables
CREATE TABLE workspaces (
    name VARCHAR(255) PRIMARY KEY,
    display_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workspace_permissions (
    workspace VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL,
    permission VARCHAR(255) NOT NULL,
    PRIMARY KEY (workspace, user_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Seed default workspace
INSERT INTO workspaces (name, display_name) VALUES ('default', 'Default Workspace');
```

**Phase 2 — Extend registered model permissions:**

```sql
-- Add nullable workspace column (backward-compatible)
ALTER TABLE registered_model_permissions
    ADD COLUMN workspace VARCHAR(255) DEFAULT 'default';

-- Update unique constraint to include workspace
-- (requires migration: drop old constraint, add new one)
```

**Phase 3 — Optional: workspace-scoped groups:**

```sql
-- Groups can optionally belong to a workspace
ALTER TABLE groups ADD COLUMN workspace VARCHAR(255) DEFAULT NULL;
-- NULL = global group (backward-compatible)
-- Non-null = workspace-scoped group
```

### Existing Deployment Migration Path

1. **Before upgrade:** All resources implicitly belong to "default" workspace. No workspace awareness.
2. **After upgrade (workspaces disabled):** Feature flag off. Zero behavioral changes. Migration creates tables but they're unused.
3. **After enabling workspaces:** All existing resources are in "default" workspace. All existing users have no workspace permissions (fall through to global default, preserving current behavior). Admins explicitly create new workspaces and assign permissions.
4. **No data loss:** Existing permission tables unchanged. New tables are additive.

## Alignment with Upstream MLflow 3.10

### What Upstream MLflow 3.10 Provides

| Feature | Status | Plugin Interaction |
|---------|--------|-------------------|
| `MLFLOW_ENABLE_WORKSPACES` env var | Upstream controls this | Plugin should respect it AND have its own flag |
| `X-MLFLOW-WORKSPACE` header | Upstream reads this | Plugin extracts and validates before upstream sees it |
| `WorkspacePermission` entity | Upstream defines it | Plugin uses its own enhanced version (adds group support) |
| `SqlWorkspacePermission` table | Upstream owns this table | Plugin creates a parallel table in its own DB (different store URI) |
| Workspace permission resolution | Upstream has basic user-level only | Plugin extends with group/regex/group-regex fallback |
| Resource creation gating | Upstream checks MANAGE on workspace | Plugin does this in before_request hooks (intercepts before upstream) |
| Workspace store (`MLFLOW_WORKSPACE_STORE_URI`) | Upstream manages resource→workspace mapping | Plugin does NOT duplicate — queries upstream's store for workspace membership |
| `workspace_context` ContextVar | Upstream sets per-request | Plugin may need to also set this for upstream compatibility |

### Plugin's Value-Add Over Upstream

The plugin extends upstream's workspace model with capabilities upstream lacks:

1. **Group-level workspace permissions:** Upstream only has user-level workspace permissions. Plugin adds group-level (assign entire groups to workspaces).
2. **OIDC claim-based workspace assignment:** Upstream requires explicit header. Plugin can auto-derive workspace from OIDC identity provider claims.
3. **Workspace management UI:** Upstream has no UI for workspace administration. Plugin's React SPA adds workspace CRUD, member management, permission visualization.
4. **Regex-based workspace permissions:** Plugin's regex permission pattern could extend to workspace-level (e.g., grant READ to all workspaces matching `team-*`).

## Build Order Implications

Based on architecture analysis, the recommended build order is:

### Phase 1: Foundation (Lowest Risk, Highest Dependency)
**Build:** Feature flag, workspace config, workspace DB model + migration, bridge extension, workspace utility module.
**Rationale:** Everything else depends on the workspace concept existing in the system. Additive changes only — nothing breaks.

### Phase 2: Backend Core (Permission Model)
**Build:** Workspace permission entity/model/repo, workspace permission resolution (fallback layer), workspace-level store methods.
**Rationale:** Permission resolution is the core of the plugin. Getting this right before building APIs on top is critical.

### Phase 3: Backend API (Workspace Management)
**Build:** Workspace CRUD router, workspace permission management router, before_request workspace validation, after_request workspace scoping.
**Rationale:** Needs Phase 1 + 2. Enables testing of workspace behavior via API before building UI.

### Phase 4: Frontend (Workspace UI)
**Build:** Workspace context/switcher, workspace management feature, workspace-scoped permission views.
**Rationale:** Needs backend API (Phase 3) to function. Last in chain but high user-visibility.

### Phase 5: Advanced Features (OIDC Integration, Cross-Workspace)
**Build:** OIDC claim→workspace mapping, shared resources across workspaces, workspace-scoped groups.
**Rationale:** Optional enhancements after core workspace support is stable.

## Sources

- Upstream MLflow 3.10 source code: `mlflow/server/auth/` module (entities.py, routes.py, sqlalchemy_store.py, db/models.py, __init__.py)
- Upstream MLflow workspace utilities: `mlflow/utils/workspace_utils.py`, `mlflow/utils/workspace_context.py`
- Upstream MLflow environment variables: `mlflow/environment_variables.py` (MLFLOW_ENABLE_WORKSPACES, MLFLOW_WORKSPACE)
- MLflow 3.10 release: https://github.com/mlflow/mlflow/releases/tag/v3.10.0
- Existing plugin codebase analysis: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`
- Confidence: HIGH — based on direct source code analysis of both upstream MLflow and the plugin

---
*Architecture research for: Multi-tenant workspace support in mlflow-oidc-auth*
*Researched: 2026-03-23*
