# External Integrations

**Analysis Date:** 2026-03-23

## APIs & External Services

### MLflow Tracking Server

- **Role:** Core dependency; this project is an auth plugin for MLflow
- **Integration Point:** `mlflow.app` entry point registered in `pyproject.toml` (`[project.entry-points."mlflow.app"]`)
- **How it works:**
  - FastAPI app (`mlflow_oidc_auth/app.py`) creates the OIDC-aware application
  - MLflow's Flask app is mounted as WSGI middleware under FastAPI at root `/`
  - Flask `before_request` and `after_request` hooks registered for RBAC (`mlflow_oidc_auth/hooks/`)
  - GraphQL authorization middleware injected into MLflow's Graphene layer (`mlflow_oidc_auth/graphql/middleware.py`)
- **CLI invocation:** `mlflow server --app-name oidc-auth` or `mlflow-oidc-server`
- **MLflow APIs used:**
  - `mlflow.server.app` - Flask application instance
  - `mlflow.server.handlers._get_tracking_store` - Access to MLflow tracking store
  - `mlflow.server.handlers._get_rest_path` - REST API path construction (`mlflow_oidc_auth/routers/_prefix.py`)
  - `mlflow.store.db.utils` - Database engine creation and session management
  - `mlflow.entities.webhook` - Webhook entity classes
  - `mlflow.webhooks.delivery.test_webhook` - Webhook testing
  - `mlflow.tracking._model_registry.registry.ModelRegistryStoreRegistry` - Model registry store access

### OIDC / OAuth2 Identity Providers

- **Role:** User authentication via OpenID Connect
- **SDK:** `authlib` (Starlette OAuth integration at `mlflow_oidc_auth/oauth.py`)
- **Supported providers:** Any OIDC-compliant provider (Keycloak, Auth0, Okta, Microsoft Entra ID, Google, etc.)
- **Configuration:**
  - `OIDC_DISCOVERY_URL` - Provider's `.well-known/openid-configuration` URL
  - `OIDC_CLIENT_ID` - OAuth2 client ID
  - `OIDC_CLIENT_SECRET` - OAuth2 client secret
  - `OIDC_REDIRECT_URI` - Callback URI (optional, auto-calculated from request headers)
  - `OIDC_SCOPE` - Scopes to request (default: `openid,email,profile`)

## Authentication & Authorization

### OIDC Auth Flow

**Login Flow (`mlflow_oidc_auth/routers/auth.py`):**
1. User hits `/login` → generates CSRF state, stores in session
2. Redirects to OIDC provider's authorize endpoint via `authlib`
3. Provider redirects back to `/callback` with authorization code
4. Server exchanges code for tokens via `oauth.oidc.authorize_access_token()`
5. Validates ID token, extracts email/groups from userinfo
6. Creates/updates user and groups in auth database
7. Sets session cookie with username, redirects to UI

**Token Validation (`mlflow_oidc_auth/auth.py`):**
- Bearer tokens validated using OIDC provider's JWKS endpoint
- JWKS fetched from provider's discovery metadata (no local caching)
- Automatic retry on `BadSignatureError` (handles key rotation)

**Auth Middleware (`mlflow_oidc_auth/middleware/auth_middleware.py`):**
- Starlette `BaseHTTPMiddleware` intercepts all requests
- Authentication order: Basic Auth → Bearer Token → Session Cookie
- Unprotected routes: `/health`, `/login`, `/callback`, `/oidc/static`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, `/oidc/ui`
- Sets `request.state.username` and `request.state.is_admin` for downstream use
- ASGI scope `request.scope["mlflow_oidc_auth"]` for Flask WSGI compatibility

**GraphQL Authorization (`mlflow_oidc_auth/graphql/middleware.py`):**
- Graphene middleware enforcing per-field authorization
- Protected fields: `mlflowGetExperiment`, `mlflowGetRun`, `mlflowSearchRuns`, `mlflowSearchModelVersions`, etc.
- Auth context passed from FastAPI → Flask WSGI environ → `mlflow_oidc_auth.bridge`

### Group-Based Access Control

- **Group Detection:** From OIDC token's `groups` attribute (configurable via `OIDC_GROUPS_ATTRIBUTE`)
- **Plugin Support:** Custom group detection via `OIDC_GROUP_DETECTION_PLUGIN` (e.g., Microsoft Entra ID plugin at `mlflow_oidc_auth/plugins/group_detection_microsoft_entra_id/`)
- **Admin Groups:** Configured via `OIDC_ADMIN_GROUP_NAME` (default: `mlflow-admin`)
- **Allowed Groups:** Configured via `OIDC_GROUP_NAME` (default: `mlflow`)
- **Permission Source Order:** Configurable via `PERMISSION_SOURCE_ORDER` (default: `user,group,regex,group-regex`)

### Service Account Authentication

- Basic Auth support for service accounts (machine-to-machine)
- Credentials stored in auth database, validated by `AuthMiddleware`

## Data Storage

### Auth Database

