"""Minting helpers for tests that need real, signed JWTs.

Tokens are signed with ``joserfc`` so a test exercises the same library the validator uses.
"""

from typing import Any

from joserfc import jwt
from joserfc.jwk import JWKRegistry, Key, RSAKey


def generate_rsa_key(bits: int = 2048) -> RSAKey:
    """A fresh private RSA key.

    Parameters:
        bits: Modulus size.

    Returns:
        The private key; ``as_dict(private=False)`` gives the public JWK.
    """
    return RSAKey.generate_key(bits, private=True)


def encode_jwt(header: dict[str, Any], claims: dict[str, Any], key: Key | dict[str, Any]) -> str:
    """Sign ``claims`` as a compact JWS with ``header["alg"]``.

    Parameters:
        header: The protected header; must name ``alg``.
        claims: The payload.
        key: A private key, or its JWK dict.

    Returns:
        The compact token.
    """
    if isinstance(key, dict):
        key = JWKRegistry.import_key(key)
    return jwt.encode(header, claims, key, algorithms=[header["alg"]])
