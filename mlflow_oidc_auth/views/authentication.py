import secrets

from flask import redirect, render_template, request, session, url_for
from mlflow.server import app

from mlflow_oidc_auth.auth import get_oauth_instance, process_oidc_callback
from mlflow_oidc_auth.config import config


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
    """Validate the state to protect against CSRF and handle login."""

    email, errors = process_oidc_callback(request, session)
    if errors:
        return render_template(
            "auth.html",
            username=None,
            provide_display_name=config.OIDC_PROVIDER_DISPLAY_NAME,
            error_messages=errors,
        )
    session["username"] = email
    return redirect(url_for("oidc_ui"))