- **Type:** SQLAlchemy ORM with any supported backend
- **Default:** SQLite (`sqlite:///auth.db`)
- **Connection:** `OIDC_USERS_DB_URI` environment variable
- **Client:** SQLAlchemy 2.x ORM (`mlflow_oidc_auth/sqlalchemy_store.py`)
- **Migrations:** Alembic (`mlflow_oidc_auth/db/migrations/`)
- **Tables:** Users, Groups, UserGroups, ExperimentPermissions, RegisteredModelPermissions, ScorerPermissions, GatewayEndpointPermissions, GatewaySecretPermissions, GatewayModelDefinitionPermissions (plus regex/group variants for each)

### File Storage

- No direct file storage; MLflow handles artifact storage separately
- Frontend UI built into `mlflow_oidc_auth/ui/` (committed via build process, gitignored)

### Caching

- Cookie-based sessions via Starlette `SessionMiddleware` (no server-side cache required)
- Redis available for development/testing (`scripts/docker-compose.yaml`)
- Config providers cache secrets in-memory with configurable TTL

## Cloud Provider Integrations

### AWS Secrets Manager (`mlflow_oidc_auth/config_providers/aws_secrets_provider.py`)
- **SDK:** `boto3` (optional `[aws]` extra)
- **Enable:** `CONFIG_AWS_SECRETS_ENABLED=true`
- **Config:** `CONFIG_AWS_SECRETS_NAME`, `CONFIG_AWS_SECRETS_REGION`
- **Purpose:** Secure storage for `OIDC_CLIENT_SECRET`, `SECRET_KEY`, `OIDC_USERS_DB_URI`
- **Priority:** 10 (highest tier)

### AWS Parameter Store (`mlflow_oidc_auth/config_providers/aws_parameter_store_provider.py`)
- **SDK:** `boto3` (optional `[aws]` extra)
- **Enable:** `CONFIG_AWS_PARAMETER_STORE_ENABLED=true`
- **Config:** `CONFIG_AWS_PARAMETER_STORE_PREFIX` (default: `/mlflow-oidc-auth/`)
- **Purpose:** Non-secret configuration values
- **Priority:** 50 (medium)

### Azure Key Vault (`mlflow_oidc_auth/config_providers/azure_keyvault_provider.py`)
- **SDK:** `azure-identity`, `azure-keyvault-secrets` (optional `[azure]` extra)
- **Enable:** `CONFIG_AZURE_KEYVAULT_ENABLED=true`
- **Config:** `CONFIG_AZURE_KEYVAULT_NAME`
- **Auth:** `DefaultAzureCredential` (managed identity, env vars, or Azure CLI)
- **Note:** Underscores in key names converted to hyphens for Azure naming convention
- **Priority:** 10 (highest tier)

### HashiCorp Vault (`mlflow_oidc_auth/config_providers/vault_provider.py`)
- **SDK:** `hvac` (optional `[vault]` extra)
- **Enable:** `CONFIG_VAULT_ENABLED=true`
- **Config:** `CONFIG_VAULT_ADDR`, `CONFIG_VAULT_TOKEN` or `CONFIG_VAULT_ROLE_ID`/`CONFIG_VAULT_SECRET_ID`
- **Supports:** KV v1 and v2, namespaces (enterprise), token and AppRole auth
- **Priority:** 10 (highest tier)

### Kubernetes Secrets (`mlflow_oidc_auth/config_providers/kubernetes_provider.py`)
- **SDK:** None (reads mounted files from filesystem)
- **Enable:** `CONFIG_K8S_SECRETS_ENABLED=true`
- **Config:** `CONFIG_K8S_SECRETS_PATH` (default: `/var/run/secrets/mlflow-oidc-auth`)
- **Purpose:** Kubernetes Secret volumes mounted as files
- **Priority:** 20

## Monitoring & Observability

**Error Tracking:**
- No external error tracking service integrated
- Structured logging via Python `logging` module (`mlflow_oidc_auth/logger.py`)
- Logger defaults to `uvicorn` logger name for FastAPI compatibility

**Logs:**
- Configurable via `LOG_LEVEL` (default: `INFO`) and `LOGGING_LOGGER_NAME` (default: `uvicorn`)
- StreamHandler with format: `%(asctime)s %(levelname)s %(name)s: %(message)s`

**Health Checks (`mlflow_oidc_auth/routers/health.py`):**
- `GET /health` - Basic health check (always returns ok)
- `GET /health/ready` - Readiness probe: checks OIDC client + database connectivity
- `GET /health/live` - Liveness probe: lightweight process check
- `GET /health/startup` - Startup probe: checks OIDC initialization status

**Code Quality:**
- SonarCloud integration (`sonar-project.properties`)
- Project key: `mlflow-oidc_mlflow-oidc-auth`
- Coverage paths: Python `coverage.xml`, TypeScript `web-react/coverage/lcov.info`

## CI/CD & Deployment

**Hosting:**
- Published to PyPI as `mlflow-oidc-auth` package
- Test PyPI for pre-releases

