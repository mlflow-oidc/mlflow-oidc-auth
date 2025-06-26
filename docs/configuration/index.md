# Configuration
The plugin required the following environment variables but also supported `.env` file

## Application configuration
| Parameter | Description| Default | Mandatory |
|---|---|---|---|
| OIDC_REDIRECT_URI      |  Application redirect/callback url (https://example.com/callback) | None | Yes |
| OIDC_DISCOVERY_URL     | OIDC Discovery URL | None | Yes |
| OIDC_CLIENT_SECRET     | OIDC Client Secret | None | Yes |
| OIDC_CLIENT_ID         |  OIDC Client ID | None | Yes |
| OIDC_GROUP_DETECTION_PLUGIN | OIDC plugin to detect groups | None | No |
| OIDC_PROVIDER_DISPLAY_NAME | any text to display | "Login with OIDC" | No |
| OIDC_SCOPE | OIDC scope | "openid,email,profile" | No |
| OIDC_GROUP_NAME | User group name to be allowed login to MLFlow, currently supported groups in OIDC claims and Microsoft Entra ID groups | "mlflow" | No |
| OIDC_ADMIN_GROUP_NAME | User group name to be allowed login to MLFlow manage and define permissions, currently supported groups in OIDC claims and Microsoft Entra ID groups | "mlflow-admin" | No |
| SECRET_KEY             | Key to perform cookie encryption | A secret key will be generated | No |
| LOG_LEVEL                   | Application log level | "INFO" | No |
| OIDC_USERS_DB_URI | Database connection string | "sqlite:///auth.db" | No |
| OIDC_ALEMBIC_VERSION_TABLE  | Name of the table to use for alembic versions | "alembic_version" | No |
| DEFAULT_MLFLOW_PERMISSION         | Default fallback permission on all resources  | "MANAGE" | No |
| DEFAULT_MLFLOW_GROUP_PERMISSION   | Default group permission assigned on resource creation, no permission will be assigned if unspecified | None | No |

## Application session storage configuration
| Parameter | Description | Default | Mandatory |
|---|---|---|---|
| SESSION_TYPE | Flask session type (filesystem or redis supported) | filesystem | No |
| SESSION_FILE_DIR | The directory where session files are stored | flask_session | No |
| SESSION_PERMANENT | Whether use permanent session or not | False | No |
| PERMANENT_SESSION_LIFETIME | Server-side session expiration time (in seconds) | 86400 | No |
| SESSION_KEY_PREFIX | A prefix that is added before all session keys | mlflow_oidc: | No |
| REDIS_HOST | Redis hostname | localhost | No |
| REDIS_PORT | Redis port | 6379 | No |
| REDIS_DB | Redis DB number | 0 | No |
| REDIS_USERNAME | Redis username | None | No |
| REDIS_PASSWORD | Redis password | None | No |
| REDIS_SSL | Use SSL | false | No |
