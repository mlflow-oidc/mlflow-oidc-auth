import fnmatch
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


def get_user_groups(token: dict) -> list[str]:
    """Retrieve the list of groups this user (based on the provided token) is a member of

    Args:
        token: dictionary holding the oidc token information

    Returns:
        list of all the groups this user is a member of
    """
    user_groups = []

    if config.OIDC_GROUP_DETECTION_PLUGIN:
        import importlib

        user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(token["access_token"])
    else:
        user_groups = token["userinfo"][config.OIDC_GROUPS_ATTRIBUTE]

    app.logger.debug(f"All user groups: {user_groups}")

    # Now filter the user groups to keep only those matching the pattern or the ADMIN group
    user_groups = sorted(
        set(
            [
                x
                for p in config.OIDC_GROUP_FILTER_PATTERNS
                for x in [g for g in user_groups if (fnmatch.fnmatch(g, p) or (g == config.OIDC_ADMIN_GROUP_NAME))]
            ]
        )
    )

    app.logger.debug(f"Filtered user groups: {user_groups}")

    return user_groups


def get_is_admin(user_groups: list[str]):
    """Check if the admin group is included in the user_groups. In that case
    it means that the user is an admin user

    Args:
        user_groups (list[str]): list of the groups the current user belongs to

    Returns:
        True if the admin group is in the list of the groups of the current user, False otherwise

    """
    is_admin = False

    if config.OIDC_ADMIN_GROUP_NAME in user_groups:
        app.logger.debug(f"User is in admin group {config.OIDC_ADMIN_GROUP_NAME}")
        is_admin = True

    return is_admin


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
    user_groups = []

    if config.OIDC_GROUP_DETECTION_PLUGIN:
        import importlib

        user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(token["access_token"])
    else:
        user_groups = token["userinfo"][config.OIDC_GROUPS_ATTRIBUTE]

    app.logger.debug(f"All user groups: {user_groups}")

    # Now filter the user groups to keep only those matching the pattern
    user_groups = sorted(
        set([x for p in config.OIDC_GROUP_FILTER_PATTERNS for x in [g for g in user_groups if fnmatch.fnmatch(g, p)]])
    )

    app.logger.debug(f"Filtered user groups: {user_groups}")

    if config.OIDC_ADMIN_GROUP_NAME in user_groups:
        app.logger.debug(f"User is in admin group {config.OIDC_ADMIN_GROUP_NAME}")
        is_admin = True
    elif not len(user_groups):
        return "User is not allowed to login", 401

    create_user(username=email.lower(), display_name=display_name, is_admin=is_admin)
    populate_groups(group_names=user_groups)
    update_user(email.lower(), user_groups)
    session["username"] = email.lower()

    return redirect(url_for("oidc_ui"))
