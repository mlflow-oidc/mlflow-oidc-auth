# Configuration Reference

The application is configured through environment variables, `.env` files, or pluggable secret providers (AWS, Azure, Vault, Kubernetes). See [Configuration Providers](configuration-providers) for cloud-specific setup.

## Environment Variables

### OIDC Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_DISCOVERY_URL` | String | *Required* | OIDC discovery endpoint URL (e.g., `https://idp.example.com/.well-known/openid-configuration`) |
| `OIDC_CLIENT_ID` | String | *Required* | Client ID registered with your OIDC provider |
| `OIDC_CLIENT_SECRET` | String | *Required* | Client secret for your OIDC application |
| `OIDC_REDIRECT_URI` | String | Auto-detected | Redirect URI for the OIDC callback (`/callback`). If not set, calculated dynamically from proxy headers, which works correctly behind reverse proxies |
| `OIDC_SCOPE` | String | `openid,email,profile` | Comma-separated list of OIDC scopes to request |
| `OIDC_AUDIENCE` | String | None | Expected JWT `aud` claim value (e.g., your client ID or API identifier). When set, bearer tokens are rejected if the `aud` claim doesn't match. Recommended for production to prevent token confusion attacks |
| `OIDC_PROVIDER_DISPLAY_NAME` | String | `Login with OIDC` | Display name shown on the login page button |
| `OIDC_GROUPS_ATTRIBUTE` | String | `groups` | Attribute name in the ID token that contains the user's group memberships |

