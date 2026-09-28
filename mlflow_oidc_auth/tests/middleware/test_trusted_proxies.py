"""
Forwarded headers are honoured only from a client listed in ``TRUSTED_PROXIES``.

Runs ``ProxyHeadersMiddleware`` in front of a route that reports what each consumer of the
request context derives from it: the routed path, the OIDC redirect URI, the SAML SP base URL,
the login path, the UI URL and the recorded client address (including the one the SCIM
dependency audits and rate-limits on). ``scope["client"]`` itself always stays the direct
connection. Three cases are checked for every header:

* ``TRUSTED_PROXIES`` unset — ignored from every client, the direct connection is used;
* set to the connecting client's network — honoured;
* set to another network — ignored.
"""

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, Request
from starlette.testclient import TestClient

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.middleware.proxy_headers_middleware import ProxyHeadersMiddleware, client_address
from mlflow_oidc_auth.middleware.route_path import routed_path

PROXY = ("10.0.0.5", 40000)
DIRECT_HOST = "mlflow.internal:5000"
FORWARDED = {
    "Host": DIRECT_HOST,
    "X-Forwarded-Proto": "https",
    "X-Forwarded-Host": "mlflow.example.com",
    "X-Forwarded-Prefix": "/mlflow",
    "X-Forwarded-For": "203.0.113.7",
}

# What the route reports with the forwarded headers applied, and with them ignored.
HONOURED = {
    "scheme": "https",
    "routed_path": "/echo",
    "root_path": "/mlflow",
    "redirect_uri": "https://mlflow.example.com/mlflow/callback",
    "sp_base_url": "https://mlflow.example.com/mlflow",
    "login_path": "/mlflow/login/entra",
    "ui_url": "https://mlflow.example.com/mlflow/oidc/ui/auth",
    "client": "203.0.113.7",
    "peer": PROXY[0],
}
IGNORED = {
    "scheme": "http",
    "routed_path": "/mlflow/echo",
    "root_path": "",
    "redirect_uri": "http://mlflow.internal:5000/callback",
    "sp_base_url": "http://mlflow.internal:5000",
    "login_path": "/login/entra",
    "ui_url": "http://mlflow.internal:5000/oidc/ui/auth",
    "client": PROXY[0],
    "peer": PROXY[0],
}


def _build_app() -> FastAPI:
    from mlflow_oidc_auth.dependencies import require_scim_token
    from mlflow_oidc_auth.routers.auth import _build_ui_url, _login_path
    from mlflow_oidc_auth.saml import sp_base_url
    from mlflow_oidc_auth.utils.uri import get_configured_or_dynamic_redirect_uri

    app = FastAPI()
    app.add_middleware(ProxyHeadersMiddleware)

    @app.get("/echo")
    @app.get("/mlflow/echo")
    async def echo(request: Request):
        return {
            "scheme": request.url.scheme,
            "routed_path": routed_path(request.scope),
            "root_path": request.scope.get("root_path", ""),
            "redirect_uri": get_configured_or_dynamic_redirect_uri(request, "/callback", None),
            "sp_base_url": sp_base_url(request),
            "login_path": _login_path(request, "/login/entra"),
            "ui_url": _build_ui_url(request, "/auth"),
            "client": client_address(request.scope),
            "peer": request.client.host if request.client else None,
        }

    @app.get("/scim-probe")
    async def scim_probe(record=Depends(require_scim_token)):
        return {"ok": True}

    return app


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.setattr(config, "OIDC_REDIRECT_URI", None, raising=False)

    def _make(trusted_proxies, client=PROXY):
        monkeypatch.setattr(config, "TRUSTED_PROXIES", trusted_proxies, raising=False)
        return TestClient(_build_app(), client=client, follow_redirects=False)

    return _make


@pytest.mark.parametrize(
    "trusted_proxies, expected",
    [
        pytest.param(None, IGNORED, id="unset"),
        pytest.param([], IGNORED, id="empty"),
        pytest.param([" ", ""], IGNORED, id="blank-entries"),
        pytest.param(["10.0.0.0/8"], HONOURED, id="client-network"),
        pytest.param(["10.0.0.5"], HONOURED, id="client-address"),
        pytest.param(["192.168.0.0/16"], IGNORED, id="other-network"),
        pytest.param(["not-a-cidr"], IGNORED, id="all-invalid"),
    ],
)
def test_forwarded_headers_follow_trusted_proxies(make_client, trusted_proxies, expected):
    client = make_client(trusted_proxies)
    # The proxy does not strip its prefix: with it recorded as root_path the request routes as
    # /echo; without it the raw path /mlflow/echo is routed as-is.
    response = client.get("/mlflow/echo", headers=FORWARDED)
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("client_addr", [("127.0.0.1", 40000), ("::1", 40000), ("203.0.113.9", 40000)])
def test_unset_ignores_forwarded_headers_from_any_client(make_client, client_addr):
    client = make_client([], client=client_addr)
    body = client.get("/mlflow/echo", headers=FORWARDED).json()
    assert body["scheme"] == "http"
    assert body["root_path"] == ""
    assert body["routed_path"] == "/mlflow/echo"
    assert body["redirect_uri"] == "http://mlflow.internal:5000/callback"
    assert body["client"] == body["peer"] == client_addr[0]


