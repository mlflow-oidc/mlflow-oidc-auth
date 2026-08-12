"""Validating the authorization response's issuer — RFC 9207 (issue #307).

An authorization response is a redirect carrying ``code`` and ``state``, and nothing else that
says who sent it. With one authorization server that is fine: there is only one answer. With
two, it is the OAuth **mix-up attack** — an attacker who controls, or can induce a login at, one
authorization server sends its response to the client's callback for a *different* one, and the
client redeems the code at the wrong token endpoint, handing it to the attacker's server or
accepting an identity the honest server never asserted.

[RFC 9207](https://www.rfc-editor.org/rfc/rfc9207.html) closes it by having the authorization
server return an ``iss`` parameter, and the client compare it against the issuer it started the
transaction with.

**What is here and what is not.** This module is the decision — a pure function, so it can be
tested exhaustively against every shape of response an attacker can produce. Wiring it into the
callback belongs to #316, which is what introduces per-provider routes and the ``auth_state``
row holding the issuer a transaction began with. Nothing calls this yet, so no deployment's
behaviour changes: the point of landing it with the suite is that #316 inherits a decision that
is already pinned by tests, rather than writing both at once.
"""

from typing import Optional

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


class IssuerMismatchError(Exception):
    """The authorization response did not come from the issuer the transaction started with."""


def validate_response_issuer(
    returned_iss: Optional[str],
    expected_iss: Optional[str],
    *,
    iss_parameter_supported: bool,
) -> None:
    """Check the ``iss`` of an authorization response against the issuer that started it.

    Parameters:
        returned_iss: The ``iss`` query parameter on the callback, or None when absent. A value
            that is not a string — a list, from a repeated parameter — is refused.
        expected_iss: The issuer recorded when the login began. None when the deployment has no
            record of it — which is every deployment before #316 gives transactions a home.
        iss_parameter_supported: Whether the provider's discovery metadata advertises
            ``authorization_response_iss_parameter_supported``.

    Raises:
        IssuerMismatchError: If the response names a different issuer, or names none at all when
            the provider advertises that it always sends one.

    The three cases and why each is decided this way:

    * **Mismatch** — always fatal, whatever the metadata says. A response naming an issuer other
      than the one this transaction began with is a mix-up by definition, and there is no
      configuration under which honouring it is correct.
    * **Missing, and the provider advertises support** — fatal. If it were tolerated, an attacker
      would simply strip the parameter, which recreates exactly the ambiguity RFC 9207 removes.
    * **Missing, and the provider advertises nothing** — allowed. RFC 9207 is recent and plenty
      of deployed servers do not implement it; refusing here would break working logins to
      protect against an attack that needs a second authorization server to exist. #313 and #316
      are where a multi-provider deployment can start requiring it.

    ``expected_iss`` being None means the caller has nothing to compare against, so there is
    nothing to decide; the mix-up defence for that deployment is that it has one provider.
    """
    if expected_iss is None:
        return

    # A query string can repeat a parameter — ``?iss=honest&iss=attacker`` — so a caller reading
    # it with ``getlist`` hands this a list. Refused as the documented error rather than left to
    # raise ``AttributeError`` on the ``.strip()`` below: that would escape a caller catching
    # only ``IssuerMismatchError``, turning the mix-up defence into an unhandled 500.
    if returned_iss is not None and not isinstance(returned_iss, str):
        raise IssuerMismatchError(
            f"The authorization response carried a non-string 'iss' ({type(returned_iss).__name__}); a response that "
            "names more than one issuer, or none in a readable form, cannot be attributed to one."
        )

    # ``?iss=`` arrives as an empty string and ``?iss=%20`` as whitespace; neither identifies an
    # issuer, so both are the *missing* case rather than a mismatch. Deciding them differently
    # would mean a provider that emits an empty parameter is refused while one that omits it
    # entirely is allowed — an arbitrary distinction an attacker gets to choose between.
    if returned_iss is not None and not returned_iss.strip():
        returned_iss = None

    if returned_iss is None:
        if iss_parameter_supported:
            raise IssuerMismatchError(
                f"The authorization response carried no 'iss' parameter, but the provider for {expected_iss!r} "
                "advertises authorization_response_iss_parameter_supported. A response missing it cannot be "
                "attributed to an issuer, which is what RFC 9207 exists to prevent."
            )
        logger.debug("Authorization response for %s carried no 'iss'; the provider does not advertise support", expected_iss)
        return

    if returned_iss != expected_iss:
        raise IssuerMismatchError(
            f"The authorization response was issued by {returned_iss!r}, but this login was started with " f"{expected_iss!r}. Refusing to exchange the code."
        )
