from typing import Union, Optional

import requests
from authlib.integrations.flask_client import OAuth
from authlib.jose import jwt
from flask import Response, request
from werkzeug.datastructures import Authorization

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.user import create_user 
from mlflow.exceptions import MlflowException


_oauth_instance: Optional[OAuth] = None


def get_oauth_instance(app) -> OAuth:
    # returns a singleton instance of OAuth
    # to avoid circular imports
    global _oauth_instance

    if _oauth_instance is None:
        _oauth_instance = OAuth(app)
        _oauth_instance.register(
            name="oidc",
            client_id=config.OIDC_CLIENT_ID,
            client_secret=config.OIDC_CLIENT_SECRET,
            server_metadata_url=config.OIDC_DISCOVERY_URL,
            client_kwargs={"scope": config.OIDC_SCOPE},
        )
    return _oauth_instance


def _get_oidc_jwks():
    from mlflow_oidc_auth.app import cache, app

    jwks = cache.get("jwks")
    if jwks:
        app.logger.debug("JWKS cache hit")
        return jwks
    app.logger.debug("JWKS cache miss")
    metadata = requests.get(config.OIDC_DISCOVERY_URL).json()
    jwks_uri = metadata.get("jwks_uri")
    jwks = requests.get(jwks_uri).json()
    cache.set("jwks", jwks, timeout=3600)
    return jwks


def validate_token(token):
    jwks = _get_oidc_jwks()
    payload = jwt.decode(token, jwks)
    payload.validate()
    return payload


def authenticate_request_basic_auth() -> Union[Authorization, Response]:
    from mlflow_oidc_auth.app import app

    username = request.authorization.username
    password = request.authorization.password
    app.logger.debug("Authenticating user %s", username)
    if store.authenticate_user(username.lower(), password):
        app.logger.debug("User %s authenticated", username)
        return True
    else:
        app.logger.debug("User %s not authenticated", username)
        return False


def authenticate_request_bearer_token() -> Union[Authorization, Response]:
    from mlflow_oidc_auth.app import app

    token = request.authorization.token
    try:
        user = validate_token(token)
        app.logger.debug("User %s authenticated", user.get("email"))
        return True
    except Exception as e:
        app.logger.debug("JWT auth failed")
        return False


def login_with_trusted_header():
    from mlflow_oidc_auth.app import app
    
    email = request.headers.get(config.TRUSTED_USER_ID_HEADER)
    if not email:
        return False
    try:
        create_user(username=email, display_name=email, is_admin=False)
        app.logger.debug("User %s logged in for first time -> created", email)
    except MlflowException as e:
        app.logger.debug(f"User {email} logged in for first time but could no be created")
    return True