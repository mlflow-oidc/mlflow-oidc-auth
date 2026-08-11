"""The verifier chooses the signature algorithm, never the token (RFC 8725 §3.1).

A JWT names its algorithm in an unauthenticated header. A decoder that trusts that field lets
whoever presents the token decide how — or whether — it is verified, so the accepted set has to be
pinned by the verifier and every other value refused before any signature work happens.

These cases are the permanent guard for that. They are written against ``validate_token`` and, for
the paths that matter most, end to end through ``AuthMiddleware``, because a helper that rejects a
token is only useful if the request it arrived on is also refused.
"""

import base64
import hashlib
import hmac
import json
import time

import pytest
from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.auth as auth_module
import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.middleware import AuthMiddleware

USERNAME = "admin@example.com"
PROTECTED = "/oidc/api/whoami"


def _b64(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


@pytest.fixture
def signing_key():
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    private, public = key.as_dict(is_private=True), key.as_dict(is_private=False)
    kid = public.get("kid") or key.thumbprint()
    public["kid"] = private["kid"] = kid
    return key, private, public, kid


@pytest.fixture
def claims():
    now = int(time.time())
    return {"email": USERNAME, "iat": now, "exp": now + 3600}


@pytest.fixture
def validate(signing_key, monkeypatch):
    """Call ``validate_token`` with a primed JWKS and no claim constraints.

    Audience and issuer are deliberately left unset — the default for most deployments — so these
    cases prove the *signature* is what rejects the token, not a claim check that a differently
    configured deployment would not perform.
    """
    _, _, public, _ = signing_key
    monkeypatch.setattr(auth_module.config, "OIDC_AUDIENCE", None)
    monkeypatch.setattr(auth_module.config, "OIDC_ISSUER", None)
    monkeypatch.setattr(auth_module, "_get_oidc_jwks", lambda force_refresh=False: {"keys": [public]})
    return auth_module.validate_token


@pytest.fixture
def client(signing_key, monkeypatch, tmp_path):
    """The real middleware, over a store holding the user a forged token would impersonate."""
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    _, _, public, _ = signing_key
    store = SqlAlchemyStore()
    store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    store.create_user(USERNAME, "token", "Admin", is_admin=True)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)

    monkeypatch.setattr(auth_module.config, "OIDC_AUDIENCE", None)
    monkeypatch.setattr(auth_module.config, "OIDC_ISSUER", None)
    monkeypatch.setattr(auth_module, "_get_oidc_jwks", lambda force_refresh=False: {"keys": [public]})

    app = FastAPI()

    @app.get(PROTECTED)
    async def whoami(request: Request):
        return {"username": getattr(request.state, "username", None)}

    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")

    with TestClient(app) as test_client:
        yield test_client

    object.__setattr__(store_module.store, "_instance", previous)
    store.engine.dispose()


def unsigned_token(claims: dict) -> str:
    """A token declaring ``alg: none``, with an empty signature."""
    header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64(json.dumps(claims).encode())
    return (header + b"." + payload + b".").decode()


def hmac_token(claims: dict, kid: str, secret: bytes, algorithm: str = "HS256") -> str:
    """A symmetric token hand-built from ``secret``.

    Constructed by hand because a correct JOSE library refuses to sign with a public key, which
    is the whole point of the attack: the forgery is only ever produced by an attacker's own
    code, so a test that relies on the library to mint it tests nothing.
    """
    digest = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}[algorithm]
    header = _b64(json.dumps({"alg": algorithm, "kid": kid}).encode())
    payload = _b64(json.dumps(claims).encode())
    signature = _b64(hmac.new(secret, header + b"." + payload, digest).digest())
    return (header + b"." + payload + b"." + signature).decode()


class TestUnsignedTokensAreRejected:
    """``alg: none`` removes signature verification entirely, so accepting it means accepting
    anything anyone writes."""

    def test_validate_token_rejects_an_unsigned_token(self, validate, claims):
        with pytest.raises(Exception):
            validate(unsigned_token(claims))

    def test_an_unsigned_token_does_not_authenticate(self, client, claims):
        """End to end: the helper rejecting it is only useful if the request is refused."""
        response = client.get(PROTECTED, headers={"Authorization": f"Bearer {unsigned_token(claims)}"})

        assert response.status_code == 401
        assert response.json().get("username") is None

    def test_an_unsigned_token_naming_an_admin_does_not_confer_admin(self, client, claims):
        response = client.get(PROTECTED, headers={"Authorization": f"Bearer {unsigned_token(claims)}"})

        assert response.status_code == 401

    @pytest.mark.parametrize("spelling", ["none", "None", "NONE", "nOnE"])
    def test_no_spelling_of_none_is_accepted(self, validate, claims, spelling):
        """Case variations are a standard filter bypass; the pinned set matches exactly."""
        header = _b64(json.dumps({"alg": spelling, "typ": "JWT"}).encode())
        payload = _b64(json.dumps(claims).encode())

        with pytest.raises(Exception):
            validate((header + b"." + payload + b".").decode())


