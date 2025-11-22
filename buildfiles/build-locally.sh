#!/bin/bash
set -e

# Get the repository root and buildfiles directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Repository root: $REPO_ROOT"
echo "Build directory: $BUILD_DIR"

# Change to buildfiles directory for docker build context
cd "$BUILD_DIR"

# Copy mlflow-oidc-auth source into the build context
echo "Copying source files..."
cp -r "$REPO_ROOT/mlflow_oidc_auth" .
cp -r "$REPO_ROOT/web-ui" .
cp "$REPO_ROOT/pyproject.toml" mlflow_oidc_auth_pyproject.toml

# Build the Docker image
echo "Building Docker image..."
docker build --platform linux/amd64 \
  -t mlflow-oidc-auth-fixed .

# Clean up
echo "Cleaning up build artifacts..."
rm -rf mlflow_oidc_auth
rm -rf web-ui
rm -f mlflow_oidc_auth_pyproject.toml

echo ""
echo "✓ Docker image built successfully as 'mlflow-oidc-auth-fixed'"
echo ""
echo "To run the image:"
echo "  docker run -p 5000:5000 mlflow-oidc-auth-fixed"