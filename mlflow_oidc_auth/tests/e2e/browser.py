"""A headless "browser" for the end-to-end identity suite: httpx plus just enough HTML.

The suite drives real OIDC and SAML flows against a real Keycloak without a browser engine. That
works because every step is plain HTTP a browser would perform: follow a redirect, submit the
login form, auto-submit the SAML POST-binding form. What a browser adds on top — cookie scoping
and the SameSite rules — is reproduced here deliberately, because the SAML ACS behaves
differently depending on which cookies arrive with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

# ``routers._prefix.UI_ROUTER_PREFIX``, spelled out: importing it would import every router, and
# with them the app's configuration, into the test process that only plays the browser.
UI_ROUTER_PREFIX = "/oidc/ui"

# Hosts a browser treats as a secure context even over plain http (the "potentially trustworthy"
# origins of the Secure Contexts spec). Keycloak sets ``Secure; SameSite=None`` on its login
# cookies even when served over http, and Chrome and Firefox send them back to localhost anyway.
_LOOPBACK_HOSTS = {"localhost", "localhost.local", "127.0.0.1", "[::1]", "::1"}

MAX_REDIRECTS = 25


def is_ui_redirect(response: httpx.Response) -> bool:
    """Whether ``response`` redirects into the plugin's React SPA (``/oidc/ui/...``).

    The SPA is static build output that may not exist where the suite runs (CI does not build
    ``web-react``), and nothing the suite checks lives in it: where a flow *lands* is the redirect's
    ``Location``, which is asserted on directly.
    """
    if response.status_code not in (301, 302, 303, 307, 308):
        return False
    path = urlparse(urljoin(str(response.url), response.headers.get("location", ""))).path
    return path == UI_ROUTER_PREFIX or path.startswith(UI_ROUTER_PREFIX + "/")


@dataclass
class Form:
    """One ``<form>``: where it posts and the fields it would submit untouched."""

    action: str
    method: str
    fields: Dict[str, str] = field(default_factory=dict)
    attrs: Dict[str, str] = field(default_factory=dict)


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: List[Form] = []
        self._current: Optional[Form] = None

    def handle_starttag(self, tag, attrs):
        attributes = {name: (value or "") for name, value in attrs}
        if tag == "form":
            self._current = Form(action=attributes.get("action", ""), method=attributes.get("method", "get").lower(), attrs=attributes)
            self.forms.append(self._current)
        elif tag == "input" and self._current is not None and attributes.get("name"):
            if attributes.get("type", "text").lower() in ("submit", "button", "image", "checkbox", "radio"):
                return
            self._current.fields[attributes["name"]] = attributes.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self._current = None


def parse_forms(html: str) -> List[Form]:
    """Every form in ``html``, with hidden and pre-filled fields."""
    parser = _FormParser()
    parser.feed(html)
    return parser.forms


def find_form(html: str, *, containing: Optional[str] = None, form_id: Optional[str] = None) -> Form:
    """The form with ``form_id``, or the first carrying a field named ``containing``."""
    for form in parse_forms(html):
        if form_id is not None and form.attrs.get("id") == form_id:
            return form
        if containing is not None and containing in form.fields:
            return form
    raise AssertionError(f"no form (id={form_id!r}, field={containing!r}) on the page:\n{html[:2000]}")


def same_site(cookie) -> str:
    """A stored cookie's ``SameSite`` attribute, lower-cased; ``lax`` when unset, as browsers default."""
    for name, value in getattr(cookie, "_rest", {}).items():
        if name.lower() == "samesite":
            return (value or "lax").lower()
    return "lax"


class Browser:
    """A cookie-carrying client that follows redirects the way the suite needs to watch them.

    Redirects are followed explicitly (``follow``), so a test can stop at any hop — for example
    to check that ``/logout`` revoked the session *before* the browser reaches the IdP.
    """

    def __init__(self, *, verify) -> None:
        self._verify = verify
        self.client = httpx.Client(follow_redirects=False, verify=verify, timeout=30.0)
        self.history: List[httpx.Response] = []

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Browser":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- requests -----------------------------------------------------------------------------

    def _record(self, response: httpx.Response) -> httpx.Response:
        # A cookie policy cannot do this: httpx copies the jar into a fresh one, with the default
        # policy, on every request. So loopback cookies simply stop being ``Secure`` once stored.
        for cookie in self.client.cookies.jar:
            if cookie.secure and cookie.domain in _LOOPBACK_HOSTS:
                cookie.secure = False
        self.history.append(response)
        return response

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self._record(self.client.get(url, **kwargs))

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self._record(self.client.post(url, **kwargs))

    def follow(self, response: httpx.Response, *, stop_at: Optional[str] = None, into_ui: bool = False) -> httpx.Response:
        """Follow ``Location`` headers until a non-redirect, or until a URL starting with ``stop_at``.

        When stopping at ``stop_at`` the redirect *to* it is returned, unfollowed. So is, by
        default, a redirect into the plugin's SPA (see ``is_ui_redirect``): assert on its
        ``Location`` rather than on a page that needs a built UI. ``into_ui=True`` follows it.
        """
        for _ in range(MAX_REDIRECTS):
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            if not into_ui and is_ui_redirect(response):
                return response
            location = urljoin(str(response.url), response.headers["location"])
            if stop_at is not None and location.startswith(stop_at):
                return response
            response = self.get(location)
        raise AssertionError(f"too many redirects, last at {response.url}")

    def submit(self, page: httpx.Response, form: Form, values: Optional[Dict[str, str]] = None, *, cookies: bool = True) -> httpx.Response:
        """Submit ``form`` from ``page`` as a browser would.

        ``cookies=False`` makes it a cross-site top-level POST (the SAML ACS): the target site's
        ``SameSite=Lax`` and ``Strict`` cookies are withheld, and only its ``SameSite=None`` ones
        — still subject to their path, domain and ``Secure`` — go with it. Whatever the response
        sets is stored as usual.
        """
        url = urljoin(str(page.url), form.action) if form.action else str(page.url)
        data = {**form.fields, **(values or {})}
        if form.method != "post":
            return self.get(url, params=data)
        if cookies:
            return self.post(url, data=data)
        with httpx.Client(follow_redirects=False, verify=self._verify, timeout=30.0) as cross_site:
            for cookie in self.client.cookies.jar:
                if same_site(cookie) == "none":
                    cross_site.cookies.jar.set_cookie(cookie)
            response = cross_site.post(url, data=data)
        self.client.cookies.extract_cookies(response)
        return self._record(response)

    # -- helpers ------------------------------------------------------------------------------

    def cookies_named(self, prefix: str, *, host: str) -> List:
        """Every stored cookie for ``host`` whose name starts with ``prefix``."""
        return [cookie for cookie in self.client.cookies.jar if cookie.name.startswith(prefix) and cookie.domain.split(".local")[0] == host]

    def cookie(self, name: str, *, host: str) -> Optional[str]:
        """The value of cookie ``name`` held for ``host``, or None."""
        for cookie in self.client.cookies.jar:
            if cookie.name == name and cookie.domain.split(".local")[0] == host:
                return cookie.value
        return None
