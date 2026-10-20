"""Group names containing "/" on the group permission routes (``routers/_group_route.py``).

A group name may contain "/" — Keycloak sends ``/data-science`` — and clients percent-encode it.
Matched on the decoded path, a name such as ``x/prompts`` used to land on another route with group
``x``: these tests resolve every group route, for names built to collide with the route keywords,
the way the router does, and require each to reach its own route with its own group.
"""

from unittest.mock import MagicMock
from urllib.parse import quote, unquote

import pytest
from starlette.routing import Match

from mlflow_oidc_auth.routers import get_all_routers
from mlflow_oidc_auth.middleware.route_path import routed_path
from mlflow_oidc_auth.routers._group_route import GroupNameRoute, segment_preserving_path

GROUP_BASE = "/api/2.0/mlflow/permissions/groups"

# Each segment of the keyword-shaped names is a literal of some group route.
CONFUSABLE_NAMES = [
    "/data-science",
    "org/team",
    "x/experiments",
    "x/experiments/1",
    "x/users",
    "x/prompts",
    "x/scorers/1",
    "x/mcp-servers",
    "x/gateways/endpoints",
    "50%",
    "%2F",
    "a%2Fb",
]


# In the order the app registers them. Newer FastAPI keeps an included router as one nested route,
# so the app's own route list does not show them; the routers' routes are what it matches with.
ROUTES = [route for router in get_all_routers() for route in router.routes]
GROUP_ROUTES = [route for route in ROUTES if "{group_name}" in getattr(route, "path", "")]


def _resolve(raw_path: str, method: str):
    """The first route matching in full, and its path parameters, as the router would dispatch."""
    scope = {"type": "http", "method": method, "path": unquote(raw_path), "raw_path": raw_path.encode(), "root_path": ""}
    for route in ROUTES:
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            return route, child_scope["path_params"]
    return None, None


def _cases():
    for route in GROUP_ROUTES:
        for method in sorted(route.methods - {"HEAD"}):
            for name in CONFUSABLE_NAMES:
                yield pytest.param(route, method, name, id=f"{method} {route.path} {name}")


def test_every_group_route_uses_the_group_name_route():
    assert GROUP_ROUTES, "no group routes found"
    assert all(isinstance(route, GroupNameRoute) for route in GROUP_ROUTES)


@pytest.mark.parametrize("route,method,name", list(_cases()))
def test_a_percent_encoded_group_name_reaches_its_own_route(route, method, name):
    # A ``:path`` parameter after the group gets a value with a "/" of its own.
    params = {key: "nested/value" if convertor.regex == ".*" else "1" for key, convertor in route.param_convertors.items()}
    params["group_name"] = name
    raw_path = route.path
    for key, value in params.items():
        raw_path = raw_path.replace(f"{{{key}:path}}", quote(value, safe="")).replace(f"{{{key}}}", quote(value, safe=""))

    resolved, path_params = _resolve(raw_path, method)

    assert resolved is route
    assert path_params == params


@pytest.mark.parametrize(
    "raw_path",
    [
        f"{GROUP_BASE}//data-science/experiments",  # unencoded leading "/": an empty group segment
        f"{GROUP_BASE}/x/prompts/prompts",  # unencoded: group "x", not "x/prompts"
    ],
)
def test_an_unencoded_slash_separates(raw_path):
    resolved, path_params = _resolve(raw_path, "GET")
    assert resolved is None or path_params.get("group_name") == "x"


class TestSegmentPreservingPath:
    def test_keeps_slash_and_percent_encoded_inside_a_segment(self):
        scope = {"path": "/groups//a b/50%/x", "raw_path": b"/groups/%2Fa%20b/50%25/x"}
        assert segment_preserving_path(scope) == "/groups/%2Fa b/50%25/x"

    def test_without_raw_path(self):
        assert segment_preserving_path({"path": "/groups/a/x"}) is None

    def test_raw_path_that_does_not_decode_to_path(self):
        """Something rewrote ``path`` after the server decoded it: match nothing."""
        assert segment_preserving_path({"path": "/groups/b/x", "raw_path": b"/groups/a/x"}) is None

    def test_strips_a_forwarded_prefix_as_the_middleware_does(self):
        scope = {"path": "/ml/groups//a/x", "raw_path": b"/ml/groups/%2Fa/x", "root_path": "/ml"}
        assert segment_preserving_path(scope) == "/groups/%2Fa/x"

    def test_a_prefix_ending_inside_an_encoded_segment(self):
        """The middleware strips ``/a`` from ``/a/b/...``; the client sent ``a%2Fb`` as one segment."""
        scope = {"path": "/a/b/groups/g/x", "raw_path": b"/a%2Fb/groups/g/x", "root_path": "/a"}
        assert segment_preserving_path(scope) is None


