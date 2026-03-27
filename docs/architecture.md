# Architecture

This page describes the internal architecture of the plugin for operators and contributors.

## System Overview

The plugin runs as a FastAPI (ASGI) application that wraps MLflow's Flask (WSGI) server. Both frameworks share the same process and the same HTTP port.

```
Browser / API Client
        │
        ▼
┌───────────────────────────────────────────────┐
│  FastAPI (ASGI)                               │
│  ├── /login, /logout, /callback   (OIDC)      │
│  ├── /health/*                    (probes)     │
│  ├── /oidc/ui/*                   (admin UI)   │
│  ├── /oidc/trash/*                (trash mgmt) │
│  ├── /oidc/webhook/*              (webhooks)   │
│  ├── /api/2.0/mlflow/users/*      (user mgmt)  │
│  ├── /api/2.0/mlflow/permissions/* (RBAC API)   │
│  └── /api/3.0/mlflow/*            (workspaces)  │
│                                               │
│  ┌───────────────────────────────────────────┐│
│  │  Flask (WSGI) — MLflow Native App          ││
│  │  ├── /api/2.0/mlflow/experiments/*         ││
│  │  ├── /api/2.0/mlflow/runs/*                ││
│  │  ├── /api/2.0/mlflow/registered-models/*   ││
│  │  ├── /api/2.0/mlflow/model-versions/*      ││
│  │  ├── /graphql                              ││
│  │  └── ... (all MLflow tracking/registry)    ││
│  └───────────────────────────────────────────┘│
└───────────────────────────────────────────────┘
```

FastAPI handles authentication, the admin UI, and the permission management API. MLflow's Flask app handles the core tracking API. The Flask app is mounted inside FastAPI via an ASGI-to-WSGI bridge.

## Middleware Stack

Middleware is applied to every request. The execution order (outermost to innermost) is:

```
Request → ProxyHeaders → Auth → WorkspaceContext → Session → Route Handler
```

| Middleware | Purpose |
|-----------|---------|
| **ProxyHeadersMiddleware** | Reads `X-Forwarded-*` headers from reverse proxies. Updates the request's scheme, host, port, and client IP. When `TRUSTED_PROXIES` is configured, only applies headers from requests originating within the trusted CIDR ranges |
| **AuthMiddleware** | Authenticates the user via basic auth, JWT bearer token, or session cookie. Sets `request.state.username`, `request.state.is_admin`, and `request.scope["mlflow_oidc_auth"]`. When `OIDC_AUDIENCE` is configured, JWT `aud` claim is validated |
| **FastAPIPermissionMiddleware** | Enforces RBAC on MLflow's native FastAPI routers (gateway invocations, chat completions, embeddings). Extracts the gateway endpoint name from the URL path and checks USE permission before forwarding |
| **WorkspaceContextMiddleware** | When workspaces are enabled, reads the `X-MLFLOW-WORKSPACE` header and sets MLflow's workspace ContextVar so tracking store operations run in the correct workspace |
| **SessionMiddleware** | Starlette's built-in cookie-based session. Decodes/encodes the signed session cookie |

### Unprotected Routes

These paths bypass authentication:

- `/health/*` — Health probes
- `/login`, `/callback` — OIDC login flow
- `/oidc/ui/*` — Admin UI static files (the API calls within the SPA are authenticated)
- `/docs`, `/redoc`, `/openapi.json` — API documentation (if enabled)

## Authentication Methods

The `AuthMiddleware` tries authentication methods in order:

### 1. Basic Auth (Highest Priority)

```
Authorization: Basic base64(username:password)
```

Authenticates against the plugin's user database. Used by MLflow CLI/SDK (`mlflow.set_tracking_uri()` with credentials).

### 2. JWT Bearer Token

```
Authorization: Bearer <jwt_token>
```

Validates the JWT against the OIDC provider's JWKS endpoint. Extracts `email` or `preferred_username` from claims. Handles key rotation by retrying with a fresh JWKS on signature failure. When `OIDC_AUDIENCE` is configured, the `aud` claim is validated to prevent token confusion attacks.

