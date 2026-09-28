"""The HTTP method an authorization lookup must be keyed on (issue #286).

werkzeug auto-registers ``HEAD`` on every ``GET`` rule and dispatches it to the same
view, stripping the body afterwards but keeping ``Content-Length``. MLflow's endpoint
registry (and therefore every validator and filter map in this package) only ever
records ``GET``. A lookup keyed on the literal method therefore finds nothing for a
``HEAD``, and a missing validator is not a deny — the request falls through and the
response headers become an existence and exact-size oracle over any tenant's data.

Every lookup that decides authorization or response filtering by method must go
through :func:`authorization_method` so the fold cannot be applied in one place and
forgotten in another.
"""


def authorization_method(method: str) -> str:
    """Return the method whose validator governs a request sent with ``method``.

    Parameters:
        method: The literal HTTP method of the request.

    Returns:
        ``"GET"`` for ``"HEAD"`` (werkzeug serves HEAD through the GET view);
        every other method unchanged.
    """
    return "GET" if method == "HEAD" else method
