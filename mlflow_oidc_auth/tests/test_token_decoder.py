"""The joserfc-backed token decoder keeps the acceptance rules the validator has always had (#402).

Each case pairs a token that must be refused with the nearest one that must still be accepted,
so a decoder that refused everything would fail here as surely as one that accepted too much.
"""

import base64
import json
import time
from contextlib import nullcontext

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from joserfc.errors import (
    BadSignatureError,
    DecodeError,
    ExpiredTokenError,
    InvalidClaimError,
    InvalidPayloadError,
    MissingClaimError,
    SecurityWarning,
    UnsupportedAlgorithmError,
    UnsupportedHeaderError,
    UnsupportedKeyAlgorithmError,
    UnsupportedKeyUseError,
)
from joserfc.jwk import ECKey, OKPKey

from mlflow_oidc_auth.auth import _ACCEPTED_ALGORITHMS, _TokenDecoder
from mlflow_oidc_auth.tests.jose_helpers import encode_jwt, generate_rsa_key

ISSUER = "https://idp.example.com"
AUDIENCE = "mlflow-api"
OPTIONS = {"exp": {"essential": True}, "aud": {"essential": True, "value": AUDIENCE}, "iss": {"essential": True, "value": ISSUER}}


def _b64(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


@pytest.fixture(scope="module")
def rsa():
    key = generate_rsa_key()
    public = key.as_dict(private=False)
    public["kid"] = "k1"
    return key, public


@pytest.fixture
def claims():
    now = int(time.time())
    return {"iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300, "email": "user@example.com"}


def _decode(token, jwks, options=OPTIONS, algorithms=None):
    payload = _TokenDecoder(algorithms or list(_ACCEPTED_ALGORITHMS)).decode(token, jwks, claims_options=options)
    payload.validate()
    return payload


def _hand_signed(key, header: dict, payload: bytes, encode_payload: bool = True) -> str:
    """An RS256 token built by hand, for headers the joserfc encoder will not produce."""
    signing_input = _b64(json.dumps(header).encode()) + b"." + (_b64(payload) if encode_payload else payload)
    signature = key.private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return (signing_input + b"." + _b64(signature)).decode()


class TestSignatureAndKeys:
    def test_a_genuine_token_validates(self, rsa, claims):
        key, public = rsa
        assert _decode(encode_jwt({"alg": "RS256", "kid": "k1"}, claims, key), {"keys": [public]})["email"] == "user@example.com"

    def test_a_token_signed_by_another_key_is_refused(self, rsa, claims):
        _, public = rsa
        with pytest.raises(BadSignatureError):
            _decode(encode_jwt({"alg": "RS256", "kid": "k1"}, claims, generate_rsa_key()), {"keys": [public]})

    def test_an_algorithm_outside_the_pinned_set_is_refused(self, rsa, claims):
        key, public = rsa
        token = encode_jwt({"alg": "PS256", "kid": "k1"}, claims, key)
        with pytest.raises(UnsupportedAlgorithmError):
            _decode(token, {"keys": [public]}, algorithms=["RS256"])
        assert _decode(token, {"keys": [public]}, algorithms=["PS256"])

    def test_an_unknown_kid_is_refused(self, rsa, claims):
        key, public = rsa
        with pytest.raises(ValueError):
            _decode(encode_jwt({"alg": "RS256", "kid": "other"}, claims, key), {"keys": [public]})

    def test_a_token_without_a_kid_needs_a_single_key_set(self, rsa, claims):
        key, public = rsa
        token = encode_jwt({"alg": "RS256"}, claims, key)
        second = dict(generate_rsa_key().as_dict(private=False), kid="k2")
        with pytest.raises(ValueError):
            _decode(token, {"keys": [public, second]})
        assert _decode(token, {"keys": [public]})

    def test_a_key_without_a_kid_cannot_be_named_by_its_thumbprint(self, rsa, claims):
        """joserfc would assign such a key its thumbprint as ``kid``; the selection here does not."""
        key, public = rsa
        unlabelled = {k: v for k, v in public.items() if k != "kid"}
        with pytest.raises(ValueError):
            _decode(encode_jwt({"alg": "RS256", "kid": key.thumbprint()}, claims, key), {"keys": [unlabelled]})

    def test_an_encryption_key_is_not_used_to_verify(self, rsa, claims):
        key, public = rsa
        token = encode_jwt({"alg": "RS256", "kid": "k1"}, claims, key)
        with pytest.raises(UnsupportedKeyUseError):
            _decode(token, {"keys": [dict(public, use="enc")]})
        assert _decode(token, {"keys": [dict(public, use="sig")]})

    def test_a_key_bound_to_another_algorithm_is_not_used(self, rsa, claims):
        key, public = rsa
        token = encode_jwt({"alg": "RS256", "kid": "k1"}, claims, key)
        with pytest.raises(UnsupportedKeyAlgorithmError):
            _decode(token, {"keys": [dict(public, alg="PS256")]})
        assert _decode(token, {"keys": [dict(public, alg="RS256")]})

    @pytest.mark.parametrize(
        "make_key,algorithm",
        [(lambda: ECKey.generate_key("P-256"), "ES256"), (lambda: OKPKey.generate_key("Ed25519"), "EdDSA")],
        ids=["ES256", "EdDSA"],
    )
    def test_non_rsa_algorithms_in_the_set_still_verify(self, claims, make_key, algorithm):
        key = make_key()
        public = dict(key.as_dict(private=False), kid="k")
        # joserfc flags the EdDSA name as deprecated (RFC 9864) but still verifies it.
        with pytest.warns(SecurityWarning) if algorithm == "EdDSA" else nullcontext():
            assert _decode(encode_jwt({"alg": algorithm, "kid": "k"}, claims, key), {"keys": [public]})


class TestSerialisation:
    def test_a_five_segment_token_is_refused(self, rsa):
        _, public = rsa
        with pytest.raises(DecodeError):
            _decode("a.b.c.d.e", {"keys": [public]})

    def test_a_payload_that_is_not_an_object_is_refused(self, rsa, claims):
        key, public = rsa
        with pytest.raises(InvalidPayloadError):
            _decode(_hand_signed(key, {"alg": "RS256", "kid": "k1"}, b"[1, 2]"), {"keys": [public]})
        assert _decode(_hand_signed(key, {"alg": "RS256", "kid": "k1"}, json.dumps(claims).encode()), {"keys": [public]})

    @pytest.mark.parametrize("encode", [lambda text: text.encode("utf-16-le"), lambda text: b"\xef\xbb\xbf" + text.encode()], ids=["utf-16", "utf-8-bom"])
    def test_json_that_is_not_plain_utf8_is_refused(self, rsa, claims, encode):
        key, public = rsa
        header = {"alg": "RS256", "kid": "k1"}
        with pytest.raises(InvalidPayloadError):
            _decode(_hand_signed(key, header, encode(json.dumps(claims))), {"keys": [public]})
        signing_input = _b64(encode(json.dumps(header))) + b"." + _b64(json.dumps(claims).encode())
        token = (signing_input + b"." + _b64(key.private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256()))).decode()
        with pytest.raises(DecodeError):
            _decode(token, {"keys": [public]})

    def test_an_unencoded_payload_is_refused(self, rsa):
        """RFC 7797 ``b64: false``. The payload carries no ``.``, which would split the token."""
        key, public = rsa
        header = {"alg": "RS256", "kid": "k1", "b64": False, "crit": ["b64"]}
        payload = json.dumps({"iss": "idp", "exp": int(time.time()) + 300}).encode()
        with pytest.raises(UnsupportedHeaderError):
            _decode(_hand_signed(key, header, payload, encode_payload=False), {"keys": [public]}, options={})

    def test_an_unregistered_header_parameter_is_ignored(self, rsa, claims):
        """Some IdPs add their own header parameters; only ``crit`` makes one mandatory to understand."""
        key, public = rsa
        assert _decode(_hand_signed(key, {"alg": "RS256", "kid": "k1", "nonce": "x"}, json.dumps(claims).encode()), {"keys": [public]})
        with pytest.raises(UnsupportedHeaderError):
            _decode(_hand_signed(key, {"alg": "RS256", "kid": "k1", "nonce": "x", "crit": ["nonce"]}, json.dumps(claims).encode()), {"keys": [public]})

    def test_a_large_header_is_accepted_and_an_oversized_token_is_not(self, rsa, claims):
        key, public = rsa
        chain = ["A" * 4000]
        assert _decode(_hand_signed(key, {"alg": "RS256", "kid": "k1", "x5c": chain}, json.dumps(claims).encode()), {"keys": [public]})
        with pytest.raises(ValueError, match="too long"):
            _decode(_hand_signed(key, {"alg": "RS256", "kid": "k1", "x5c": ["A" * 300000]}, json.dumps(claims).encode()), {"keys": [public]})


class TestClaims:
    @pytest.fixture
    def mint(self, rsa):
        key, public = rsa

        def mint(claims, options=OPTIONS):
            return _decode(encode_jwt({"alg": "RS256", "kid": "k1"}, claims, key), {"keys": [public]}, options)

        return mint

    def test_an_audience_list_containing_ours_is_accepted(self, mint, claims):
        assert mint(dict(claims, aud=["other", AUDIENCE]))
        with pytest.raises(InvalidClaimError):
            mint(dict(claims, aud=["other"]))

    @pytest.mark.parametrize("claim", ["aud", "iss", "exp"])
    def test_a_missing_essential_claim_is_refused(self, mint, claims, claim):
        with pytest.raises(MissingClaimError, match=claim):
            mint({k: v for k, v in claims.items() if k != claim})

    @pytest.mark.parametrize("claim,value", [("aud", ""), ("aud", []), ("iss", ""), ("exp", 0)])
    def test_an_empty_essential_claim_is_refused(self, mint, claims, claim, value):
        with pytest.raises(InvalidClaimError):
            mint(dict(claims, **{claim: value}))

    def test_a_wrong_issuer_is_refused(self, mint, claims):
        with pytest.raises(InvalidClaimError):
            mint(dict(claims, iss="https://elsewhere.example.com"))

    def test_expiry_has_no_leeway(self, mint, claims):
        now = int(time.time())
        with pytest.raises(ExpiredTokenError):
            mint(dict(claims, exp=now - 1))
        assert mint(dict(claims, exp=now + 60))

    @pytest.mark.parametrize("claim", ["nbf", "iat"])
    def test_a_token_from_the_future_is_refused(self, mint, claims, claim):
        now = int(time.time())
        with pytest.raises(InvalidClaimError):
            mint(dict(claims, **{claim: now + 60}))
        assert mint(dict(claims, **{claim: now - 60}))

    def test_unconfigured_claims_are_not_type_checked(self, mint, claims):
        """``sub`` and an unpinned ``aud``/``iss`` were never checked when nothing is configured."""
        assert mint(dict(claims, sub=123, aud=5, iss=7), options={"exp": {"essential": True}})

    def test_no_expiry_is_accepted_only_when_not_essential(self, mint, claims):
        without = {k: v for k, v in claims.items() if k != "exp"}
        with pytest.raises(MissingClaimError):
            mint(without)
        assert mint(without, options={k: v for k, v in OPTIONS.items() if k != "exp"})
