"""Harness for the end-to-end identity suite: the Keycloak admin client, the app server, the auth DB.

Fixtures live in ``conftest.py``; this module holds what tests and helpers import by name.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx

REALM = "mlflow-e2e"

# Test-only literals, mirrored in the realm JSON. They protect nothing outside a throwaway
# Keycloak on the loopback interface.
OIDC_CLIENT_ID = "mlflow"
OIDC_CLIENT_SECRET = "mlflow-e2e-client-secret-not-a-secret"
PASSWORDS = {
    "alice@example.com": "alice-e2e-not-a-secret",
    "bob@example.com": "bob-e2e-not-a-secret",
    "carol@example.com": "carol-e2e-not-a-secret",
    "root@example.com": "root-e2e-not-a-secret",
}

OIDC_PROVIDER_ID = "default"
# A second, *named* OIDC provider over the same realm and client. Reached through the other
# loopback name (see ``Keycloak.named_issuer``), so Keycloak gives it a distinct issuer and the
# registry accepts it next to ``default``.
NAMED_OIDC_PROVIDER_ID = "keycloak-named"
SAML_PROVIDER_ID = "keycloak-saml"
SAML_CLIENT_ID = "mlflow-saml"
ACCESS_TOKEN_LIFESPAN_SECONDS = 10

DEFAULT_KEYCLOAK_URL = "http://localhost:8080"
DEFAULT_KEYCLOAK_HTTPS_URL = "https://localhost:8443"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

_MD = "{urn:oasis:names:tc:SAML:2.0:metadata}"
_DS = "{http://www.w3.org/2000/09/xmldsig#}"
_REDIRECT_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
_EMAIL_NAME_ID = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"


def truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def keycloak_verify() -> Any:
    """TLS verification for Keycloak's https listener: its CA file if given, otherwise off.

    Off is allowed only for a loopback Keycloak, whose certificate is generated per run. The
    descriptor fetched over this connection supplies the IdP certificate the app will trust, so an
    unverified fetch from anywhere else would let the network choose it. CI passes the CA.
    """
    ca = os.environ.get("MLFLOW_OIDC_E2E_KEYCLOAK_CA")
    if ca:
        return ssl.create_default_context(cafile=ca)
    host = urlparse(os.environ.get("MLFLOW_OIDC_E2E_KEYCLOAK_HTTPS_URL", DEFAULT_KEYCLOAK_HTTPS_URL)).hostname
    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(f"MLFLOW_OIDC_E2E_KEYCLOAK_CA is required for a non-loopback Keycloak ({host})")
    return False


# ---------------------------------------------------------------------------------------------
# Keycloak
# ---------------------------------------------------------------------------------------------


class Keycloak:
    """The realm under test, and the parts of Keycloak's admin REST API the suite reads."""

    def __init__(self, url: str, https_url: str, admin_user: str, admin_password: str) -> None:
        self.url = url.rstrip("/")
        self.https_url = https_url.rstrip("/")
        self._admin_user = admin_user
        self._admin_password = admin_password
        self._token: Optional[str] = None
        self._token_at = 0.0
        self._http = httpx.Client(timeout=30.0)

    # -- plumbing ---------------------------------------------------------------------------

    @property
    def issuer(self) -> str:
        return f"{self.url}/realms/{REALM}"

    @property
    def saml_issuer(self) -> str:
        return f"{self.https_url}/realms/{REALM}"

    @property
    def named_url(self) -> str:
        """Keycloak's http listener under the *other* loopback name (localhost <-> 127.0.0.1).

        Keycloak in dev mode derives the issuer from the request's host, so this is the same realm
        with a different ``iss`` — which is what lets a second registry entry point at it: the
        registry refuses two providers claiming one issuer.
        """
        parsed = urlparse(self.url)
        other = {"localhost": "127.0.0.1", "127.0.0.1": "localhost"}.get(parsed.hostname or "")
        if other is None:
            raise RuntimeError(f"the named-provider e2e test needs a loopback Keycloak URL (localhost or 127.0.0.1), not {self.url}")
        return parsed._replace(netloc=f"{other}:{parsed.port}" if parsed.port else other).geturl()

    @property
    def named_issuer(self) -> str:
        return f"{self.named_url}/realms/{REALM}"

    @property
    def token_endpoint(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/token"

    def _admin_token(self) -> str:
        # master's admin-cli tokens live 60 s; renew well before that.
        if self._token is None or time.monotonic() - self._token_at > 30:
            response = self._http.post(
                f"{self.url}/realms/master/protocol/openid-connect/token",
                data={"grant_type": "password", "client_id": "admin-cli", "username": self._admin_user, "password": self._admin_password},
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]
            self._token_at = time.monotonic()
        return self._token

    def admin(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._admin_token()}", **kwargs.pop("headers", {})}
        response = self._http.request(method, f"{self.url}/admin/realms/{REALM}{path}", headers=headers, **kwargs)
        response.raise_for_status()
        return response

    # -- realm state ------------------------------------------------------------------------

    def user_id(self, username: str) -> str:
        users = self.admin("GET", "/users", params={"username": username, "exact": "true"}).json()
        assert len(users) == 1, f"expected exactly one Keycloak user {username!r}, got {users}"
        return users[0]["id"]

    def user_sessions(self, username: str) -> List[Dict[str, Any]]:
        return self.admin("GET", f"/users/{self.user_id(username)}/sessions").json()

    def offline_session_count(self, username: str) -> int:
        client = self._client(OIDC_CLIENT_ID)
        return len(self.admin("GET", f"/users/{self.user_id(username)}/offline-sessions/{client['id']}").json())

    def logout_everywhere(self, username: str) -> None:
        self.admin("POST", f"/users/{self.user_id(username)}/logout")

    def clear_events(self) -> None:
        self.admin("DELETE", "/events")

    def events(self, *types: str, username: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Realm events of ``types``, optionally narrowed to a user and a Keycloak session.

        Filtered here rather than with the ``user`` query parameter: error events such as
        ``REFRESH_TOKEN_ERROR`` carry the session id but no user id.
        """
        params: List[tuple] = [("max", "1000")] + [("type", event_type) for event_type in types]
        events = self.admin("GET", "/events", params=params).json()
        if username is not None:
            user_id = self.user_id(username)
            events = [event for event in events if event.get("userId") == user_id]
        if session_id is not None:
            events = [event for event in events if event.get("sessionId") == session_id]
        return events

    def _client(self, client_id: str) -> Dict[str, Any]:
        clients = self.admin("GET", "/clients", params={"clientId": client_id}).json()
        assert len(clients) == 1, f"Keycloak client {client_id!r} missing from realm {REALM}; was the realm imported?"
        return clients[0]

    def point_clients_at(self, app_url: str) -> None:
        """Rewrite both clients' redirect, ACS and SLO URLs for the app's actual port.

        The realm JSON carries a placeholder port; Keycloak does not accept a wildcard port in a
        redirect URI, and the app runs on whichever loopback port was free.
        """
        oidc = self._client(OIDC_CLIENT_ID)
        oidc["redirectUris"] = [f"{app_url}/*"]
        oidc.setdefault("attributes", {})["post.logout.redirect.uris"] = f"{app_url}/*"
        self.admin("PUT", f"/clients/{oidc['id']}", json=oidc)

        saml = self._client(SAML_CLIENT_ID)
        saml["redirectUris"] = [f"{app_url}/*"]
        attributes = saml.setdefault("attributes", {})
        attributes["saml_assertion_consumer_url_post"] = f"{app_url}/callback/{SAML_PROVIDER_ID}"
        attributes["saml_single_logout_service_url_redirect"] = f"{app_url}/slo/{SAML_PROVIDER_ID}"
        self.admin("PUT", f"/clients/{saml['id']}", json=saml)

    def saml_idp(self) -> Dict[str, str]:
        """entityID, HTTP-Redirect SSO/SLO locations and the signing certificate from the descriptor."""
        response = httpx.get(f"{self.saml_issuer}/protocol/saml/descriptor", verify=keycloak_verify(), timeout=30.0)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        idp = root.find(f"{_MD}IDPSSODescriptor")
        assert idp is not None, "Keycloak SAML descriptor has no IDPSSODescriptor"

        def location(tag: str) -> str:
            for element in idp.findall(f"{_MD}{tag}"):
                if element.get("Binding") == _REDIRECT_BINDING:
                    return element.get("Location")
            raise AssertionError(f"no HTTP-Redirect {tag} in the Keycloak descriptor")

        cert = None
        for descriptor in idp.findall(f"{_MD}KeyDescriptor"):
            if descriptor.get("use") in (None, "signing"):
                cert = descriptor.find(f"{_DS}KeyInfo/{_DS}X509Data/{_DS}X509Certificate")
                if cert is not None:
                    break
        assert cert is not None and cert.text, "no signing certificate in the Keycloak descriptor"
        return {
            "entity_id": root.get("entityID"),
            "sso_url": location("SingleSignOnService"),
            "slo_url": location("SingleLogoutService"),
            "cert": "".join(cert.text.split()),
        }

    # -- direct protocol calls (control experiments, no app involved) ----------------------

    def password_grant(self, username: str, scope: str = "openid") -> Dict[str, Any]:
        response = self._http.post(
            self.token_endpoint,
            data={
                "grant_type": "password",
                "client_id": OIDC_CLIENT_ID,
                "client_secret": OIDC_CLIENT_SECRET,
                "username": username,
                "password": PASSWORDS[username],
                "scope": scope,
            },
        )
        response.raise_for_status()
        return response.json()

    def refresh(self, refresh_token: str, issuer: Optional[str] = None) -> httpx.Response:
        """A refresh-token grant at ``issuer``'s token endpoint (default: the http issuer).

        Keycloak checks a refresh token's ``iss`` against the endpoint it is presented to, so a
        token minted through ``named_issuer`` must be refreshed there.
        """
        return self._http.post(
            f"{issuer or self.issuer}/protocol/openid-connect/token",
            data={"grant_type": "refresh_token", "client_id": OIDC_CLIENT_ID, "client_secret": OIDC_CLIENT_SECRET, "refresh_token": refresh_token},
        )


# ---------------------------------------------------------------------------------------------
# Auth database
# ---------------------------------------------------------------------------------------------


@dataclass
class AuthDatabase:
    uri: str
    dialect: str
    _drop: Optional[Callable[[], None]] = None

    def query(self, sql: str, **params) -> List[Dict[str, Any]]:
        """Read the auth database directly — only to assert on what the app wrote."""
        from sqlalchemy import create_engine, text

        engine = create_engine(self.uri)
        try:
            with engine.connect() as connection:
                return [dict(row._mapping) for row in connection.execute(text(sql), params)]
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------------------------
# The app under test
# ---------------------------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class AppServer:
    url: str
    log_path: Path
    secret_key: str
    db: AuthDatabase
    workers: int
    process: Optional[subprocess.Popen] = field(default=None, repr=False)

    def log(self) -> str:
        try:
            return self.log_path.read_text(errors="replace")
        except FileNotFoundError:
            return ""

    def tail(self, lines: int = 150) -> str:
        return "\n".join(self.log().splitlines()[-lines:])

    def audit_events(self, event: str) -> List[Dict[str, Any]]:
        """Audit events named ``event`` from the server log (one JSON object per line)."""
        found = []
        for line in self.log().splitlines():
            if '"event"' not in line:
                continue
            try:
                record = json.loads(line[line.index("{") :])
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("event") == event:
                found.append(record)
        return found


def server_env(*, app_url: str, secret_key: str, db_uri: str, keycloak: Keycloak) -> Dict[str, str]:
    idp = keycloak.saml_idp()
    providers = [
        {
            # The legacy id: RP-initiated logout and the flat OIDC_* settings (redirect URI,
            # client secret) belong to it.
            "id": OIDC_PROVIDER_ID,
            "type": "oidc",
            "display_name": "Keycloak (OIDC)",
            "discovery_url": f"{keycloak.issuer}/.well-known/openid-configuration",
            "client_id": OIDC_CLIENT_ID,
            "issuer": keycloak.issuer,
            "audience": OIDC_CLIENT_ID,
            "identity_binding": "email",
            "allowed_email_domains": ["example.com"],
            "provisioning": "jit",
            "group_sync": "every_login",
            "admin_source": "claims",
        },
        {
            # Same realm and client as ``default``, under its own id and issuer: RP-initiated
            # logout and token revocation must go to the provider that opened the session.
            "id": NAMED_OIDC_PROVIDER_ID,
            "type": "oidc",
            "display_name": "Keycloak (named OIDC)",
            "discovery_url": f"{keycloak.named_issuer}/.well-known/openid-configuration",
            "client_id": OIDC_CLIENT_ID,
            "issuer": keycloak.named_issuer,
            "audience": OIDC_CLIENT_ID,
            "identity_binding": "email",
            "allowed_email_domains": ["example.com"],
            "provisioning": "jit",
            "group_sync": "every_login",
            "admin_source": "claims",
        },
        {
            "id": SAML_PROVIDER_ID,
            "type": "saml",
            "display_name": "Keycloak (SAML)",
            "entity_id": SAML_CLIENT_ID,
            "idp_entity_id": idp["entity_id"],
            "idp_sso_url": idp["sso_url"],
            "idp_slo_url": idp["slo_url"],
            "idp_x509_cert": idp["cert"],
            "name_id_format": _EMAIL_NAME_ID,
            "attribute_username": "email",
            "attribute_groups": "groups",
            "attribute_display_name": "displayName",
            "provisioning": "jit",
            "group_sync": "every_login",
        },
    ]
    # A clean environment, not a copy of the developer's: stray OIDC_* or MLFLOW_* variables in a
    # shell must not reconfigure the app under test.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "VIRTUAL_ENV") if key in os.environ}
    env.update(
        {
            # config.py calls load_dotenv(), which walks up from the package to a developer's
            # repository-root .env. The suite must see only what is set here.
            "PYTHON_DOTENV_DISABLED": "1",
            "PYTHONUNBUFFERED": "1",
            "SECRET_KEY": secret_key,
            "AUTH_PROVIDERS": json.dumps(providers),
            "OIDC_DISCOVERY_URL": f"{keycloak.issuer}/.well-known/openid-configuration",
            "OIDC_CLIENT_ID": OIDC_CLIENT_ID,
            "OIDC_CLIENT_SECRET": OIDC_CLIENT_SECRET,
            "OIDC_CLIENT_SECRET_KEYCLOAK_NAMED": OIDC_CLIENT_SECRET,
            "OIDC_REDIRECT_URI": f"{app_url}/callback",
            "OIDC_USE_REFRESH_TOKEN": "true",
            # Keycloak access tokens live ACCESS_TOKEN_LIFESPAN_SECONDS; with no leeway the tests
            # wait that long for a session to need a refresh. A leeway >= the lifespan would make
            # every refreshed session count as expired at once, defeating single-flight.
            "OIDC_SESSION_EXPIRY_LEEWAY_SECONDS": "0",
            "OIDC_GROUP_NAME": "mlflow-users",
            "OIDC_ADMIN_GROUP_NAME": "mlflow-admins",
            "MLFLOW_ENABLE_WORKSPACES": "false",
            "OIDC_USERS_DB_URI": db_uri,
            "SESSION_COOKIE_SECURE": "false",
            # The app is served over plain http here, where SAML_LOGIN_BINDING=auto would leave the
            # SAML browser binding (#374) off. Force it on: the binding cookie is still marked
            # Secure, and loopback http is a secure context to a browser (and to ``browser.py``).
            "SAML_LOGIN_BINDING": "on",
            # Several workers each keep their own permission cache; keep a grant made through one
            # visible to the others within the test's patience.
            "PERMISSION_CACHE_TTL_SECONDS": "1",
            "LOG_LEVEL": "INFO",
        }
    )
    return env
