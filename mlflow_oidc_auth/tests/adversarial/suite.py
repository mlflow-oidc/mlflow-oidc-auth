"""Reusable pieces for the adversarial suite (issue #307).

Two things live here:

``Issuer``
    A stand-in identity provider: its own RSA key, its own ``iss``, its own audience, and a
    ``mint`` that signs whatever claims it is handed. Two of them is the minimum needed to ask
    any cross-issuer question at all.

``TokenAdversarySuite``
    The cases themselves, as a base class. A new provider type — the Kubernetes service-account
    provider in #314, a second OIDC issuer in #313 — inherits it and supplies the ``verify``
    fixture: a callable that takes a token and raises if it is not acceptable *for that
    provider*. Every case below then applies to it without being rewritten, which is the
    acceptance criterion the issue asks for: a new provider inherits the suite rather than
    re-implementing it.
"""

import base64
import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

import pytest
from authlib.jose import JsonWebKey, jwt


def b64(raw: bytes) -> bytes:
    """URL-safe base64 without padding, as JOSE uses."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


@dataclass
class Issuer:
    """A stand-in provider: one key, one issuer identifier, one audience."""

    name: str
    iss: str
    audience: str
    key: object = field(default=None)

    def __post_init__(self):
        if self.key is None:
            self.key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
        self._private = self.key.as_dict(is_private=True)
        self._public = self.key.as_dict(is_private=False)
        kid = self._public.get("kid") or self.key.thumbprint()
        self._public["kid"] = self._private["kid"] = kid

    @property
    def kid(self) -> str:
        return self._public["kid"]

    @property
    def jwks(self) -> dict:
        return {"keys": [self._public]}

    def claims(self, **overrides) -> dict:
        """Claims a genuine token from this issuer would carry."""
        now = int(time.time())
        claims = {
            "email": "adversary-suite@example.com",
            "iss": self.iss,
            "aud": self.audience,
            "iat": now,
            "exp": now + 3600,
        }
        claims.update(overrides)
        return claims

    def mint(
        self,
        claims: Optional[dict] = None,
        *,
        kid: Optional[str] = None,
        algorithm: str = "RS256",
        extra_header: Optional[dict] = None,
        **overrides,
    ) -> str:
        """Sign a genuine token with this issuer's key.

        ``kid`` and ``extra_header`` are part of the *signed* header, which is what makes the
        header-confusion cases real: an attacker mints with their own key and names whatever
        ``kid``, ``jku`` or ``x5u`` they like, and the signature is genuine under their key.
        Editing a header after signing would instead produce a token that fails signature
        verification outright, which tests nothing about how the header is treated.

        ``overrides`` apply on top of ``claims`` when both are given, rather than being dropped
        — a silently ignored ``aud=...`` would mint a token without the property its test names.
        """
        header = {"alg": algorithm, "kid": kid or self.kid}
        if extra_header:
            header.update(extra_header)
        payload = dict(claims) if claims is not None else self.claims()
        payload.update(overrides)
        return jwt.encode(header, payload, self._private).decode("utf-8")


def unsigned_token(claims: dict) -> str:
    """A token declaring ``alg: none``, with an empty signature."""
    header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64(json.dumps(claims).encode())
    return (header + b"." + payload + b".").decode()


def hmac_token(claims: dict, kid: str, secret: bytes, algorithm: str = "HS256") -> str:
    """A symmetric token hand-built from ``secret``.

    Constructed by hand because a correct JOSE library refuses to sign with a public key — which
    is the point of the attack. A test that relies on the library to mint the forgery tests
    nothing, because the attacker is not using the library.
    """
    digest = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}[algorithm]
    header = b64(json.dumps({"alg": algorithm, "kid": kid}).encode())
    payload = b64(json.dumps(claims).encode())
    signature = b64(hmac.new(secret, header + b"." + payload, digest).digest())
    return (header + b"." + payload + b"." + signature).decode()


#: Failures that mean the *test* is broken, not that the defence worked. A rejection case that
#: ends in one of these proves nothing: the token never reached the property under test.
PROGRAMMING_ERRORS = (AttributeError, TypeError, NameError, ImportError, IndexError, KeyError)


@contextmanager
def rejects():
    """Assert the block refuses the token, and that it refuses it for a defensible reason.

    ``pytest.raises(Exception)`` is too coarse here: it accepts an ``AttributeError`` from a typo
    in the test as readily as a considered rejection, which is how a case can look like a guard
    while guarding nothing.
    """
    try:
        yield
    except PROGRAMMING_ERRORS as exc:
        raise AssertionError(f"the case failed for a reason unrelated to the defence: {exc!r}") from exc
    except Exception:
        return
    raise AssertionError("the token was accepted")


class TokenAdversarySuite:
    """Cases every token-accepting provider must reject.

    Subclass it and provide a ``verify`` fixture returning a one-argument callable that raises
    when a token is not acceptable for the provider under test, plus a ``trusted`` fixture
    returning the :class:`Issuer` that provider trusts and a ``foreign`` fixture returning one it
    does not.
    """

    def test_a_genuine_token_is_accepted(self, verify, trusted):
        """The control. Without it, every rejection below could be a rejection of everything."""
        assert verify(trusted.mint()) is not None

    def test_an_unsigned_token_is_rejected(self, verify, trusted):
        with rejects():
            verify(unsigned_token(trusted.claims()))

    def test_a_token_signed_by_a_foreign_issuer_is_rejected(self, verify, foreign):
        """Cross-issuer replay: a token that is perfectly valid somewhere else.

        The whole token is genuine — correct signature, unexpired, well-formed — and issued by a
        provider this one does not trust. Nothing about the token itself is wrong; only its
        origin is, which is why signature validity alone can never be the test.
        """
        with rejects():
            verify(foreign.mint())

    def test_a_foreign_token_wearing_the_trusted_kid_is_rejected(self, verify, trusted, foreign):
        """``kid`` confusion: the header points at a key the verifier trusts, the signature does
        not come from it. Believing the header would be believing the attacker.

        Minted with the attacker's key *and* the trusted ``kid`` in the signed header, so the
        signature is genuine under the attacker's key. A token whose header was edited after
        signing would fail signature verification outright and prove nothing about ``kid``.
        """
        forged = foreign.mint(kid=trusted.kid)

        with rejects():
            verify(forged)

    def test_a_token_naming_an_unknown_kid_is_rejected(self, verify, foreign, trusted):
        forged = foreign.mint(kid="a-key-that-was-never-published")

        with rejects():
            verify(forged)

    def test_the_trusted_public_key_is_not_an_hmac_secret(self, verify, trusted):
        """Algorithm confusion. The verifier's *public* key is public; if it can be used as a
        shared secret, anyone who can read the JWKS can mint tokens.

        **Defence in depth, and not falsifiable here.** Two independent things reject this: the
        pinned algorithm set, and authlib refusing to use a key it resolved as RSA for an HMAC
        verification. Widening the pinned set to include ``HS256`` therefore does *not* make this
        case fail, so passing it is not evidence that the pin is in place. The falsifiable
        assertion — that no symmetric algorithm is in the accepted set at all — is a structural
        one, in ``test_token_algorithm_pinning.py::TestTheAcceptedSetIsPinned``. Kept because the
        end-to-end property is still worth stating, and because a future provider might resolve
        keys differently and lose the second defence without anyone noticing.
        """
        public_pem = trusted.key.as_pem(is_private=False) if hasattr(trusted.key, "as_pem") else json.dumps(trusted.jwks["keys"][0]).encode()

        with rejects():
            verify(hmac_token(trusted.claims(), trusted.kid, public_pem))

    def test_an_expired_token_is_rejected(self, verify, trusted):
        now = int(time.time())

        with rejects():
            verify(trusted.mint(iat=now - 7200, exp=now - 3600))

    def test_an_attacker_supplied_key_url_is_not_honoured(self, verify, foreign, trusted):
        """``jku``/``x5u`` naming the attacker's own key set. Fetching it would both trust the
        attacker's keys and turn the verifier into an SSRF gadget."""
        for header in ("jku", "x5u"):
            # In the signed header, so the signature is genuine under the attacker's key and the
            # only question left is whether the verifier follows the URL.
            forged = foreign.mint(extra_header={header: "https://attacker.invalid/keys.json"})

            with rejects():
                verify(forged)
