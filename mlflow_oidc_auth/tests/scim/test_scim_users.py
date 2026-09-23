"""SCIM ``/Users`` and discovery (issue #322)."""

import pytest
from sqlalchemy import text

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.ownership import Enforcement

from .conftest import patch_body, user_body

USERS = "/scim/v2/Users"
USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


def create(client, scim, user_name, **kwargs):
    response = client.post(USERS, headers=scim, json=user_body(user_name, **kwargs))
    assert response.status_code == 201, response.text
    return response.json()


def assert_scim_error(response, status, scim_type=None):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["schemas"] == [ERROR_SCHEMA]
    assert body["status"] == str(status)
    if scim_type:
        assert body["scimType"] == scim_type


class TestDiscovery:
    def test_service_provider_config(self, client, scim):
        body = client.get("/scim/v2/ServiceProviderConfig", headers=scim).json()
        assert body["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"]
        assert body["patch"]["supported"] is True
        assert body["bulk"]["supported"] is False
        assert body["filter"]["supported"] is True
        assert body["authenticationSchemes"][0]["type"] == "oauthbearertoken"

    def test_resource_types(self, client, scim):
        body = client.get("/scim/v2/ResourceTypes", headers=scim).json()
        assert body["schemas"] == [LIST_SCHEMA]
        assert body["totalResults"] == 1
        user = body["Resources"][0]
        assert (user["id"], user["endpoint"], user["schema"]) == ("User", "/Users", USER_SCHEMA)
        assert client.get("/scim/v2/ResourceTypes/User", headers=scim).json()["id"] == "User"
        assert client.get("/scim/v2/ResourceTypes/Group", headers=scim).status_code == 404

    def test_schemas(self, client, scim):
        body = client.get("/scim/v2/Schemas", headers=scim).json()
        assert body["Resources"][0]["id"] == USER_SCHEMA
        names = {a["name"] for a in body["Resources"][0]["attributes"]}
        assert {"userName", "active", "externalId", "displayName", "name"} <= names
        assert client.get(f"/scim/v2/Schemas/{USER_SCHEMA}", headers=scim).json()["id"] == USER_SCHEMA


class TestCreate:
    def test_create(self, client, scim, bound_store):
        response = client.post(USERS, headers=scim, json=user_body("Alice@Example.com", external_id="ext-1", display_name="Alice"))
        assert response.status_code == 201
        assert response.headers["content-type"].startswith("application/scim+json")
        body = response.json()
        assert body["schemas"] == [USER_SCHEMA]
        assert body["id"] == body["userName"] == "alice@example.com"
        assert body["externalId"] == "ext-1"
        assert body["displayName"] == "Alice"
        assert body["active"] is True
        assert response.headers["location"].endswith("/scim/v2/Users/alice@example.com")

        detail = bound_store.get_user_detail("alice@example.com")
        assert detail["managed_by"] == "scim"
        assert detail["is_admin"] is False and detail["is_service_account"] is False

    def test_create_inactive(self, client, scim, bound_store):
        create(client, scim, "bob@example.com", active=False)
        assert bound_store.get_user_detail("bob@example.com")["active"] is False

    def test_duplicate_username_is_a_conflict(self, client, scim):
        create(client, scim, "alice@example.com")
        assert_scim_error(client.post(USERS, headers=scim, json=user_body("ALICE@example.com")), 409, "uniqueness")

    def test_duplicate_external_id_is_a_conflict(self, client, scim):
        create(client, scim, "alice@example.com", external_id="ext-1")
        assert_scim_error(client.post(USERS, headers=scim, json=user_body("bob@example.com", external_id="ext-1")), 409, "uniqueness")

    def test_missing_username_is_rejected(self, client, scim):
        assert_scim_error(client.post(USERS, headers=scim, json={"schemas": [USER_SCHEMA]}), 400)

    def test_malformed_json_is_rejected(self, client, scim):
        assert_scim_error(client.post(USERS, headers=scim, content=b"{not json"), 400, "invalidSyntax")

    def test_scim_cannot_create_an_admin(self, client, scim, bound_store):
        body = user_body("eve@example.com")
        body["is_admin"] = True
        body["roles"] = [{"value": "admin"}]
        create_response = client.post(USERS, headers=scim, json=body)
        assert create_response.status_code == 201
        assert bound_store.get_user_detail("eve@example.com")["is_admin"] is False

    def test_no_identity_row_is_written(self, client, scim, bound_store):
        """A directory is not an authenticating provider. Binding ("scim", externalId) would make
        every later OIDC login for this user look like a second provider claiming it — see the
        duplicate-account tests below."""
        create(client, scim, "alice@example.com", external_id="ext-1")
        assert bound_store.user_identity_repo.list_providers_for_username("alice@example.com") == []