### 3. Session Cookie (Fallback)

No `Authorization` header → checks for a valid session cookie set during OIDC login.

### OIDC Login Flow

1. `GET /login` — Generates CSRF state, redirects to OIDC provider
2. OIDC provider authenticates user, redirects back to `GET /callback`
3. `GET /callback` — Validates state, exchanges code for tokens, extracts user info and groups
4. Creates/updates user in database, sets admin status based on group membership
5. When workspaces enabled: detects workspace from token claims, auto-provisions access
6. Sets session cookie, redirects to UI

## ASGI-to-WSGI Bridge

The Flask app is mounted inside FastAPI via `AuthAwareWSGIMiddleware`:

```
FastAPI (ASGI scope) → AuthAwareWSGIMiddleware → Flask (WSGI environ)
```

The bridge copies `AuthContext` from the ASGI scope (`request.scope["mlflow_oidc_auth"]`) into the WSGI environ (`environ["mlflow_oidc_auth"]`). Flask code retrieves it via bridge functions:

```python
# In Flask hooks/validators:
from mlflow_oidc_auth.bridge.user import get_request_username, get_fastapi_admin_status
username = get_request_username()  # reads from flask.request.environ["mlflow_oidc_auth"]
```

## Flask Hooks

Flask `before_request` and `after_request` hooks enforce RBAC on every MLflow API call.

### Before-Request Hook

Runs before each MLflow API handler:

1. Skips unprotected routes (`/static`, `/health`, etc.)
2. Extracts auth context from the bridge
3. Returns 401 if unauthenticated
4. Finds the appropriate validator by mapping the request to a MLflow protobuf message type
5. Skips authorization for admin users
6. Calls the validator function (e.g., `validate_can_read_experiment`) — returns 403 on failure

The hook maps ~60 MLflow protobuf request types to validator functions, covering experiments, runs, models, model versions, scorers, prompts, gateway resources, workspaces, logged models, and artifacts.

### After-Request Hook

Runs after each MLflow API handler (only on success):

| Action | Trigger |
|--------|---------|
| **Auto-grant MANAGE** | On `CreateExperiment`, `CreateRegisteredModel`, `RegisterScorer`, `CreateGateway*`, `CreateWorkspace` — grants the creator MANAGE permission |
| **Filter search results** | On `SearchExperiments`, `SearchRegisteredModels`, `SearchLoggedModels`, `ListGateway*`, `ListWorkspaces` — removes resources the user cannot read |
| **Cascade deletes** | On `DeleteRegisteredModel`, `DeleteScorer`, `DeleteGateway*`, `DeleteWorkspace` — removes all associated permission records |
| **Rename propagation** | On `RenameRegisteredModel`, `UpdateGatewayEndpoint` — updates permission records to match the new name |

### GraphQL Authorization

A custom Graphene middleware enforces permissions on MLflow's `/graphql` endpoint:

- Intercepts queries for experiments, runs, artifacts, and model versions
- Returns `null` for unauthorized fields (does not raise errors)
- Filters `experiment_ids` in search queries to only include readable experiments
- Installed via monkey-patching MLflow's GraphQL middleware factory

## Data Access Layer

```
Routers / Hooks / Validators
        │
        ▼
┌─────────────────────┐
│  SqlAlchemyStore     │  ← Facade (singleton)
│  (store.py)          │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Repository Classes  │  ← 20+ repositories, one per entity type
│  (repository/)       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  ORM Models          │  ← SQLAlchemy declarative models
│  (db/models/)        │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Database            │  ← SQLite / PostgreSQL / MySQL
└─────────────────────┘
```

- **SqlAlchemyStore**: Singleton facade that delegates to repository classes. All database operations go through this layer.
- **Repositories**: Individual CRUD classes for each entity type (UserRepository, GroupRepository, ExperimentPermissionRepository, etc.)
- **ORM Models**: SQLAlchemy models prefixed with `Sql` (e.g., `SqlUser`, `SqlExperimentPermission`). Table definitions with `Mapped[T]` type annotations.
- **Entities**: Plain Python classes representing domain objects, decoupled from the ORM.
- **Alembic**: Manages schema migrations automatically on startup.

