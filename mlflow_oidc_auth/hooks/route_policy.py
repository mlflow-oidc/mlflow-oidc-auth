"""Which MLflow routes may be served to a non-admin without a per-resource validator.

``before_request_hook`` refuses a non-admin request whose route has no validator, unless the
route is accounted for here: listed in :data:`LEGITIMATELY_OPEN`, or a search/list route whose
response ``after_request`` filters down to what the caller may read. Admins are not affected.

The validator-coverage sweep (``tests/hooks/test_validator_coverage_sweep.py``) imports the
same list, so the test and the hook cannot disagree about which routes are open.
"""

from __future__ import annotations

import os

from mlflow.server.handlers import STATIC_PREFIX_ENV_VAR

# Routes that any AUTHENTICATED user may call without a resource check. Unauthenticated
# requests are still answered 401 by the hook before this list is consulted.
# Paths are MLflow's Flask rule strings without the optional static prefix; every entry
# needs a reason.
LEGITIMATELY_OPEN: tuple[tuple[str, tuple[str, ...]], ...] = (
    # The MLflow web UI shell and its bundled static assets. No tenant data.
    ("/", ("GET",)),
    ("/build/<path:filename>", ("GET",)),
    # MLflow's version string.
    ("/version", ("GET",)),
    # Server capability flags the UI reads at start-up (e.g. which store backs it).
    ("/api/3.0/mlflow/server-info", ("GET",)),
    ("/ajax-api/3.0/mlflow/server-info", ("GET",)),
    # UI usage-telemetry config and event sink. Carries no tracking data.
    ("/ajax-api/3.0/mlflow/ui-telemetry", ("GET", "POST")),
    # GraphQL is authorized per field by our own middleware
    # (install_mlflow_graphql_authorization_middleware in app.py), not by a route validator.
    ("/graphql", ("GET", "POST")),
    # Bound by MLflow to its `_not_implemented` handler: they answer 501 and serve nothing.
    # test_not_implemented_routes_really_are pins that.
    ("/api/2.0/mlflow/unified-traces", ("GET",)),
    ("/ajax-api/2.0/mlflow/unified-traces", ("GET",)),
    ("/api/2.0/mlflow/get-online-trace-details", ("GET",)),
    ("/ajax-api/2.0/mlflow/get-online-trace-details", ("GET",)),
)

_OPEN_PAIRS: frozenset[tuple[str, str]] = frozenset((path, method) for path, methods in LEGITIMATELY_OPEN for method in methods)


def strip_static_prefix(rule: str) -> str:
    """``rule`` without MLflow's optional static prefix (``--static-prefix``).

    MLflow registers most of its routes under that prefix when it is set, so the open list
    is kept prefix-free and every rule is compared without it.
    """
    prefix = (os.environ.get(STATIC_PREFIX_ENV_VAR) or "").rstrip("/")
    if prefix and (rule == prefix or rule.startswith(prefix + "/")):
        return rule[len(prefix) :] or "/"
    return rule


def is_legitimately_open(rule: str, method: str) -> bool:
    """True if ``method`` on the Flask rule ``rule`` is open to any authenticated user.

    Parameters:
        rule: The matched Flask rule string (``request.url_rule.rule``), e.g. ``/version``.
        method: The HTTP method, with HEAD already folded onto GET.

    Returns:
        Whether the route is on :data:`LEGITIMATELY_OPEN`.
    """
    return (strip_static_prefix(rule), method) in _OPEN_PAIRS


def is_filtered_in_after_request(rule: str, method: str) -> bool:
    """True if ``after_request`` trims this route's response to what the caller may read.

    Parameters:
        rule: The matched Flask rule string.
        method: The HTTP method, with HEAD already folded onto GET.

    Returns:
        Whether a ``_filter_*`` after-request handler is bound to the route.
    """
    # Imported lazily: after_request imports the validators package, which is also
    # imported by before_request, the only production caller of this module.
    from mlflow_oidc_auth.hooks.after_request import AFTER_REQUEST_HANDLERS

    handler = AFTER_REQUEST_HANDLERS.get((rule, method))
    return handler is not None and handler.__name__.startswith("_filter_")