class TestRead:
    def test_get_by_id(self, client, scim):
        created = create(client, scim, "alice@example.com", external_id="ext-1")
        assert client.get(f"{USERS}/{created['id']}", headers=scim).json()["userName"] == "alice@example.com"

    def test_external_id_is_not_an_id(self, client, scim):
        """The SCIM id is the username; an externalId is found only through ``filter``."""
        create(client, scim, "alice@example.com", external_id="ext-1")
        assert_scim_error(client.get(f"{USERS}/ext-1", headers=scim), 404)
        found = client.get(USERS, headers=scim, params={"filter": 'externalId eq "ext-1"'}).json()
        assert [r["userName"] for r in found["Resources"]] == ["alice@example.com"]

    def test_an_external_id_equal_to_another_username_does_not_redirect_writes(self, client, scim, bound_store):
        """alice's externalId is "bob"; /Users/bob must address the real bob, never alice."""
        create(client, scim, "alice", external_id="bob")
        create(client, scim, "bob")
        deactivate = patch_body({"op": "replace", "path": "active", "value": False})

        response = client.patch(f"{USERS}/bob", headers=scim, json=deactivate)
        assert response.status_code == 200

        assert bound_store.get_user_detail("bob")["active"] is False
        assert bound_store.get_user_detail("alice")["active"] is True

    def test_an_external_id_alone_is_not_resolved_on_writes(self, client, scim, bound_store):
        create(client, scim, "alice", external_id="ext-9")
        deactivate = patch_body({"op": "replace", "path": "active", "value": False})
        assert_scim_error(client.patch(f"{USERS}/ext-9", headers=scim, json=deactivate), 404)
        assert_scim_error(client.delete(f"{USERS}/ext-9", headers=scim), 404)
        assert bound_store.get_user_detail("alice")["active"] is True

    def test_unknown_user_is_404(self, client, scim):
        assert_scim_error(client.get(f"{USERS}/nobody@example.com", headers=scim), 404)

    def test_service_accounts_are_invisible(self, client, scim, bound_store):
        bound_store.create_user("svc-bot", "unused-secret", "Bot", is_service_account=True)
        assert_scim_error(client.get(f"{USERS}/svc-bot", headers=scim), 404)
        assert_scim_error(client.patch(f"{USERS}/svc-bot", headers=scim, json=patch_body({"op": "replace", "path": "active", "value": False})), 404)
        assert bound_store.get_user_detail("svc-bot")["active"] is True
        assert "svc-bot" not in [r["userName"] for r in client.get(USERS, headers=scim).json()["Resources"]]

    def test_list_and_filter(self, client, scim):
        for i in range(3):
            create(client, scim, f"user{i}@example.com", external_id=f"ext-{i}")

        listed = client.get(USERS, headers=scim).json()
        assert listed["schemas"] == [LIST_SCHEMA]
        assert listed["totalResults"] == 3

        by_name = client.get(USERS, headers=scim, params={"filter": 'userName eq "USER1@example.com"'}).json()
        assert by_name["totalResults"] == 1 and by_name["Resources"][0]["userName"] == "user1@example.com"

        by_external = client.get(USERS, headers=scim, params={"filter": 'externalId eq "ext-2"'}).json()
        assert [r["userName"] for r in by_external["Resources"]] == ["user2@example.com"]

        none = client.get(USERS, headers=scim, params={"filter": 'userName eq "ghost@example.com"'}).json()
        assert none["totalResults"] == 0 and none["Resources"] == []

    def test_pagination(self, client, scim):
        for i in range(5):
            create(client, scim, f"user{i}@example.com")
        page = client.get(USERS, headers=scim, params={"startIndex": 2, "count": 2}).json()
        assert page["totalResults"] == 5
        assert page["startIndex"] == 2
        assert page["itemsPerPage"] == 2
        assert [r["userName"] for r in page["Resources"]] == ["user1@example.com", "user2@example.com"]

    def test_unsupported_filter_is_rejected(self, client, scim):
        assert_scim_error(client.get(USERS, headers=scim, params={"filter": 'emails co "x"'}), 400, "invalidFilter")


