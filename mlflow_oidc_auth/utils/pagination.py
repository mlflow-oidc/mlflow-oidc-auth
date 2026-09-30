"""Opt-in offset pagination and search for the plugin's own list endpoints.

Every list endpoint that supports it accepts three query parameters:

* ``limit`` (1..``MAX_PAGE_SIZE``) — the page size. Absent, the endpoint returns its full list
  exactly as it always has, so existing clients see no change.
* ``offset`` (>= 0, default 0) — items to skip. Ignored without ``limit``.
* ``search`` — a case-insensitive substring match on the item's display key. Applies with or
  without ``limit``.

When ``limit`` or ``search`` is given, items are ordered by their display key (case-insensitive,
tie-broken by id) and the number of matching items is returned in the ``X-Total-Count`` header.
The body keeps the shape the endpoint always had; only its contents are the requested page.

Pagination runs strictly **after** the endpoint's authorization filtering: callers pass in only
the items the caller may see, so the total never counts a hidden resource.
"""

from dataclasses import dataclass
from typing import Annotated, Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar

from fastapi import Depends, Query

#: The largest page a client may request.
MAX_PAGE_SIZE = 500

#: The longest search string accepted — a display key is never longer than this in practice.
MAX_SEARCH_LENGTH = 256

#: Response header carrying the number of matching items before slicing.
TOTAL_COUNT_HEADER = "X-Total-Count"

T = TypeVar("T")


@dataclass(frozen=True)
class PageParams:
    """The pagination and search parameters of one list request.

    Parameters:
        limit: Page size, or None for the full list.
        offset: Items to skip before the page starts. Only used with ``limit``.
        search: Case-insensitive substring to match against the display key, or None.
    """

    limit: Optional[int] = None
    offset: int = 0
    search: Optional[str] = None

    @property
    def active(self) -> bool:
        """Whether the request asked for paging or search — and so gets ordering and a total.

        Returns:
            True when ``limit`` or ``search`` was given.
        """
        return self.limit is not None or self.search is not None


#: The parameters of a request that asked for neither paging nor search.
NO_PAGE = PageParams()


def page_params(
    limit: Optional[int] = Query(None, ge=1, le=MAX_PAGE_SIZE, description=f"Page size (1..{MAX_PAGE_SIZE}). Omit for the full list."),
    offset: int = Query(0, ge=0, description="Items to skip before the page. Ignored without limit."),
    search: Optional[str] = Query(None, max_length=MAX_SEARCH_LENGTH, description="Case-insensitive substring match on the item's name."),
) -> PageParams:
    """FastAPI dependency reading ``limit``, ``offset`` and ``search`` from the query string.

    Out-of-range values are rejected by FastAPI's validation with a 422 before the endpoint runs.

    Parameters:
        limit: Page size, 1..``MAX_PAGE_SIZE``; None for the full list.
        offset: Items to skip, >= 0.
        search: Substring to match; an empty string is treated as no search.

    Returns:
        PageParams: The validated parameters.
    """
    return PageParams(limit=limit, offset=offset, search=search or None)


#: Annotated parameter type for endpoints: ``page: PageQuery = NO_PAGE``. The default keeps the
#: endpoint callable directly (as in unit tests) without paging.
PageQuery = Annotated[PageParams, Depends(page_params)]


def _tiebreak(value: Any) -> Tuple[int, Any]:
    """Sort key for an id: numeric ids in numeric order, then everything else as text."""
    if isinstance(value, bool) or value is None:
        return (2, str(value))
    if isinstance(value, int):
        return (0, value)
    text = str(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text)


def paginate(
    items: Iterable[T],
    key: Callable[[T], Optional[str]],
    params: PageParams,
    tiebreak: Optional[Callable[[T], Any]] = None,
) -> Tuple[List[T], int]:
    """Search, order and slice a list that has already been filtered for authorization.

    Without ``limit`` or ``search`` the items come back untouched, in their original order.
    Otherwise: keep items whose display key contains ``search`` (case-insensitive), sort by the
    display key case-insensitively (then by the exact key, then by ``tiebreak``), and take
    ``[offset:offset + limit]``.

    Parameters:
        items: The items the caller is allowed to see. Never pass an unfiltered list.
        key: Returns an item's display key. None is treated as an empty string.
        params: The request's pagination parameters.
        tiebreak: Returns an item's id, used to order items with equal keys.

    Returns:
        Tuple[List[T], int]: The page, and the number of matching items before slicing.
    """
    materialized: List[T] = list(items)
    if not params.active:
        return materialized, len(materialized)

    def display(item: T) -> str:
        value = key(item)
        return "" if value is None else str(value)

    if params.search is not None:
        needle = params.search.casefold()
        materialized = [item for item in materialized if needle in display(item).casefold()]

    def sort_key(item: T) -> Tuple[str, str, Tuple[int, Any]]:
        text = display(item)
        return (text.casefold(), text, _tiebreak(tiebreak(item)) if tiebreak else (0, 0))

    materialized.sort(key=sort_key)
    total = len(materialized)
    if params.limit is None:
        return materialized, total
    return materialized[params.offset : params.offset + params.limit], total


def total_count_headers(total: int, params: PageParams) -> Dict[str, str]:
    """The ``X-Total-Count`` header for a paged or searched response.

    Parameters:
        total: Matching items before slicing, as returned by :func:`paginate`.
        params: The request's pagination parameters.

    Returns:
        Dict[str, str]: ``{"X-Total-Count": "<total>"}`` when paging or search was requested,
        otherwise an empty dict so an unpaged response is unchanged.
    """
    return {TOTAL_COUNT_HEADER: str(total)} if params.active else {}


def paginate_with_headers(
    items: Iterable[T], key: Callable[[T], Optional[str]], params: PageParams, tiebreak: Optional[Callable[[T], Any]] = None
) -> Tuple[List[T], Dict[str, str]]:
    """:func:`paginate` plus :func:`total_count_headers`, for the common case.

    Parameters:
        items: The items the caller is allowed to see.
        key: Returns an item's display key.
        params: The request's pagination parameters.
        tiebreak: Returns an item's id, used to order items with equal keys.

    Returns:
        Tuple[List[T], Dict[str, str]]: The page, and the headers to add to the response.
    """
    page, total = paginate(items, key, params, tiebreak)
    return page, total_count_headers(total, params)