class TestForwardedClientAddress:
    """Which ``X-Forwarded-For`` entry becomes the client address behind a trusted proxy."""

    @pytest.mark.parametrize(
        "header, expected",
        [
            ("203.0.113.7", "203.0.113.7"),
            # The right-most address that is not a trusted proxy is the client; entries to its
            # left were supplied from further out.
            ("198.51.100.1, 203.0.113.7", "203.0.113.7"),
            ("198.51.100.1, 203.0.113.7, 10.0.0.9", "203.0.113.7"),
            # Every hop is a trusted proxy: the left-most one.
            ("10.0.0.8, 10.0.0.9", "10.0.0.8"),
            # Not an address: the direct connection is kept.
            ("unknown", PROXY[0]),
            ("198.51.100.1, garbage", PROXY[0]),
            ("", PROXY[0]),
        ],
    )
    def test_x_forwarded_for(self, make_client, header, expected):
        client = make_client(["10.0.0.0/8"])
        assert client.get("/echo", headers={"X-Forwarded-For": header}).json()["client"] == expected

    @pytest.mark.parametrize(
        "header, expected",
        [
            ("203.0.113.7:5678", "203.0.113.7"),
            ("[2001:db8::7]", "2001:db8::7"),
            ("[2001:db8::7]:443", "2001:db8::7"),
            ("2001:db8::7", "2001:db8::7"),
            # An IPv4-mapped trusted hop is recognised as trusted.
            ("203.0.113.7, ::ffff:10.0.0.9", "203.0.113.7"),
            ("203.0.113.7:notaport", PROXY[0]),
            ("[2001:db8::7]x", PROXY[0]),
        ],
    )
    def test_address_forms(self, make_client, header, expected):
        client = make_client(["10.0.0.0/8"])
        assert client.get("/echo", headers={"X-Forwarded-For": header}).json()["client"] == expected

    def test_repeated_header_lines_are_read_as_one_list(self, make_client):
        """A proxy that adds its own line rather than appending to the client's is read in order."""
        client = make_client(["10.0.0.0/8"])
        headers = [("x-forwarded-for", "127.0.0.1"), ("x-forwarded-for", "203.0.113.7")]
        assert client.get("/echo", headers=headers).json()["client"] == "203.0.113.7"

    @pytest.mark.parametrize("header", ["127.0.0.1", "::1", "0.0.0.0"])
    def test_forwarded_address_never_replaces_the_connection_address(self, make_client, header):
        """The forwarded address is recorded for rate limits and audit; ``request.client`` stays the peer."""
        client = make_client(["10.0.0.0/8"])
        body = client.get("/echo", headers={"X-Forwarded-For": header}).json()
        assert body["client"] == header
        assert body["peer"] == PROXY[0]

    def test_ipv4_mapped_peer_is_matched_against_ipv4_ranges(self, make_client):
        client = make_client(["10.0.0.0/8"], client=("::ffff:10.0.0.5", 40000))
        assert client.get("/echo", headers={"X-Forwarded-Proto": "https"}).json()["scheme"] == "https"

    @pytest.mark.parametrize("header, expected", [("203.0.113.7", "203.0.113.7"), ("not-an-ip", PROXY[0])])
    def test_x_real_ip(self, make_client, header, expected):
        client = make_client(["10.0.0.0/8"])
        assert client.get("/echo", headers={"X-Real-IP": header}).json()["client"] == expected

    def test_x_real_ip_ignored_when_untrusted(self, make_client):
        client = make_client([])
        assert client.get("/echo", headers={"X-Real-IP": "203.0.113.7"}).json()["client"] == PROXY[0]


def test_client_address_is_read_only_for_rate_limits_and_audit():
    """``client_address`` names a client for rate limits and audit records, never for authorization.

    Its one caller is the SCIM dependency. A new caller should be reviewed for that before this
    list grows.
    """
    from pathlib import Path

    import mlflow_oidc_auth

    root = Path(mlflow_oidc_auth.__file__).parent
    callers = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "tests" not in path.relative_to(root).parts and path.name != "proxy_headers_middleware.py" and "client_address(" in path.read_text()
    )
    assert callers == ["dependencies.py"]


class TestScimClientAddress:
    """The SCIM dependency audits and rate-limits on the address the trust decision produced."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        from mlflow_oidc_auth.dependencies import scim_auth_failure_audit, scim_auth_failure_limiter

        scim_auth_failure_audit.reset()
        scim_auth_failure_limiter.reset()
        yield
        scim_auth_failure_audit.reset()
        scim_auth_failure_limiter.reset()

    @pytest.mark.parametrize(
        "trusted_proxies, expected",
        [([], PROXY[0]), (["10.0.0.0/8"], "203.0.113.7"), (["192.168.0.0/16"], PROXY[0])],
    )
    def test_audited_client(self, make_client, trusted_proxies, expected):
        client = make_client(trusted_proxies)
        with patch("mlflow_oidc_auth.audit.emit_audit_event") as emit:
            response = client.get("/scim-probe", headers={"X-Forwarded-For": "203.0.113.7"})
        assert response.status_code == 401
        emit.assert_called_once()
        assert emit.call_args.kwargs["detail"]["client"] == expected