class TestReplace:
    def test_put_replaces_attributes(self, client, scim, bound_store):
        create(client, scim, "alice@example.com", external_id="ext-1", display_name="Alice")
        response = client.put(f"{USERS}/alice@example.com", headers=scim, json=user_body("alice@example.com", external_id="ext-9", display_name="Alice B"))
        assert response.status_code == 200
        assert response.json()["displayName"] == "Alice B"
        assert response.json()["externalId"] == "ext-9"

    def test_put_without_external_id_clears_it(self, client, scim, bound_store):
        create(client, scim, "alice@example.com", external_id="ext-1")
        client.put(f"{USERS}/alice@example.com", headers=scim, json=user_body("alice@example.com"))
        assert bound_store.get_user_detail("alice@example.com")["external_id"] is None

    def test_put_cannot_rename(self, client, scim):
        create(client, scim, "alice@example.com")
        assert_scim_error(client.put(f"{USERS}/alice@example.com", headers=scim, json=user_body("mallory@example.com")), 400, "mutability")

    def test_put_on_unknown_user_is_404(self, client, scim):
        assert_scim_error(client.put(f"{USERS}/ghost@example.com", headers=scim, json=user_body("ghost@example.com")), 404)


class TestPatch:
    def test_replace_active(self, client, scim, bound_store):
        create(client, scim, "alice@example.com")
        response = client.patch(f"{USERS}/alice@example.com", headers=scim, json=patch_body({"op": "replace", "path": "active", "value": False}))
        assert response.status_code == 200
        assert response.json()["active"] is False
        assert bound_store.get_user_detail("alice@example.com")["active"] is False

    def test_entra_style_capitalised_op_and_string_boolean(self, client, scim, bound_store):
        create(client, scim, "alice@example.com")
        response = client.patch(f"{USERS}/alice@example.com", headers=scim, json=patch_body({"op": "Replace", "path": "active", "value": "False"}))
        assert response.status_code == 200
        assert bound_store.get_user_detail("alice@example.com")["active"] is False

    def test_pathless_replace(self, client, scim, bound_store):
        create(client, scim, "alice@example.com")
        ops = patch_body({"op": "replace", "value": {"active": False, "displayName": "A", "name": {"givenName": "Al", "formatted": "Alice F"}}})
        response = client.patch(f"{USERS}/alice@example.com", headers=scim, json=ops)
        assert response.status_code == 200, response.text
        assert response.json()["displayName"] == "A", "displayName wins over name.formatted"
        assert response.json()["active"] is False

    def test_add_external_id_and_urn_qualified_path(self, client, scim, bound_store):
        create(client, scim, "alice@example.com")
        ops = patch_body(
            {"op": "add", "path": "externalId", "value": "ext-7"},
            {"op": "replace", "path": f"{USER_SCHEMA}:displayName", "value": "Alice Q"},
        )
        response = client.patch(f"{USERS}/alice@example.com", headers=scim, json=ops)
        assert response.status_code == 200
        detail = bound_store.get_user_detail("alice@example.com")
        assert (detail["external_id"], detail["display_name"]) == ("ext-7", "Alice Q")

    def test_unknown_path_is_rejected_and_nothing_is_written(self, client, scim, bound_store):
        create(client, scim, "alice@example.com")
        ops = patch_body({"op": "replace", "path": "active", "value": False}, {"op": "replace", "path": 'emails[type eq "work"].value', "value": "a@b.c"})
        assert_scim_error(client.patch(f"{USERS}/alice@example.com", headers=scim, json=ops), 400, "invalidPath")
        assert bound_store.get_user_detail("alice@example.com")["active"] is True, "a refused PATCH must not half-apply"

    def test_remove_is_unsupported(self, client, scim):
        create(client, scim, "alice@example.com")
        assert_scim_error(client.patch(f"{USERS}/alice@example.com", headers=scim, json=patch_body({"op": "remove", "path": "externalId"})), 400)

    def test_rename_is_refused(self, client, scim):
        create(client, scim, "alice@example.com")
        ops = patch_body({"op": "replace", "path": "userName", "value": "mallory@example.com"})
        assert_scim_error(client.patch(f"{USERS}/alice@example.com", headers=scim, json=ops), 400, "mutability")

    def test_invalid_active_value(self, client, scim):
        create(client, scim, "alice@example.com")
        ops = patch_body({"op": "replace", "path": "active", "value": "maybe"})
        assert_scim_error(client.patch(f"{USERS}/alice@example.com", headers=scim, json=ops), 400, "invalidValue")

    def test_missing_operations_is_rejected(self, client, scim):
        create(client, scim, "alice@example.com")
        assert_scim_error(client.patch(f"{USERS}/alice@example.com", headers=scim, json={"schemas": []}), 400, "invalidSyntax")

    def test_external_id_taken_by_someone_else(self, client, scim):
        create(client, scim, "alice@example.com", external_id="ext-1")
        create(client, scim, "bob@example.com")
        ops = patch_body({"op": "replace", "path": "externalId", "value": "ext-1"})
        assert_scim_error(client.patch(f"{USERS}/bob@example.com", headers=scim, json=ops), 409, "uniqueness")


