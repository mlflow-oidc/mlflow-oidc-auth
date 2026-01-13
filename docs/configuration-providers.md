# Configuration Providers

MLflow OIDC Auth Plugin supports pluggable configuration providers for seamless deployment across different cloud platforms and environments.

## Overview

The plugin uses a **chain-of-responsibility pattern** where configuration values are retrieved from multiple sources in priority order. The first provider that returns a value wins.

```
┌─────────────────────────────────────────────────────────────┐
│                    ConfigManager                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Provider Chain (by priority)                ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐   ││
│  │  │Secrets  │→│Parameter│→│ K8s     │→│ Environment  │   ││
│  │  │Manager  │ │ Store   │ │ Secrets │ │ Variables    │   ││
│  │  └─────────┘ └─────────┘ └─────────┘ └──────────────┘   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Cloud Deployments (AWS/Azure/GCP)

Use the `mlflow-oidc-server` command which automatically loads configuration from cloud providers:

```bash
# Install with cloud provider support
pip install mlflow-oidc-auth[aws]   # or [azure], [vault], [cloud]

# Configure provider (e.g., AWS)
export CONFIG_AWS_SECRETS_ENABLED=true
export CONFIG_AWS_SECRETS_NAME=mlflow-oidc-auth

# Start server - secrets loaded automatically from AWS Secrets Manager
mlflow-oidc-server --host 0.0.0.0 --port 8080
```

### Local Development

For local development with `.env` files, use MLflow's built-in `--env-file` option:

```bash
# MLflow's --env-file must come BEFORE the 'server' subcommand
mlflow --env-file .env server --app-name oidc-auth --host 0.0.0.0 --port 8080
```

> **⚠️ Important Timing Note**: The `.env` file loaded by `python-dotenv` in the plugin code runs *after* MLflow CLI has already parsed its configuration. Use `--env-file` or `mlflow-oidc-server` instead.

### Kubernetes

In Kubernetes, environment variables are set by the container runtime, so they're available before MLflow starts:

```bash
# Works automatically - env vars already set by K8s
mlflow server --app-name oidc-auth --host 0.0.0.0 --port 8080
```

---

## The `mlflow-oidc-server` Command

A CLI wrapper that loads configuration from cloud providers before starting MLflow. Uses `os.execvp` for zero overhead (replaces the process, no subprocess).

```bash
# Basic usage - all mlflow server options are passed through
mlflow-oidc-server --host 0.0.0.0 --port 8080 --workers 4

# Show resolved configuration (secrets masked)
mlflow-oidc-server --show-config

