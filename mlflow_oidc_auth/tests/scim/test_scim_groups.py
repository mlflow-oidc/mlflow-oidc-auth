"""SCIM ``/Groups`` (issue #323), including the provider-specific membership shapes.

Microsoft Entra ID adds members with ``PATCH add members`` and removes them with a *filtered* path,
``members[value eq "<id>"]`` — the shape naive PATCH implementations get wrong. Okta, in some
configurations, sends the whole group with ``PUT``. Both are exercised against the real store and
the real permission resolution, because membership is only interesting for what it grants.

Memberships SCIM writes are owned by ``scim`` per row (#360), so they coexist with memberships an
administrator or a login's claims granted: SCIM adds freely, and removes only through the
ownership guard.
"""

import pytest

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.ownership import Enforcement
from mlflow_oidc_auth.provider_registry import ProviderConfig

from .conftest import ADMIN, patch_body, user_body

GROUPS = "/scim/v2/Groups"
USERS = "/scim/v2/Users"
GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"

ALICE = "alice@example.com"
BOB = "bob@example.com"
CAROL = "carol@example.com"


@pytest.fixture(autouse=True)
def no_tracking_store(monkeypatch):
    """Permission resolution falls through to the regex sources, which look the experiment name up
    in MLflow's tracking store. These tests grant nothing by regex, so give that lookup a stub
    rather than let it build whatever store ``MLFLOW_TRACKING_URI`` (or its absence) implies."""
    from types import SimpleNamespace

    from mlflow_oidc_auth.utils import permissions

    class _Store:
        def get_experiment(self, experiment_id):
            return SimpleNamespace(experiment_id=experiment_id, name=f"experiment-{experiment_id}")

    monkeypatch.setattr(permissions, "_get_tracking_store", lambda: _Store())


def assert_scim_error(response, status, scim_type=None):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["schemas"] == [ERROR_SCHEMA]
    assert body["status"] == str(status)
    if scim_type:
        assert body["scimType"] == scim_type


def group_body(name, members=(), external_id=None, **extra):
    body = {"schemas": [GROUP_SCHEMA], "displayName": name, **extra}
    if members is not None:
        body["members"] = [{"value": m} for m in members]
    if external_id is not None:
        body["externalId"] = external_id
    return body


def member_ids(resource):
    return sorted(m["value"] for m in resource.get("members", []))


def owners(store, group_name):
    """``{username: managed_by}`` for one group, service accounts included, read from the table."""
    from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

    with store.ManagedSessionMaker() as session:
        rows = (
            session.query(SqlUser.username, SqlUserGroup.managed_by)
            .join(SqlUserGroup, SqlUserGroup.user_id == SqlUser.id)
            .join(SqlGroup, SqlGroup.id == SqlUserGroup.group_id)
            .filter(SqlGroup.group_name == group_name)
            .all()
        )
        return dict(rows)


@pytest.fixture
def users(client, scim):
    for name in (ALICE, BOB, CAROL):
        response = client.post(USERS, headers=scim, json=user_body(name))
        assert response.status_code == 201
    return ALICE, BOB, CAROL


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)


def create_group(client, scim, name, members=(), **kwargs):
    response = client.post(GROUPS, headers=scim, json=group_body(name, members, **kwargs))
    assert response.status_code == 201, response.text
    return response.json()


def login(username, groups, monkeypatch):
    """The real login path (OIDC callback and SAML ACS share it), for claim-derived memberships."""
    from mlflow_oidc_auth.routers.auth import _provision_login

    monkeypatch.setattr(config, "OIDC_GROUP_NAME", ["mlflow-users"])
    monkeypatch.setattr(config, "OIDC_ADMIN_GROUP_NAME", ["mlflow-admins"])
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    provider = ProviderConfig(
        id="default",
        type="oidc",
        audience="mlflow",
        issuer="https://idp.invalid",
        provisioning="jit",
        group_sync="every_login",
        group_sync_mode="authoritative",
        admin_source="claims",
    )
    username, errors = _provision_login(
        provider, username=username, display_name=username, userinfo={"email": username}, user_groups=["mlflow-users", *groups], access_token=None
    )
    assert errors == []
    return username


