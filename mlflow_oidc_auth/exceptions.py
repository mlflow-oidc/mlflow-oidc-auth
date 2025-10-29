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

        return JSONResponse(
            status_code=status_code,
            content={"error_code": exc.error_code, "message": str(exc), "details": getattr(exc, "message", None)},
        )