class TestAlgorithmConfusionIsRejected:
    """The classic RS256 -> HS256 substitution: re-sign with the verifier's *public* key as an
    HMAC secret, and a decoder that honours the header's ``alg`` verifies it happily."""

    @pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
    def test_public_key_pem_as_hmac_secret_is_rejected(self, validate, signing_key, claims, algorithm):
        key, _, _, kid = signing_key
        pem = key.get_public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

        with pytest.raises(Exception):
            validate(hmac_token(claims, kid, pem, algorithm))

    def test_jwk_json_as_hmac_secret_is_rejected(self, validate, signing_key, claims):
        """The key material is published as JSON, so that encoding is just as available to an
        attacker as the PEM."""
        _, _, public, kid = signing_key

        with pytest.raises(Exception):
            validate(hmac_token(claims, kid, json.dumps(public).encode()))

    def test_modulus_as_hmac_secret_is_rejected(self, validate, signing_key, claims):
        _, _, public, kid = signing_key

        with pytest.raises(Exception):
            validate(hmac_token(claims, kid, public["n"].encode()))

    def test_algorithm_confusion_does_not_authenticate(self, client, signing_key, claims):
        key, _, _, kid = signing_key
        pem = key.get_public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

        response = client.get(PROTECTED, headers={"Authorization": f"Bearer {hmac_token(claims, kid, pem)}"})

        assert response.status_code == 401


class TestAttackerSuppliedKeysAreIgnored:
    """``jku`` and ``x5u`` point at key material. Honouring them would let the presenter nominate
    the key that verifies their own token, and would turn validation into an SSRF primitive."""

    @pytest.mark.parametrize("header_name", ["jku", "x5u"])
    def test_a_token_signed_by_an_attacker_key_is_rejected(self, validate, signing_key, claims, header_name):
        _, _, _, kid = signing_key
        attacker = JsonWebKey.generate_key("RSA", 2048, is_private=True)
        token = jwt.encode({"alg": "RS256", "kid": kid, header_name: "https://attacker.invalid/keys"}, claims, attacker.as_dict(is_private=True))

        with pytest.raises(Exception):
            validate(token.decode())

    def test_the_url_is_never_fetched(self, validate, signing_key, claims, monkeypatch):
        """Not merely rejected — not requested. A fetch would be SSRF regardless of the outcome."""
        import requests

        def explode(*args, **kwargs):  # pragma: no cover - the point is that it is not reached
            raise AssertionError(f"validation fetched an attacker-supplied URL: {args} {kwargs}")

        monkeypatch.setattr(requests, "get", explode)
        _, _, _, kid = signing_key
        attacker = JsonWebKey.generate_key("RSA", 2048, is_private=True)
        token = jwt.encode({"alg": "RS256", "kid": kid, "jku": "https://attacker.invalid/keys"}, claims, attacker.as_dict(is_private=True))

        with pytest.raises(Exception):
            validate(token.decode())


class TestGenuineTokensStillWork:
    """The guard is worthless if it also rejects real traffic — and a rejection-only suite would
    pass just as happily against a validator that refused everything."""

    def test_a_genuine_token_validates(self, validate, signing_key, claims):
        _, private, _, kid = signing_key

        payload = validate(jwt.encode({"alg": "RS256", "kid": kid}, claims, private).decode())

        assert payload["email"] == USERNAME

    def test_a_genuine_token_authenticates(self, client, signing_key, claims):
        _, private, _, kid = signing_key
        token = jwt.encode({"alg": "RS256", "kid": kid}, claims, private).decode()

        response = client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["username"] == USERNAME

    @pytest.mark.parametrize("algorithm", ["RS256", "RS384", "RS512", "PS256"])
    def test_the_supported_asymmetric_algorithms_are_accepted(self, validate, claims, monkeypatch, algorithm):
        """Pinning the set must not quietly narrow it to whatever one IdP happens to use."""
        key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
        private, public = key.as_dict(is_private=True), key.as_dict(is_private=False)
        kid = public.get("kid") or key.thumbprint()
        public["kid"] = private["kid"] = kid
        monkeypatch.setattr(auth_module, "_get_oidc_jwks", lambda force_refresh=False: {"keys": [public]})

        payload = validate(jwt.encode({"alg": algorithm, "kid": kid}, claims, private).decode())

        assert payload["email"] == USERNAME


class TestTheAcceptedSetIsPinned:
    def test_no_symmetric_algorithm_is_accepted(self):
        """This plugin verifies against keys fetched from the provider's JWKS, so a shared-secret
        algorithm has no legitimate use — and its presence is what makes confusion possible."""
        assert not [a for a in auth_module._ACCEPTED_ALGORITHMS if a.upper().startswith("HS")]

    def test_none_is_not_in_the_accepted_set(self):
        assert not [a for a in auth_module._ACCEPTED_ALGORITHMS if a.lower() == "none"]

    def test_the_set_matches_the_provider_registry(self):
        """One source of truth: the registry refuses to configure an algorithm the validator
        would not accept, and vice versa."""
        from mlflow_oidc_auth.provider_registry import ASYMMETRIC_ALGORITHMS

        assert list(auth_module._ACCEPTED_ALGORITHMS) == list(ASYMMETRIC_ALGORITHMS)
