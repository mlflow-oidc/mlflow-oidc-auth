# Installation

## Requirements

- Python >=3.10 (3.12 recommended)
- MLflow >=3.10.0, <4
- An OIDC-compatible identity provider (Keycloak, Okta, Auth0, Azure AD, Google, etc.)

## Package Installation

The plugin is available on [PyPI](https://pypi.org/project/mlflow-oidc-auth/).

### Full Installation (Recommended)

Includes the complete MLflow package with the UI:

```bash
pip install "mlflow-oidc-auth"
```

Since `mlflow>=3.10.0` is a dependency, the full MLflow package (including the tracking UI) is installed automatically.

### With Cloud Provider Support

Install with extras for your deployment environment:

```bash
# AWS (Secrets Manager + Parameter Store)
pip install "mlflow-oidc-auth[aws]"

# Azure (Key Vault)
pip install "mlflow-oidc-auth[azure]"

# HashiCorp Vault
pip install "mlflow-oidc-auth[vault]"

# Redis cache backend (for multi-replica deployments)
pip install "mlflow-oidc-auth[cache]"

# All cloud providers
pip install "mlflow-oidc-auth[cloud]"
```

See [Configuration Providers](configuration-providers) for details on each provider.

## OIDC Provider Setup

Before starting the server, register a client application with your OIDC provider.

### Required OIDC Configuration

1. **Client type**: Confidential (with a client secret)
2. **Grant type**: Authorization Code
3. **Redirect URI**: `https://your-mlflow-host/callback`
4. **Scopes**: `openid`, `email`, `profile`
5. **Token claims**: The ID token must include `email` (or `preferred_username`) and `groups`

### Provider-Specific Notes

**Keycloak:**
- Create a client in your realm with "Client authentication" enabled
- Add a mapper for the `groups` claim (Type: "Group Membership", Token Claim Name: `groups`)
- Ensure users are members of at least one allowed group (default: `mlflow`)

**Okta:**
- Create a Web Application in the Applications dashboard
- Add a Groups claim to the ID token (name: `groups`, filter: matches your group names)
- Assign users to the `mlflow` group (or your configured group name)

**Azure AD / Entra ID:**
- Register an application in Azure AD
- Add a client secret under "Certificates & secrets"
- Configure token claims to include group memberships
- The `groups` claim may contain group Object IDs — configure `OIDC_GROUPS_ATTRIBUTE` accordingly

**Auth0:**
- Create a Regular Web Application
- Enable the Authorization Code grant
- Use an Auth0 Action or Rule to add a `groups` claim to the ID token

## Starting the Server

### Using MLflow Directly

```bash
# With environment file
mlflow --env-file .env server --app-name oidc-auth --host 0.0.0.0 --port 8080

# With environment variables
export OIDC_DISCOVERY_URL=https://your-idp.example.com/.well-known/openid-configuration
export OIDC_CLIENT_ID=your-client-id
export OIDC_CLIENT_SECRET=your-client-secret
export SECRET_KEY=your-random-secret
mlflow server --app-name oidc-auth --host 0.0.0.0 --port 8080
```

> **Note:** The `--env-file` flag must come before the `server` subcommand.

### Using the Wrapper CLI

The `mlflow-oidc-server` command loads configuration from cloud providers before starting MLflow:

```bash
# Basic usage (passes all flags to mlflow server)
mlflow-oidc-server --host 0.0.0.0 --port 8080 --workers 4

# Show resolved configuration (secrets masked)
mlflow-oidc-server --show-config

# Dry run (see what would be executed)
mlflow-oidc-server --dry-run --host 0.0.0.0 --port 8080
```

### With a Database Backend

For production, use PostgreSQL or MySQL instead of the default SQLite:

```bash
export MLFLOW_BACKEND_STORE_URI="postgresql://user:pass@host:5432/mlflow"
export OIDC_USERS_DB_URI="postgresql://user:pass@host:5432/mlflow_auth"
mlflow-oidc-server --host 0.0.0.0 --port 8080
```

The plugin uses two databases:
- **MLflow tracking database** (`MLFLOW_BACKEND_STORE_URI`) — Managed by MLflow for experiments, runs, models
- **Auth database** (`OIDC_USERS_DB_URI`) — Managed by the plugin for users, groups, permissions

Both can point to different databases on the same server, or to different servers entirely.

## First-Run Setup

On first startup, the plugin:

1. Runs database migrations automatically (Alembic)
2. Creates a default admin user (if none exists)
3. Connects to the OIDC provider to verify configuration

### Default Admin Access

After installation, the first user who logs in via OIDC and belongs to the admin group (`OIDC_ADMIN_GROUP_NAME`, default: `mlflow-admin`) will have full admin privileges.

For API/CLI access before OIDC login, a built-in admin user is created with a random password printed in the server logs on first startup.

### Verifying the Installation

```bash
# Health check
curl http://localhost:8080/health

# Readiness probe (checks OIDC + database)
curl http://localhost:8080/health/ready

# Auth status (should return unauthenticated)
curl http://localhost:8080/auth/status
```

## Docker Deployment

### Basic Docker

```dockerfile
FROM python:3.12-slim

RUN pip install mlflow-oidc-auth

EXPOSE 8080

CMD ["mlflow-oidc-server", "--host", "0.0.0.0", "--port", "8080"]
```

### Kubernetes

See [Configuration Providers](configuration-providers#kubernetes-deployment) for Kubernetes-specific secret mounting and deployment patterns.

Key considerations:
- All replicas **must** share the same `SECRET_KEY` for session cookie validation
- Use `OIDC_USERS_DB_URI` pointing to a shared database (not SQLite)
- Configure `TRUSTED_PROXIES` with your load balancer's CIDR range(s) to validate proxy headers
- For multi-replica deployments, use `CACHE_BACKEND=redis` with a shared Redis instance so permission changes propagate immediately across replicas (install with `pip install "mlflow-oidc-auth[cache]"`)
- Set `OIDC_AUDIENCE` to your client ID to validate JWT audience claims
- Health probes: `/health/live` (liveness), `/health/ready` (readiness), `/health/startup` (startup)

## Upgrading

The plugin runs Alembic database migrations automatically on each startup. No manual migration steps are required.

When upgrading, simply update the package:

```bash
pip install --upgrade mlflow-oidc-auth
```

Restart the server and migrations will be applied automatically.
