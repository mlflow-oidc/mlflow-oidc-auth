"""Shared pieces of the three gateway list routes (#470).

Each route builds its list-item models once, orders and pages those, and returns the model list, so FastAPI
validates it against the route's ``response_model`` and serialises it. The pagination headers go on the injected
``Response``.
"""

from typing import Any, Callable, Iterable, List, TypeVar

from fastapi import Response

from mlflow_oidc_auth.utils.pagination import PageParams, paginate_with_headers

M = TypeVar("M")


def as_text(*values: Any) -> str:
    """Return the first truthy value as text, or an empty string.

    A present value that is not a string (a shape change in MLflow) is coerced with ``str()`` rather than
    failing the response model's validation, which would turn the whole list into a 500.

    Parameters:
        *values: Candidate values, most preferred first. ``None`` and other falsy values are skipped.

    Returns:
        The first truthy value as a string, or ``""``.
    """
    for value in values:
        if value:
            return value if isinstance(value, str) else str(value)
    return ""


def page_models(models: Iterable[M], key: Callable[[M], str], page: PageParams, response: Response) -> List[M]:
    """Search, order and slice list-item models, and set ``X-Total-Count`` when the request paged.

    Parameters:
        models: The models for the items the caller may see (never an unfiltered list).
        key: Returns a model's display key.
        page: The request's pagination parameters.
        response: The injected response whose headers receive the total.

    Returns:
        The page of models.
    """
    items, headers = paginate_with_headers(models, key=key, params=page)
    response.headers.update(headers)
    return items
