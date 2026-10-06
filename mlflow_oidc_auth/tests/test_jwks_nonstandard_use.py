"""An IdP JWKS holding keys with a non-standard ``use`` must not break OIDC login (#446).

RFC 7517 §4.2 allows ``use`` values beyond ``sig``/``enc``; §5 says a set's unusable keys SHOULD
be ignored. joserfc refuses the whole set instead, and authlib's ``parse_id_token`` imports the
whole set. These tests drive a real signed id_token through authlib with such a set, and pin
that the keys dropped to make that work can still never verify anything.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from joserfc.errors import BadSignatureError, InvalidKeyIdError, KeyParameterError, MissingKeyError
from joserfc.jwk import KeySet, RSAKey

from mlflow_oidc_auth import oauth as oauth_module
from mlflow_oidc_auth.oauth import _OAuth, _OAuth2App, usable_jwks
from mlflow_oidc_auth.tests.jose_helpers import encode_jwt

ISSUER = "https://idp.example.test"
CLIENT_ID = "mlflow"
NONCE = "n-0S6_WzA2Mj"


@pytest.fixture(scope="module")
def sig_key() -> RSAKey:
    return RSAKey.generate_key(2048, parameters={"kid": "sig-1", "use": "sig", "alg": "RS256"})


@pytest.fixture(scope="module")
def saml_key() -> RSAKey:
    return RSAKey.generate_key(2048, parameters={"kid": "saml-1"})


def _public(key: RSAKey, **overrides) -> dict:
    return {**key.as_dict(private=False), **overrides}


@pytest.fixture
def zitadel_jwks(sig_key, saml_key) -> dict:
    """A Zitadel-shaped set: SAML keys with non-standard ``use`` next to the signing key."""
    return {
        "keys": [
            _public(saml_key, use="saml_ca"),
            _public(saml_key, kid="saml-2", use="saml_response_sig"),
            _public(sig_key),
            _public(saml_key, kid="saml-3", use="saml_metadata_sig"),
        ]
    }


def _id_token(key: RSAKey, kid: str, **claims) -> str:
    now = int(time.time())
    payload = {"iss": ISSUER, "sub": "user-1", "aud": CLIENT_ID, "iat": now, "exp": now + 300, "nonce": NONCE, **claims}
    return encode_jwt({"alg": "RS256", "kid": kid}, payload, key)


def _client(registry: OAuth, jwks: dict) -> StarletteOAuth2App:
    client = registry.register(name="t", client_id=CLIENT_ID, client_secret="unused")
    client.server_metadata = {"issuer": ISSUER, "jwks": jwks, "id_token_signing_alg_values_supported": ["RS256"]}
    return client


def _parse(client, id_token: str):
    return asyncio.run(client.parse_id_token({"id_token": id_token}, nonce=NONCE))


# --- the defect, pinned against the libraries ------------------------------------------------


def test_joserfc_still_rejects_the_whole_set(zitadel_jwks):
    """Documents the upstream behaviour this works around; if it starts passing, joserfc fixed it."""
    with pytest.raises(KeyParameterError, match="'use'"):
        KeySet.import_key_set(zitadel_jwks)


def test_stock_authlib_client_fails_login(zitadel_jwks, sig_key):
    """The reported failure, reproduced: a valid id_token is refused because of a sibling key."""
    client = _client(OAuth(), zitadel_jwks)
    with pytest.raises(KeyParameterError):
        _parse(client, _id_token(sig_key, "sig-1"))


# --- usable_jwks ------------------------------------------------------------------------------


def test_drops_only_keys_joserfc_cannot_import(zitadel_jwks):
    result = usable_jwks(zitadel_jwks)
    assert [k["kid"] for k in result["keys"]] == ["sig-1"]
    KeySet.import_key_set(result)  # now importable


def test_also_drops_bad_key_ops_and_missing_members(sig_key, saml_key):
    jwks = {
        "keys": [
            _public(saml_key, kid="ops", key_ops=["saml"]),
            {"kty": "RSA", "kid": "no-n", "e": "AQAB"},
            {"kty": "EC", "kid": "bp", "crv": "BP-256", "x": "AA", "y": "AA"},
            "not-a-jwk",
            _public(sig_key),
        ]
    }
    assert [k["kid"] for k in usable_jwks(jwks)["keys"]] == ["sig-1"]


def test_keeps_enc_and_unlabelled_keys(sig_key, saml_key):
    """Standard ``use`` values and keys with no ``use`` are importable and are not touched."""
    jwks = {"keys": [_public(saml_key, use="enc"), _public(saml_key, kid="plain"), _public(sig_key)]}
    assert usable_jwks(jwks) is jwks


def test_does_not_mutate_input_and_keeps_other_members(zitadel_jwks):
    jwks = {**zitadel_jwks, "x-extra": 1}
    before = list(jwks["keys"])
    result = usable_jwks(jwks)
    assert jwks["keys"] == before
    assert result["x-extra"] == 1


@pytest.mark.parametrize("value", [None, [], "jwks", {"no": "keys"}, {"keys": "x"}])
def test_non_sets_pass_through(value):
    assert usable_jwks(value) is value


def test_set_with_no_usable_key_still_fails_closed(saml_key):
    result = usable_jwks({"keys": [_public(saml_key, use="saml_ca")]})
    assert result["keys"] == []
    with pytest.raises(MissingKeyError):
        KeySet.import_key_set(result)


def test_dropped_key_material_is_not_logged(zitadel_jwks, saml_key):
    with patch.object(oauth_module.logger, "debug") as debug:
        usable_jwks(zitadel_jwks, "zitadel")
    logged = repr(debug.call_args_list)
    assert "saml-2" in logged
    assert saml_key.as_dict(private=False)["n"] not in logged


# --- through authlib's id_token verification -------------------------------------------------


def test_registry_uses_the_filtering_client():
    assert isinstance(oauth_module.oauth, OAuth)
    assert issubclass(_OAuth2App, StarletteOAuth2App)
    assert isinstance(_client(_OAuth(), {"keys": []}), _OAuth2App)


def test_reset_keeps_the_filtering_client():
    oauth_module.reset_oauth()
    try:
        assert isinstance(oauth_module.oauth, _OAuth)
    finally:
        oauth_module.reset_oauth()


def test_login_succeeds_with_non_standard_use_keys(zitadel_jwks, sig_key):
    client = _client(_OAuth(), zitadel_jwks)
    userinfo = _parse(client, _id_token(sig_key, "sig-1"))
    assert userinfo["sub"] == "user-1"
    # The cached set is the reduced one, so later logins do not re-filter it.
    assert [k["kid"] for k in client.server_metadata["jwks"]["keys"]] == ["sig-1"]


def test_force_refresh_is_filtered_too(zitadel_jwks, sig_key):
    """``force=True`` (key rotation, InvalidKeyIdError retry) goes to the network; filter that result."""
    client = _client(_OAuth(), {"keys": [_public(sig_key, kid="old")]})
    with patch.object(StarletteOAuth2App, "fetch_jwk_set", AsyncMock(return_value=zitadel_jwks)) as fetch:
        result = asyncio.run(client.fetch_jwk_set(force=True))
    fetch.assert_awaited_once_with(force=True)
    assert [k["kid"] for k in result["keys"]] == ["sig-1"]


def test_token_signed_by_a_dropped_key_is_refused(zitadel_jwks, saml_key):
    """Dropping a key must not let it be used: a token naming it finds no key."""
    client = _client(_OAuth(), zitadel_jwks)
    with patch.object(StarletteOAuth2App, "fetch_jwk_set", AsyncMock(return_value=zitadel_jwks)):
        with pytest.raises(InvalidKeyIdError):
            _parse(client, _id_token(saml_key, "saml-2"))


def test_token_claiming_the_sig_kid_but_signed_by_another_key_is_refused(zitadel_jwks, saml_key):
    client = _client(_OAuth(), zitadel_jwks)
    with pytest.raises(BadSignatureError):
        _parse(client, _id_token(saml_key, "sig-1"))


def test_claims_are_still_validated(zitadel_jwks, sig_key):
    client = _client(_OAuth(), zitadel_jwks)
    with pytest.raises(Exception, match="iss"):
        _parse(client, _id_token(sig_key, "sig-1", iss="https://evil.example.test"))
