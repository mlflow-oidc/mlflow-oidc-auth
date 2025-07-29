# PyPI

The PyPI package is available at [mlflow-oidc-auth](https://pypi.org/project/mlflow-oidc-auth/).

## Recommended Option
To get the full version (with entire MLflow, MLflow UI and all dependencies), run:

```bash
python3 -m pip install mlflow-oidc-auth[full]
```

## Distributed Deployment (Autoscaling/K8s)

To achieve the best experience and allow application scaling, you need to install the package with caching support:

```bash
python3 -m pip install mlflow-oidc-auth[full,caching-redis]
```

## Lightweight Installation

To get the lightweight version, run:

```bash
python3 -m pip install mlflow-oidc-auth
```

> **Please note**: The lightweight installation does not include the MLflow UI package because it is not included in the mlflow-skinny version. Please install the full version, or install mlflow without dependencies at your own risk.

# Anaconda

Not available yet.
