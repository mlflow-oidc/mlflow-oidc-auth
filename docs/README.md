# MLflow OIDC Auth

An authentication and authorization plugin for [MLflow](https://mlflow.org/) that adds OpenID Connect (OIDC) single sign-on, role-based access control (RBAC), and per-resource permission management to MLflow tracking servers.

## Features

- **OIDC single sign-on** — Authenticate users via any OpenID Connect provider (Keycloak, Okta, Auth0, Azure AD, Google, etc.)
- **Multiple auth methods** — Session cookies (browser), JWT bearer tokens (service-to-service), and basic auth (CLI/SDK)
- **User-level permissions** — Assign READ, USE, EDIT, or MANAGE permissions to individual users per resource
- **Group-based access control** — Organize users into groups with shared permissions, synchronized from the OIDC provider
- **Regex pattern permissions** — Define permissions using regular expressions that match resource names (e.g., `^prod-.*` → READ for all production experiments)
- **Workspace support** — Multi-tenant resource isolation with workspace-scoped experiments, models, webhooks, and trash (requires MLflow >=3.10)
- **AI Gateway permissions** — Control access to MLflow AI Gateway endpoints, secrets, and model definitions
- **Prompt and scorer permissions** — Fine-grained access control for MLflow prompts and scorers
- **Webhook management** — Create, test, and manage workspace-scoped webhooks through the admin UI
- **Trash management** — View, restore, and permanently delete experiments and runs from the admin UI
- **Admin UI** — React-based management interface for permissions, users, groups, webhooks, and trash
- **Pluggable configuration** — Load secrets from AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, Kubernetes Secrets, or environment variables
- **GraphQL authorization** — Permission enforcement on MLflow's GraphQL API
- **Health probes** — Kubernetes-compatible liveness, readiness, and startup health check endpoints
- **MLflow UI integration** — Injects sign-in/sign-out links and permission management navigation into the built-in MLflow UI

## Quick Start

### 1. Install

```bash
pip install mlflow-oidc-auth
```

### 2. Configure

Create a `.env` file with your OIDC provider settings:

```bash
OIDC_DISCOVERY_URL=https://your-idp.example.com/.well-known/openid-configuration
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_GROUP_NAME=mlflow
OIDC_ADMIN_GROUP_NAME=mlflow-admin
SECRET_KEY=your-random-secret-key
```

### 3. Run

```bash
mlflow --env-file .env server --app-name oidc-auth --host 0.0.0.0 --port 8080
```

Or use the wrapper CLI that supports cloud secret providers:

```bash
mlflow-oidc-server --host 0.0.0.0 --port 8080
```

### 4. Access

- **MLflow UI**: `http://localhost:8080/` — Redirects to OIDC login
- **Admin UI**: `http://localhost:8080/oidc/ui/` — Permission management interface
- **Health**: `http://localhost:8080/health/ready` — Readiness probe

## How It Works

The plugin runs as a FastAPI application that wraps MLflow's Flask server:

1. **FastAPI** handles OIDC authentication, the admin UI, permission management API, and health endpoints
2. **Flask** (MLflow's native app) handles the core MLflow tracking API (experiments, runs, models)
3. **Before-request hooks** intercept every MLflow API call and enforce RBAC before the request reaches MLflow
4. **After-request hooks** auto-grant permissions on resource creation, filter search results, and cascade permission deletes

Authentication context flows from FastAPI middleware through an ASGI-to-WSGI bridge into Flask, so all layers share the same user identity and admin status.

## Documentation

| Page | Description |
|------|-------------|
| [Installation](installation) | Installation options and first-run setup |
| [Configuration](configuration) | Environment variables and settings reference |
| [Configuration Providers](configuration-providers) | AWS, Azure, Vault, K8s secret backends |
| [Permissions](permissions) | Permission system, hierarchy, and resolution |
| [Workspaces](workspaces) | Multi-tenant workspace isolation |
| [Architecture](architecture) | System design, middleware stack, hooks |
| [API Reference](api-reference) | REST API endpoint catalog |
| [Admin UI](admin-ui) | Using the permission management interface |
| [Development](development) | Contributing, local setup, testing |

## Requirements

- Python >=3.10 (3.12 recommended)
- MLflow >=3.10.0, <4
- An OIDC provider (Keycloak, Okta, Auth0, Azure AD, etc.)
- Database: SQLite (default), PostgreSQL, or MySQL

## Links

- [PyPI](https://pypi.org/project/mlflow-oidc-auth/)
- [GitHub](https://github.com/mlflow-oidc/mlflow-oidc-auth)
- [Issues](https://github.com/mlflow-oidc/mlflow-oidc-auth/issues)
