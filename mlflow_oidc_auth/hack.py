import os

from flask import Response

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

_BODY_CLOSE_TAG = "</body>"


def index():
    import textwrap

    from mlflow.server import app

    static_folder = app.static_folder

    text_notfound = textwrap.dedent("Unable to display MLflow UI - landing page not found")
    text_notset = textwrap.dedent("Static folder is not set")

    if static_folder is None:
        return Response(text_notset, mimetype="text/plain")

    index_path = os.path.join(static_folder, "index.html")
    menu_path = os.path.join(os.path.dirname(__file__), "hack", "menu.html")

    if not os.path.exists(index_path):
        return Response(text_notfound, mimetype="text/plain")

    with open(index_path, "r") as f:
        html_content = f.read()

    if _BODY_CLOSE_TAG not in html_content:
        logger.warning(
            "MLflow index.html does not contain '%s' marker; menu injection skipped",
            _BODY_CLOSE_TAG,
        )
        return html_content

    if not os.path.exists(menu_path):
        logger.warning(
            "Menu injection file not found at %s; serving unmodified index.html",
            menu_path,
        )
        return html_content

    with open(menu_path, "r") as js_file:
        js_injection = js_file.read()

    modified_html_content = html_content.replace(_BODY_CLOSE_TAG, f"{js_injection}\n{_BODY_CLOSE_TAG}")
    return modified_html_content
