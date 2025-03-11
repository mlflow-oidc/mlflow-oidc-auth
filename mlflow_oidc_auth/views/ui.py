import os

from flask import Response, send_from_directory


def oidc_static(filename):
    # Specify the directory where your static files are located
    static_directory = os.path.join(os.path.dirname(__file__), "..", "static")
    # Return the file from the specified directory
    return send_from_directory(static_directory, filename)


def oidc_ui(filename=None):
    # Specify the directory where your static files are located
    ui_directory = os.path.join(os.path.dirname(__file__), "..", "ui")
    if not filename:
        filename = "index.html"
    elif not os.path.exists(os.path.join(ui_directory, filename)):
        filename = "index.html"
    return send_from_directory(ui_directory, filename)


def index():
    import textwrap

    from mlflow_oidc_auth.app import static_folder

    text_notfound = textwrap.dedent("Unable to display MLflow UI - landing page not found")
    text_notset = textwrap.dedent("Static folder is not set")

    if static_folder is None:
        return Response(text_notset, mimetype="text/plain")

    if os.path.exists(os.path.join(static_folder, "index.html")):
        with open(os.path.join(static_folder, "index.html"), "r") as f:
            html_content = f.read()
            with open(os.path.join(os.path.dirname(__file__), "..", "hack", "menu.html"), "r") as js_file:
                js_injection = js_file.read()
                modified_html_content = html_content.replace("</body>", f"{js_injection}\n</body>")
                return modified_html_content

    return Response(text_notfound, mimetype="text/plain")