class TestDiscovery:
    def test_group_resource_type_and_schema(self, client, scim):
        resource_type = client.get("/scim/v2/ResourceTypes/Group", headers=scim).json()
        assert (resource_type["endpoint"], resource_type["schema"]) == ("/Groups", GROUP_SCHEMA)

        schema = client.get(f"/scim/v2/Schemas/{GROUP_SCHEMA}", headers=scim).json()
        attributes = {a["name"]: a for a in schema["attributes"]}
        assert attributes["displayName"]["mutability"] == "immutable"
        assert {s["name"] for s in attributes["members"]["subAttributes"]} == {"value", "$ref", "type"}
        listed = client.get("/scim/v2/Schemas", headers=scim).json()
        assert {r["id"] for r in listed["Resources"]} == {GROUP_SCHEMA, "urn:ietf:params:scim:schemas:core:2.0:User"}

    def test_groups_need_the_scim_token(self, client, bound_store, admin):
        response = client.get(GROUPS)
        assert response.status_code == 401
        response = client.get(GROUPS, headers=admin)
        assert response.status_code == 401, "not even an administrator's credential"
        response = client.post(GROUPS, json=group_body("x"))
        assert response.status_code == 401


class TestCreateAndRead:
    def test_create_with_members(self, client, scim, users, bound_store, audit_events):
        response = client.post(GROUPS, headers=scim, json=group_body("data-science", [ALICE, BOB], external_id="ext-ds"))

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["id"] == body["displayName"] == "data-science"
        assert body["externalId"] == "ext-ds"
        assert member_ids(body) == [ALICE, BOB]
        assert body["meta"]["resourceType"] == "Group"
        assert response.headers["location"] == body["meta"]["location"]
        assert response.headers["content-type"].startswith("application/scim+json")
        assert owners(bound_store, "data-science") == {ALICE: "scim", BOB: "scim"}
        [event] = [e for e in audit_events if e["event"] == "group.create"]
        assert event["detail"]["members"] == [ALICE, BOB]

    def test_get_by_id_and_member_refs(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE])

        body = client.get(f"{GROUPS}/eng", headers=scim).json()

        [member] = body["members"]
        assert (member["value"], member["type"]) == (ALICE, "User")
        assert member["$ref"].endswith(f"/scim/v2/Users/{ALICE}")

    def test_an_external_id_is_not_an_id(self, client, scim):
        create_group(client, scim, "eng", external_id="ext-eng")

        assert_scim_error(client.get(f"{GROUPS}/ext-eng", headers=scim), 404)
        found = client.get(GROUPS, headers=scim, params={"filter": 'externalId eq "ext-eng"'}).json()
        assert [r["id"] for r in found["Resources"]] == ["eng"]

    def test_filter_by_display_name_and_paging(self, client, scim, users):
        for name in ("a-team", "b-team", "c-team"):
            create_group(client, scim, name, [ALICE])

        found = client.get(GROUPS, headers=scim, params={"filter": 'displayName eq "b-team"'}).json()
        assert (found["totalResults"], [r["id"] for r in found["Resources"]]) == (1, ["b-team"])

        page = client.get(GROUPS, headers=scim, params={"startIndex": 2, "count": 1}).json()
        assert (page["totalResults"], page["startIndex"], page["itemsPerPage"]) == (3, 2, 1)
        assert [r["id"] for r in page["Resources"]] == ["b-team"]

    def test_excluded_attributes_members(self, client, scim, users):
        """What Entra sends when it looks a group up before PATCHing it."""
        create_group(client, scim, "eng", [ALICE])

        found = client.get(GROUPS, headers=scim, params={"filter": 'displayName eq "eng"', "excludedAttributes": "members"}).json()
        assert "members" not in found["Resources"][0]
        response = client.get(f"{GROUPS}/eng", headers=scim, params={"excludedAttributes": "members"})
        assert "members" not in response.json()

    @pytest.mark.parametrize("expression", ['members eq "x"', 'displayName co "x"', 'displayName eq "a" or displayName eq "b"'])
    def test_unsupported_filters(self, client, scim, expression):
        assert_scim_error(client.get(GROUPS, headers=scim, params={"filter": expression}), 400, "invalidFilter")

    def test_name_and_external_id_are_unique(self, client, scim):
        create_group(client, scim, "eng", external_id="ext-1")

        assert_scim_error(client.post(GROUPS, headers=scim, json=group_body("eng")), 409, "uniqueness")
        assert_scim_error(client.post(GROUPS, headers=scim, json=group_body("ops", external_id="ext-1")), 409, "uniqueness")

    def test_an_existing_group_made_elsewhere_is_not_recreated(self, client, scim, bound_store):
        bound_store.populate_groups(["from-claims"])

        assert_scim_error(client.post(GROUPS, headers=scim, json=group_body("from-claims")), 409, "uniqueness")

    @pytest.mark.parametrize("name", ["a/b", "a?b", "a#b", "a%b", "", "  ", "x" * 256, "tab\tname"])
    def test_invalid_names(self, client, scim, name):
        assert_scim_error(client.post(GROUPS, headers=scim, json=group_body(name)), 400)

    def test_an_unknown_member_creates_nothing(self, client, scim, users, bound_store):
        response = client.post(GROUPS, headers=scim, json=group_body("eng", [ALICE, "nobody@example.com"]))

        assert_scim_error(response, 400, "invalidValue")
        assert bound_store.get_group_detail("eng") is None

    def test_nested_groups_are_refused(self, client, scim, users):
        create_group(client, scim, "inner")
        body = group_body("outer", None)
        body["members"] = [{"value": "inner", "type": "Group"}]

        assert_scim_error(client.post(GROUPS, headers=scim, json=body), 400, "invalidValue")

    def test_service_accounts_are_invisible(self, client, scim, users, bound_store):
        bound_store.create_user("svc", "unused-secret", "Service", is_service_account=True)
        create_group(client, scim, "eng", [ALICE])
        bound_store.add_user_to_group("svc", "eng", written_by="manual")

        response = client.get(f"{GROUPS}/eng", headers=scim)
        assert member_ids(response.json()) == [ALICE]
        assert_scim_error(client.post(GROUPS, headers=scim, json=group_body("ops", ["svc"])), 400, "invalidValue")
        # A PUT is a sync of what SCIM can see, so it never removes what it cannot.
        response = client.put(f"{GROUPS}/eng", headers=scim, json=group_body("eng", []))
        assert response.status_code == 200
        assert owners(bound_store, "eng") == {"svc": "manual"}


