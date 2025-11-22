# Build Files

Docker build configuration for mlflow-oidc-auth with ProKube security fixes.

## Why Custom Dockerfile?

The upstream [mlflow-tracking-server-docker](https://github.com/mlflow-oidc/mlflow-tracking-server-docker) expects mlflow-oidc-auth to be available on PyPI. 

We need these modifications to build directly from source (without PyPI package):
- Install Node.js/Yarn to build the Angular web-ui from source
- Copy and install local mlflow-oidc-auth code
- Build and bundle the web-ui into the package

## Files

- **Dockerfile**: Modified version of upstream Dockerfile
  - Added Node.js/Yarn installation
  - Added web-ui build steps
  - Installs mlflow-oidc-auth from local source

- **pyproject.toml & uv.lock**: From upstream https://github.com/mlflow-oidc/mlflow-tracking-server-docker
  - Defines MLflow version + cloud storage dependencies
  - Update by copying from upstream when needed

- **build-locally.sh**: Standalone build script
  - Copies source files into build context
  - Runs docker build
  - Cleans up afterwards

## Our Security Fixes

- Security fixes for `list_users()` and `list_groups()` (non-admin users see only themselves)
- User deletion with cascade delete of permissions
- Validator fixes for permission LIST endpoints
- MLflow 3.6.0 + mlflow-oidc-auth 5.7.0

## Build & Deploy

```bash
# Local build (run from buildfiles/ or repo root)
./buildfiles/build-locally.sh

# Tag and push
docker tag mlflow-oidc-auth-fixed:latest \
  europe-west3-docker.pkg.dev/prokube-internal/prokube-customer/mlflow-tracking-server:v1.0.7
docker push europe-west3-docker.pkg.dev/prokube-internal/prokube-customer/mlflow-tracking-server:v1.0.7
```

CI/CD workflow builds automatically on push to `pk-internal-build-branch`.