@pytest.mark.parametrize(
    "root_path,raw_path",
    [
        # The prefix as the client encoded it: the middleware does not strip it from the decoded path.
        ("/health%2Fx", f"/health%2Fx{GROUP_BASE}/g/experiments"),
        ("/a", f"/a%2Fb{GROUP_BASE}/g/experiments"),
    ],
)
def test_a_forwarded_prefix_cannot_split_router_and_middleware(root_path, raw_path):
    """A group route matches only when the middleware's routed path is that group route too."""
    scope = {"type": "http", "method": "GET", "path": unquote(raw_path), "raw_path": raw_path.encode(), "root_path": root_path}
    assert not routed_path(scope).startswith(GROUP_BASE + "/")
    assert all(route.matches(scope)[0] == Match.NONE for route in GROUP_ROUTES)


def test_a_forwarded_prefix_still_routes():
    raw_path = f"/ml{GROUP_BASE}/{quote('x/prompts', safe='')}/prompts"
    scope = {"type": "http", "method": "GET", "path": unquote(raw_path), "raw_path": raw_path.encode(), "root_path": "/ml"}
    [(route, params)] = [(r, c["path_params"]) for r in GROUP_ROUTES for m, c in [r.matches(scope)] if m == Match.FULL]
    assert route.path == f"{GROUP_BASE}/{{group_name}}/prompts"
    assert params == {"group_name": "x/prompts"}


@pytest.mark.parametrize("route_suffix", ["registered-models/{name:path}", "prompts/{prompt_name:path}"])
def test_without_raw_path_a_slash_name_never_reaches_another_group(route_suffix):
    """Fail closed: on the decoded path ``x%2Fregistered-models`` would read as group ``x``."""
    route = next(r for r in GROUP_ROUTES if r.path == f"{GROUP_BASE}/{{group_name}}/{route_suffix}")
    keyword = route_suffix.split("/", 1)[0]
    scope = {"type": "http", "method": next(iter(route.methods)), "path": f"{GROUP_BASE}/x/{keyword}/{keyword}/m", "root_path": ""}
    assert route.matches(scope)[0] == Match.NONE


def test_only_the_routes_own_parameters_are_decoded():
    """A value an enclosing scope matched is decoded already; decoding it again would change it."""
    route = next(r for r in GROUP_ROUTES if r.path == f"{GROUP_BASE}/{{group_name}}/prompts")
    raw_path = f"{GROUP_BASE}/x/prompts"
    scope = {"type": "http", "method": "GET", "path": raw_path, "raw_path": raw_path.encode(), "path_params": {"outer": "a%41"}}
    match, child_scope = route.matches(scope)
    assert match == Match.FULL
    assert child_scope["path_params"] == {"outer": "a%41", "group_name": "x"}


@pytest.mark.usefixtures("authenticated_session")
@pytest.mark.parametrize("name", ["x/prompts", "/data-science", "x/experiments", "50%"])
def test_the_handler_reads_the_whole_group_name(admin_client, mock_store, name):
    """Over HTTP, through the app's middleware and FastAPI's own router: ``x%2Fprompts`` is group ``x/prompts``."""
    prompt = MagicMock()
    prompt.name = "p"
    prompt.permission = "READ"
    mock_store.get_group_prompts.return_value = [prompt]

    response = admin_client.get(f"{GROUP_BASE}/{quote(name, safe='')}/prompts")

    assert response.status_code == 200, response.text
    mock_store.get_group_prompts.assert_called_once_with(name)


def test_a_route_without_a_group_name_matches_on_the_decoded_path():
    """Only a ``{group_name}`` route needs ``raw_path``; the others of a group router match as usual."""
    routes = [route for route in ROUTES if isinstance(route, GroupNameRoute) and "{group_name}" not in route.path]
    assert routes
    for route in routes:
        path = route.path.replace("{", "").replace("}", "")
        scope = {"type": "http", "method": next(iter(route.methods)), "path": path, "root_path": ""}
        assert route.matches(scope)[0] == Match.FULL, route.path


def test_workspace_routes_without_a_group_name_keep_the_default_route_class():
    from mlflow_oidc_auth.routers.workspace_permissions import workspace_permissions_router

    assert {route.path for route in workspace_permissions_router.routes if isinstance(route, GroupNameRoute)} == {
        "/api/3.0/mlflow/permissions/workspaces/{workspace}/groups/{group_name}"
    }


def test_the_path_is_worked_out_once_per_scope():
    raw_path = f"{GROUP_BASE}/{quote('x/prompts', safe='')}/prompts"
    scope = {"type": "http", "path": unquote(raw_path), "raw_path": raw_path.encode(), "root_path": ""}
    first = segment_preserving_path(scope)
    assert segment_preserving_path(scope) == first == f"{GROUP_BASE}/x%2Fprompts/prompts"

    # A scope rewritten after the first call is worked out again, not served from the cache.
    scope["path"] = f"{GROUP_BASE}/y/prompts"
    assert segment_preserving_path(scope) is None


def test_a_utf8_raw_path():
    scope = {"path": "/groups/équipe/x", "raw_path": "/groups/équipe/x".encode()}
    assert segment_preserving_path(scope) == "/groups/équipe/x"