# Dry run - see what would be executed
mlflow-oidc-server --dry-run --host 0.0.0.0 --port 8080
```

**How it works:**
1. Loads configuration from enabled providers (AWS Secrets Manager, Azure Key Vault, etc.)
2. Sets environment variables (`MLFLOW_BACKEND_STORE_URI`, etc.)
3. Executes `mlflow server --app-name oidc-auth` with your arguments

---

## MLflow Environment Variables

MLflow natively supports environment variables for server configuration:

| CLI Parameter | Environment Variable | Description |
|--------------|---------------------|-------------|
| `--backend-store-uri` | `MLFLOW_BACKEND_STORE_URI` | Database connection string |
| `--registry-store-uri` | `MLFLOW_REGISTRY_STORE_URI` | Model registry URI |
| `--default-artifact-root` | `MLFLOW_DEFAULT_ARTIFACT_ROOT` | Default artifact location |
| `--artifacts-destination` | `MLFLOW_ARTIFACTS_DESTINATION` | Proxied artifact storage |
| `--serve-artifacts` | `MLFLOW_SERVE_ARTIFACTS` | Enable artifact proxying |
| `--workers` | `MLFLOW_WORKERS` | Number of workers |
| `--uvicorn-opts` | `MLFLOW_UVICORN_OPTS` | Uvicorn server options |
| `--gunicorn-opts` | `MLFLOW_GUNICORN_OPTS` | Gunicorn server options |

### Secure Deployment Example

**❌ BAD: Secrets visible in process list and logs**
```bash
mlflow server --backend-store-uri postgresql://user:PASSWORD@host/db
```

**✅ GOOD: Secrets from environment**
```bash
export MLFLOW_BACKEND_STORE_URI="postgresql://user:PASSWORD@host/db"
mlflow server --app-name oidc-auth --host 0.0.0.0 --port 8080
```

---

## Available Providers

| Provider | Priority | Best For | Enable With |
|----------|----------|----------|-------------|
| AWS Secrets Manager | 10 | Secrets in AWS | `CONFIG_AWS_SECRETS_ENABLED=true` |
| Azure Key Vault | 10 | Secrets in Azure | `CONFIG_AZURE_KEYVAULT_ENABLED=true` |
| HashiCorp Vault | 10 | Multi-cloud secrets | `CONFIG_VAULT_ENABLED=true` |
| Kubernetes Secrets | 20 | K8s deployments | `CONFIG_K8S_SECRETS_ENABLED=true` |
| AWS Parameter Store | 50 | Config in AWS | `CONFIG_AWS_PARAMETER_STORE_ENABLED=true` |
| Environment Variables | 1000 | Local dev, fallback | Always available |

## Secret Classification

Configuration values are classified by sensitivity:

| Level | Examples | Handling |
|-------|----------|----------|
| **SECRET** | `SECRET_KEY`, `OIDC_CLIENT_SECRET` | Must come from secure providers |
| **SENSITIVE** | `OIDC_USERS_DB_URI`, `OIDC_CLIENT_ID` | Should not be logged |
| **PUBLIC** | `EXTEND_MLFLOW_MENU`, `DEFAULT_MLFLOW_PERMISSION` | Can be in config files |

Secret providers (AWS Secrets Manager, Azure Key Vault, etc.) only handle SECRET and SENSITIVE values, allowing public config to come from Parameter Store or environment variables.

---

## AWS Deployment

### AWS Secrets Manager

Store sensitive values like client secrets in AWS Secrets Manager.

**Installation:**
```bash
pip install mlflow-oidc-auth[aws]
```

**Secret Format:**
Create a secret in AWS Secrets Manager with JSON content:
```json
{
  "OIDC_CLIENT_SECRET": "your-client-secret",
  "SECRET_KEY": "your-session-secret-key",
  "OIDC_USERS_DB_URI": "postgresql://user:pass@host/db"
}
```

**Configuration:**
```bash
CONFIG_AWS_SECRETS_ENABLED=true
CONFIG_AWS_SECRETS_NAME=mlflow-oidc-auth          # Secret name
CONFIG_AWS_SECRETS_REGION=us-east-1               # Optional, defaults to AWS_REGION
```

### AWS Parameter Store

Store non-secret configuration in SSM Parameter Store.

**Configuration:**
```bash
CONFIG_AWS_PARAMETER_STORE_ENABLED=true
CONFIG_AWS_PARAMETER_STORE_PREFIX=/mlflow-oidc-auth/
CONFIG_AWS_PARAMETER_STORE_REGION=us-east-1
```

Parameters should be stored with the prefix, e.g., `/mlflow-oidc-auth/OIDC_DISCOVERY_URL`.

### Combined AWS Setup

For AWS Marketplace deployments, use both providers:

```bash
# Secrets from Secrets Manager
CONFIG_AWS_SECRETS_ENABLED=true
CONFIG_AWS_SECRETS_NAME=mlflow-oidc-auth

# Config from Parameter Store
CONFIG_AWS_PARAMETER_STORE_ENABLED=true
CONFIG_AWS_PARAMETER_STORE_PREFIX=/mlflow-oidc-auth/

