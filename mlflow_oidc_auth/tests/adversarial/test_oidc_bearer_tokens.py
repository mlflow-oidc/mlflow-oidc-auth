"""The adversarial suite applied to the OIDC bearer-token path (issue #307).

This is the only provider that exists today, so it is the only instantiation of
``TokenAdversarySuite``. #313 adds a second issuer and #314 the Kubernetes service-account
provider; each inherits the class rather than restating the cases.

Two configurations are exercised deliberately, because they reject different things:

* **Issuer and audience pinned** — what a multi-provider deployment will always be. The suite
  runs here, and cross-issuer replay is rejected by the ``iss`` check.
* **Neither pinned** — today's default. ``TestTheUnpinnedDefault`` records exactly what that
  configuration does and does not refuse. Those are not cases the suite should pass; they are the
  boundary #313 exists to move, written down so the move is visible when it happens.
"""

import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.auth as auth_module
import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.middleware import AuthMiddleware

from .suite import Issuer, TokenAdversarySuite, rejects, unsigned_token

PROTECTED = "/oidc/api/whoami"
USERNAME = "adversary-suite@example.com"


@pytest.fixture
def trusted():
    return Issuer(name="trusted", iss="https://trusted.idp.invalid", audience="mlflow-tracking")


@pytest.fixture
def foreign():
    """A second, entirely legitimate provider that this deployment does not trust.

    Realistic: one company's Entra tenant and another's, or the Kubernetes API server's service
    account issuer next to a human-login IdP. Its tokens are genuine — they are simply not for
    this deployment.
    """
    return Issuer(name="foreign", iss="https://foreign.idp.invalid", audience="some-other-app")


def registry_of(*providers, source="env"):
    """A registry result holding exactly these providers.

    Since #313 the issuer and audience a token is held to come from the matched provider, not
    from the flat ``OIDC_*`` variables, so configuring a case means configuring a registry.
    """
    from mlflow_oidc_auth.provider_registry import RegistryLoadResult

    return RegistryLoadResult(providers=list(providers), errors=[], source=source)


def provider_for(trusted_issuer: Issuer, provider_id: str = "default", **overrides):
    """A registry entry that trusts ``issuer``'s keys, issuer identifier and audience."""
    from mlflow_oidc_auth.provider_registry import ASYMMETRIC_ALGORITHMS, ProviderConfig

    fields = {
        "id": provider_id,
        "type": "oidc",
        "allowed_algorithms": ASYMMETRIC_ALGORITHMS,
        "audience": trusted_issuer.audience,
        "issuer": trusted_issuer.iss,
    }
    fields.update(overrides)
    return ProviderConfig(**fields)


@pytest.fixture
def verify(trusted, monkeypatch):
    """``validate_token`` with the trusted issuer's keys, issuer and audience pinned."""
    monkeypatch.setattr(auth_module.config, "AUTH_PROVIDERS", registry_of(provider_for(trusted)))
    monkeypatch.setattr(auth_module, "_get_oidc_jwks", lambda force_refresh=False: trusted.jwks)
    return auth_module.validate_token


class TestOIDCBearerTokens(TokenAdversarySuite):
    """Every case in the base class, against the configured OIDC provider."""


class TestAudienceConfusion:
    """A token minted for another application by the *same* identity provider.

    The signature is valid, the issuer is the expected one, the user is real. Only ``aud`` says
    it was never meant for this deployment — which is the only thing standing between a shared
    corporate IdP and every application on it accepting each other's tokens.
    """

    def test_a_token_for_another_audience_is_rejected(self, verify, trusted):
        with rejects():
            verify(trusted.mint(aud="a-different-application"))

    def test_a_token_with_no_audience_is_rejected(self, verify, trusted):
        claims = trusted.claims()
        claims.pop("aud")

        with rejects():
            verify(trusted.mint(claims))

    def test_the_expected_audience_among_several_is_accepted(self, verify, trusted):
        """Providers routinely mint multi-audience tokens; rejecting them would be wrong."""
        assert verify(trusted.mint(aud=[trusted.audience, "another-app"])) is not None

    def test_an_audience_list_without_ours_is_rejected(self, verify, trusted):
        with rejects():
            verify(trusted.mint(aud=["another-app", "a-third-app"]))


class TestIssuerConfusion:
    def test_a_token_from_another_issuer_is_rejected(self, verify, foreign, trusted):
        """Even when it names the right audience — the case that matters once two providers can
        both mint tokens for this deployment's audience."""
        with rejects():
            verify(foreign.mint(aud=trusted.audience))

    def test_a_token_with_no_issuer_is_rejected(self, verify, trusted):
        claims = trusted.claims()
        claims.pop("iss")

        with rejects():
            verify(trusted.mint(claims))

    def test_a_lookalike_issuer_is_rejected(self, verify, trusted):
        """Issuer comparison is exact. A prefix or suffix match would accept
        ``https://trusted.idp.invalid.attacker.example``."""
        for lookalike in (
            trusted.iss + ".attacker.invalid",
            trusted.iss + "/",
            trusted.iss.replace("https", "http"),
            trusted.iss.upper(),
        ):
            with rejects():
                verify(trusted.mint(iss=lookalike))