class TestEntraPatch:
    def test_add_members(self, client, scim, users, bound_store, audit_events):
        create_group(client, scim, "eng", [ALICE])

        response = client.patch(
            f"{GROUPS}/eng",
            headers=scim,
            json=patch_body({"op": "Add", "path": "members", "value": [{"value": BOB}, {"value": CAROL}]}),
        )

        assert response.status_code == 200, response.text
        assert member_ids(response.json()) == [ALICE, BOB, CAROL]
        assert owners(bound_store, "eng") == {ALICE: "scim", BOB: "scim", CAROL: "scim"}
        [event] = [e for e in audit_events if e["event"] == "group.members_changed"]
        assert event["detail"]["added"] == [BOB, CAROL]

    def test_remove_by_filtered_path(self, client, scim, users, bound_store):
        create_group(client, scim, "eng", [ALICE, BOB])

        response = client.patch(f"{GROUPS}/eng", headers=scim, json=patch_body({"op": "Remove", "path": f'members[value eq "{BOB}"]'}))

        assert response.status_code == 200, response.text
        assert member_ids(response.json()) == [ALICE]
        assert owners(bound_store, "eng") == {ALICE: "scim"}

    def test_remove_with_a_value_list(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE, BOB])

        response = client.patch(f"{GROUPS}/eng", headers=scim, json=patch_body({"op": "Remove", "path": "members", "value": [{"value": ALICE}]}))

        assert member_ids(response.json()) == [BOB]

    def test_remove_of_a_non_member_is_a_no_op(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE])

        response = client.patch(f"{GROUPS}/eng", headers=scim, json=patch_body({"op": "remove", "path": f'members[value eq "{BOB}"]'}))

        assert response.status_code == 200
        assert member_ids(response.json()) == [ALICE]

    def test_filtered_path_with_urn_and_whitespace(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE, BOB])
        path = f'{GROUP_SCHEMA}:members[ value eq "{ALICE}" ]'

        response = client.patch(f"{GROUPS}/eng", headers=scim, json=patch_body({"op": "remove", "path": path}))

        assert response.status_code == 200, response.text
        assert member_ids(response.json()) == [BOB]

    def test_operations_apply_in_order(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE])

        response = client.patch(
            f"{GROUPS}/eng",
            headers=scim,
            json=patch_body(
                {"op": "add", "path": "members", "value": [{"value": BOB}]},
                {"op": "remove", "path": f'members[value eq "{ALICE}"]'},
                {"op": "replace", "path": "externalId", "value": "ext-eng"},
            ),
        )

        body = response.json()
        assert (member_ids(body), body["externalId"]) == ([BOB], "ext-eng")

    def test_path_less_replace(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE])

        response = client.patch(
            f"{GROUPS}/eng",
            headers=scim,
            json=patch_body({"op": "replace", "value": {"id": "eng", "displayName": "eng", "externalId": "e1", "members": [{"value": CAROL}]}}),
        )

        assert response.status_code == 200, response.text
        assert (member_ids(response.json()), response.json()["externalId"]) == ([CAROL], "e1")

    @pytest.mark.parametrize(
        "operation,scim_type",
        [
            ({"op": "replace", "path": "description", "value": "x"}, "invalidPath"),
            ({"op": "add", "path": 'members[value eq "x"]', "value": [{"value": "x"}]}, "invalidPath"),
            ({"op": "remove", "path": 'members[display eq "x"]'}, "invalidPath"),
            ({"op": "remove", "path": 'members[value eq "x"].display'}, "invalidPath"),
            ({"op": "replace", "path": "displayName", "value": "renamed"}, "mutability"),
            ({"op": "move", "path": "members", "value": []}, "invalidSyntax"),
            ({"op": "remove"}, "noTarget"),
        ],
    )
    def test_unsupported_operations_apply_nothing(self, client, scim, users, operation, scim_type):
        create_group(client, scim, "eng", [ALICE])

        response = client.patch(
            f"{GROUPS}/eng",
            headers=scim,
            json=patch_body({"op": "add", "path": "members", "value": [{"value": BOB}]}, operation),
        )

        assert_scim_error(response, 400, scim_type)
        response = client.get(f"{GROUPS}/eng", headers=scim)
        assert member_ids(response.json()) == [ALICE], "the valid add in the same request must not land"

    def test_an_unknown_member_applies_nothing(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE])

        response = client.patch(
            f"{GROUPS}/eng",
            headers=scim,
            json=patch_body({"op": "add", "path": "members", "value": [{"value": BOB}, {"value": "ghost@example.com"}]}),
        )

        assert_scim_error(response, 400, "invalidValue")
        response = client.get(f"{GROUPS}/eng", headers=scim)
        assert member_ids(response.json()) == [ALICE]

    def test_unknown_group_is_404(self, client, scim):
        assert_scim_error(client.patch(f"{GROUPS}/nope", headers=scim, json=patch_body({"op": "add", "path": "members", "value": []})), 404)


