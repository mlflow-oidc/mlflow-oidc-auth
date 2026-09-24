"""Every route MLflow serves must be accounted for by the authorization layer (#286, #291).

``before_request_hook`` refuses a non-admin request on a route that has no validator, no
response filter and no entry on the open list (``hooks/route_policy.py``). That makes a
missing validator a denial rather than an unchecked route, but a denial is still a broken
feature for the users who should have access, so these tests sweep the WHOLE surface:

* ``test_every_flask_route_is_accounted_for`` walks every rule in MLflow's Flask
  ``url_map`` and every method it serves (HEAD folded onto GET, exactly as the hook does).
  Each pair must be validator-mapped, filtered in ``after_request``, served under an
  unprotected prefix, or listed below. A new MLflow route that is none of these fails.
* ``test_every_mutating_proto_is_gated`` walks every protobuf message MLflow registers via
  ``get_endpoints()`` and requires every one that looks like a mutation to be gated.

The lists below may only SHRINK: an entry that gains a validator, or that MLflow stops
registering, fails the test until it is removed.
"""

import re

import pytest
from flask import request
from mlflow.server import app as mlflow_app
from mlflow.server.handlers import get_endpoints

from mlflow_oidc_auth.hooks import before_request
from mlflow_oidc_auth.hooks.http_method import authorization_method
from mlflow_oidc_auth.hooks.route_policy import LEGITIMATELY_OPEN, is_filtered_in_after_request

# Routes that are open by design live in production code (hooks/route_policy.py), which
# before_request_hook consults before refusing a route with no validator. Importing the
# same list here means the sweep and the hook cannot disagree about what is open.

# Routes MLflow registers that have no validator yet; entries are removed as validators land.
# Never add an entry here without a validator PR.
ROUTES_AWAITING_VALIDATOR: tuple = ()

# Protobuf messages whose names mark them as mutations. Anything matching must be gated.
_MUTATING_PROTO_NAME = re.compile(
    r"^(Log|Set|Delete|Update|Create|Restore|Rename|Transition|Finalize|Batch|Start|End|Add|Remove|Upsert"
    r"|Link|Register|Attach|Detach|Cancel|Abort|Complete|Upload|Merge|Test|Invoke)"
)

# Mutating messages that are deliberately left without a validator. Each needs a reason.
# Empty today: every mutation must be gated or listed (per route) in the sets above.
DELIBERATELY_UNMAPPED_MUTATIONS: frozenset = frozenset()


def _concrete(rule_path: str) -> str:
    """A request path that matches ``rule_path`` (every converter replaced by one segment)."""
    return re.sub(r"<[^>]+>", "x", rule_path)


def _served_methods(rule) -> set:
    """Methods a rule serves, with HEAD folded onto GET exactly as the hook folds it.

    OPTIONS is dropped only where Flask answers it automatically — such a request never
    reaches a view. A rule that declares its own OPTIONS handler keeps it.
    """
    methods = set(rule.methods or ())
    if rule.provide_automatic_options:
        methods.discard("OPTIONS")
    return {authorization_method(m) for m in methods}


def _classify(rule_path: str, method: str) -> str | None:
    """How the authorization layer handles one route/method pair, or None if it does not."""
    path = _concrete(rule_path)
    if before_request._is_unprotected_route(path):
        return "unprotected-prefix"
    with mlflow_app.test_request_context(path, method=method):
        if before_request._find_validator(request) is not None:
            return "validator"
        if before_request._is_proxy_artifact_path(path):
            # Unrecognised artifact routes are denied by the hook, so any match is gated.
            return "artifact-proxy"
    if is_filtered_in_after_request(rule_path, method):
        return "filtered"
    return None


def _all_pairs():
    return sorted({(str(rule), method) for rule in mlflow_app.url_map.iter_rules() for method in _served_methods(rule)})


def _expand(entries):
    return {(path, method) for path, methods in entries for method in methods}


_LISTED = {
    "LEGITIMATELY_OPEN": _expand(LEGITIMATELY_OPEN),
    "ROUTES_AWAITING_VALIDATOR": _expand(ROUTES_AWAITING_VALIDATOR),
}


def test_lists_do_not_overlap():
    names = list(_LISTED)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not (_LISTED[a] & _LISTED[b]), f"{a} and {b} overlap: {sorted(_LISTED[a] & _LISTED[b])}"


