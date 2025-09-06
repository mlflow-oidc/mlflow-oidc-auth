import os

from flask import Response


def index():
    import textwrap

    from mlflow.server import app

    static_folder = app.static_folder

    text_notfound = textwrap.dedent("Unable to display MLflow UI - landing page not found")
    text_notset = textwrap.dedent("Static folder is not set")

    if static_folder is None:
        return Response(text_notset, mimetype="text/plain")

    if os.path.exists(os.path.join(static_folder, "index.html")):
        with open(os.path.join(static_folder, "index.html"), "r") as f:
            html_content = f.read()
            with open(os.path.join(os.path.dirname(__file__), "hack", "menu.html"), "r") as js_file:
                js_injection = js_file.read()
                modified_html_content = html_content.replace("</body>", f"{js_injection}\n</body>")
                return modified_html_content

    return Response(text_notfound, mimetype="text/plain")
