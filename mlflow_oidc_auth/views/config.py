"""
Configuration endpoint for dynamic runtime configuration.

This module provides endpoints to expose runtime configuration
to the frontend, including proxy path information.
"""

from flask import jsonify, request, Response
from mlflow_oidc_auth.routes import UI_ROOT


def get_runtime_config() -> Response:
    """
    Get runtime configuration for the frontend application.

    This endpoint provides configuration that may change at runtime,
    particularly proxy path information. With ProxyFix middleware configured,
    Flask's request object automatically contains the correct values.

    Returns:
        Response: JSON response containing runtime configuration:
            - basePath: The base path for the application
            - uiPath: The relative path where UI files are served
    """

    config = {"basePath": request.script_root, "uiPath": request.script_root + UI_ROOT}

    return jsonify(config)
