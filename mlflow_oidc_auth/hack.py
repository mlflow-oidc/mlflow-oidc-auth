import os

from flask import Response

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

_BODY_CLOSE_TAG = "</body>"
_HACK_DIR = os.path.join(os.path.dirname(__file__), "hack")


def _read_snippet(name: str) -> str:
    """Read a snippet from the hack/ directory. Returns empty string if missing."""

    path = os.path.join(_HACK_DIR, name)
    if not os.path.exists(path):
        logger.warning("Injection snippet '%s' not found at %s; skipping", name, path)
        return ""
    with open(path, "r") as f:
        return f.read()


def index():
    import textwrap

    from mlflow.server import app

    static_folder = app.static_folder

    text_notfound = textwrap.dedent("Unable to display MLflow UI - landing page not found")
    text_notset = textwrap.dedent("Static folder is not set")

    if static_folder is None:
        return Response(text_notset, mimetype="text/plain")

    index_path = os.path.join(static_folder, "index.html")

    if not os.path.exists(index_path):
        return Response(text_notfound, mimetype="text/plain")

    with open(index_path, "r") as f:
        html_content = f.read()

    if _BODY_CLOSE_TAG not in html_content:
        logger.warning(
            "MLflow index.html does not contain '%s' marker; injection skipped",
            _BODY_CLOSE_TAG,
        )
        return html_content

    # Build the combined injection. Re-auth runs first so the fetch/XHR patch is
    # in place before the menu code (or any later script) issues network calls.
    injections = []
    if config.EXTEND_MLFLOW_REAUTH:
        injections.append(_read_snippet("reauth.html"))
    if config.EXTEND_MLFLOW_MENU:
        injections.append(_read_snippet("menu.html"))
    if config.EXTEND_MLFLOW_EXPERIMENT_GUARD:
        injections.append(_read_snippet("experiment_guard.html"))

    injected = "\n".join(s for s in injections if s)
    if not injected:
        return html_content

    return html_content.replace(_BODY_CLOSE_TAG, f"{injected}\n{_BODY_CLOSE_TAG}")