class TestOwnershipGuard:
    """SCIM owns what it provisions, and nothing else."""

    def test_post_creates_a_scim_owned_row(self, client, scim, bound_store):
        create(client, scim, "new@example.com")
        assert bound_store.get_user_detail("new@example.com")["managed_by"] == "scim"

    def test_an_attribute_write_does_not_claim_a_manual_row(self, client, scim, bound_store):
        bound_store.create_user("carol@example.com", "unused-secret", "Carol")
        ops = patch_body({"op": "replace", "path": "displayName", "value": "Carol D"})
        response = client.patch(f"{USERS}/carol@example.com", headers=scim, json=ops)
        assert response.status_code == 200
        detail = bound_store.get_user_detail("carol@example.com")
        assert (detail["display_name"], detail["managed_by"]) == ("Carol D", "manual")

    def test_binding_an_external_id_claims_a_manual_row(self, client, scim, bound_store, audit_events):
        """Provisioning: the directory adopts an account an admin created before SCIM existed."""
        bound_store.create_user("carol@example.com", "unused-secret", "Carol")
        ops = patch_body({"op": "add", "path": "externalId", "value": "ext-carol"})
        response = client.patch(f"{USERS}/carol@example.com", headers=scim, json=ops)
        assert response.status_code == 200
        assert bound_store.get_user_detail("carol@example.com")["managed_by"] == "scim"
        assert any(e["event"] == "user.ownership_claimed" for e in audit_events)

    def test_a_manual_admin_is_never_claimed(self, client, scim, bound_store):
        bound_store.create_user("root@example.com", "unused-secret", "Root", is_admin=True)
        ops = patch_body({"op": "add", "path": "externalId", "value": "ext-root"})
        client.patch(f"{USERS}/root@example.com", headers=scim, json=ops)
        assert bound_store.get_user_detail("root@example.com")["managed_by"] == "manual"

    def test_enforce_refuses_a_manual_admin(self, client, scim, bound_store, monkeypatch):
        bound_store.create_user("root@example.com", "unused-secret", "Root", is_admin=True)
        bound_store.create_user("root2@example.com", "unused-secret", "Root 2", is_admin=True)
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        ops = patch_body({"op": "replace", "path": "displayName", "value": "Owned"})
        assert_scim_error(client.patch(f"{USERS}/root@example.com", headers=scim, json=ops), 409, "mutability")
        assert_scim_error(client.patch(f"{USERS}/root@example.com", headers=scim, json=patch_body({"op": "replace", "path": "active", "value": False})), 409)
        assert_scim_error(client.delete(f"{USERS}/root@example.com", headers=scim), 409, "mutability")
        detail = bound_store.get_user_detail("root@example.com")
        assert (detail["display_name"], detail["active"], detail["managed_by"]) == ("Root", True, "manual")

    def test_report_applies_to_a_manual_admin_and_records_it(self, client, scim, bound_store, audit_events):
        bound_store.create_user("root@example.com", "unused-secret", "Root", is_admin=True)
        ops = patch_body({"op": "replace", "path": "displayName", "value": "Renamed"})
        response = client.patch(f"{USERS}/root@example.com", headers=scim, json=ops)
        assert response.status_code == 200
        detail = bound_store.get_user_detail("root@example.com")
        assert (detail["display_name"], detail["managed_by"]) == ("Renamed", "manual")
        conflicts = [e for e in audit_events if e["event"] == "user.ownership_conflict"]
        assert conflicts and conflicts[-1]["detail"]["permitted"] is True

    def test_enforce_refuses_a_row_another_source_owns(self, client, scim, bound_store, monkeypatch):
        bound_store.create_user("dave@example.com", "unused-secret", "Dave")
        bound_store.update_user("dave@example.com", managed_by="oidc:default", written_by="oidc:default")
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        ops = patch_body({"op": "replace", "path": "active", "value": False})
        assert_scim_error(client.patch(f"{USERS}/dave@example.com", headers=scim, json=ops), 409, "mutability")
        assert bound_store.get_user_detail("dave@example.com")["active"] is True
        assert_scim_error(client.delete(f"{USERS}/dave@example.com", headers=scim), 409, "mutability")
        assert bound_store.has_user("dave@example.com")


