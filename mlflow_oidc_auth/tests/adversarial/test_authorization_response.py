"""Mix-up cases against the authorization response — RFC 9207 (issue #307).

The three cases the issue names — missing ``iss``, stripped ``iss``, mismatched ``iss`` — plus
the ones that decide whether the rule can be enforced without breaking working deployments.

The decision lives in ``mlflow_oidc_auth/authorization_response.py`` as a pure function. #316
wires it into the per-provider callback; these cases are what it will have to keep passing.
"""

import pytest

from mlflow_oidc_auth.authorization_response import IssuerMismatchError, validate_response_issuer

HONEST = "https://honest.idp.invalid"
ATTACKER = "https://attacker.idp.invalid"


class TestMismatchedIssuer:
    """The mix-up itself: a response from one authorization server delivered to a callback that
    is expecting another."""

    def test_a_response_from_another_issuer_is_refused(self):
        with pytest.raises(IssuerMismatchError):
            validate_response_issuer(ATTACKER, HONEST, iss_parameter_supported=True)

    def test_it_is_refused_even_when_the_provider_advertises_nothing(self):
        """Metadata is the attacker's to influence in a mix-up — it is fetched from whichever
        server the client thinks it is talking to. A mismatch is fatal regardless."""
        with pytest.raises(IssuerMismatchError):
            validate_response_issuer(ATTACKER, HONEST, iss_parameter_supported=False)

    def test_a_lookalike_issuer_is_refused(self):
        """Comparison is exact. Anything looser accepts a host the attacker registered."""
        for lookalike in (HONEST + ".attacker.invalid", HONEST + "/", HONEST.replace("https", "http"), HONEST.upper(), HONEST + " "):
            with pytest.raises(IssuerMismatchError):
                validate_response_issuer(lookalike, HONEST, iss_parameter_supported=True)

    def test_the_error_names_both_issuers(self):
        """An operator reading this in a log needs to know which two servers were involved."""
        with pytest.raises(IssuerMismatchError) as excinfo:
            validate_response_issuer(ATTACKER, HONEST, iss_parameter_supported=True)

        message = str(excinfo.value)
        assert ATTACKER in message
        assert HONEST in message


class TestStrippedIssuer:
    """An attacker removing the parameter must not be able to opt out of the check.

    This is the case that decides whether RFC 9207 is worth implementing at all: if a missing
    ``iss`` is treated as "nothing to check", then every mix-up is one deleted query parameter
    away from succeeding.
    """

    def test_a_missing_iss_is_refused_when_the_provider_sends_one(self):
        with pytest.raises(IssuerMismatchError):
            validate_response_issuer(None, HONEST, iss_parameter_supported=True)

    @pytest.mark.parametrize("blank", ["", " ", "\t"])
    def test_a_blank_iss_is_refused_when_the_provider_sends_one(self, blank):
        """``?iss=`` arrives as an empty string, not as absent — and must be treated as the
        missing case rather than as a mismatch, or a provider emitting an empty parameter would
        be refused while one omitting it entirely is allowed."""
        with pytest.raises(IssuerMismatchError):
            validate_response_issuer(blank, HONEST, iss_parameter_supported=True)

    @pytest.mark.parametrize("blank", ["", " ", "\t"])
    def test_a_blank_iss_is_allowed_when_the_provider_sends_none(self, blank):
        validate_response_issuer(blank, HONEST, iss_parameter_supported=False)

    def test_the_error_says_the_parameter_was_missing(self):
        with pytest.raises(IssuerMismatchError) as excinfo:
            validate_response_issuer(None, HONEST, iss_parameter_supported=True)

        assert "iss" in str(excinfo.value)


class TestProvidersThatDoNotImplementRFC9207:
    """Refusing these would break logins that work today, to defend against an attack that needs
    a second authorization server to exist."""

    def test_a_missing_iss_is_allowed_when_the_provider_advertises_nothing(self):
        validate_response_issuer(None, HONEST, iss_parameter_supported=False)

    def test_a_matching_iss_is_allowed(self):
        validate_response_issuer(HONEST, HONEST, iss_parameter_supported=True)
        validate_response_issuer(HONEST, HONEST, iss_parameter_supported=False)


class TestNothingToCompareAgainst:
    """Before #316 gives a transaction a home, there is no recorded issuer.

    The check has to be inert in that case rather than guess — and a deployment with one
    provider is not exposed to mix-up in the first place.
    """

    def test_no_expected_issuer_means_no_decision(self):
        validate_response_issuer(ATTACKER, None, iss_parameter_supported=True)
        validate_response_issuer(None, None, iss_parameter_supported=True)


class TestTheDecisionIsTotal:
    """Whatever an attacker puts in the query string, the function decides — it never raises
    something the caller has not planned for, and never returns for a mismatch."""

    @pytest.mark.parametrize(
        "returned",
        [None, "", " ", HONEST, ATTACKER, "not-a-url", "https://honest.idp.invalid#fragment", "https://honest.idp.invalid?a=b"],
    )
    @pytest.mark.parametrize("supported", [True, False])
    def test_every_shape_of_response_is_either_accepted_or_refused(self, returned, supported):
        try:
            validate_response_issuer(returned, HONEST, iss_parameter_supported=supported)
            accepted = True
        except IssuerMismatchError:
            accepted = False

        # The rule, stated independently of the implementation: a response is accepted only if it
        # names the expected issuer exactly, or names no issuer at all against a provider that
        # never sends one. "No issuer at all" covers absent, empty and whitespace alike.
        identifies_an_issuer = bool(returned and returned.strip())
        expected_to_be_accepted = (identifies_an_issuer and returned == HONEST) or (not identifies_an_issuer and not supported)

        assert accepted is expected_to_be_accepted