class TestOktaPut:
    def test_put_replaces_membership(self, client, scim, users, bound_store):
        create_group(client, scim, "eng", [ALICE, BOB], external_id="okta-1")

        response = client.put(
            f"{GROUPS}/eng",
            headers=scim,
            json={
                "schemas": [GROUP_SCHEMA],
                "id": "eng",
                "displayName": "eng",
                "externalId": "okta-1",
                "members": [{"value": BOB, "display": "Bob"}, {"value": CAROL, "display": "Carol"}],
            },
        )

        assert response.status_code == 200, response.text
        assert member_ids(response.json()) == [BOB, CAROL]
        assert owners(bound_store, "eng") == {BOB: "scim", CAROL: "scim"}

    def test_put_cannot_rename(self, client, scim):
        create_group(client, scim, "eng")

        assert_scim_error(client.put(f"{GROUPS}/eng", headers=scim, json=group_body("renamed")), 400, "mutability")

    def test_put_without_members_leaves_membership_alone(self, client, scim, users):
        create_group(client, scim, "eng", [ALICE], external_id="e1")

        response = client.put(f"{GROUPS}/eng", headers=scim, json=group_body("eng", None))

        assert member_ids(response.json()) == [ALICE]
        assert "externalId" not in response.json(), "PUT replaces: an absent externalId is cleared"

    def test_put_external_id_conflict(self, client, scim):
        create_group(client, scim, "eng", external_id="e1")
        create_group(client, scim, "ops", external_id="e2")

        assert_scim_error(client.put(f"{GROUPS}/ops", headers=scim, json=group_body("ops", None, external_id="e1")), 409, "uniqueness")