# Remaining values from environment (container definition)
DEFAULT_MLFLOW_PERMISSION=READ
```

**IAM Policy Example:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:mlflow-oidc-auth-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParametersByPath",
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/mlflow-oidc-auth/*"
    }
  ]
}
```

---

## Azure Deployment

### Azure Key Vault

Store secrets in Azure Key Vault for Azure Marketplace deployments.

**Installation:**
```bash
pip install mlflow-oidc-auth[azure]
```

**Configuration:**
```bash
CONFIG_AZURE_KEYVAULT_ENABLED=true
CONFIG_AZURE_KEYVAULT_NAME=my-keyvault-name
```

**Secret Naming:**
Azure Key Vault doesn't allow underscores in secret names. The provider automatically converts:
- `OIDC_CLIENT_SECRET` → `OIDC-CLIENT-SECRET`
- `SECRET_KEY` → `SECRET-KEY`

**Authentication:**
Uses Azure's `DefaultAzureCredential` which supports:
1. **Managed Identity** (recommended for Azure deployments)
2. **Environment variables** (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`)
3. **Azure CLI** (for local development)

**Example Azure CLI Setup (local dev):**
```bash
az login
az keyvault secret set --vault-name my-keyvault --name OIDC-CLIENT-SECRET --value "secret"
```

---

## Kubernetes Deployment

### Kubernetes Secrets (Mounted as Files)

For Kubernetes deployments, secrets can be mounted as files in the pod.

**Configuration:**
```bash
CONFIG_K8S_SECRETS_ENABLED=true
CONFIG_K8S_SECRETS_PATH=/var/run/secrets/mlflow-oidc-auth
```

**Kubernetes Secret:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mlflow-oidc-auth-secrets
type: Opaque
stringData:
  OIDC_CLIENT_SECRET: "your-client-secret"
  SECRET_KEY: "your-session-secret"
  OIDC_USERS_DB_URI: "postgresql://user:pass@host/db"
```

**Pod Spec:**
```yaml
spec:
  containers:
    - name: mlflow
      volumeMounts:
        - name: secrets
          mountPath: /var/run/secrets/mlflow-oidc-auth
          readOnly: true
      env:
        - name: CONFIG_K8S_SECRETS_ENABLED
          value: "true"
        # Non-secret config from env
        - name: OIDC_DISCOVERY_URL
          value: "https://login.example.com/.well-known/openid-configuration"
  volumes:
    - name: secrets
      secret:
        secretName: mlflow-oidc-auth-secrets
```

---

## HashiCorp Vault

For multi-cloud or on-premise deployments using HashiCorp Vault.

**Installation:**
```bash
pip install mlflow-oidc-auth[vault]
```

**Configuration (Token Auth):**
```bash
CONFIG_VAULT_ENABLED=true
CONFIG_VAULT_ADDR=https://vault.example.com:8200
CONFIG_VAULT_TOKEN=hvs.your-token
CONFIG_VAULT_PATH=secret/data/mlflow-oidc-auth
```

**Configuration (AppRole Auth):**
```bash
CONFIG_VAULT_ENABLED=true
CONFIG_VAULT_ADDR=https://vault.example.com:8200
CONFIG_VAULT_ROLE_ID=your-role-id
CONFIG_VAULT_SECRET_ID=your-secret-id
CONFIG_VAULT_PATH=secret/data/mlflow-oidc-auth
CONFIG_VAULT_NAMESPACE=my-namespace  # Optional, for enterprise
```

---

## Local Development

For local development, environment variables (via `.env` file) are sufficient:

```bash
# .env file
OIDC_DISCOVERY_URL=https://login.example.com/.well-known/openid-configuration
OIDC_CLIENT_ID=my-client-id
OIDC_CLIENT_SECRET=my-client-secret
SECRET_KEY=dev-secret-key-not-for-production
```

No additional configuration needed - the environment variable provider is always available as a fallback.

---

## Custom Providers

You can create custom configuration providers by implementing the `ConfigProvider` interface and registering via entry points.

**1. Create the Provider:**
```python
# mypackage/provider.py
from mlflow_oidc_auth.config_providers.base import ConfigProvider

class MyCustomProvider(ConfigProvider):
    @property
    def name(self) -> str:
        return "my-custom-provider"
    
    @property
    def priority(self) -> int:
        return 30  # After secrets, before env
    
    def is_available(self) -> bool:
        # Check if your backend is available
        return True
    
    def get(self, key: str, default=None):
        # Retrieve configuration value
        return my_backend.get(key) or default
```

**2. Register via Entry Point:**
```toml
# pyproject.toml
[project.entry-points."mlflow_oidc_auth.config_providers"]
my-provider = "mypackage.provider:MyCustomProvider"
```

**3. Install and Use:**
```bash
pip install mypackage
# Provider is automatically discovered and used
```

---

## Configuration Reference

### Provider Selection

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_PROVIDERS` | Comma-separated list of providers to use | All available |

Example: `CONFIG_PROVIDERS=aws-secrets-manager,env` uses only those two providers.

### AWS Secrets Manager

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_AWS_SECRETS_ENABLED` | Enable this provider | `false` |
| `CONFIG_AWS_SECRETS_NAME` | Secret name in Secrets Manager | `mlflow-oidc-auth` |
| `CONFIG_AWS_SECRETS_REGION` | AWS region | `AWS_REGION` or `us-east-1` |

### AWS Parameter Store

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_AWS_PARAMETER_STORE_ENABLED` | Enable this provider | `false` |
| `CONFIG_AWS_PARAMETER_STORE_PREFIX` | Parameter path prefix | `/mlflow-oidc-auth/` |
| `CONFIG_AWS_PARAMETER_STORE_REGION` | AWS region | `AWS_REGION` or `us-east-1` |

### Azure Key Vault

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_AZURE_KEYVAULT_ENABLED` | Enable this provider | `false` |
| `CONFIG_AZURE_KEYVAULT_NAME` | Key Vault name (required) | - |

### HashiCorp Vault

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_VAULT_ENABLED` | Enable this provider | `false` |
| `CONFIG_VAULT_ADDR` | Vault server address | `http://localhost:8200` |
| `CONFIG_VAULT_TOKEN` | Auth token (for token auth) | - |
| `CONFIG_VAULT_ROLE_ID` | AppRole role ID | - |
| `CONFIG_VAULT_SECRET_ID` | AppRole secret ID | - |
| `CONFIG_VAULT_PATH` | Path to secrets | `secret/data/mlflow-oidc-auth` |
| `CONFIG_VAULT_NAMESPACE` | Vault namespace (enterprise) | - |
| `CONFIG_VAULT_KV_VERSION` | KV engine version (1 or 2) | `2` |

### Kubernetes Secrets

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_K8S_SECRETS_ENABLED` | Enable this provider | `false` |
| `CONFIG_K8S_SECRETS_PATH` | Mount path for secrets | `/var/run/secrets/mlflow-oidc-auth` |

---

## Troubleshooting

### Debug Provider Chain

Set logging to DEBUG to see which providers are active:
```bash
export MLFLOW_OIDC_LOG_LEVEL=DEBUG
```

Look for log messages like:
```
INFO: Config providers initialized: aws-secrets-manager, aws-parameter-store, env
```

### Provider Not Activating

1. Check the enable flag: `CONFIG_*_ENABLED=true`
2. Verify required libraries are installed: `pip install mlflow-oidc-auth[aws]`
3. Check credentials are configured (AWS roles, Azure managed identity, etc.)

### Secret Not Found

1. Verify the secret exists in the provider
2. Check the key name matches (Azure converts underscores to hyphens)
3. Ensure the secret is classified correctly (SECRET/SENSITIVE keys only from secure providers)
