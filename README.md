# mlflow-oidc-auth
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI Downloads](https://static.pepy.tech/badge/mlflow-oidc-auth/month)](https://pepy.tech/projects/mlflow-oidc-auth)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/mlflow-oidc/mlflow-oidc-auth)

MLflow auth plugin to use OpenID Connect (OIDC) as authentication and authorization provider.

This plugin allows you to use OIDC for user management in MLflow, enabling single sign-on (SSO) capabilities and centralized user management.

### Features
- OIDC-based authentication for MLflow UI and API
- User management through OIDC provider
- User-level access control
- Group-based access control
- Permissions management based on regular expressions (allows or denies access to specific MLflow resources based on regular expressions and assigns permissions to users or groups)
- Support for session, JWT, and basic authentication methods
- Compatible with mlflow-client (basic auth)

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

## Development

For development quick start, please refer to the [Development and Contribution](docs/development.md) section.

## License

Apache 2 Licensed. For more information, please see [LICENSE](https://github.com/mlflow-oidc/mlflow-oidc-auth?tab=Apache-2.0-1-ov-file).

### Based on MLflow basic-auth plugin
https://github.com/mlflow/mlflow/tree/master/mlflow/server/auth
