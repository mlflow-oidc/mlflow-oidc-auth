# Architecture

**Analysis Date:** 2026-03-23

## Pattern Overview

**Overall:** Dual-Framework ASGI/WSGI Hybrid — FastAPI wraps MLflow's Flask app

**Key Characteristics:**
- FastAPI (ASGI) handles authentication, OIDC flows, permission management API, and UI serving
- Flask (WSGI) handles core MLflow tracking API (experiments, runs, models, etc.) via MLflow's native app
- Flask app is mounted inside FastAPI via `AuthAwareWSGIMiddleware` (ASGI-to-WSGI bridge)
- Auth context flows from FastAPI middleware → ASGI scope → WSGI environ → Flask request.environ
- Plugin-based integration: installed as an MLflow app plugin via entry point `mlflow.app`
- Repository pattern for data access with SQLAlchemy ORM and Alembic migrations
- Chain-of-responsibility pattern for configuration providers (secrets managers, env vars)

## Layers

**FastAPI Application Layer:**
- Purpose: HTTP entry point, OIDC auth flows, permission management REST API, React SPA serving
- Location: `mlflow_oidc_auth/app.py`
- Contains: App factory (`create_app`), middleware stack setup, router registration, Flask app mounting
- Depends on: Routers, Middleware, Config, Store, OAuth
- Used by: ASGI server (uvicorn via MLflow CLI)

**Middleware Layer:**
- Purpose: Authentication, proxy header handling, session management, WSGI bridging, workspace context
- Location: `mlflow_oidc_auth/middleware/`
- Contains: `AuthMiddleware`, `AuthAwareWSGIMiddleware`, `ProxyHeadersMiddleware`, `WorkspaceContextMiddleware`
- Depends on: Config, Store, Auth (JWT validation), Bridge
- Used by: FastAPI app (applied in order during `create_app`)

**Router Layer (FastAPI):**
- Purpose: REST API endpoints for permissions, users, groups, auth flows, health, UI, workspaces
- Location: `mlflow_oidc_auth/routers/`
- Contains: 18 routers — auth, experiment_permissions, group_permissions, prompt_permissions, registered_model_permissions, scorers_permissions, gateway_endpoint_permissions, gateway_secret_permissions, gateway_model_definition_permissions, health, trash, ui, user_permissions, users, webhook, workspace_crud, workspace_permissions, workspace_regex_permissions
- Depends on: Store, Config, Models (Pydantic), Utils, Dependencies
- Used by: FastAPI app (registered in `create_app`)

**Hooks Layer (Flask before/after request):**
- Purpose: RBAC enforcement on MLflow's native Flask endpoints
- Location: `mlflow_oidc_auth/hooks/`
- Contains: `before_request.py` (~567 lines) maps MLflow protobuf request classes to validator functions; `after_request.py` (~663 lines) handles post-request actions (auto-grant MANAGE on create, filter search results, cascade permission deletes, workspace-level filtering)
- Depends on: Validators, Store, Bridge, Config, Permissions
- Used by: Flask app (registered as `before_request` and `after_request` hooks)

**Validators Layer:**
- Purpose: Per-resource permission checking logic
- Location: `mlflow_oidc_auth/validators/`
- Contains: Validator functions for experiments, registered models, prompts, scorers, gateway endpoints/secrets/model definitions, workspaces
- Depends on: Store, Bridge, Permissions, Utils
- Used by: Hooks layer (before_request dispatches to validators)