class TestMembershipOwnership:
    """SCIM + manual + claim-derived memberships on one user, resolved through the real permission
    path; and what SCIM may and may not remove of the other two, inside a group SCIM owns."""

    @pytest.fixture
    def mixed(self, client, scim, users, bound_store, monkeypatch):
        from mlflow_oidc_auth.utils.permissions import flush_permission_cache

        login(ALICE, ["claims-grp"], monkeypatch)  # oidc:default membership, in a group the login created
        create_group(client, scim, "directory-grp", [ALICE])  # scim
        bound_store.populate_groups(["hand-grp"])
        bound_store.add_user_to_group(ALICE, "hand-grp")  # manual
        bound_store.create_group_experiment_permission("directory-grp", "1", "READ")
        bound_store.create_group_experiment_permission("hand-grp", "2", "EDIT")
        bound_store.create_group_experiment_permission("claims-grp", "3", "MANAGE")
        flush_permission_cache()
        return ALICE

    @pytest.fixture
    def shared(self, client, scim, users, bound_store, monkeypatch):
        """A SCIM-owned group that also holds a login-derived and a hand-made membership."""
        create_group(client, scim, "shared", [ALICE])
        login(BOB, ["shared"], monkeypatch)
        bound_store.add_user_to_group(CAROL, "shared")
        assert owners(bound_store, "shared") == {ALICE: "scim", BOB: "oidc:default", CAROL: "manual"}
        return "shared"

    def _permissions(self):
        from mlflow_oidc_auth.utils.permissions import effective_experiment_permission

        return {experiment: effective_experiment_permission(experiment, ALICE) for experiment in ("1", "2", "3")}

    def test_all_three_sources_resolve(self, bound_store, mixed):
        resolved = self._permissions()

        assert {k: (v.permission.name, v.kind) for k, v in resolved.items()} == {"1": ("READ", "group"), "2": ("EDIT", "group"), "3": ("MANAGE", "group")}
        from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

        with bound_store.ManagedSessionMaker() as session:
            rows = dict(
                session.query(SqlGroup.group_name, SqlUserGroup.managed_by)
                .join(SqlUserGroup, SqlUserGroup.group_id == SqlGroup.id)
                .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                .filter(SqlUser.username == ALICE)
                .all()
            )
        assert rows == {"directory-grp": "scim", "hand-grp": "manual", "claims-grp": "oidc:default", "mlflow-users": "oidc:default"}

    @pytest.mark.parametrize("mode", list(Enforcement))
    def test_a_login_keeps_the_directorys_group_in_every_mode(self, bound_store, mixed, monkeypatch, audit_events, mode):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", mode)

        login(ALICE, ["claims-grp"], monkeypatch)

        permissions = self._permissions()
        assert permissions["1"].permission.name == "READ", "the directory's grant survives"
        assert permissions["2"].kind != "group", "the unowned membership the claims no longer assert is revoked"
        assert permissions["3"].permission.name == "MANAGE"
        skipped = [e for e in audit_events if e["event"] == "user.ownership_conflict" and e["detail"]["group"] == "directory-grp"]
        assert [(e["status"], e["detail"]["operation"]) for e in skipped] == [("success", "membership.sync_kept")], "recorded in every mode, never as a denial"

    def test_scim_cannot_remove_a_login_derived_membership_under_enforce(self, client, scim, bound_store, shared, enforce, audit_events):
        response = client.patch(
            f"{GROUPS}/shared",
            headers=scim,
            json=patch_body({"op": "add", "path": "members", "value": [{"value": CAROL}]}, {"op": "remove", "path": f'members[value eq "{BOB}"]'}),
        )

        assert_scim_error(response, 409, "mutability")
        assert owners(bound_store, "shared") == {ALICE: "scim", BOB: "oidc:default", CAROL: "manual"}, "nothing applied"
        [event] = [e for e in audit_events if e["event"] == "user.ownership_conflict"]
        assert (event["status"], event["detail"]["owner"], event["detail"]["group"]) == ("denied", "oidc:default", "shared")

    def test_report_removes_it_and_records(self, client, scim, bound_store, shared, audit_events):
        response = client.patch(f"{GROUPS}/shared", headers=scim, json=patch_body({"op": "remove", "path": f'members[value eq "{BOB}"]'}))

        assert response.status_code == 200, response.text
        assert BOB not in owners(bound_store, "shared")
        assert [e["status"] for e in audit_events if e["event"] == "user.ownership_conflict"] == ["success"]

    @pytest.mark.parametrize("mode", list(Enforcement))
    def test_put_is_a_sync_that_never_removes_the_login_derived_row(self, client, scim, bound_store, shared, monkeypatch, audit_events, mode):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", mode)

        response = client.put(f"{GROUPS}/shared", headers=scim, json=group_body("shared", [ALICE]))

        assert response.status_code == 200, response.text
        assert member_ids(response.json()) == [ALICE, BOB], "the response shows the membership as it really is"
        assert owners(bound_store, "shared") == {ALICE: "scim", BOB: "oidc:default"}, "the manual row goes, the login's stays"
        [changed] = [e for e in audit_events if e["event"] == "group.members_changed"]
        assert changed["detail"]["removed"] == [CAROL]
        assert changed["detail"]["kept"] == [BOB]

    def test_scim_removes_a_manual_membership(self, client, scim, bound_store, shared, enforce):
        """Unowned memberships are revocable by any source — including every pre-#360 row."""
        response = client.patch(f"{GROUPS}/shared", headers=scim, json=patch_body({"op": "remove", "path": f'members[value eq "{CAROL}"]'}))

        assert response.status_code == 200, response.text
        assert CAROL not in owners(bound_store, "shared")

    def test_but_not_a_hand_made_administrators(self, client, scim, bound_store, admin, enforce):
        create_group(client, scim, "ops")
        bound_store.add_user_to_group(ADMIN, "ops")

        response = client.patch(f"{GROUPS}/ops", headers=scim, json=patch_body({"op": "remove", "path": f'members[value eq "{ADMIN}"]'}))

        assert_scim_error(response, 409, "mutability")
        assert owners(bound_store, "ops") == {ADMIN: "manual"}

    def test_a_put_keeping_a_hand_made_admins_membership_is_not_a_denial(self, client, scim, bound_store, admin, enforce, audit_events):
        """The PUT returns 200 and the row stays: that is a kept row, not a refused removal."""
        create_group(client, scim, "ops")
        bound_store.add_user_to_group(ADMIN, "ops")

        response = client.put(f"{GROUPS}/ops", headers=scim, json=group_body("ops", []))

        assert response.status_code == 200, response.text
        assert owners(bound_store, "ops") == {ADMIN: "manual"}
        [event] = [e for e in audit_events if e["event"] == "user.ownership_conflict"]
        assert (event["status"], event["detail"]["operation"], event["detail"]["owner"]) == ("success", "membership.sync_kept", "manual")
        assert not [e for e in audit_events if e["status"] == "denied"]

    def test_a_scim_add_takes_effect_without_waiting_for_the_cache(self, client, scim, users, bound_store):
        from mlflow_oidc_auth.utils.permissions import effective_experiment_permission

        create_group(client, scim, "late", [])
        bound_store.create_group_experiment_permission("late", "9", "EDIT")
        before = effective_experiment_permission("9", BOB)
        assert before.kind != "group"

        client.patch(f"{GROUPS}/late", headers=scim, json=patch_body({"op": "add", "path": "members", "value": [{"value": BOB}]}))

        assert effective_experiment_permission("9", BOB).permission.name == "EDIT"


