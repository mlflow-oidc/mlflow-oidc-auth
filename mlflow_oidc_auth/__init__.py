import os

version = os.environ.get("MLFLOW_OIDC_AUTH_VERSION", "7.0.0.dev0")

__version__ = version
