"""
Exception handling utilities for MLflow OIDC Auth Plugin.

This module provides functions for handling exceptions in the FastAPI application,
particularly focusing on MLflow-specific exceptions.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import mlflow.exceptions


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers for the FastAPI application.

    This function adds handlers for MLflow-specific exceptions and converts them
    to appropriate HTTP responses with meaningful error messages and status codes.

    Parameters:
    app (FastAPI): The FastAPI application instance to register handlers for.
    """

    @app.exception_handler(mlflow.exceptions.MlflowException)
    async def handle_mlflow_exception(request: Request, exc: mlflow.exceptions.MlflowException) -> JSONResponse:
        """
        Handle MLflow exceptions and convert them to appropriate HTTP responses.

        Maps MLflow error codes to corresponding HTTP status codes and formats
        the error message for consistent API responses.

        Parameters:
        request (Request): The request that caused the exception.
        exc (MlflowException): The MLflow exception that was raised.

        Returns:
        JSONResponse: A JSON response containing error details and appropriate status code.
        """
        status_code = 500  # Default to internal server error

        # Map MLflow error codes to HTTP status codes
        if exc.error_code == "RESOURCE_ALREADY_EXISTS":
            status_code = 409  # Conflict
        elif exc.error_code == "RESOURCE_DOES_NOT_EXIST":
            status_code = 404  # Not found
        elif exc.error_code == "INVALID_PARAMETER_VALUE":
            status_code = 400  # Bad request
        elif exc.error_code == "UNAUTHORIZED":
            status_code = 401  # Unauthorized
        elif exc.error_code == "UNAUTHENTICATED":
            status_code = 401  # Unauthorized
        elif exc.error_code == "PERMISSION_DENIED":
            status_code = 403  # Forbidden
        elif exc.error_code == "INVALID_STATE":
            status_code = 400  # Bad request (e.g., regex validation, duplicate permission)

        return JSONResponse(
            status_code=status_code,
            content={
                "error_code": exc.error_code,
                "message": str(exc),
                "details": getattr(exc, "message", None),
            },
        )


def register_skill_registry_exception_handlers(app: FastAPI) -> None:
    """Answer errors on MLflow's skill registry routes as MLflow itself does.

    MLflow serves the registry with exception handlers scoped to its paths, which turn an
    ``MlflowException``, a request that fails validation and an ``HTTPException`` into
    ``{error_code, message}`` with MLflow's status code — what its registry clients parse. Those
    handlers live in ``mlflow.server.fastapi_app``, which builds MLflow's own app when imported, so
    the same scoping is installed here: off the registry paths every handler defers to the one it
    replaced. Must run after :func:`register_exception_handlers`.

    Parameters:
        app: The plugin's FastAPI application.
    """
    import inspect

    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException
    from starlette.responses import Response

    from mlflow_oidc_auth.middleware.route_path import routed_path
    from mlflow_oidc_auth.middleware.skill_registry import is_skill_registry_path

    def on_registry(request: Request) -> bool:
        return is_skill_registry_path(routed_path(request.scope))

    def mlflow_response(exc: mlflow.exceptions.MlflowException) -> Response:
        return Response(content=exc.serialize_as_json(), media_type="application/json", status_code=exc.get_http_status_code())

    async def defer(handler, request: Request, exc: Exception):
        response = handler(request, exc)
        return await response if inspect.isawaitable(response) else response

    original_mlflow = app.exception_handlers.get(mlflow.exceptions.MlflowException)
    original_validation = app.exception_handlers.get(RequestValidationError)
    original_http = app.exception_handlers.get(HTTPException)

    @app.exception_handler(mlflow.exceptions.MlflowException)
    async def skill_registry_mlflow_exception(request: Request, exc: mlflow.exceptions.MlflowException):
        if on_registry(request) or original_mlflow is None:
            return mlflow_response(exc)
        return await defer(original_mlflow, request, exc)

    if original_validation is not None:

        @app.exception_handler(RequestValidationError)
        async def skill_registry_validation_error(request: Request, exc: RequestValidationError):
            if on_registry(request):
                messages = "; ".join(str(error.get("msg", error)) if isinstance(error, dict) else str(error) for error in exc.errors())
                return mlflow_response(mlflow.exceptions.MlflowException.invalid_parameter_value(f"Invalid request: {messages}"))
            return await defer(original_validation, request, exc)

    if original_http is not None:

        @app.exception_handler(HTTPException)
        async def skill_registry_http_exception(request: Request, exc: HTTPException):
            if on_registry(request):
                return JSONResponse(status_code=exc.status_code, content={"error_code": "BAD_REQUEST", "message": exc.detail}, headers=exc.headers)
            return await defer(original_http, request, exc)
