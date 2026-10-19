"""Map an ``MlflowException``'s error code to an HTTP status, for the FastAPI routers.

``MlflowException.error_code`` holds the code's NAME (``"RESOURCE_ALREADY_EXISTS"``), not the int
proto constant, so a comparison with the constant never matches (#475). Every router compares
through :func:`mlflow_error_status` / :func:`has_error_code` instead of by hand.
"""

from typing import Mapping, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST, ErrorCode

GRANT_ERROR_STATUS: Mapping[int, int] = {
    RESOURCE_ALREADY_EXISTS: 409,
    INVALID_PARAMETER_VALUE: 400,
    RESOURCE_DOES_NOT_EXIST: 404,
}
"""The statuses a store refusal maps to; anything else is a 500."""


def has_error_code(error: BaseException, *codes: int) -> bool:
    """Whether ``error`` is an ``MlflowException`` carrying one of ``codes``.

    Parameters:
        error: The exception.
        codes: Proto error code constants, e.g. ``RESOURCE_ALREADY_EXISTS``.

    Returns:
        ``True`` if the exception's error code is one of them.
    """
    if not isinstance(error, MlflowException):
        return False
    return getattr(error, "error_code", None) in {ErrorCode.Name(code) for code in codes}


def mlflow_error_status(error: BaseException, statuses: Mapping[int, int] = GRANT_ERROR_STATUS) -> Optional[int]:
    """The HTTP status ``error``'s error code maps to, or ``None``.

    Parameters:
        error: The exception; anything but an ``MlflowException`` maps to ``None``.
        statuses: Proto error code constant to HTTP status.

    Returns:
        The status, or ``None`` if the error is not an ``MlflowException`` or its code is unmapped.
    """
    for code, status in statuses.items():
        if has_error_code(error, code):
            return status
    return None
