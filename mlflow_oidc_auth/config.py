import os
import secrets
import requests
import secrets
import importlib

from dotenv import load_dotenv
from mlflow.server import app

load_dotenv()  # take environment variables from .env.
app.logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


class AppConfig:
    def __init__(self):
        self.DEFAULT_MLFLOW_PERMISSION = os.environ.get("DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        self.SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(16))
        self.OIDC_USERS_DB_URI = os.environ.get("OIDC_USERS_DB_URI", "sqlite:///auth.db")
        self.OIDC_GROUP_NAME = [group.strip() for group in os.environ.get("OIDC_GROUP_NAME", "mlflow").split(",")]
        self.OIDC_ADMIN_GROUP_NAME = os.environ.get("OIDC_ADMIN_GROUP_NAME", "mlflow-admin")
        self.OIDC_PROVIDER_DISPLAY_NAME = os.environ.get("OIDC_PROVIDER_DISPLAY_NAME", "Login with OIDC")
        self.OIDC_DISCOVERY_URL = os.environ.get("OIDC_DISCOVERY_URL", None)
        self.OIDC_GROUPS_ATTRIBUTE = os.environ.get("OIDC_GROUPS_ATTRIBUTE", "groups")
        self.OIDC_SCOPE = os.environ.get("OIDC_SCOPE", "openid,email,profile")
        self.OIDC_GROUP_DETECTION_PLUGIN = os.environ.get("OIDC_GROUP_DETECTION_PLUGIN", None)
        self.OIDC_REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", None)
        self.OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", None)
        self.OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", None)
        self.USE_TRUSTED_USER_ID_HEADER = os.environ.get("USE_TRUSTED_USER_ID_HEADER", str(False)).lower() in ("true", "1", "t")
        self.TRUSTED_USER_ID_HEADER = os.environ.get("TRUSTED_USER_ID_HEADER", None)

        # session
        self.SESSION_TYPE = os.environ.get("SESSION_TYPE", "cachelib")
        self.SESSION_PERMANENT = os.environ.get("SESSION_PERMANENT", str(False)).lower() in ("true", "1", "t")
        self.SESSION_KEY_PREFIX = os.environ.get("SESSION_KEY_PREFIX", "mlflow_oidc:")
        self.PERMANENT_SESSION_LIFETIME = os.environ.get("PERMANENT_SESSION_LIFETIME", 86400)
        if self.SESSION_TYPE:
            try:
                session_module = importlib.import_module(f"mlflow_oidc_auth.session.{(self.SESSION_TYPE).lower()}")
                app.logger.debug(f"Session module for {self.SESSION_TYPE} imported.")
                for attr in dir(session_module):
                    if attr.isupper():
                        setattr(self, attr, getattr(session_module, attr))
            except ImportError:
                app.logger.error(f"Session module for {self.SESSION_TYPE} could not be imported.")
        # cache
        self.CACHE_TYPE = os.environ.get("CACHE_TYPE", "FileSystemCache")
        if self.CACHE_TYPE:
            try:
                cache_module = importlib.import_module(f"mlflow_oidc_auth.cache.{(self.CACHE_TYPE).lower()}")
                app.logger.debug(f"Cache module for {self.CACHE_TYPE} imported.")
                for attr in dir(cache_module):
                    if attr.isupper():
                        setattr(self, attr, getattr(cache_module, attr))
            except ImportError:
                app.logger.error(f"Cache module for {self.CACHE_TYPE} could not be imported.")


config = AppConfig()