def test_every_flask_route_is_accounted_for():
    """A new MLflow route that reaches no check fails here, whatever its method."""
    listed = set().union(*_LISTED.values())
    unaccounted = [f"{method} {path}" for path, method in _all_pairs() if _classify(path, method) is None and (path, method) not in listed]
    assert not unaccounted, (
        "MLflow serves these with no authorization check. Map each to a validator in "
        "hooks/before_request.py (see mlflow_oidc_auth/AGENTS.md):\n" + "\n".join(unaccounted)
    )


@pytest.mark.parametrize("list_name", list(_LISTED))
def test_listed_routes_only_shrink(list_name):
    """An entry that gained a validator, or that MLflow no longer serves, must be removed."""
    served = set(_all_pairs())
    stale = sorted(f"{m} {p}" for p, m in _LISTED[list_name] if (p, m) not in served)
    assert not stale, f"{list_name} lists routes MLflow does not serve; remove them:\n" + "\n".join(stale)
    now_handled = sorted(f"{m} {p} -> {_classify(p, m)}" for p, m in _LISTED[list_name] if _classify(p, m) is not None)
    assert not now_handled, f"{list_name} lists routes that are now handled; remove them:\n" + "\n".join(now_handled)


def test_not_implemented_routes_really_are():
    """The LEGITIMATELY_OPEN reason for these is that MLflow serves nothing on them."""
    not_implemented = {
        "/api/2.0/mlflow/unified-traces",
        "/ajax-api/2.0/mlflow/unified-traces",
        "/api/2.0/mlflow/get-online-trace-details",
        "/ajax-api/2.0/mlflow/get-online-trace-details",
    }
    endpoints = {str(rule): rule.endpoint for rule in mlflow_app.url_map.iter_rules() if str(rule) in not_implemented}
    assert set(endpoints) == not_implemented
    for path, endpoint in endpoints.items():
        assert mlflow_app.view_functions[endpoint].__name__ == "_not_implemented", f"{path} now has a real handler: it needs a validator"


def test_head_is_folded_in_the_sweep():
    """The sweep must see HEAD as GET, or it would report every GET route twice or miss #286."""
    rule = next(r for r in mlflow_app.url_map.iter_rules() if str(r) == "/get-artifact")
    assert "HEAD" in rule.methods
    assert _served_methods(rule) == {"GET"}
    assert _classify("/get-artifact", "GET") == "validator"


def _proto_pairs():
    """{proto class: {(path, method)}} for every protobuf endpoint MLflow registers."""
    pairs: dict = {}
    for path, handler, methods in get_endpoints(lambda request_class: request_class):
        if hasattr(handler, "DESCRIPTOR"):
            pairs.setdefault(handler, set()).update((path, m) for m in methods)
    return pairs


def test_every_mutating_proto_is_gated():
    """Every Log*/Set*/Delete*/Create*/... message must reach a validator on every route.

    LogInputs and LogOutputs were missed while every sibling run-mutating proto was
    mapped; this fails as soon as MLflow adds the next one.
    """
    pairs = _proto_pairs()
    mutating = {cls for cls in pairs if _MUTATING_PROTO_NAME.match(cls.__name__)}
    assert len(mutating) > 50, "precondition: expected MLflow to register many mutating protos"

    tracked = _LISTED["ROUTES_AWAITING_VALIDATOR"]
    gaps = []
    for cls in sorted(mutating, key=lambda c: c.__name__):
        if cls.__name__ in DELIBERATELY_UNMAPPED_MUTATIONS:
            continue
        for path, method in sorted(pairs[cls]):
            kind = _classify(path, method)
            # A filter trims a RESPONSE; it cannot stop a write, so it never counts here.
            if kind in ("validator", "artifact-proxy") or (path, method) in tracked:
                continue
            gaps.append(f"{cls.__name__}: {method} {path} ({kind or 'no check'})")
    assert not gaps, "mutating protos reaching no validator:\n" + "\n".join(gaps)


def test_log_inputs_and_outputs_are_gated_like_log_batch():
    """The two #291 protos must share LogBatch's validator, not merely have one."""
    from mlflow.protos.service_pb2 import LogBatch, LogInputs, LogOutputs

    handlers = before_request.BEFORE_REQUEST_HANDLERS
    assert handlers[LogInputs] is handlers[LogBatch]
    assert handlers[LogOutputs] is handlers[LogBatch]


def test_deliberately_unmapped_mutations_are_real_protos():
    names = {cls.__name__ for cls in _proto_pairs()}
    assert DELIBERATELY_UNMAPPED_MUTATIONS <= names