class TestGroupOwnership:
    """SCIM writes only the groups it owns under ``enforce`` (deny by default). A login-derived or
    Kubernetes namespace group is the provider's; a hand-made group is the administrator's."""

    @pytest.fixture
    def login_group(self, users, monkeypatch, bound_store):
        login(ALICE, ["from-claims"], monkeypatch)
        assert bound_store.get_group_detail("from-claims")["managed_by"] == "oidc:default"
        return "from-claims"

    WRITES = {
        "add": lambda client, scim, group: client.patch(
            f"{GROUPS}/{group}", headers=scim, json=patch_body({"op": "add", "path": "members", "value": [{"value": BOB}]})
        ),
        "remove": lambda client, scim, group: client.patch(
            f"{GROUPS}/{group}", headers=scim, json=patch_body({"op": "remove", "path": f'members[value eq "{ALICE}"]'})
        ),
        "put": lambda client, scim, group: client.put(f"{GROUPS}/{group}", headers=scim, json=group_body(group, [BOB])),
        "external_id": lambda client, scim, group: client.patch(
            f"{GROUPS}/{group}", headers=scim, json=patch_body({"op": "add", "path": "externalId", "value": "adopt"})
        ),
        "delete": lambda client, scim, group: client.delete(f"{GROUPS}/{group}", headers=scim),
    }

    @pytest.mark.parametrize("write", sorted(WRITES))
    def test_refused_on_a_login_owned_group_under_enforce(self, client, scim, bound_store, login_group, enforce, audit_events, write):
        before = owners(bound_store, login_group)

        assert_scim_error(self.WRITES[write](client, scim, login_group), 409, "mutability")

        detail = bound_store.get_group_detail(login_group)
        assert detail is not None and detail["external_id"] is None
        assert owners(bound_store, login_group) == before
        [event] = [e for e in audit_events if e["event"] == "group.ownership_conflict"]
        assert (event["status"], event["resource_id"], event["detail"]["owner"]) == ("denied", login_group, "oidc:default")

    @pytest.mark.parametrize("write", sorted(WRITES))
    def test_permitted_and_recorded_under_report(self, client, scim, bound_store, login_group, audit_events, write):
        response = self.WRITES[write](client, scim, login_group)

        assert response.status_code in (200, 204), response.text
        [event] = [e for e in audit_events if e["event"] == "group.ownership_conflict"]
        assert (event["status"], event["detail"]["permitted"]) == ("success", True)

    def test_silent_under_off(self, client, scim, login_group, monkeypatch, audit_events):
        monkeypatch.setattr(config, "MANAGED_BY_ENFORCEMENT", Enforcement.OFF)

        response = self.WRITES["add"](client, scim, login_group)
        assert response.status_code == 200
        assert not [e for e in audit_events if e["event"] == "group.ownership_conflict"]

    def test_a_hand_made_group_is_refused_too(self, client, scim, users, bound_store, enforce):
        bound_store.populate_groups(["hand-made"])

        assert_scim_error(self.WRITES["add"](client, scim, "hand-made"), 409, "mutability")
        assert owners(bound_store, "hand-made") == {}

    def test_an_operator_can_hand_an_existing_group_to_the_directory(self, client, scim, users, bound_store, enforce, tmp_path):
        """The break glass for groups: adopting a pre-existing group under ``enforce`` is an operator
        action with a journal, not something SCIM can do by itself."""
        from click.testing import CliRunner

        from mlflow_oidc_auth.db.cli import commands

        bound_store.populate_groups(["legacy-team"])
        assert_scim_error(self.WRITES["add"](client, scim, "legacy-team"), 409, "mutability")
        url, journal = str(bound_store.engine.url), str(tmp_path / "groups.json")

        dry = CliRunner().invoke(commands, ["reconcile-ownership", "--url", url, "--groups", "--group", "legacy-team", "--set-owner", "scim"])
        assert dry.exit_code == 0, dry.output
        assert "group legacy-team: manual -> scim" in dry.output
        assert bound_store.get_group_detail("legacy-team")["managed_by"] == "manual"

        applied = CliRunner().invoke(
            commands, ["reconcile-ownership", "--url", url, "--groups", "--group", "legacy-team", "--set-owner", "scim", "--apply", "--journal", journal]
        )
        assert applied.exit_code == 0, applied.output
        response = self.WRITES["add"](client, scim, "legacy-team")
        assert response.status_code == 200
        assert bound_store.get_user_detail(ALICE)["managed_by"] == "scim", "user rows untouched"

        restored = CliRunner().invoke(commands, ["restore-ownership", "--url", url, "--journal", journal, "--apply"])
        assert restored.exit_code == 0, restored.output
        assert bound_store.get_group_detail("legacy-team")["managed_by"] == "manual"

    def test_a_namespace_group_is_the_clusters(self, client, scim, users, bound_store, enforce):
        from unittest.mock import MagicMock
        from types import SimpleNamespace

        from mlflow_oidc_auth.kubernetes import ServiceAccount
        from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware

        account = ServiceAccount(namespace="ml", name="trainer")
        AuthMiddleware(app=MagicMock())._provision_service_account(account, SimpleNamespace(id="cluster"))
        assert bound_store.get_group_detail(account.group)["managed_by"] == "oidc:cluster"

        assert_scim_error(self.WRITES["add"](client, scim, account.group), 409, "mutability")
        assert_scim_error(client.delete(f"{GROUPS}/{account.group}", headers=scim), 409, "mutability")

    def test_a_scim_owned_group_is_fully_writable_under_enforce(self, client, scim, users, bound_store, enforce, audit_events):
        create_group(client, scim, "mine", [ALICE])
        assert bound_store.get_group_detail("mine")["managed_by"] == "scim"

        for write in ("add", "remove", "external_id", "put"):
            response = self.WRITES[write](client, scim, "mine")
            assert response.status_code == 200, (write, response.text)
        response = self.WRITES["delete"](client, scim, "mine")
        assert response.status_code == 204
        assert not [e for e in audit_events if e["event"].endswith("ownership_conflict")]

    def test_any_user_may_be_added_to_a_scim_owned_group(self, client, scim, users, bound_store, enforce, monkeypatch):
        """Including one a login owns the membership rows of elsewhere: adding is never a cross-source write."""
        login(CAROL, [], monkeypatch)
        create_group(client, scim, "mine")

        response = self.WRITES["add"](client, scim, "mine")
        assert response.status_code == 200
        response = client.patch(f"{GROUPS}/mine", headers=scim, json=patch_body({"op": "add", "path": "members", "value": [{"value": CAROL}]}))
        assert member_ids(response.json()) == [BOB, CAROL]


