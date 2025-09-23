# """
# Flask Hooks Bridge - Compatibility Layer for Flask Hooks with FastAPI Auth
# """

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def get_fastapi_username() -> str:
    """
    Get username from FastAPI authentication context via Flask request environ.

    FastAPI AuthMiddleware stores auth info in ASGI scope, and AuthPassingWSGIMiddleware
    injects it into Flask's WSGI environ where we can access it here.

    Returns:
        Username if authenticated, None otherwise
    """
    try:
        from flask import request

        # Get username from WSGI environ (set by AuthPassingWSGIMiddleware)
        if hasattr(request, "environ"):
            username = request.environ.get("mlflow_oidc_auth.username")
            logger.debug(f"Retrieved FastAPI username from Flask environ: {username}")
            if username:
                return username
    except Exception as e:
        logger.debug(f"Could not access FastAPI username from Flask request: {e}")

    raise Exception("Could not retrieve FastAPI username")


def get_fastapi_admin_status() -> bool:
    """
    Get admin status from FastAPI authentication context via Flask request environ.

    FastAPI AuthMiddleware stores auth info in ASGI scope, and AuthPassingWSGIMiddleware
    injects it into Flask's WSGI environ where we can access it here.

    Returns:
        True if user is admin, False otherwise
    """
    try:
        from flask import request

        # Get admin status from WSGI environ (set by AuthPassingWSGIMiddleware)
        if hasattr(request, "environ"):
            is_admin = request.environ.get("mlflow_oidc_auth.is_admin", False)
            logger.debug(f"Retrieved FastAPI admin status from Flask environ: {is_admin}")
            return is_admin
        else:
            logger.debug("Flask request has no environ attribute")
    except Exception as e:
        logger.debug(f"Could not access FastAPI admin status from Flask request: {e}")

    return False