class TestSsoLoginOnADirectoryOwnedRow:
    """Login is not an ownership change: under ``enforce`` a SCIM-managed user must still be able
    to sign in, through the same call the OIDC/SAML callback makes."""

    @pytest.mark.parametrize("writer", ["oidc:default", "saml:corp"])
    @pytest.mark.parametrize("is_admin", [False, True])
    def test_login_write_is_permitted_under_enforce(self, client, scim, bound_store, monkeypatch, writer, is_admin):
        from mlflow_oidc_auth import user as user_module

        create(client, scim, "alice@example.com")
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        created, _ = user_module.create_user("alice@example.com", "Alice", is_admin=is_admin, written_by=writer)

        assert created is False
        detail = bound_store.get_user_detail("alice@example.com")
        assert detail["managed_by"] == "scim", "a login never takes ownership"
        assert detail["is_admin"] is is_admin

    def test_login_still_cannot_touch_directory_owned_state(self, client, scim, bound_store, monkeypatch):
        from mlflow.exceptions import MlflowException

        create(client, scim, "alice@example.com")
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)
        for change in ({"active": False}, {"managed_by": "oidc:default"}, {"is_service_account": True}, {"password": "x"}):
            with pytest.raises(MlflowException):
                bound_store.update_user("alice@example.com", written_by="oidc:default", **change)
        detail = bound_store.get_user_detail("alice@example.com")
        assert (detail["active"], detail["managed_by"], detail["is_service_account"]) == (True, "scim", False)


