# Configuration Reference

The application can be configured through environment variables, dotenv files, or database settings.

## Environment Variables

### Core Authentication Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_DISCOVERY_URL` ⚠️ | String | None | The OIDC discovery endpoint URL for your identity provider |
| `OIDC_CLIENT_ID` ⚠️ | String | None | The client ID registered with your OIDC provider |
| `OIDC_CLIENT_SECRET` ⚠️ | String | None | The client secret for your OIDC application |
| `OIDC_REDIRECT_URI` | String | None | The redirect URI for OIDC callback. If not set, calculated dynamically from request headers |
| `OIDC_SCOPE` | String | `openid,email,profile` | Comma-separated list of OIDC scopes to request |
| `OIDC_PROVIDER_DISPLAY_NAME` | String | `Login with OIDC` | Display name for the OIDC provider shown on the login page |
| `OIDC_GROUPS_ATTRIBUTE` | String | `groups` | The attribute name in the ID token that contains user groups |
| `OIDC_GROUP_DETECTION_PLUGIN` | String | None | Custom plugin for enhanced group detection |
| `EXTEND_MLFLOW_MENU` | Boolean | `true` | Extend MLflow UI with OIDC management features |
| `DEFAULT_LANDING_PAGE_IS_PERMISSIONS` | Boolean | `true` | Use the permissions page as the default landing page |

### Group and Permission Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_GROUP_NAME` | String | `mlflow` | Comma-separated list of allowed groups |
| `OIDC_ADMIN_GROUP_NAME` | String | `mlflow-admin` | Name of the admin group for full privileges |
| `DEFAULT_MLFLOW_PERMISSION` | String | `MANAGE` | Default permission level for MLflow objects (`READ`, `USE`, `EDIT`, `MANAGE`, `NO_PERMISSIONS`) |
| `PERMISSION_SOURCE_ORDER` | String | `user,group,regex,group-regex` | Order of precedence for permission resolution. See [Permissions](permissions) for details |

### Database Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_USERS_DB_URI` | String | `sqlite:///auth.db` | Database connection URI for user/permission storage |
| `OIDC_ALEMBIC_VERSION_TABLE` | String | `alembic_version` | Alembic version table name for migrations |

### Security Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SECRET_KEY` | String | Auto-generated | Secret used to sign the Starlette session cookie and also set the mounted MLflow (Flask) app secret |
| `AUTOMATIC_LOGIN_REDIRECT` | Boolean | `false` | Automatically redirect to the OIDC login page |

### Sessions

This FastAPI implementation uses Starlette's built-in cookie-based sessions.

- Session data is stored client-side in a signed cookie.
- No server-side session backend (Redis/filesystem) is required.
- For multi-instance deployments, all instances must use the same `SECRET_KEY` so they can validate the session cookie.

### Feature Flags

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_GEN_AI_GATEWAY_ENABLED` | Boolean | `true` | Enable AI Gateway permission management in the UI and API |
| `MLFLOW_ENABLE_WORKSPACES` | Boolean | `false` | Enable workspace (multi-tenant) support. Requires MLflow >=3.10. See [Permissions](permissions#workspace-permissions) for details |

### Workspace Settings

These settings only apply when `MLFLOW_ENABLE_WORKSPACES=true`.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_WORKSPACE_DEFAULT_PERMISSION` | String | `NO_PERMISSIONS` | Permission level auto-assigned to users during OIDC login for workspaces |
| `OIDC_WORKSPACE_CLAIM_NAME` | String | `workspace` | OIDC token claim name used for workspace detection |
| `OIDC_WORKSPACE_DETECTION_PLUGIN` | String | None | Custom plugin for workspace detection from OIDC tokens |
| `WORKSPACE_CACHE_MAX_SIZE` | Integer | `1024` | Maximum number of entries in the workspace permission cache |
| `WORKSPACE_CACHE_TTL_SECONDS` | Integer | `300` | Time-to-live in seconds for workspace permission cache entries |

### Logging Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | String | `INFO` | Application logging level |
| `LOGGING_LOGGER_NAME` | String | `uvicorn` | Logger name to configure (defaults to the Uvicorn logger) |