## Caching

Two independent caching layers reduce database load and external HTTP calls:

### JWKS Cache

The OIDC provider's signing keys (JWKS) are fetched once and cached in-process for `OIDC_JWKS_CACHE_TTL_SECONDS` (default: 300). On JWT signature failure, the cache is bypassed and a fresh JWKS is fetched (handles key rotation). This cache is always local (in-process) because JWKS data is identical across replicas.

### Permission Cache

Permission resolution results (the computed permission for a user + resource pair) are cached with a TTL of `PERMISSION_CACHE_TTL_SECONDS` (default: 30). The cache is automatically invalidated whenever permissions are created, updated, or deleted through the `SqlAlchemyStore`.

The cache backend is configurable via `CACHE_BACKEND`:
- **`local`** (default): In-process TTL cache. Suitable for single-replica deployments.
- **`redis`**: Shared Redis instance. Required for multi-replica deployments where permission changes must propagate immediately across all replicas. Requires `CACHE_REDIS_URL` to be set. Install with `pip install "mlflow-oidc-auth[cache]"`.

The workspace permission cache uses the same backend and has separate configuration (`WORKSPACE_CACHE_TTL_SECONDS`, `WORKSPACE_CACHE_MAX_SIZE`).

## Configuration System

```
┌───────────────────────────────────────────────┐
│  ConfigManager (chain-of-responsibility)       │
│  ┌─────────┐ ┌──────────┐ ┌──────┐ ┌───────┐ │
│  │ AWS     │→│ Azure    │→│ Vault│→│ K8s   │→│→ Environment Variables
│  │ Secrets │ │ KeyVault │ │      │ │Secrets│ │
│  └─────────┘ └──────────┘ └──────┘ └───────┘ │
└───────────────────────────────────────────────┘
```

The first provider that returns a value wins. Environment variables are always available as a fallback. See [Configuration Providers](configuration-providers) for details.

## Health Endpoints

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `GET /health` | Basic health check | Returns `{"status": "ok"}` |
| `GET /health/live` | Liveness probe | Lightweight, always returns 200 |
| `GET /health/ready` | Readiness probe | Verifies OIDC provider connectivity and database access |
| `GET /health/startup` | Startup probe | Checks if OIDC client is initialized |

Use these with Kubernetes probe configuration:
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
startupProbe:
  httpGet:
    path: /health/startup
    port: 8080
  failureThreshold: 30
  periodSeconds: 2
```

## MLflow UI Integration

The plugin injects HTML into MLflow's built-in UI via `mlflow_oidc_auth/hack.py`:

- Adds "Sign In" / "Sign Out" navigation links
- Adds a link to the permission management UI (`/oidc/ui/`)
- Controlled by `EXTEND_MLFLOW_MENU` configuration (default: `true`)

This uses string replacement on MLflow's served HTML — it is a deliberate hack due to the plugin boundary (the plugin cannot modify MLflow core behavior).

## Entry Points

### MLflow Plugin

```toml
# pyproject.toml
[project.entry-points."mlflow.app"]
oidc-auth = "mlflow_oidc_auth.app:app"
```

Activated with: `mlflow server --app-name oidc-auth`

### CLI Wrapper

```toml
[project.scripts]
mlflow-oidc-server = "mlflow_oidc_auth.cli:run"
```

The `mlflow-oidc-server` command:
1. Loads configuration from cloud providers
2. Sets environment variables
3. Replaces the process with `mlflow server --app-name oidc-auth` via `os.execvp` (zero overhead)

### App Factory

`create_app()` in `mlflow_oidc_auth/app.py`:
1. Creates the FastAPI application
2. Configures the middleware stack (Session → Workspace → Auth → Proxy)
3. Registers all routers
4. Creates the MLflow Flask app
5. Mounts Flask via `AuthAwareWSGIMiddleware`
6. Runs Alembic database migrations
7. Creates the default admin user
8. Installs GraphQL authorization middleware
