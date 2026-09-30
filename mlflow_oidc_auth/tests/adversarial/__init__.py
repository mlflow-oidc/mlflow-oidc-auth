"""Adversarial suite for token validation and the authorization response (issue #307).

Multi-issuer bearer tokens (#313) and multi-provider login (#316) add attack surface that does
not exist in a single-provider deployment: with one issuer, "which provider issued this?" has
only one answer, and every mix-up question is vacuous. The epic requires this suite to exist
*before* that lands, so the properties are written down while they are still easy to state.

The cases are grouped by what an attacker controls:

* ``token_forgery`` — the token: its header, its signature, its ``kid``.
* ``claims`` — the claims: ``iss``, ``aud``, ``exp``.
* ``authorization_response`` — the redirect back from the provider: ``state``, ``iss``, ``code``.

``suite.py`` holds the reusable pieces. A new provider type is meant to inherit
``TokenAdversarySuite`` and supply one fixture rather than re-implement the cases — the point of
the suite is that the next provider cannot forget one.
"""
