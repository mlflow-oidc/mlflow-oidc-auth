import secrets

from flask import redirect, render_template, session, url_for
from mlflow.server import app

import mlflow_oidc_auth.utils as utils
from mlflow_oidc_auth.auth import get_oauth_instance
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.user import create_user, populate_groups, update_user


def login():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    oauth_instance = get_oauth_instance(app)
    if oauth_instance is None or oauth_instance.oidc is None:
        app.logger.error("OAuth instance or OIDC is not properly initialized")
        return "Internal Server Error", 500
    return oauth_instance.oidc.authorize_redirect(config.OIDC_REDIRECT_URI, state=state)


def logout():
    session.clear()
    if config.AUTOMATIC_LOGIN_REDIRECT:
        return render_template(
            "auth.html",
            username=None,
            provide_display_name=config.OIDC_PROVIDER_DISPLAY_NAME,
        )
    return redirect("/")


def callback():
    """Validate the state to protect against CSRF"""

    if "oauth_state" not in session or utils.get_request_param("state") != session["oauth_state"]:
        return "Invalid state parameter", 401

    oauth_instance = get_oauth_instance(app)
    if oauth_instance is None or oauth_instance.oidc is None:
        app.logger.error("OAuth instance or OIDC is not properly initialized")
        return "Internal Server Error", 500
    token = oauth_instance.oidc.authorize_access_token()
    app.logger.debug(f"Token: {token}")
    session["user"] = token["userinfo"]

    email = token["userinfo"]["email"]
    if email is None:
        return "No email provided", 401
    display_name = token["userinfo"]["name"]
    is_admin = False
    user_groups = utils.get_user_groups()
    is_admin = config.OIDC_ADMIN_GROUP_NAME in user_groups
    if len(user_groups) == 0:
        return "User is not allowed to login", 401

    create_user(username=email.lower(), display_name=display_name, is_admin=is_admin)
    populate_groups(group_names=user_groups)
    update_user(email.lower(), user_groups)
    session["username"] = email.lower()
    session[config.OIDC_GROUPS_ATTRIBUTE] = user_groups

    return redirect(url_for("oidc_ui"))
