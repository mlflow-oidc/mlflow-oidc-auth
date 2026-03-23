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
- Purpose: Authentication, proxy header handling, session management, WSGI bridging
- Location: `mlflow_oidc_auth/middleware/`
- Contains: `AuthMiddleware`, `AuthAwareWSGIMiddleware`, `ProxyHeadersMiddleware`
- Depends on: Config, Store, Auth (JWT validation), Bridge
- Used by: FastAPI app (applied in order during `create_app`)

**Router Layer (FastAPI):**
- Purpose: REST API endpoints for permissions, users, groups, auth flows, health, UI
- Location: `mlflow_oidc_auth/routers/`
- Contains: 15 routers — auth, experiment_permissions, group_permissions, prompt_permissions, registered_model_permissions, scorers_permissions, gateway_endpoint_permissions, gateway_secret_permissions, gateway_model_definition_permissions, health, trash, ui, user_permissions, users, webhook
- Depends on: Store, Config, Models (Pydantic), Utils
- Used by: FastAPI app (registered in `create_app`)

**Hooks Layer (Flask before/after request):**
- Purpose: RBAC enforcement on MLflow's native Flask endpoints
- Location: `mlflow_oidc_auth/hooks/`
- Contains: `before_request.py` (~428 lines) maps MLflow protobuf request classes to validator functions; `after_request.py` (~426 lines) handles post-request actions (auto-grant MANAGE on create, filter search results, cascade permission deletes)
- Depends on: Validators, Store, Bridge, Config, Permissions
- Used by: Flask app (registered as `before_request` and `after_request` hooks)

**Validators Layer:**
- Purpose: Per-resource permission checking logic
- Location: `mlflow_oidc_auth/validators/`
- Contains: Validator functions for experiments, registered models, prompts, scorers, gateway endpoints/secrets/model definitions
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
- Contains: `SqlAlchemyStore` class (~721 lines) delegates to 20+ repository classes
- Depends on: Repository classes, DB models, Entities, SQLAlchemy, Alembic
- Used by: Routers, Hooks, Validators, Middleware

**Repository Layer:**
- Purpose: Individual CRUD operations per entity type
- Location: `mlflow_oidc_auth/repository/`
- Contains: 20+ repository classes (UserRepository, GroupRepository, ExperimentPermissionRepository, RegisteredModelRegexPermissionRepository, etc.)
- Depends on: DB models, Entities, SQLAlchemy session
- Used by: SqlAlchemyStore

**Database Models Layer:**
- Purpose: SQLAlchemy ORM table definitions
- Location: `mlflow_oidc_auth/db/models/`
- Contains: ORM models for all entities (users, groups, user_groups, experiment_permissions, registered_model_permissions, prompt_permissions, scorer_permissions, gateway_*_permissions, plus regex and group-regex variants of each)
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
- Pattern: Facade over 20+ repository classes, each handling one entity type

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

---

*Architecture analysis: 2026-03-23*