**GraphQL Authorization Layer:**
- Purpose: Authorization middleware for MLflow's `/graphql` endpoint
- Location: `mlflow_oidc_auth/graphql/`
- Contains: Custom authorization middleware that intercepts GraphQL queries
- Depends on: Bridge, Store, Permissions
- Used by: Flask app (via MLflow's GraphQL integration)

**Bridge Layer:**
- Purpose: Retrieves FastAPI auth context from Flask's WSGI environ
- Location: `mlflow_oidc_auth/bridge/`
- Key file: `mlflow_oidc_auth/bridge/user.py`
- Contains: `get_request_username()` extracts username from `request.environ["mlflow_oidc_auth"]`
- Depends on: Flask request context
- Used by: Hooks, Validators, GraphQL layer

**Data Access Layer (Store):**
- Purpose: All database operations for users, groups, permissions
- Location: `mlflow_oidc_auth/sqlalchemy_store.py` (main), `mlflow_oidc_auth/store.py` (singleton)
- Contains: `SqlAlchemyStore` class (~1474 lines) delegates to 30+ repository classes
- Depends on: Repository classes, DB models, Entities, SQLAlchemy, Alembic
- Used by: Routers, Hooks, Validators, Middleware

**Repository Layer:**
- Purpose: Individual CRUD operations per entity type
- Location: `mlflow_oidc_auth/repository/`
- Contains: 30+ repository classes (UserRepository, GroupRepository, ExperimentPermissionRepository, RegisteredModelRegexPermissionRepository, WorkspacePermissionRepository, etc.)
- Depends on: DB models, Entities, SQLAlchemy session
- Used by: SqlAlchemyStore

**Database Models Layer:**
- Purpose: SQLAlchemy ORM table definitions
- Location: `mlflow_oidc_auth/db/models/`
- Contains: ORM models for all entities (users, groups, user_groups, experiment_permissions, registered_model_permissions, prompt_permissions, scorer_permissions, gateway_*_permissions, workspace_permissions, plus regex and group-regex variants of each)
- Depends on: SQLAlchemy declarative base
- Used by: Repository classes, Alembic migrations

**Domain Entities Layer:**
- Purpose: Plain Python dataclasses representing domain objects (decoupled from ORM)
- Location: `mlflow_oidc_auth/entities/`
- Contains: Entity classes matching each DB model
- Depends on: Nothing (pure data classes)
- Used by: Store, Routers, Validators

**Pydantic Models Layer:**
- Purpose: Request/response validation for FastAPI endpoints
- Location: `mlflow_oidc_auth/models/`
- Contains: Pydantic BaseModel classes for API input/output
- Depends on: Pydantic
- Used by: Routers

**Configuration Layer:**
- Purpose: Application configuration with pluggable secret providers
- Location: `mlflow_oidc_auth/config.py` (AppConfig), `mlflow_oidc_auth/config_providers/` (providers)
- Contains: `AppConfig` dataclass, `ConfigManager` singleton with chain-of-responsibility provider resolution
- Depends on: Config providers (AWS Secrets Manager, AWS Parameter Store, Azure Key Vault, HashiCorp Vault, Kubernetes Secrets, Environment Variables)
- Used by: All layers

**Frontend Layer (React SPA):**
- Purpose: Admin UI for managing permissions, users, groups
- Location: `web-react/`
- Contains: React 19 + TypeScript + Vite + TailwindCSS application
- Depends on: FastAPI REST API (via fetch with cookie-based sessions)
- Used by: End users via browser, served from `/oidc/ui/` by FastAPI `ui_router`

## Data Flow

**OIDC Login Flow:**

1. User navigates to `/oidc/ui/` → FastAPI serves React SPA
2. React app redirects to `/oidc/login` → `auth_router` initiates OIDC flow
3. OIDC provider redirects back to `/oidc/callback` → `auth_router` validates tokens
4. Server creates/updates user in DB, sets session cookie
5. React app loads, fetches `/oidc/auth-status` to confirm authentication

**Authenticated MLflow API Request:**

1. Client sends request to MLflow API endpoint (e.g., `GET /api/2.0/mlflow/experiments/list`)
2. `ProxyHeadersMiddleware` processes proxy headers
3. `AuthMiddleware` authenticates via Basic Auth / Bearer Token / Session → sets `request.state.username` and `request.scope["mlflow_oidc_auth"]`
4. `AuthAwareWSGIMiddleware` bridges ASGI scope to WSGI environ (copies `mlflow_oidc_auth` key)
5. Flask `before_request` hook fires → maps request to validator function → checks user permissions against DB
6. If authorized, MLflow processes the request normally
7. Flask `after_request` hook fires → may auto-grant permissions (on create), filter results (on search), or cascade deletes

**Permission Management API Request:**

1. Client sends request to permission API (e.g., `POST /api/2.0/mlflow/experiments/permissions`)
2. `AuthMiddleware` authenticates user
3. FastAPI router handles request directly (no Flask involvement)
4. Router calls `SqlAlchemyStore` methods to read/write permissions
5. Response returned to client

**Permission Resolution:**

1. Validator receives resource ID and username
2. Resolution order (configurable): `["user", "group", "regex", "group-regex"]`
3. For each resolver in order: check if a matching permission exists
4. First match wins (highest priority in configured order)
5. Permission levels: `READ` < `USE` < `EDIT` < `MANAGE` < `NO_PERMISSIONS`
6. Admin users bypass all permission checks

**State Management (Frontend):**
- React Context for global state (auth status, config)
- React Query / SWR patterns via custom hooks in `core/hooks/`
- Runtime config loaded from `/oidc/ui/config.json` endpoint at startup
- Protected routes via `ProtectedRoute` component; admin routes for trash/webhooks

## Key Abstractions

**Permission:**
- Purpose: Represents an access level for a resource
- Definition: `mlflow_oidc_auth/permissions.py`
- Values: `READ`, `USE`, `EDIT`, `MANAGE`, `NO_PERMISSIONS` (priority-ordered dataclass)
- Pattern: Comparable via priority field for permission level checks

**SqlAlchemyStore:**
- Purpose: Central data access facade — all DB operations go through this
- Definition: `mlflow_oidc_auth/sqlalchemy_store.py`
- Singleton: `mlflow_oidc_auth/store.py` (module-level `store` instance)
- Pattern: Facade over 30+ repository classes, each handling one entity type

**AppConfig:**
- Purpose: Immutable application configuration
- Definition: `mlflow_oidc_auth/config.py`
- Pattern: Dataclass populated by `ConfigManager` from pluggable providers

**ConfigManager:**
- Purpose: Resolves configuration values from multiple secret backends
- Definition: `mlflow_oidc_auth/config_providers/manager.py`
- Pattern: Chain-of-responsibility — tries AWS Secrets Manager, AWS Parameter Store, Azure Key Vault, HashiCorp Vault, Kubernetes Secrets, then Environment Variables (fallback)
- Extensible: Custom providers via `mlflow_oidc_auth.config_provider` entry point

**AuthAwareWSGIMiddleware:**
- Purpose: Bridges FastAPI (ASGI) to Flask (WSGI) while preserving auth context
- Definition: `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py`
- Pattern: Extends standard ASGI-to-WSGI middleware, copies `mlflow_oidc_auth` from ASGI scope to WSGI environ

**Bridge (get_request_username):**
- Purpose: Retrieves authenticated username inside Flask request context
- Definition: `mlflow_oidc_auth/bridge/user.py`
- Pattern: Reads from `flask.request.environ["mlflow_oidc_auth"]`

## Entry Points

**MLflow Plugin Entry Point:**
- Location: `pyproject.toml` → `[project.entry-points."mlflow.app"]`
- Value: `oidc-auth = "mlflow_oidc_auth.app:app"`
- Triggers: `mlflow server --app-name oidc-auth`
- Responsibilities: MLflow loads `mlflow_oidc_auth.app:app` as the ASGI application

**CLI Entry Point:**
- Location: `mlflow_oidc_auth/cli.py`
- Command: `mlflow-oidc-server`
- Triggers: Installed as console script via pyproject.toml
- Responsibilities: Wraps `mlflow server --app-name oidc-auth` with additional CLI options

**FastAPI App Factory:**
- Location: `mlflow_oidc_auth/app.py` → `create_app()`
- Triggers: Called when MLflow loads the plugin
- Responsibilities: Creates FastAPI app, configures middleware stack, registers all routers, creates MLflow Flask app, mounts Flask via `AuthAwareWSGIMiddleware`, runs DB migrations, creates default admin user

**React SPA Entry:**
- Location: `web-react/src/main.tsx`
- Triggers: Browser loads `/oidc/ui/`
- Responsibilities: Renders React app with router, context providers

## Error Handling

**Strategy:** Layered exception handling with FastAPI exception handlers

**Patterns:**
- FastAPI exception handlers registered in `mlflow_oidc_auth/exceptions.py` for `HTTPException`, `MlflowException`, and generic `Exception`
- MLflow exceptions (e.g., `ResourceDoesNotExist`) are caught and mapped to appropriate HTTP status codes
- Hooks layer raises `HTTPException` (403/401) when permission checks fail
- Validators return boolean or raise exceptions on authorization failure
- Frontend handles HTTP errors in the shared HTTP client (`web-react/src/core/services/http.ts`)

## Cross-Cutting Concerns

**Logging:**
- Custom logger setup in `mlflow_oidc_auth/logger.py`
- Used throughout backend via standard Python logging

**Validation:**
- FastAPI Pydantic models for request/response validation on permission management API
- MLflow's own protobuf-based validation for core MLflow API endpoints
- Frontend form validation in React components

**Authentication:**
- Multi-method: OIDC, Basic Auth, Bearer Token (JWT), Session cookies
- `AuthMiddleware` handles all methods, sets unified auth context
- JWT validation via OIDC provider's JWKS endpoint (`mlflow_oidc_auth/auth.py`)
- OAuth client configured in `mlflow_oidc_auth/oauth.py` using authlib

**Authorization:**
- RBAC with configurable permission resolution order
- Permission types: user-level, group-level, regex (pattern-matched), group-regex
- Admin users bypass all checks
- Enforced in Flask hooks (before_request) for MLflow API
- Enforced in FastAPI route dependencies for permission management API
- GraphQL authorization middleware for `/graphql` endpoint

**Database Migrations:**
- Alembic manages schema migrations
- Migrations run automatically on app startup in `create_app()`
- Migration scripts in `mlflow_oidc_auth/db/migrations/versions/`

**UI Menu Injection:**
- `mlflow_oidc_auth/hack.py` injects navigation links into MLflow's built-in UI HTML
- Adds "Sign In" / "Sign Out" and permission management links to MLflow's navbar

## Workspace Permission Enforcement

Workspaces provide multi-tenant resource isolation, gated by the `MLFLOW_ENABLE_WORKSPACES` feature flag (default `False`). When enabled, all workspace access requires explicit permission grants — there are no implicit grants for any workspace, including the "default" workspace.

### Permission Model

Workspace permissions use the same `Permission` dataclass as resource permissions:

| Permission       | Priority | `can_read` | `can_manage` | Meaning                            |
|------------------|----------|------------|--------------|-------------------------------------|
| `READ`           | 1        | `True`     | `False`      | Can view workspace and its resources|
| `USE`            | 2        | `True`     | `False`      | Can use workspace resources         |
| `EDIT`           | 3        | `True`     | `False`      | Can modify workspace resources      |
| `MANAGE`         | 4        | `True`     | `True`       | Full control including permission grants |
| `NO_PERMISSIONS` | 100      | `False`    | `False`      | Explicit denial — not `None`        |

**Critical distinction:** `NO_PERMISSIONS` is a valid permission object (not `None`) with `can_read=False`. All enforcement points must check `perm.can_read` or `perm.can_manage`, not just `perm is not None`.

### Enforcement Layers

There are 5 enforcement layers, each serving a different purpose:

**Layer 1 — WorkspaceContextMiddleware** (`middleware/workspace_context_middleware.py`)
- Purpose: Sets MLflow's workspace `ContextVar` from `X-MLFLOW-WORKSPACE` request header
- Auth checks: **None** — only context propagation
- Applies to: All requests when `MLFLOW_ENABLE_WORKSPACES=True`

**Layer 2 — Before-request validators** (`hooks/before_request.py` + `validators/workspace.py`)
- Purpose: Authorize access to workspace RPC endpoints (`GetWorkspace`, `UpdateWorkspace`, `DeleteWorkspace`, `ListWorkspaces`, `CreateWorkspace`)
- Key function: `validate_can_read_workspace()` checks `perm is not None and perm.can_read`; `validate_can_manage_workspace()` checks `perm is not None and perm.can_manage`
- Workspace name extracted from Flask `request.path` (e.g., `/api/3.0/mlflow/workspaces/<name>`)
- Admin bypass: Admins skip all workspace permission checks

**Layer 3 — Before-request workspace creation gating** (`hooks/before_request.py` lines 479-492)
- Purpose: Prevent resource creation (`CreateExperiment`, `CreateRegisteredModel`) in workspaces the user cannot manage
- Check: `get_workspace_permission_cached(username, workspace_name)` → `ws_perm.can_manage`
- Only fires when `MLFLOW_ENABLE_WORKSPACES=True` and a workspace context is set

**Layer 4 — After-request filtering** (`hooks/after_request.py`)
- Purpose: Filter search/list results to only include resources in workspaces the user can access
- Key function: `_can_access_workspace(username, workspace_name)` → `perm is not None and perm.can_read`
- Filters applied to:
  - `SearchExperiments` — removes experiments in inaccessible workspaces
  - `SearchRegisteredModels` — removes models in inaccessible workspaces
  - `SearchLoggedModels` — removes logged models in inaccessible workspaces
  - `ListWorkspaces` — `_filter_list_workspaces()` removes workspaces where user has no `can_read` permission
- Admin bypass: Admins see all results unfiltered

**Layer 5 — FastAPI route dependencies** (`dependencies.py`)
- Purpose: Protect workspace CRUD and permission management API routes
- `check_workspace_manage_permission` — requires `perm.can_manage` (used for create/update/delete permissions)
- `check_workspace_read_permission` — requires `perm.can_read` (used for listing workspace permissions)
- Applied via FastAPI `Depends()` on workspace router endpoints

### Permission Resolution Flow

Workspace permissions are resolved through a cached, configurable resolution chain:

1. **Cache lookup** (`utils/workspace_cache.py`): TTL-based cache keyed by `(username, workspace_name)`
2. **Resolution order** (configured via `PERMISSION_SOURCE_ORDER`, default `["user", "group", "regex", "group-regex"]`):
   - `user` — Direct user→workspace permission in `SqlWorkspacePermission`
   - `group` — User's groups → workspace permission in `SqlWorkspaceGroupPermission` (highest priority wins)
   - `regex` — User's regex patterns matched against workspace name in `SqlWorkspaceRegexPermission`
   - `group-regex` — User's groups' regex patterns in `SqlWorkspaceGroupRegexPermission`
3. **First match wins**: Resolution stops at the first source that returns a permission
4. **No match**: Returns `None` (treated as "no access" at all enforcement points)

### Cache Invalidation Strategy

- **User permission CUD**: Targeted invalidation — only the affected `(username, workspace_name)` entry
- **Group permission CUD**: Targeted invalidation of all users in the affected group
- **Regex permission CUD**: Full cache flush — regex changes can affect any user/workspace pair
- **Group membership changes**: Targeted invalidation of affected user entries
- **TTL expiry**: Configurable via `OIDC_WORKSPACE_CACHE_TTL` (default 300 seconds)

### OIDC Auto-Assign

When a user logs in via OIDC (`auth.py`), the system can auto-assign workspace permissions using `OIDC_WORKSPACE_DEFAULT_PERMISSION` (default `"NO_PERMISSIONS"`). This controls what permission level new users receive for workspaces during the OIDC callback flow. Setting this to `"NO_PERMISSIONS"` means new users get no workspace access until explicitly granted by an admin.

### Configuration Variables

| Variable                          | Default            | Purpose                                                |
|-----------------------------------|--------------------|--------------------------------------------------------|
| `MLFLOW_ENABLE_WORKSPACES`        | `False`            | Master feature flag for workspace support              |
| `OIDC_WORKSPACE_DEFAULT_PERMISSION` | `"NO_PERMISSIONS"` | Permission level auto-assigned during OIDC login       |
| `PERMISSION_SOURCE_ORDER`         | `["user", "group", "regex", "group-regex"]` | Resolution chain order |
| `OIDC_WORKSPACE_CACHE_TTL`        | `300`              | Cache TTL in seconds                                   |
| `OIDC_WORKSPACE_CACHE_MAXSIZE`    | `1024`             | Maximum cache entries                                  |

---

*Architecture analysis: 2026-03-23 (workspace permissions: 2026-03-26)*
