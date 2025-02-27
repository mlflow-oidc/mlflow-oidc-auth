# mlflow-oidc-auth
Mlflow auth plugin to use OpenID Connect (OIDC) as authentication and authorization provider


# Installation

To get full version (with entire MLFlow and all dependencies) run:
```bash
python3 -m pip install mlflow-oidc-auth[full]
```

To get skinny version run:
```bash
python3 -m pip install mlflow-oidc-auth
```

# Configuration
The plugin required the following environment variables but also supported `.env` file

## Application configuration
| Parameter | Description|
|---|---|
| OIDC_REDIRECT_URI      |  Application redirect/callback url (https://example.com/callback) |
| OIDC_DISCOVERY_URL     | OIDC Discovery URL |
| OIDC_CLIENT_SECRET     | OIDC Client Secret |
| OIDC_CLIENT_ID         |  OIDC Client ID |
| OIDC_GROUP_DETECTION_PLUGIN | OIDC plugin to detect groups |
| OIDC_PROVIDER_DISPLAY_NAME | any text to display |
| OIDC_SCOPE | OIDC scope |
| OIDC_GROUP_NAME | User group name to be allowed login to MLFlow, currently supported groups in OIDC claims and Microsoft Entra ID groups |
| OIDC_ADMIN_GROUP_NAME | User group name to be allowed login to MLFlow manage and define permissions, currently supported groups in OIDC claims and Microsoft Entra ID groups |
| OIDC_AUTHORIZATION_URL | OIDC Auth URL (if discovery URL is not defined) |
| OIDC_TOKEN_URL         | OIDC Token URL (if discovery URL is not defined) |
| OIDC_USER_URL          | OIDC User info URL (if discovery URL is not defined) |
| SECRET_KEY             | Key to perform cookie encryption |
| LOG_LEVEL                   | Application log level |
| OIDC_USERS_DB_URI | Database connection string |
| OIDC_ALEMBIC_VERSION_TABLE  | Name of the table to use for alembic versions (defaults to alembic_version if not provided)                                                          |

## Application session storage configuration
| Parameter | Description | Default |
|---|---|---|
| SESSION_TYPE | Flask session type (filesystem or redis supported) | filesystem |
| SESSION_FILE_DIR | The directory where session files are stored | flask_session |
| SESSION_PERMANENT | Whether use permanent session or not | False |
| PERMANENT_SESSION_LIFETIME | Server-side session expiration time (in seconds) | 86400 |
| SESSION_KEY_PREFIX | A prefix that is added before all session keys | mlflow_oidc: |
| REDIS_HOST | Redis hostname | localhost |
| REDIS_PORT | Redis port | 6379 |
| REDIS_DB | Redis DB number | 0 |
| REDIS_USERNAME | Redis username | None |
| REDIS_PASSWORD | Redis password | None |
| REDIS_SSL | Use SSL | false |

# Configuration examples

## Okta

```bash
OIDC_DISCOVERY_URL = 'https://<your_domain>.okta.com/.well-known/openid-configuration'
OIDC_CLIENT_SECRET ='<super_secret>'
OIDC_CLIENT_ID ='<client_id>'
OIDC_PROVIDER_DISPLAY_NAME = "Login with Okta"
OIDC_SCOPE = "openid,profile,email,groups"
OIDC_GROUP_NAME = "mlflow-users-group-name"
OIDC_ADMIN_GROUP_NAME = "mlflow-admin-group-name"
```

## Microsoft Entra ID

```bash
OIDC_DISCOVERY_URL = 'https://login.microsoftonline.com/<tenant_id>/v2.0/.well-known/openid-configuration'
OIDC_CLIENT_SECRET = '<super_secret>'
OIDC_CLIENT_ID = '<client_id>'
OIDC_PROVIDER_DISPLAY_NAME = "Login with Microsoft"
OIDC_GROUP_DETECTION_PLUGIN = 'mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id'
OIDC_SCOPE = "openid,profile,email"
OIDC_GROUP_NAME = "mlflow_users_group_name"
OIDC_ADMIN_GROUP_NAME = "mlflow_admins_group_name"
```

> please note, that for getting group membership information, the application should have "GroupMember.Read.All" permission

# Development

Preconditions:

The following tools should be installed for local development:

* git
* nodejs
* Python

```shell
git clone https://github.com/mlflow-oidc/mlflow-oidc-auth
cd mlflow-oidc-auth
./scripts/run-dev-server.sh
```

# License
Apache 2 Licensed. For more information please see [LICENSE](./LICENSE)

### Based on MLFlow basic-auth plugin
https://github.com/mlflow/mlflow/tree/master/mlflow/server/auth
