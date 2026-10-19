"""SCIM ``/Users`` responses never carry a credential (#458).

``/scim/v2`` bodies follow RFC 7643/7644, not this plugin's OpenAPI models, so the contract checker
does not see inside them. SCIM's ``password`` attribute is ``writeOnly`` (RFC 7643 §4.1.1): an IdP
may send it, but it must never come back. This drives every user operation — with a password in
each request body that can carry one — and fails on any credential-named key in any response.
"""

from mlflow_oidc_auth.tests.contract import find_credentials

from .conftest import patch_body, user_body

USERS = "/scim/v2/Users"


def _no_credentials(response, status: int = 200) -> None:
    assert response.status_code == status, response.text
    leaked = find_credentials(response.json())
    assert not leaked, f"{response.request.method} {response.request.url.path} returned {leaked}"


def _with_password(body: dict) -> dict:
    return {**body, "password": "Sup3r-secret!"}


def test_user_responses_never_carry_a_credential(client, scim):
    created = client.post(USERS, headers=scim, json=_with_password(user_body("alice@example.com", external_id="ext-1")))
    _no_credentials(created, 201)
    user_id = created.json()["id"]

    _no_credentials(client.get(f"{USERS}/{user_id}", headers=scim))
    _no_credentials(client.get(USERS, headers=scim))
    _no_credentials(client.get(USERS, headers=scim, params={"filter": 'userName eq "alice@example.com"'}))
    _no_credentials(client.put(f"{USERS}/{user_id}", headers=scim, json=_with_password(user_body("alice@example.com", display_name="Alice"))))
    # Password is not an attribute this server patches, by path or inside a value object: the
    # operation is refused, and the error body has no credential key and does not echo the value.
    for operation in ({"op": "replace", "path": "password", "value": "N3w-secret!"}, {"op": "replace", "value": {"password": "N3w-secret!"}}):
        refused = client.patch(f"{USERS}/{user_id}", headers=scim, json=patch_body(operation))
        _no_credentials(refused, 400)
        assert "N3w-secret!" not in refused.text
    _no_credentials(client.patch(f"{USERS}/{user_id}", headers=scim, json=patch_body({"op": "replace", "path": "active", "value": False})))


def test_find_credentials_catches_nested_and_mixed_case_keys():
    """The scan itself: nested objects, lists and case."""
    body = {"id": "a", "emails": [{"value": "a@b"}], "meta": {"Password": "x"}, "x": [{"ID_Token": 1}]}
    assert find_credentials(body) == ["$.meta.Password", "$.x[0].ID_Token"]
