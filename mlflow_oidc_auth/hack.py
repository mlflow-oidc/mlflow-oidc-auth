import functools
import json
import os

from flask import Response, has_request_context, request

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

_BODY_CLOSE_TAG = "</body>"
_HACK_DIR = os.path.join(os.path.dirname(__file__), "hack")

# Snippets refer to the deployment's path prefix through this placeholder, which index() replaces
# with the prefix as the content of a JavaScript string literal.
BASE_PATH_PLACEHOLDER = "__MLFLOW_OIDC_BASE_PATH__"


@functools.lru_cache(maxsize=None)
def _read_snippet(name: str) -> str:
    """Read a snippet from the hack/ directory once. Returns empty string if missing."""

    path = os.path.join(_HACK_DIR, name)
    if not os.path.exists(path):
        logger.warning("Injection snippet '%s' not found at %s; skipping", name, path)
        return ""
    with open(path, "r") as f:
        return f.read()


def _base_path() -> str:
    """The prefix the deployment is served under, without a trailing slash.

    The plugin's own pages (``/oidc/ui``, ``/login``, ``/logout``, its API) live under this prefix
    and not under MLflow's ``--static-prefix``, so links to them cannot be relative to MLflow's page.
    Flask is mounted at the root of the ASGI app, so ``SCRIPT_NAME`` carries the ASGI ``root_path``:
    the same trusted prefix the FastAPI side builds its redirects from. Anything that is not a
    single-slash path is ignored.
    """
    if not has_request_context():
        return ""
    root = request.script_root or ""
    if not root.startswith("/") or root.startswith("//"):
        return ""
    return root.rstrip("/")


def _js_string_content(value: str) -> str:
    """``value`` escaped for use between the double quotes of an inline-script string literal."""
    return json.dumps(value)[1:-1].replace("<", "\\u003c").replace(">", "\\u003e")


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

    # Build the combined injection. The admin redirect runs first so a page that is
    # about to be replaced does not start any work. Re-auth runs next so the
    # fetch/XHR patch is in place before the menu code (or any later script)
    # issues network calls.
    injections = []
    if config.EXTEND_MLFLOW_REDIRECT_ADMIN:
        injections.append(_read_snippet("redirect.html"))
    if config.EXTEND_MLFLOW_REAUTH:
        injections.append(_read_snippet("reauth.html"))
    if config.EXTEND_MLFLOW_MENU:
        injections.append(_read_snippet("menu.html"))

    injected = "\n".join(s for s in injections if s)
    if not injected:
        return html_content
    injected = injected.replace(BASE_PATH_PLACEHOLDER, _js_string_content(_base_path()))

    return html_content.replace(_BODY_CLOSE_TAG, f"{injected}\n{_BODY_CLOSE_TAG}")