class TestUserNameValidation:
    @pytest.mark.parametrize(
        "user_name",
        [
            "",
            "   ",
            "evil\nname@example.com",
            "nul\u0000@example.com",
            "tab\tname@example.com",
            "zero\u200bwidth@example.com",
            "a" * 256,
            "\uff41lice@example.com",  # fullwidth "a": NFKC folds it to an existing-looking name
            "stra\u00dfe@example.com",  # "ß" case-folds to "ss"
            "team/alice",  # would be a /Users/{id} path its own location could not address
            "alice?x=1",
            "alice#frag",
            "alice%2Fbob",
        ],
    )
    def test_rejected(self, client, scim, bound_store, user_name):
        assert_scim_error(client.post(USERS, headers=scim, json=user_body(user_name)), 400, "invalidValue")
        with bound_store.engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 0

    def test_surrounding_whitespace_is_stripped(self, client, scim):
        assert create(client, scim, "  Alice@Example.com  ")["userName"] == "alice@example.com"

    def test_255_characters_is_accepted(self, client, scim):
        name = "a" * 243 + "@example.com"
        assert len(name) == 255
        assert create(client, scim, name)["userName"] == name

    def test_look_alike_of_an_existing_user_cannot_be_created(self, client, scim):
        create(client, scim, "alice@example.com")
        response = client.post(USERS, headers=scim, json=user_body("\uff21lice@example.com"))
        assert response.status_code == 400
        assert_scim_error(client.post(USERS, headers=scim, json=user_body("ALICE@example.com")), 409, "uniqueness")


class TestMalformedFilter:
    @pytest.mark.parametrize(
        "expression",
        [
            'userName eq "bad\\q"',  # invalid JSON escape
            'userName eq "tab\there"',  # raw control character
            'userName eq "\\ud800"',  # lone surrogate
            'externalId eq "\\ud800"',
            'userName eq "\\u12"',  # truncated escape
        ],
    )
    def test_is_a_400_not_a_500(self, client, scim, expression):
        assert_scim_error(client.get(USERS, headers=scim, params={"filter": expression}), 400, "invalidFilter")


class TestPutKeepsActiveWhenOmitted:
    def test_put_without_active_does_not_reactivate(self, client, scim, bound_store):
        create(client, scim, "alice@example.com", active=False)
        body = {"schemas": [USER_SCHEMA], "userName": "alice@example.com", "displayName": "Alice"}
        response = client.put(f"{USERS}/alice@example.com", headers=scim, json=body)
        assert response.status_code == 200
        assert bound_store.get_user_detail("alice@example.com")["active"] is False

    def test_post_without_active_creates_an_active_user(self, client, scim, bound_store):
        response = client.post(USERS, headers=scim, json={"schemas": [USER_SCHEMA], "userName": "new@example.com"})
        assert response.status_code == 201
        assert bound_store.get_user_detail("new@example.com")["active"] is True


class TestDelete:
    def test_delete(self, client, scim, bound_store):
        create(client, scim, "alice@example.com", external_id="ext-1")
        response = client.delete(f"{USERS}/alice@example.com", headers=scim)
        assert response.status_code == 204
        assert not bound_store.has_user("alice@example.com")
        assert_scim_error(client.get(f"{USERS}/alice@example.com", headers=scim), 404)

    def test_delete_unknown_is_404(self, client, scim):
        assert_scim_error(client.delete(f"{USERS}/ghost@example.com", headers=scim), 404)