### Group and Access Control

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_GROUP_NAME` | String | `mlflow` | Comma-separated list of allowed groups. Users must belong to at least one of these groups (or an admin group) to log in |
| `OIDC_ADMIN_GROUP_NAME` | String | `mlflow-admin` | Comma-separated list of admin groups. Members have full admin privileges and bypass all permission checks |
| `OIDC_GROUP_DETECTION_PLUGIN` | String | None | Python module path for a custom group detection plugin. When set, groups are extracted from the access token using this plugin instead of the ID token's groups attribute |

### Permissions

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEFAULT_MLFLOW_PERMISSION` | String | `MANAGE` | Default permission level when no explicit permission is found. Options: `READ`, `USE`, `EDIT`, `MANAGE`, `NO_PERMISSIONS`. See [Permissions](permissions) |
| `PERMISSION_SOURCE_ORDER` | String | `user,group,regex,group-regex` | Comma-separated order for evaluating permission sources. The first source with a matching permission wins. See [Permissions](permissions#permission-source-order) |

### Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_USERS_DB_URI` | String | `sqlite:///auth.db` | Database connection URI for user/permission storage. Supports SQLite, PostgreSQL, MySQL, and any SQLAlchemy-compatible database |
| `OIDC_ALEMBIC_VERSION_TABLE` | String | `alembic_version` | Alembic migration version table name. Change this if you need to avoid conflicts with other Alembic-managed schemas in the same database |

### Security

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SECRET_KEY` | String | Auto-generated | Secret key used to sign session cookies. **All replicas must share the same value** in multi-instance deployments. If not set, a random key is generated on startup and a warning is logged — sessions will not survive restarts or work across replicas |
| `TRUSTED_PROXIES` | String (CSV) | Empty (trust all) | Comma-separated list of trusted proxy IP addresses or CIDR ranges (e.g., `10.0.0.0/8,172.16.0.0/12`). When configured, `X-Forwarded-*` headers from untrusted sources are ignored. When empty, all proxy headers are trusted for backward compatibility |
| `AUTOMATIC_LOGIN_REDIRECT` | Boolean | `false` | When `true`, unauthenticated browser requests are automatically redirected to the OIDC login page instead of showing the login UI |

### UI Behavior

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `EXTEND_MLFLOW_MENU` | Boolean | `true` | Inject sign-in/sign-out links and permission management navigation into MLflow's built-in UI |
| `DEFAULT_LANDING_PAGE_IS_PERMISSIONS` | Boolean | `true` | Use the permissions management page as the default landing page in the admin UI |

### Feature Flags

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_GEN_AI_GATEWAY_ENABLED` | Boolean | `true` | Enable AI Gateway permission management in the admin UI and API. Disable if you don't use MLflow AI Gateway |
| `MLFLOW_ENABLE_WORKSPACES` | Boolean | `false` | Enable workspace (multi-tenant) support. Requires MLflow >=3.10. See [Workspaces](workspaces) |

### Caching

The plugin uses TTL caches to avoid repeated database lookups on every request. Two independent caches exist: one for OIDC/JWT key material and one for permission resolution results.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_JWKS_CACHE_TTL_SECONDS` | Integer | `300` | Time-to-live (seconds) for the JWKS key set cache. The OIDC provider's signing keys are fetched once and cached for this duration. This is always a local in-process cache (not affected by `CACHE_BACKEND`) because JWKS data is identical across replicas |
| `PERMISSION_CACHE_TTL_SECONDS` | Integer | `30` | Time-to-live (seconds) for the permission resolution cache. Cached permission decisions expire after this duration. Lower values mean faster propagation of permission changes; higher values reduce database load |
| `CACHE_BACKEND` | String | `local` | Cache backend for permission and workspace caches. Options: `local` (in-process TTL cache) or `redis` (shared Redis instance). Use `redis` for multi-replica deployments where permission changes must propagate immediately across all replicas |
| `CACHE_REDIS_URL` | String | None | Redis connection URL. Required when `CACHE_BACKEND=redis`. Example: `redis://localhost:6379/0` or `redis://:password@redis-host:6379/1` |
| `CACHE_KEY_PREFIX` | String | `mlflow_oidc_auth:` | Key prefix for Redis cache entries. Useful when sharing a Redis instance with other applications |

> **Note:** Permission caches are automatically invalidated when permissions are created, updated, or deleted through the plugin's API. The TTL acts as a safety net, not the primary invalidation mechanism.

> **Compatibility:** Any Redis-protocol-compatible server works — including [Valkey](https://valkey.io/), [Dragonfly](https://www.dragonflydb.io/), and [KeyDB](https://docs.keydb.dev/). The plugin uses standard Redis commands (`GET`, `SET`, `DELETE`, `SCAN`) via the `redis-py` client library.

### Workspace Settings

These settings only apply when `MLFLOW_ENABLE_WORKSPACES=true`.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_WORKSPACE_DEFAULT_PERMISSION` | String | `NO_PERMISSIONS` | Permission level auto-assigned to users for workspaces detected during OIDC login |
| `OIDC_WORKSPACE_CLAIM_NAME` | String | `workspace` | OIDC token claim name used for workspace detection during login |
| `OIDC_WORKSPACE_DETECTION_PLUGIN` | String | None | Python module path for a custom workspace detection plugin. Used to extract workspace assignments from the OIDC token |
| `WORKSPACE_CACHE_MAX_SIZE` | Integer | `1024` | Maximum number of entries in the workspace permission cache |
| `WORKSPACE_CACHE_TTL_SECONDS` | Integer | `300` | Time-to-live (seconds) for workspace permission cache entries |

### Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | String | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `LOGGING_LOGGER_NAME` | String | `uvicorn` | Logger name to configure. Defaults to the uvicorn logger for FastAPI compatibility |

## Sessions

The plugin uses Starlette's built-in cookie-based sessions:

- Session data is stored client-side in a **signed cookie** (not encrypted — do not store secrets in sessions)
- No server-side session backend (Redis, database) is required
- The cookie is signed with `SECRET_KEY` — all replicas **must** share the same key
- Sessions survive server restarts only if `SECRET_KEY` is explicitly configured

## MLflow Server Environment Variables

MLflow natively supports environment variables for server configuration. These are not managed by the plugin but are commonly used alongside it:

| CLI Parameter | Environment Variable | Description |
|--------------|---------------------|-------------|
| `--backend-store-uri` | `MLFLOW_BACKEND_STORE_URI` | Database URI for experiments, runs, models |
| `--registry-store-uri` | `MLFLOW_REGISTRY_STORE_URI` | Model registry URI (defaults to backend store) |
| `--default-artifact-root` | `MLFLOW_DEFAULT_ARTIFACT_ROOT` | Default artifact storage location |
| `--artifacts-destination` | `MLFLOW_ARTIFACTS_DESTINATION` | Proxied artifact storage destination |
| `--serve-artifacts` | `MLFLOW_SERVE_ARTIFACTS` | Enable artifact proxying |
| `--workers` | `MLFLOW_WORKERS` | Number of uvicorn workers |
| `--uvicorn-opts` | `MLFLOW_UVICORN_OPTS` | Additional uvicorn server options |
| `--gunicorn-opts` | `MLFLOW_GUNICORN_OPTS` | Additional gunicorn server options |

## Configuration Examples

### Minimal Development Setup

```bash
# .env file
OIDC_DISCOVERY_URL=https://your-idp.example.com/.well-known/openid-configuration
OIDC_CLIENT_ID=mlflow-dev
OIDC_CLIENT_SECRET=dev-secret
SECRET_KEY=dev-not-for-production
```

### Security-First Production Setup

```bash
# Deny all access by default — require explicit permission grants
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS

# Strict group requirements
OIDC_GROUP_NAME=mlflow-users,mlflow-data-scientists
OIDC_ADMIN_GROUP_NAME=mlflow-admins

# PostgreSQL backends
MLFLOW_BACKEND_STORE_URI=postgresql://mlflow:pass@db:5432/mlflow
OIDC_USERS_DB_URI=postgresql://mlflow:pass@db:5432/mlflow_auth

# Explicit secret key for multi-replica deployments
SECRET_KEY=your-random-64-char-hex-string

# Auto-redirect to OIDC login
AUTOMATIC_LOGIN_REDIRECT=true
```

### Multi-Tenant Workspace Setup

```bash
# Enable workspaces
MLFLOW_ENABLE_WORKSPACES=true

# New users get no workspace access by default
OIDC_WORKSPACE_DEFAULT_PERMISSION=NO_PERMISSIONS

# Detect workspace from OIDC token claim
OIDC_WORKSPACE_CLAIM_NAME=organization

# Cache workspace permissions (5 min TTL, 2048 max entries)
WORKSPACE_CACHE_MAX_SIZE=2048
WORKSPACE_CACHE_TTL_SECONDS=300

# Deny access to resources without explicit permissions
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS
```

### Group-Priority Permission Resolution

```bash
# Check group permissions before individual user permissions
PERMISSION_SOURCE_ORDER=group,user,group-regex,regex

# Read-only by default
DEFAULT_MLFLOW_PERMISSION=READ
```

### Multi-Replica with Redis Cache

```bash
# Shared cache backend for permission invalidation across replicas
CACHE_BACKEND=redis
CACHE_REDIS_URL=redis://redis-host:6379/0

# Short permission cache TTL for faster propagation
PERMISSION_CACHE_TTL_SECONDS=30

# JWKS cache (always local, 5 min default is fine)
OIDC_JWKS_CACHE_TTL_SECONDS=300

# JWT audience validation (recommended for production)
OIDC_AUDIENCE=my-mlflow-client-id

# Trusted proxy CIDR (if behind a load balancer)
TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12

# All replicas must share the same secret key
SECRET_KEY=your-random-64-char-hex-string
```
