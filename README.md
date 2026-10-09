# MLflow Access Control (`mlflow-oidc-auth`)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI Downloads](https://static.pepy.tech/badge/mlflow-oidc-auth/month)](https://pepy.tech/projects/mlflow-oidc-auth)
[![Ask DeepWiki](https://img.shields.io/badge/Ask-DeepWiki-blue)](https://deepwiki.com/mlflow-oidc/mlflow-oidc-auth)

Authentication and access control for MLflow tracking servers: single sign-on (OIDC, SAML 2.0), SCIM user and group provisioning, service accounts, and per-resource permissions for users, groups and workspaces.

It is an MLflow server plugin, installed as `mlflow-oidc-auth` and started with `--app-name oidc-auth`. The package keeps its original name; it has long since grown beyond OIDC.

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by the MLflow Project, Databricks, the Linux Foundation, or LF Projects, LLC.
MLflow and related marks are trademarks of their respective owners.
Maintained by Kharkevich Engineering Lab.

### Features
- **Single sign-on** for the MLflow UI and API through any OpenID Connect provider (confidential or PKCE public clients) or SAML 2.0 identity provider, with several providers side by side
- **Programmatic access**: automation authenticates with short-lived workload identities — Kubernetes service-account tokens or IdP client-credentials / workload-identity tokens (JWT bearer); people using the MLflow client from a laptop or notebook use named personal access tokens (basic auth). See [Programmatic access](docs/programmatic-access.md)
- **SCIM 2.0 provisioning** of users and groups from your directory
- **Permissions** (READ, USE, EDIT, MANAGE) on experiments, registered models, prompts, scorers and AI Gateway resources, granted to users, groups or regex patterns, with deny by default
- **Workspaces** for multi-tenant isolation on a shared MLflow server
- **Admin UI** for users, groups, service accounts, permissions, workspaces, webhooks and trash
- **Operations**: server-side sessions, audit log, health probes, Redis-backed permission cache, and secrets from AWS, Azure, HashiCorp Vault or Kubernetes

### Documentation

For detailed documentation, please refer to the [docs](https://mlflow-oidc.github.io/mlflow-oidc-auth/). AI generated documentation is available at [DeepWiki](https://deepwiki.com/mlflow-oidc/mlflow-oidc-auth).

## Quick Start

To get the full version (with entire MLflow and all dependencies), run:
```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install mlflow-oidc-auth[full]
mlflow server --app-name oidc-auth --host 0.0.0.0 --port 8080
```

## Webhook secret encryption key 🔐

Webhook secrets are stored encrypted in the database using a Fernet key. If you plan to use MLflow webhooks with secrets, set the encryption key in the environment variable `MLFLOW_WEBHOOK_SECRET_ENCRYPTION_KEY` before creating any webhooks. Generate a key with:

```bash
MLFLOW_WEBHOOK_SECRET_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export MLFLOW_WEBHOOK_SECRET_ENCRYPTION_KEY
```

Important: keep this key stable across application restarts and replicas. If the key is lost or changed after webhooks are created, previously stored secrets cannot be decrypted and will cause webhook listing to fail until you restore the original key or remove/rotate the affected webhook secrets.


## Development

For development quick start, please refer to the [Development and Contribution](docs/development.md) section.
Contribution guidelines are available in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2 Licensed. For more information, please see [LICENSE](https://github.com/mlflow-oidc/mlflow-oidc-auth?tab=Apache-2.0-1-ov-file).

### Based on MLflow basic-auth plugin
https://github.com/mlflow/mlflow/tree/master/mlflow/server/auth
