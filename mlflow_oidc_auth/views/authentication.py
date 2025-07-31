import secrets

from flask import redirect, render_template, request, session, url_for
from mlflow.server import app

from mlflow_oidc_auth.auth import get_oauth_instance, process_oidc_callback
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils import get_configured_or_dynamic_redirect_uri


def login():
    """
    Initiate OIDC login flow with dynamically calculated redirect URI.

    This function automatically determines the correct redirect URI based on
    the current request context and proxy headers, falling back to the
    configured OIDC_REDIRECT_URI if explicitly set.
    """
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    oauth_instance = get_oauth_instance(app)
    if oauth_instance is None or oauth_instance.oidc is None:
        app.logger.error("OAuth instance or OIDC is not properly initialized")
        return "Internal Server Error", 500

    redirect_uri = get_configured_or_dynamic_redirect_uri(config.OIDC_REDIRECT_URI)
    app.logger.debug(f"Redirect URI for OIDC login: {redirect_uri}")

    return oauth_instance.oidc.authorize_redirect(redirect_uri, state=state)


def logout():
    session.clear()
    if config.AUTOMATIC_LOGIN_REDIRECT:
        return render_template(
            "auth.html",
            username=None,
            provide_display_name=config.OIDC_PROVIDER_DISPLAY_NAME,
        )
    return redirect(url_for("serve"))


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
    if config.DEFAULT_LANDING_PAGE_IS_PERMISSIONS:
        return redirect(url_for("oidc_ui"))
    return redirect(url_for("serve"))