class TestTheUnpinnedDefault:
    """What today's default configuration — no ``OIDC_ISSUER``, no ``OIDC_AUDIENCE`` — refuses.

    These are not suite cases. They record the boundary as it stands, so that when #313 makes
    issuer and audience validation per-provider and mandatory, the change shows up here as a
    test that has to be rewritten rather than as silence.
    """

    @pytest.fixture
    def verify_unpinned(self, trusted, monkeypatch):
        """The synthesised ``default`` provider of a deployment that set neither variable."""
        monkeypatch.setattr(
            auth_module.config,
            "AUTH_PROVIDERS",
            registry_of(provider_for(trusted, audience=None, issuer=None), source="legacy"),
        )
        monkeypatch.setattr(auth_module, "_get_oidc_jwks", lambda force_refresh=False: trusted.jwks)
        return auth_module.validate_token

    def test_the_signature_is_still_the_floor(self, verify_unpinned, foreign):
        """Unpinned does not mean unverified: a token this deployment's keys did not sign is
        still refused, whatever it claims."""
        with rejects():
            verify_unpinned(foreign.mint())

    def test_an_unsigned_token_is_still_refused(self, verify_unpinned, trusted):
        with rejects():
            verify_unpinned(unsigned_token(trusted.claims()))

    def test_an_expired_token_is_still_refused(self, verify_unpinned, trusted):
        now = int(time.time())

        with rejects():
            verify_unpinned(trusted.mint(iat=now - 7200, exp=now - 3600))

    def test_but_any_issuer_and_audience_are_accepted(self, verify_unpinned, trusted):
        """**The gap.** With nothing pinned, a token signed by the configured keys is accepted
        whatever it says about who it was for.

        For a dedicated IdP that is nearly harmless: only that IdP holds the signing key. On a
        shared corporate IdP that signs for every application with the same key, it means a token
        minted for a *different* application authenticates here — the user is genuine, the
        consent was for something else. Pinning ``OIDC_AUDIENCE`` closes it today; #313 makes it
        per-provider so it cannot be left unset.
        """
        accepted = verify_unpinned(trusted.mint(iss="https://anyone.invalid", aud="a-different-application"))

        assert accepted is not None


class TestEndToEndThroughTheMiddleware:
    """A helper that rejects a token is only useful if the request it arrived on is refused too."""

    @pytest.fixture
    def client(self, trusted, monkeypatch, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        store = SqlAlchemyStore()
        store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        store.create_user(USERNAME, "token", "Adversary Suite", is_admin=True)
        previous = object.__getattribute__(store_module.store, "_instance")
        object.__setattr__(store_module.store, "_instance", store)

        monkeypatch.setattr(auth_module.config, "AUTH_PROVIDERS", registry_of(provider_for(trusted)))
        monkeypatch.setattr(auth_module, "_get_oidc_jwks", lambda force_refresh=False: trusted.jwks)

        app = FastAPI()

        @app.get(PROTECTED)
        async def whoami(request: Request):
            return {"username": getattr(request.state, "username", None), "is_admin": getattr(request.state, "is_admin", None)}

        app.add_middleware(AuthMiddleware)
        app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")

        with TestClient(app) as test_client:
            yield test_client

        object.__setattr__(store_module.store, "_instance", previous)
        store.engine.dispose()

    def _get(self, client, token):
        return client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"})

    def test_a_genuine_token_authenticates(self, client, trusted):
        response = self._get(client, trusted.mint(email=USERNAME))

        assert response.status_code == 200
        assert response.json()["username"] == USERNAME

    def test_a_foreign_token_naming_the_admin_does_not(self, client, foreign):
        """The forgery that matters: a real user's address, a real signature, the wrong issuer."""
        response = self._get(client, foreign.mint(email=USERNAME, aud="mlflow-tracking"))

        assert response.status_code == 401
        assert response.json().get("username") is None

    def test_a_kid_swapped_token_does_not(self, client, trusted, foreign):
        """Minted with the attacker's key and the trusted ``kid`` in the signed header, so the
        signature is genuine under that key — the header is the only thing vouching for it."""
        response = self._get(client, foreign.mint(email=USERNAME, kid=trusted.kid))

        assert response.status_code == 401

    def test_a_token_for_another_audience_does_not(self, client, trusted):
        response = self._get(client, trusted.mint(email=USERNAME, aud="a-different-application"))

        assert response.status_code == 401

    def test_an_unsigned_token_does_not(self, client, trusted):
        response = self._get(client, unsigned_token(trusted.claims(email=USERNAME)))

        assert response.status_code == 401