class TestDelete:
    def test_delete_removes_the_group_its_memberships_and_its_grants(self, client, scim, users, bound_store, audit_events):
        create_group(client, scim, "eng", [ALICE, BOB])
        bound_store.create_group_experiment_permission("eng", "5", "EDIT")

        response = client.delete(f"{GROUPS}/eng", headers=scim)

        assert response.status_code == 204
        assert bound_store.get_group_detail("eng") is None
        assert bound_store.get_groups_for_user(ALICE) == []
        from mlflow_oidc_auth.utils.permissions import effective_experiment_permission

        assert effective_experiment_permission("5", ALICE).kind != "group"
        [event] = [e for e in audit_events if e["event"] == "group.delete"]
        assert event["detail"]["members_removed"] == [ALICE, BOB]
        assert event["detail"]["grants_removed"] == {"experiment_group_permissions": 1}, "the grants cannot be rebuilt from anything else"

    def test_unknown_group_is_404(self, client, scim):
        assert_scim_error(client.delete(f"{GROUPS}/nope", headers=scim), 404)

    @pytest.mark.parametrize("other_owner", ["manual", "oidc:default"])
    def test_refused_under_enforce_when_another_source_has_members(self, client, scim, users, bound_store, enforce, audit_events, other_owner):
        create_group(client, scim, "eng", [ALICE])
        bound_store.add_user_to_group(BOB, "eng", written_by=other_owner)

        assert_scim_error(client.delete(f"{GROUPS}/eng", headers=scim), 409, "mutability")

        assert owners(bound_store, "eng") == {ALICE: "scim", BOB: other_owner}
        [event] = [e for e in audit_events if e["event"] == "user.ownership_conflict"]
        assert (event["status"], event["detail"]["operation"], event["detail"]["owner"]) == ("denied", "group.delete", other_owner)
        assert not [e for e in audit_events if e["event"] == "group.delete"]

    def test_report_deletes_and_records(self, client, scim, users, bound_store, audit_events):
        create_group(client, scim, "eng", [ALICE])
        bound_store.add_user_to_group(BOB, "eng")

        response = client.delete(f"{GROUPS}/eng", headers=scim)
        assert response.status_code == 204

        assert bound_store.get_group_detail("eng") is None
        [event] = [e for e in audit_events if e["event"] == "user.ownership_conflict"]
        assert (event["status"], event["detail"]["operation"]) == ("success", "group.delete")

    def test_every_request_is_audited(self, client, scim, audit_events):
        create_group(client, scim, "eng")
        client.delete(f"{GROUPS}/eng", headers=scim)

        requests = [e for e in audit_events if e["event"] == "scim.request"]
        assert [(e["detail"]["method"], e["detail"]["status"]) for e in requests] == [("POST", 201), ("DELETE", 204)]