**CI Pipeline (GitHub Actions):**

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| Unit tests | `.github/workflows/unit-tests.yml` | PR + push to main | Python (tox) + React (vitest) tests + SonarCloud |
| Pre-commit | `.github/workflows/pre-commit.yml` | PR | Linting, formatting, file checks |
| Bandit | `.github/workflows/bandit.yml` | PR (Python changes) | Security analysis (high severity/confidence) |
| Release | `.github/workflows/pypi.yml` | Push to main | semantic-release → build → PyPI publish |
| Pre Release | `.github/workflows/pypi-test.yml` | Manual dispatch | semantic-release → Test PyPI publish |
| Documentation | `.github/workflows/documentation.yaml` | Push to main | Deploy docs to GitHub Pages |
| PR Title | `.github/workflows/pr-validate-title.yml` | PR | Validate PR title format |
| Commit Messages | `.github/workflows/commit-message-check.yml` | PR | Validate commit message format |

**Release Process:**
1. Semantic release runs on push to `main` (`.releaserc`)
2. `scripts/release.sh` builds frontend (yarn install + yarn release) then Python package (`python -m build`)
3. Frontend output goes to `mlflow_oidc_auth/ui/` (bundled in Python package)
4. `.whl` artifact attached to GitHub release
5. Package published to PyPI via `pypa/gh-action-pypi-publish`

**Pre-release:**
- `rc` branch for pre-releases (configured in `.releaserc`)
- Manual workflow dispatch to publish to Test PyPI

## REST API Endpoints Exposed

### Authentication Routes (`mlflow_oidc_auth/routers/auth.py`)
- `GET /login` - Initiate OIDC login flow
- `GET /callback` - OIDC callback handler
- `GET /logout` - User logout (session clear + OIDC provider logout)
- `GET /auth/status` - Current authentication status (JSON)

### Permission Management Routes (`mlflow_oidc_auth/routers/`)
- `/api/2.0/mlflow/permissions/experiments/*` - Experiment permission CRUD
- `/api/2.0/mlflow/permissions/registered-models/*` - Model permission CRUD
- `/api/2.0/mlflow/permissions/prompts/*` - Prompt permission CRUD
- `/api/2.0/mlflow/permissions/groups/*` - Group permission CRUD
- `/api/2.0/mlflow/permissions/users/*` - User permission CRUD
- `/api/2.0/mlflow/permissions/gateways/*` - Gateway endpoint/secret/model permissions
- `/api/3.0/mlflow/permissions/scorers/*` - Scorer permission CRUD
- `/api/2.0/mlflow/users/*` - User management

### Admin Routes
- `/oidc/webhook/*` - Webhook CRUD (admin-only, `mlflow_oidc_auth/routers/webhook.py`)
- `/oidc/trash/*` - Soft-deleted resource management (admin-only)
- `/oidc/ui/*` - UI static file serving and SPA routes

### Health Endpoints
- `/health` - Basic health
- `/health/ready` - Readiness probe
- `/health/live` - Liveness probe
- `/health/startup` - Startup probe

### Documentation (optional)
- `/docs` - Swagger UI (controlled by `ENABLE_API_DOCS`)
- `/redoc` - ReDoc (controlled by `ENABLE_API_DOCS`)
- `/openapi.json` - OpenAPI spec

## Webhooks & Callbacks

**Incoming:**
- `GET /callback` - OIDC provider callback after authentication

**Outgoing:**
- MLflow webhook system for model registry events (`mlflow_oidc_auth/routers/webhook.py`)
- Supported events: `registered_model.created`, `model_version.created`, `prompt.created`, etc.
- Webhook CRUD and testing via `/oidc/webhook/` endpoints

## Environment Configuration

**Required env vars (minimum for operation):**
- `OIDC_DISCOVERY_URL` - OIDC provider discovery URL
- `OIDC_CLIENT_ID` - OAuth2 client ID
- `OIDC_CLIENT_SECRET` - OAuth2 client secret

**Important env vars:**
- `OIDC_USERS_DB_URI` - Auth database connection (default: `sqlite:///auth.db`)
- `SECRET_KEY` - Session signing key (auto-generated if not set)
- `OIDC_GROUP_NAME` - Allowed OIDC groups (default: `mlflow`)
- `OIDC_ADMIN_GROUP_NAME` - Admin group name (default: `mlflow-admin`)
- `DEFAULT_MLFLOW_PERMISSION` - Default permission level (default: `MANAGE`)
- `OIDC_SCOPE` - OIDC scopes (default: `openid,email,profile`)
- `OIDC_GROUPS_ATTRIBUTE` - Token attribute for groups (default: `groups`)

**Provider selection env vars:**
- `CONFIG_PROVIDERS` - Comma-separated list of providers to enable
- `CONFIG_AWS_SECRETS_ENABLED` / `CONFIG_AWS_PARAMETER_STORE_ENABLED`
- `CONFIG_AZURE_KEYVAULT_ENABLED`
- `CONFIG_VAULT_ENABLED`
- `CONFIG_K8S_SECRETS_ENABLED`

**Secrets location:**
- `.env` file (local development, gitignored)
- Cloud provider secrets managers (production)
- Kubernetes Secrets (K8s deployments)
- Environment variables (container/VM deployments)

**Full configuration reference:** `docs/configuration.md` and `docs/configuration-providers.md`

---

*Integration audit: 2026-03-23*
