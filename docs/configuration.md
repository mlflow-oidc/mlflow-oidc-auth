# Configuration Reference

The application can be configured through environment variables, dotenv files, or database settings.

## Environment Variables

### Core Authentication Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_DISCOVERY_URL` ⚠️ | String | None | The OIDC discovery endpoint URL for your identity provider |
| `OIDC_CLIENT_ID` ⚠️ | String | None | The client ID registered with your OIDC provider |
| `OIDC_CLIENT_SECRET` ⚠️ | String | None | The client secret for your OIDC application |
| `OIDC_REDIRECT_URI` | String | None | The redirect URI for OIDC callback |
| `OIDC_SCOPE` | String | `openid,email,profile` | Comma-separated list of OIDC scopes to request |
| `OIDC_PROVIDER_DISPLAY_NAME` | String | `Login with OIDC` | Display name for the OIDC provider shown on the login page |
| `OIDC_GROUPS_ATTRIBUTE` | String | `groups` | The attribute name in the ID token that contains user groups |
| `OIDC_GROUP_DETECTION_PLUGIN` | String | None | Custom plugin for enhanced group detection |
| `EXTEND_MLFLOW_MENU` | Boolean | `true` | Extend MLflow UI with OIDC management features |
| `DEFAULT_LANDING_PAGE_IS_PERMISSIONS` | Boolean | `true` | Use the permissions page as the default landing page |

### Group and Permission Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_GROUP_NAME` | String | `mlflow` | List of allowed groups separated by the delimiter |
| `OIDC_GROUP_NAME_DELIMITER` | String | `,` | Delimiter to separate groups in `OIDC_GROUP_NAME` |
| `OIDC_ADMIN_GROUP_NAME` | String | `mlflow-admin` | Name of the admin group for full privileges |
| `DEFAULT_MLFLOW_PERMISSION` | String | `MANAGE` | Default permission level for MLflow objects |
| `PERMISSION_SOURCE_ORDER` | String | `user,group,regex,group-regex` | Order of precedence for permission resolution |

### Database Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_USERS_DB_URI` | String | `sqlite:///auth.db` | Database connection URI for user/permission storage |
| `OIDC_ALEMBIC_VERSION_TABLE` | String | `alembic_version` | Alembic version table name for migrations |

### Security Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SECRET_KEY` | String | Auto-generated | Flask secret key for session signing |
| `AUTOMATIC_LOGIN_REDIRECT` | Boolean | `false` | Automatically redirect to the OIDC login page |

### Session Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SESSION_TYPE` | String | `cachelib` | Session storage backend type |
| `SESSION_PERMANENT` | Boolean | `false` | Whether sessions should be permanent |
| `SESSION_KEY_PREFIX` | String | `mlflow_oidc:` | Prefix for session keys |
| `PERMANENT_SESSION_LIFETIME` | Integer | `86400` | Lifetime of permanent sessions (seconds) |

### Session Backend: CacheLib (File System)
*Used when `SESSION_TYPE=cachelib`*

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SESSION_CACHE_DIR` | String | `/tmp/flask_session` | Directory for session file storage |
| `SESSION_CACHE_THRESHOLD` | Integer | `500` | Maximum number of session files before cleanup |

### Session Backend: Redis
*Used when `SESSION_TYPE=redis`*

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_HOST` | String | `localhost` | Redis server hostname |
| `REDIS_PORT` | Integer | `6379` | Redis server port |
| `REDIS_DB` | Integer | `0` | Redis database number |
| `REDIS_PASSWORD` | String | None | Redis server password |
| `REDIS_SSL` | Boolean | `false` | Use SSL connection to Redis |
| `REDIS_USERNAME` | String | None | Redis username for authentication |

### Session Backend: Cookie
*Used when `SESSION_TYPE=cookie`*

This backend is intended for running multiple instances behind a load balancer (no sticky sessions). You must set a consistent `SECRET_KEY` across all instances.

### Cache Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_TYPE` | String | `FileSystemCache` | Cache backend type |

### Cache Backend: File System
*Used when `CACHE_TYPE=FileSystemCache`*

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_DEFAULT_TIMEOUT` | Integer | `300` | Default cache timeout (seconds) |
| `CACHE_IGNORE_ERRORS` | Boolean | `true` | Whether to ignore cache errors |
| `CACHE_DIR` | String | `/tmp/flask_cache` | Directory for cache file storage |
| `CACHE_THRESHOLD` | Integer | `500` | Maximum number of cache files before cleanup |

### Cache Backend: Redis
*Used when `CACHE_TYPE=RedisCache`*

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_DEFAULT_TIMEOUT` | Integer | `300` | Default cache timeout (seconds) |
| `CACHE_KEY_PREFIX` | String | `mlflow_oidc:` | Prefix for cache keys |
| `CACHE_REDIS_HOST` | String | `localhost` | Redis server hostname for caching |
| `CACHE_REDIS_PORT` | Integer | `6379` | Redis server port for caching |
| `CACHE_REDIS_PASSWORD` | String | None | Redis server password for caching |
| `CACHE_REDIS_DB` | Integer | `4` | Redis database number for caching |

### Logging Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | String | `INFO` | Application logging level |
