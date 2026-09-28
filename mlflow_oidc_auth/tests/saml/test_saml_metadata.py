"""SP metadata and the routes SAML adds to the unauthenticated surface (issues #328, #329)."""

from fastapi import FastAPI

from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.tests.saml.conftest import (
    ACS_URL,
    PROVIDER_ID,
    SLS_URL,
    SP_ENTITY_ID,
    install_providers,
    requires_saml,
    saml_provider,
)

pytestmark = requires_saml


class TestSpMetadata:
    def test_it_describes_this_sp(self, client):
        response = client.get(f"/saml/metadata/{PROVIDER_ID}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/samlmetadata+xml")
        assert response.headers["cache-control"] == "no-store"
        body = response.text
        assert f'entityID="{SP_ENTITY_ID}"' in body
        assert f'Location="{ACS_URL}"' in body
        assert f'Location="{SLS_URL}"' in body
        # Single logout is HTTP-Redirect only (the /slo route refuses POST).
        assert 'SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"' in body
        assert 'SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"' not in body
        assert "KeyDescriptor" not in body, "no SP certificate is configured, so none is published"

    def test_it_publishes_the_signing_certificate_and_never_the_key(self, client, monkeypatch, idp_keys, sp_keys):
        install_providers(monkeypatch, saml_provider(idp_keys, sp_x509_cert=sp_keys.cert_body, sp_private_key=sp_keys.key_pem, sign_requests=True))

        body = client.get(f"/saml/metadata/{PROVIDER_ID}").text

        assert sp_keys.cert_body[:64] in body
        assert "PRIVATE KEY" not in body
        key_body = "".join(line for line in sp_keys.key_pem.splitlines() if "-----" not in line)
        assert key_body[:64] not in body

    def test_it_is_reachable_without_a_session(self, client):
        client.cookies.clear()

        assert client.get(f"/saml/metadata/{PROVIDER_ID}").status_code == 200

    def test_an_unknown_or_non_saml_provider_is_a_404(self, client):
        assert client.get("/saml/metadata/nope").status_code == 404
        assert client.get("/saml/metadata/corp-oidc").status_code == 404


class TestUnprotectedSurface:
    """Carved out by prefix with a trailing slash, so nothing merely beginning with it is exposed."""

    def test_the_saml_endpoints_are_unprotected(self):
        middleware = AuthMiddleware(FastAPI())

        assert middleware._is_unprotected_route("/slo/corp") is True
        assert middleware._is_unprotected_route("/saml/metadata/corp") is True

    def test_neighbouring_paths_stay_protected(self):
        middleware = AuthMiddleware(FastAPI())

        assert middleware._is_unprotected_route("/slo") is False
        assert middleware._is_unprotected_route("/slox/corp") is False
        assert middleware._is_unprotected_route("/saml/other") is False
        assert middleware._is_unprotected_route("/saml/metadata") is False