class TestReservedCharactersInExistingNames:
    """A row that predates the userName rules (or was made by hand) may hold a '/'. Its SCIM
    location percent-encodes it, and the decoded segment must still reach it — otherwise the
    directory could never de-provision that user."""

    def test_a_slash_username_is_addressable_through_its_location(self, client, scim, bound_store):
        bound_store.create_user("team/alice", "unused-secret", "Team Alice")
        listed = client.get(USERS, headers=scim, params={"filter": 'userName eq "team/alice"'}).json()["Resources"]
        location = listed[0]["meta"]["location"]
        assert location.endswith("/Users/team%2Falice")
        path = location[location.index("/scim/") :]

        assert client.get(path, headers=scim).json()["userName"] == "team/alice"
        deactivate = patch_body({"op": "replace", "path": "active", "value": False})
        response = client.patch(path, headers=scim, json=deactivate)
        assert response.status_code == 200
        assert bound_store.get_user_detail("team/alice")["active"] is False
        response = client.delete(path, headers=scim)
        assert response.status_code == 204
        assert not bound_store.has_user("team/alice")


class TestNoDuplicateAccount:
    """#322: a user SCIM provisioned, who then signs in through OIDC, must land on the SAME row.

    Exercised through the real decision functions the OIDC callback runs —
    ``resolve_identity`` then ``apply_provisioning_policy`` — for both binding modes.
    """

    @staticmethod
    def _provider(provider_id="default", **overrides):
        from mlflow_oidc_auth.provider_registry import ProviderConfig

        overrides.setdefault("identity_binding", "subject")
        return ProviderConfig(id=provider_id, audience="mlflow", **overrides)

    def _login(self, bound_store, provider, subject, claims, username):
        from mlflow_oidc_auth.identity_resolution import resolve_identity
        from mlflow_oidc_auth.provisioning_policy import apply_provisioning_policy

        decision = resolve_identity(provider, subject, claims, bound_store.user_identity_repo, user_lookup=bound_store.has_user, username=username)
        return apply_provisioning_policy(
            provider,
            decision,
            derived_username=username,
            user_exists=bound_store.has_user,
            providers_bound_to=bound_store.user_identity_repo.list_providers_for_username,
        )

    def _count_users(self, bound_store):
        with bound_store.engine.connect() as conn:
            return conn.execute(text("SELECT count(*) FROM users")).scalar()

    def test_default_provider_login_reuses_the_scim_row(self, client, scim, bound_store):
        create(client, scim, "alice@example.com", external_id="ext-1")
        provider = self._provider()

        outcome = self._login(bound_store, provider, "idp-sub-123", {"email": "alice@example.com"}, "alice@example.com")

        assert outcome.allowed, outcome.reason
        assert outcome.create is False
        assert outcome.username == "alice@example.com"
        # What the callback then does: bind the identity, and refresh the row through create_user.
        bound_store.user_identity_repo.link(provider.id, "idp-sub-123", outcome.username)
        from mlflow_oidc_auth import user as user_module

        created, _ = user_module.create_user("alice@example.com", "Alice", written_by="oidc:default")
        assert created is False
        assert self._count_users(bound_store) == 1

    def test_email_bound_provider_links_the_scim_row(self, client, scim, bound_store):
        create(client, scim, "alice@example.com", external_id="ext-1")
        provider = self._provider("corp", identity_binding="email", allowed_email_domains=("example.com",))

        outcome = self._login(bound_store, provider, "corp-sub-9", {"email": "Alice@Example.com", "email_verified": True}, "alice@example.com")

        assert outcome.allowed, outcome.reason
        assert outcome.create is False
        assert outcome.username == "alice@example.com"
        assert self._count_users(bound_store) == 1

    def test_why_scim_does_not_bind_an_identity(self, client, scim, bound_store):
        """The counterfactual, pinned: had SCIM written a ("scim", externalId) identity, the
        provisioning policy would read it as a foreign provider owning the account and refuse the
        user's first OIDC login — every directory-provisioned user locked out."""
        create(client, scim, "alice@example.com", external_id="ext-1")
        bound_store.user_identity_repo.link("scim", "ext-1", "alice@example.com")

        outcome = self._login(bound_store, self._provider(), "idp-sub-123", {"email": "alice@example.com"}, "alice@example.com")

        assert outcome.allowed is False
