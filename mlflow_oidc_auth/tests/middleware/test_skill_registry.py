"""Per-skill permissions on MLflow's skill registry (MLflow 3.18+).

These tests serve MLflow's own ``skill_registry_router`` over a real MLflow tracking store, mounted
the way ``app.py`` mounts it, behind the production middleware stack, a real auth store and the
real permission resolution. Nothing here is a stand-in for MLflow: what a test sees a caller get is
what MLflow's handler returned to them.
"""

from types import SimpleNamespace
from typing import Dict

import pytest

pytest.importorskip("mlflow.server.skill_registry_api", reason="MLflow's skill registry arrived in 3.18")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import mlflow_oidc_auth.store as store_module  # noqa: E402
from mlflow_oidc_auth.config import config  # noqa: E402
from mlflow_oidc_auth.middleware import skill_registry  # noqa: E402
from mlflow_oidc_auth.middleware.skill_registry import (  # noqa: E402
    BULK_REGISTER,
    CREATE,
    DELETE_SKILL,
    MANAGE,
    READ,
    REGISTER,
    SEARCH,
    UPDATE,
    UPDATE_VERSION,
    SkillRoute,
    resolve_skill_route,
)

ADMIN = "admin@example.com"
ALICE = "alice@example.com"
BOB = "bob@example.com"
CAROL = "carol@example.com"
# Not credentials: only ever seeded into a tmp_path database.
PASSWORDS = {ADMIN: "skill-admin-pw", ALICE: "skill-alice-pw", BOB: "skill-bob-pw", CAROL: "skill-carol-pw"}

API = "/api/3.0/mlflow/skills"
AJAX = "/ajax-api/3.0/mlflow/skills"
PERMS = "/api/2.0/mlflow/permissions/skills"
USERS = "/api/2.0/mlflow/permissions/users"
GROUPS = "/api/2.0/mlflow/permissions/groups"
REMOTE = {"source_type": "git", "source": "https://git.example.com/skills.git", "ref": "main", "digest": "a" * 64}


# ---------------------------------------------------------------------------
# Route resolution follows MLflow's own router
# ---------------------------------------------------------------------------


class TestRouteResolution:
    @pytest.mark.parametrize(
        "method,suffix,expected",
        [
            ("POST", "", SkillRoute(CREATE)),
            ("GET", "", SkillRoute(SEARCH)),
            ("POST", "/bulk-register", SkillRoute(BULK_REGISTER)),
            ("GET", "/reviewer", SkillRoute(READ, "", "reviewer")),
            ("PATCH", "/reviewer", SkillRoute(UPDATE, "", "reviewer")),
            ("DELETE", "/reviewer", SkillRoute(DELETE_SKILL, "", "reviewer")),
            ("GET", "/@acme/reviewer", SkillRoute(READ, "acme", "reviewer")),
            ("PATCH", "/@acme/reviewer", SkillRoute(UPDATE, "acme", "reviewer")),
            ("DELETE", "/@acme/reviewer", SkillRoute(DELETE_SKILL, "acme", "reviewer")),
            ("POST", "/reviewer/tags", SkillRoute(UPDATE, "", "reviewer")),
            ("DELETE", "/reviewer/tags/team", SkillRoute(UPDATE, "", "reviewer")),
            ("DELETE", "/@acme/reviewer/tags/a/b", SkillRoute(UPDATE, "acme", "reviewer")),
            ("POST", "/reviewer/aliases", SkillRoute(UPDATE, "", "reviewer")),
            ("GET", "/reviewer/aliases/prod", SkillRoute(READ, "", "reviewer")),
            ("DELETE", "/reviewer/aliases/prod", SkillRoute(MANAGE, "", "reviewer")),
            ("DELETE", "/@acme/reviewer/aliases/prod", SkillRoute(MANAGE, "acme", "reviewer")),
            ("POST", "/reviewer/versions", SkillRoute(REGISTER, "", "reviewer")),
            ("POST", "/@acme/reviewer/versions", SkillRoute(REGISTER, "acme", "reviewer")),
            ("GET", "/reviewer/versions", SkillRoute(READ, "", "reviewer")),
            ("GET", "/reviewer/versions/1", SkillRoute(READ, "", "reviewer")),
            ("PATCH", "/reviewer/versions/1", SkillRoute(UPDATE_VERSION, "", "reviewer")),
            ("PATCH", "/@acme/reviewer/versions/1", SkillRoute(UPDATE_VERSION, "acme", "reviewer")),
            ("DELETE", "/reviewer/versions/1", SkillRoute(MANAGE, "", "reviewer")),
            ("POST", "/reviewer/versions/1/tags", SkillRoute(UPDATE, "", "reviewer")),
            ("DELETE", "/reviewer/versions/1/tags/k", SkillRoute(MANAGE, "", "reviewer")),
        ],
    )
    def test_each_route_resolves_to_its_operation_and_skill(self, method, suffix, expected):
        assert resolve_skill_route(API + suffix, method) == expected
        assert resolve_skill_route(AJAX + suffix, method) == expected

    def test_every_route_mlflow_serves_has_an_operation(self):
        """A handler MLflow adds must be mapped before it is served: an unmapped one is denied."""
        from mlflow.server.skill_registry_api import skill_registry_router

        names = {route.endpoint.__name__ for route in skill_registry_router.routes}
        assert names == set(skill_registry._ENDPOINT_OPERATIONS)

    def test_a_route_without_an_operation_is_denied(self, monkeypatch):
        operations = dict(skill_registry._ENDPOINT_OPERATIONS)
        del operations["get_skill"]
        monkeypatch.setattr(skill_registry, "_ENDPOINT_OPERATIONS", operations)

        assert resolve_skill_route(API + "/reviewer", "GET") is None

    @pytest.mark.parametrize(
        "method,suffix",
        [
            ("GET", "/Reviewer"),  # MLflow stores lowercase names only
            ("GET", "/@acme"),  # an organization names no skill
            ("GET", "/@Acme/reviewer"),
            ("GET", "/@acme/reviewer/extra/segment"),
            ("HEAD", "/reviewer"),  # MLflow's router serves no HEAD
            ("PUT", "/reviewer"),
            ("DELETE", ""),
            ("GET", "/"),
        ],
    )
    def test_anything_else_resolves_to_nothing(self, method, suffix):
        assert resolve_skill_route(API + suffix, method) is None

    def test_a_path_merely_starting_with_the_prefix_is_not_the_registry(self):
        assert resolve_skill_route(API + "-other", "GET") is None
        assert skill_registry.is_skill_registry_path(API + "-other")  # still routed to the validator, which denies

    def test_static_prefix(self, monkeypatch):
        from mlflow.server.handlers import STATIC_PREFIX_ENV_VAR

        monkeypatch.setenv(STATIC_PREFIX_ENV_VAR, "/mlflow")
        assert resolve_skill_route("/mlflow" + API + "/@acme/reviewer", "DELETE") == SkillRoute(DELETE_SKILL, "acme", "reviewer")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _auth_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.tests.token_helpers import set_known_token
    from mlflow_oidc_auth.utils import permissions, workspace_cache

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ADMIN, "Admin", is_admin=True)
    for user in (ALICE, BOB, CAROL):
        s.create_user(user, user.split("@")[0].title())
    s.populate_groups(["team"])
    s.set_user_groups(BOB, ["team"])
    for user, password in PASSWORDS.items():
        set_known_token(s, user, password)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    permissions._get_permission_cache().clear()
    workspace_cache.flush_workspace_cache()

    def restore():
        permissions._get_permission_cache().clear()
        workspace_cache.flush_workspace_cache()
        object.__setattr__(store_module.store, "_instance", previous)
        s.engine.dispose()

    return s, restore


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Workspaces enabled, and nothing granted by default."""
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
    s, restore = _auth_store(tmp_path, monkeypatch)
    yield s
    restore()


@pytest.fixture
def registry(tmp_path, monkeypatch, store):
    """MLflow's own workspace-aware tracking store on a fresh database."""
    import mlflow.server.handlers as handlers
    from mlflow.store.tracking.sqlalchemy_workspace_store import WorkspaceAwareSqlAlchemyStore

    monkeypatch.setenv("MLFLOW_ENABLE_WORKSPACES", "true")
    tracking = WorkspaceAwareSqlAlchemyStore(f"sqlite:///{tmp_path / 'mlflow.db'}", str(tmp_path / "artifacts"))
    monkeypatch.setattr(handlers, "_get_tracking_store", lambda *a, **k: tracking)
    monkeypatch.setattr("mlflow_oidc_auth.utils.data_fetching._get_tracking_store", lambda: tracking)
    yield tracking
    tracking.engine.dispose()


def _clients(monkeypatch):
    from mlflow.server.skill_registry_api import skill_registry_router

    from mlflow_oidc_auth.app import add_middleware_stack
    from mlflow_oidc_auth.exceptions import register_exception_handlers
    from mlflow_oidc_auth.routers.skill_permissions import group_skill_permissions_router, skill_permissions_router, user_skill_permissions_router
    from mlflow_oidc_auth.tests.scim.conftest import basic

    # MLflow resolves the header to a workspace (default when absent); no workspace store here.
    monkeypatch.setattr(
        "mlflow.server.workspace_helpers.resolve_workspace_for_request_if_enabled",
        lambda path, header: SimpleNamespace(name=(header or "").strip() or "default"),
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(skill_registry_router, prefix=API)
    app.include_router(skill_registry_router, prefix=AJAX)
    app.include_router(skill_permissions_router)
    app.include_router(user_skill_permissions_router)
    app.include_router(group_skill_permissions_router)
    add_middleware_stack(app)
    users = (("admin", ADMIN), ("alice", ALICE), ("bob", BOB), ("carol", CAROL))
    clients = {name: TestClient(app, headers=basic(user, PASSWORDS[user])) for name, user in users}
    return SimpleNamespace(anonymous=TestClient(app), **clients)


@pytest.fixture
def api(store, registry, monkeypatch):
    return _clients(monkeypatch)


def ws(name: str) -> Dict[str, str]:
    return {"X-MLFLOW-WORKSPACE": name}


A = ws("team-a")


def _clear_cache():
    from mlflow_oidc_auth.utils import permissions, workspace_cache

    permissions._get_permission_cache().clear()
    workspace_cache.flush_workspace_cache()


def _grants(store):
    from mlflow_oidc_auth.db.models import SqlSkillPermission, SqlUser

    with store.ManagedSessionMaker() as session:
        rows = session.query(SqlUser.username, SqlSkillPermission.name, SqlSkillPermission.workspace, SqlSkillPermission.permission)
        return sorted(tuple(row) for row in rows.join(SqlUser, SqlUser.id == SqlSkillPermission.user_id).all())


def _names(response):
    assert response.status_code == 200, response.text
    return [(s["organization"], s["name"]) for s in response.json()["skills"]]


@pytest.fixture
def members(store):
    """In team-a: Alice manages, Bob (and his group) reads, Carol holds nothing."""
    store.create_workspace_permission("team-a", ALICE, "MANAGE")
    store.create_workspace_permission("team-a", BOB, "READ")
    _clear_cache()


@pytest.fixture
def reviewer(api, members):
    """Alice's skill ``reviewer`` in team-a, with one version."""
    assert api.alice.post(API, json={"name": "reviewer"}, headers=A).status_code == 200
    response = api.alice.post(f"{API}/reviewer/versions", json=REMOTE, headers=A)
    assert response.status_code == 200, response.text
    _clear_cache()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestAuthentication:
    @pytest.mark.parametrize("method,suffix", [("GET", ""), ("POST", ""), ("GET", "/reviewer"), ("DELETE", "/reviewer"), ("POST", "/bulk-register")])
    def test_an_unauthenticated_request_is_refused(self, api, method, suffix):
        assert api.anonymous.request(method, API + suffix, headers=A).status_code == 401
        assert api.anonymous.request(method, AJAX + suffix, headers=A).status_code == 401


# ---------------------------------------------------------------------------
# Creation and the creator grant
# ---------------------------------------------------------------------------


class TestCreate:
    def test_manage_on_the_workspace_creates_and_the_creator_gets_manage_there(self, api, store, members, registry):
        response = api.alice.post(API, json={"name": "reviewer", "organization": "acme"}, headers=A)

        assert response.status_code == 200, response.text
        assert response.json()["created_by"] == ALICE
        assert _grants(store) == [(ALICE, "@acme/reviewer", "team-a", "MANAGE")]

    @pytest.mark.parametrize("permission", ["READ", "USE", "EDIT"])
    def test_less_than_manage_on_the_workspace_cannot_create(self, api, store, members, permission):
        store.update_workspace_permission("team-a", BOB, permission)
        _clear_cache()

        assert api.bob.post(API, json={"name": "reviewer"}, headers=A).status_code == 403
        assert _names(api.admin.get(API, headers=A)) == []
        assert _grants(store) == []

    def test_a_non_member_cannot_create(self, api, store, members):
        assert api.carol.post(API, json={"name": "reviewer"}, headers=A).status_code == 403
        assert api.alice.post(API, json={"name": "reviewer"}, headers=ws("team-b")).status_code == 403
        assert _grants(store) == []

    def test_no_workspace_named_is_judged_against_default(self, api, store, members):
        assert api.alice.post(API, json={"name": "reviewer"}).status_code == 403
        store.create_workspace_permission("default", ALICE, "MANAGE")
        _clear_cache()

        assert api.alice.post(API, json={"name": "reviewer"}).status_code == 200
        assert _grants(store) == [(ALICE, "reviewer", "default", "MANAGE")]

    @pytest.mark.parametrize("body", [{"name": "Not Valid"}, {"name": "ok", "organization": "Not/Valid"}, {"organization": "acme"}, ["reviewer"], {"name": 7}])
    def test_a_body_naming_no_storable_skill_is_refused(self, api, members, body):
        assert api.alice.post(API, json=body, headers=A).status_code == 403

    def test_an_existing_denying_grant_is_not_overridden_by_creating_the_skill(self, api, store, members):
        """A grant can be written ahead of its skill; creating it must not turn READ into MANAGE."""
        store.create_workspace_permission("team-a", CAROL, "MANAGE")
        from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        token = set_auth_context(AuthContext(username=ADMIN, is_admin=True, workspace="team-a"))
        try:
            store.create_skill_permission("reviewer", CAROL, "NO_PERMISSIONS")
        finally:
            clear_auth_context(token)
        _clear_cache()

        assert api.carol.post(API, json={"name": "reviewer"}, headers=A).status_code == 403
        assert _grants(store) == [(CAROL, "reviewer", "team-a", "NO_PERMISSIONS")]

    def test_no_grant_when_mlflow_refuses_the_create(self, api, store, members, reviewer):
        store.create_workspace_permission("team-a", CAROL, "MANAGE")
        _clear_cache()

        response = api.carol.post(API, json={"name": "reviewer"}, headers=A)

        assert response.status_code >= 400
        assert _grants(store) == [(ALICE, "reviewer", "team-a", "MANAGE")]

    def test_grants_left_under_the_name_do_not_reach_the_new_skill(self, api, store, members):
        """A grant that outlived a skill (or was written ahead of one) is someone else's permission
        on a skill they have nothing to do with: creating the skill clears it."""
        from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        token = set_auth_context(AuthContext(username=ADMIN, is_admin=True, workspace="team-a"))
        try:
            store.create_skill_permission("reviewer", CAROL, "MANAGE")
            store.create_group_skill_permission("team", "reviewer", "EDIT")
        finally:
            clear_auth_context(token)
        _clear_cache()

        assert api.alice.post(API, json={"name": "reviewer"}, headers=A).status_code == 200
        _clear_cache()

        assert _grants(store) == [(ALICE, "reviewer", "team-a", "MANAGE")]
        assert api.carol.get(f"{API}/reviewer", headers=A).status_code == 403
        assert api.bob.post(f"{API}/reviewer/tags", json={"key": "k", "value": "v"}, headers=A).status_code == 403

    def test_an_admin_creates_without_a_grant(self, api, store, members):
        assert api.admin.post(API, json={"name": "reviewer"}, headers=A).status_code == 200
        assert _grants(store) == []


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


READS = ["/reviewer", "/reviewer/versions", "/reviewer/versions/1"]


class TestRead:
    @pytest.mark.parametrize("suffix", READS)
    def test_a_workspace_reader_reads(self, api, reviewer, suffix):
        assert api.bob.get(API + suffix, headers=A).status_code == 200
        assert api.bob.get(AJAX + suffix, headers=A).status_code == 200

    @pytest.mark.parametrize("suffix", READS)
    def test_a_non_member_is_refused(self, api, reviewer, suffix):
        assert api.carol.get(API + suffix, headers=A).status_code == 403
        assert api.carol.get(AJAX + suffix, headers=A).status_code == 403

    def test_a_skill_that_does_not_exist_is_refused_the_same_way(self, api, reviewer):
        """No existence oracle: a non-member cannot tell a missing skill from a hidden one."""
        assert api.carol.get(f"{API}/no-such-skill", headers=A).status_code == 403

    def test_a_grant_shares_one_skill_with_a_non_member(self, api, reviewer):
        assert api.alice.post(f"{USERS}/{CAROL}/skills/reviewer", json={"permission": "READ"}, headers=A).status_code == 201
        _clear_cache()

        assert api.carol.get(f"{API}/reviewer", headers=A).status_code == 200
        assert api.carol.post(f"{API}/reviewer/tags", json={"key": "k", "value": "v"}, headers=A).status_code == 403

    def test_a_group_grant_reaches_its_members(self, api, store, reviewer):
        store.delete_workspace_permission("team-a", BOB)
        _clear_cache()
        assert api.bob.get(f"{API}/reviewer", headers=A).status_code == 403

        assert api.alice.post(f"{GROUPS}/team/skills/reviewer", json={"permission": "READ"}, headers=A).status_code == 201
        _clear_cache()

        assert api.bob.get(f"{API}/reviewer", headers=A).status_code == 200

    def test_no_permissions_shuts_a_workspace_member_out(self, api, reviewer):
        assert api.alice.post(f"{USERS}/{BOB}/skills/reviewer", json={"permission": "NO_PERMISSIONS"}, headers=A).status_code == 201
        _clear_cache()

        assert api.bob.get(f"{API}/reviewer", headers=A).status_code == 403

    def test_a_grant_names_one_identity_not_its_organization_twin(self, api, store, reviewer):
        """``reviewer`` and ``@acme/reviewer`` are different skills; an organization grants nothing."""
        assert api.alice.post(API, json={"name": "reviewer", "organization": "acme"}, headers=A).status_code == 200
        assert api.alice.post(f"{USERS}/{CAROL}/skills/reviewer", json={"permission": "READ"}, headers=A).status_code == 201
        _clear_cache()

        assert api.carol.get(f"{API}/reviewer", headers=A).status_code == 200
        assert api.carol.get(f"{API}/@acme/reviewer", headers=A).status_code == 403

    def test_a_grant_in_one_workspace_does_not_reach_the_same_name_in_another(self, api, store, reviewer):
        store.create_workspace_permission("team-b", ALICE, "MANAGE")
        _clear_cache()
        assert api.alice.post(API, json={"name": "reviewer"}, headers=ws("team-b")).status_code == 200
        assert api.alice.post(f"{USERS}/{CAROL}/skills/reviewer", json={"permission": "READ"}, headers=A).status_code == 201
        _clear_cache()

        assert api.carol.get(f"{API}/reviewer", headers=A).status_code == 200
        assert api.carol.get(f"{API}/reviewer", headers=ws("team-b")).status_code == 403


# ---------------------------------------------------------------------------
# Search is scoped before MLflow paginates
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.fixture
    def three(self, api, members):
        for name in ("alpha", "beta", "gamma"):
            assert api.alice.post(API, json={"name": name}, headers=A).status_code == 200
        _clear_cache()

    def test_a_workspace_reader_sees_every_skill(self, api, three):
        assert _names(api.bob.get(API, headers=A)) == [("", "alpha"), ("", "beta"), ("", "gamma")]

    def test_a_non_member_sees_nothing(self, api, three):
        assert _names(api.carol.get(API, headers=A)) == []

    def test_a_non_member_sees_only_what_a_grant_shares(self, api, three):
        assert api.alice.post(f"{USERS}/{CAROL}/skills/beta", json={"permission": "READ"}, headers=A).status_code == 201
        _clear_cache()

        assert _names(api.carol.get(API, headers=A)) == [("", "beta")]
        assert _names(api.carol.get(AJAX, headers=A)) == [("", "beta")]

    def test_a_denying_grant_hides_one_skill_from_a_reader(self, api, three):
        assert api.alice.post(f"{USERS}/{BOB}/skills/beta", json={"permission": "NO_PERMISSIONS"}, headers=A).status_code == 201
        _clear_cache()

        assert _names(api.bob.get(API, headers=A)) == [("", "alpha"), ("", "gamma")]

    def test_pages_and_tokens_do_not_count_hidden_skills(self, api, three):
        """The scope is applied before pagination: a page is full of readable skills, and the
        token ends when they do — it never tells that hidden rows were skipped."""
        assert api.alice.post(f"{USERS}/{BOB}/skills/alpha", json={"permission": "NO_PERMISSIONS"}, headers=A).status_code == 201
        assert api.alice.post(f"{USERS}/{BOB}/skills/beta", json={"permission": "NO_PERMISSIONS"}, headers=A).status_code == 201
        _clear_cache()

        first = api.bob.get(API, params={"max_results": 1}, headers=A)

        assert _names(first) == [("", "gamma")]
        assert first.json()["next_page_token"] is None

    def test_the_caller_cannot_widen_the_scope_with_its_own_selector(self, api, three):
        response = api.carol.get(API, params={"include_skill_identities": ["alpha", "beta"]}, headers=A)

        assert _names(response) == []

    def test_search_does_not_cross_workspaces(self, api, store, three):
        store.create_workspace_permission("team-b", BOB, "READ")
        _clear_cache()

        assert _names(api.bob.get(API, headers=ws("team-b"))) == []

    def test_a_registry_that_ignored_the_scope_still_returns_only_readable_skills(self, api, three, monkeypatch):
        """Defence in depth: the response is re-checked item by item."""
        monkeypatch.setattr(skill_registry, "skill_search_scope", lambda username: (None, []))

        assert _names(api.carol.get(API, headers=A)) == []

    def test_an_admin_sees_everything(self, api, three):
        assert len(_names(api.admin.get(API, headers=A))) == 3


# ---------------------------------------------------------------------------
# Changing a skill
# ---------------------------------------------------------------------------


EDITS = [
    ("PATCH", "/reviewer", {"description": "d"}),
    ("POST", "/reviewer/tags", {"key": "k", "value": "v"}),
    ("DELETE", "/reviewer/tags/k", None),
    ("POST", "/reviewer/aliases", {"alias": "prod", "version": 1}),
    ("POST", "/reviewer/versions/1/tags", {"key": "k", "value": "v"}),
    ("PATCH", "/reviewer/versions/1", {"status": "deprecated"}),
    ("POST", "/reviewer/versions", REMOTE),
]

MANAGES = [
    ("DELETE", "/reviewer/versions/1/tags/k", None),
    ("DELETE", "/reviewer/aliases/prod", None),
    ("PATCH", "/reviewer/versions/1", {"status": "deleted"}),
    ("PATCH", "/reviewer/versions/1", {"status": "some-future-status"}),
    ("DELETE", "/reviewer/versions/1", None),
    ("DELETE", "/reviewer", None),
]


def _call(client, method, suffix, body):
    return client.request(method, API + suffix, json=body, headers=A)


class TestWrite:
    @pytest.mark.parametrize("method,suffix,body", EDITS + MANAGES)
    def test_a_reader_changes_nothing(self, api, reviewer, method, suffix, body):
        assert _call(api.bob, method, suffix, body).status_code == 403

    @pytest.mark.parametrize("method,suffix,body", EDITS + MANAGES)
    def test_a_non_member_changes_nothing(self, api, reviewer, method, suffix, body):
        assert _call(api.carol, method, suffix, body).status_code == 403

    @pytest.mark.parametrize("method,suffix,body", EDITS)
    def test_edit_is_enough_to_edit(self, api, reviewer, method, suffix, body):
        assert api.alice.post(f"{USERS}/{BOB}/skills/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 201
        _clear_cache()

        assert _call(api.bob, method, suffix, body).status_code != 403

    @pytest.mark.parametrize("method,suffix,body", MANAGES)
    def test_edit_is_not_enough_to_delete(self, api, reviewer, method, suffix, body):
        assert api.alice.post(f"{USERS}/{BOB}/skills/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 201
        _clear_cache()

        assert _call(api.bob, method, suffix, body).status_code == 403
        assert api.alice.get(f"{API}/reviewer/versions/1", headers=A).json()["status"] == "active"

    @pytest.mark.parametrize("method,suffix,body", MANAGES)
    def test_manage_deletes(self, api, reviewer, method, suffix, body):
        assert _call(api.alice, method, suffix, body).status_code != 403

    @pytest.mark.parametrize("content", [b"not json", b'["deleted"]', b'{"status": ["deleted"]}', b'{"status": "DELETED"}'])
    def test_a_status_body_that_cannot_be_judged_needs_manage(self, api, reviewer, content):
        assert api.alice.post(f"{USERS}/{BOB}/skills/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 201
        _clear_cache()

        response = api.bob.patch(f"{API}/reviewer/versions/1", content=content, headers={**A, "Content-Type": "application/json"})

        assert response.status_code == 403

    def test_the_change_is_the_one_mlflow_made(self, api, reviewer):
        assert api.alice.post(f"{API}/reviewer/tags", json={"key": "team", "value": "ml"}, headers=A).status_code == 200

        assert api.bob.get(f"{API}/reviewer", headers=A).json()["tags"] == {"team": "ml"}


# ---------------------------------------------------------------------------
# Registering versions
# ---------------------------------------------------------------------------


class TestRegister:
    def test_registering_a_new_skill_is_a_creation_and_grants_manage(self, api, store, members):
        response = api.alice.post(f"{API}/@acme/linter/versions", json=REMOTE, headers=A)

        assert response.status_code == 200, response.text
        assert _grants(store) == [(ALICE, "@acme/linter", "team-a", "MANAGE")]

    def test_edit_on_the_workspace_cannot_register_a_new_skill(self, api, store, members):
        store.update_workspace_permission("team-a", BOB, "EDIT")
        _clear_cache()

        assert api.bob.post(f"{API}/linter/versions", json=REMOTE, headers=A).status_code == 403
        assert _names(api.admin.get(API, headers=A)) == []

    def test_registering_on_an_existing_skill_grants_nothing_more(self, api, store, reviewer):
        assert api.alice.post(f"{USERS}/{BOB}/skills/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 201
        _clear_cache()

        assert api.bob.post(f"{API}/reviewer/versions", json=REMOTE, headers=A).status_code == 200
        assert _grants(store) == [(ALICE, "reviewer", "team-a", "MANAGE"), (BOB, "reviewer", "team-a", "EDIT")]

    def test_bulk_register_creates_and_grants_each_new_skill(self, api, store, members):
        body = {"organization": "acme", "skills": [{"name": "one", **REMOTE}, {"name": "two", **REMOTE}]}

        response = api.alice.post(f"{API}/bulk-register", json=body, headers=A)

        assert response.status_code == 200, response.text
        assert _grants(store) == [(ALICE, "@acme/one", "team-a", "MANAGE"), (ALICE, "@acme/two", "team-a", "MANAGE")]

    def test_bulk_register_is_all_or_nothing(self, api, store, reviewer):
        """Bob may edit ``reviewer`` but may not create: one target he cannot write refuses the batch."""
        assert api.alice.post(f"{USERS}/{BOB}/skills/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 201
        _clear_cache()
        body = {"skills": [{"name": "reviewer", **REMOTE}, {"name": "brand-new", **REMOTE}]}

        assert api.bob.post(f"{API}/bulk-register", json=body, headers=A).status_code == 403
        assert len(api.alice.get(f"{API}/reviewer/versions", headers=A).json()["skill_versions"]) == 1
        assert _names(api.admin.get(API, headers=A)) == [("", "reviewer")]

    @pytest.mark.parametrize("body", [{}, {"skills": []}, {"skills": "reviewer"}, {"skills": [{"name": "Bad Name"}]}, {"skills": [7]}, []])
    def test_a_bulk_body_naming_no_storable_skills_is_refused(self, api, members, body):
        assert api.alice.post(f"{API}/bulk-register", json=body, headers=A).status_code == 403


# ---------------------------------------------------------------------------
# Deleting a skill takes its grants with it
# ---------------------------------------------------------------------------


class TestDelete:
    def _share(self, api):
        assert api.alice.post(f"{USERS}/{CAROL}/skills/reviewer", json={"permission": "READ"}, headers=A).status_code == 201
        assert api.alice.post(f"{GROUPS}/team/skills/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 201

    @pytest.mark.parametrize("who", ["alice", "admin"])
    def test_the_grants_go_with_the_skill(self, api, store, reviewer, who):
        self._share(api)

        assert getattr(api, who).delete(f"{API}/reviewer", headers=A).status_code == 200

        assert _grants(store) == []
        assert store.list_group_skill_permissions("team") == []

    def test_a_skill_recreated_under_the_name_starts_clean(self, api, store, reviewer):
        self._share(api)
        assert api.alice.delete(f"{API}/reviewer", headers=A).status_code == 200
        assert api.alice.post(API, json={"name": "reviewer"}, headers=A).status_code == 200
        _clear_cache()

        assert api.carol.get(f"{API}/reviewer", headers=A).status_code == 403

    def test_a_refused_delete_keeps_the_grants(self, api, store, reviewer):
        self._share(api)

        assert api.bob.delete(f"{API}/reviewer", headers=A).status_code == 403
        assert (CAROL, "reviewer", "team-a", "READ") in _grants(store)


# ---------------------------------------------------------------------------
# The permission API
# ---------------------------------------------------------------------------


class TestPermissionApi:
    def test_only_a_manager_changes_grants(self, api, reviewer):
        for client in (api.bob, api.carol):
            assert client.post(f"{USERS}/{CAROL}/skills/reviewer", json={"permission": "MANAGE"}, headers=A).status_code == 403
            assert client.get(f"{PERMS}/reviewer/users", headers=A).status_code == 403
            assert client.post(f"{GROUPS}/team/skills/reviewer", json={"permission": "MANAGE"}, headers=A).status_code == 403

    def test_a_manager_grants_lists_changes_and_revokes(self, api, reviewer):
        assert api.alice.post(f"{USERS}/{CAROL}/skills/reviewer", json={"permission": "READ"}, headers=A).status_code == 201
        assert {(u["name"], u["permission"]) for u in api.alice.get(f"{PERMS}/reviewer/users", headers=A).json()} == {(ALICE, "MANAGE"), (CAROL, "READ")}
        assert api.alice.patch(f"{USERS}/{CAROL}/skills/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 200
        assert api.alice.get(f"{USERS}/{CAROL}/skills/reviewer", headers=A).json()["permission"] == "EDIT"
        assert api.alice.delete(f"{USERS}/{CAROL}/skills/reviewer", headers=A).status_code == 200
        _clear_cache()
        assert api.carol.get(f"{API}/reviewer", headers=A).status_code == 403

    def test_organization_keys_round_trip(self, api, members):
        assert api.alice.post(API, json={"name": "reviewer", "organization": "acme"}, headers=A).status_code == 200
        _clear_cache()

        assert api.alice.post(f"{GROUPS}/team/skills/@acme/reviewer", json={"permission": "EDIT"}, headers=A).status_code == 201
        assert [(g["name"], g["permission"]) for g in api.alice.get(f"{PERMS}/@acme/reviewer/groups", headers=A).json()] == [("team", "EDIT")]
        assert [s["name"] for s in api.alice.get(PERMS, headers=A).json()] == ["@acme/reviewer"]

    @pytest.mark.parametrize("key", ["*", "Reviewer", "@acme", "@/reviewer", "a/b"])
    def test_a_key_no_skill_can_have_is_refused_even_for_an_admin(self, api, members, store, key):
        assert api.admin.post(f"{USERS}/{CAROL}/skills/{key}", json={"permission": "READ"}, headers=A).status_code in (400, 404)
        assert _grants(store) == []

    def test_the_list_holds_only_skills_the_caller_manages(self, api, reviewer):
        assert [s["name"] for s in api.alice.get(PERMS, headers=A).json()] == ["reviewer"]
        assert api.bob.get(PERMS, headers=A).json() == []
        assert api.carol.get(PERMS, headers=A).json() == []

    def test_a_users_own_listing_shows_what_they_reach(self, api, reviewer):
        assert api.bob.get(f"{USERS}/{BOB}/skills", headers=A).json() == [{"name": "reviewer", "permission": "READ", "kind": "workspace"}]
        assert api.carol.get(f"{USERS}/{CAROL}/skills", headers=A).json() == []
        assert api.carol.get(f"{USERS}/{BOB}/skills", headers=A).json() == []


# ---------------------------------------------------------------------------
# Workspaces disabled: the global default decides, as for models and prompts
# ---------------------------------------------------------------------------


class TestWithoutWorkspaces:
    @pytest.fixture
    def flat(self, tmp_path, monkeypatch):
        import mlflow.server.handlers as handlers
        from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore as TrackingStore

        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        monkeypatch.setattr(config, "RESTRICT_RESOURCE_CREATION", False)
        monkeypatch.delenv("MLFLOW_ENABLE_WORKSPACES", raising=False)
        s, restore = _auth_store(tmp_path, monkeypatch)
        tracking = TrackingStore(f"sqlite:///{tmp_path / 'mlflow.db'}", str(tmp_path / "artifacts"))
        monkeypatch.setattr(handlers, "_get_tracking_store", lambda *a, **k: tracking)
        monkeypatch.setattr("mlflow_oidc_auth.utils.data_fetching._get_tracking_store", lambda: tracking)
        yield SimpleNamespace(store=s, **vars(_clients(monkeypatch)))
        tracking.engine.dispose()
        restore()

    def test_any_user_creates_and_owns_the_skill(self, flat):
        assert flat.alice.post(API, json={"name": "reviewer"}).status_code == 200

        assert [(u, k, p) for u, k, _, p in _grants(flat.store)] == [(ALICE, "reviewer", "MANAGE")]
        assert flat.alice.delete(f"{API}/reviewer").status_code == 200

    def test_without_a_grant_the_default_permission_decides(self, flat, monkeypatch):
        assert flat.alice.post(API, json={"name": "reviewer"}).status_code == 200
        _clear_cache()

        assert flat.bob.get(f"{API}/reviewer").status_code == 403
        assert _names(flat.bob.get(API)) == []
        assert flat.bob.post(f"{API}/reviewer/tags", json={"key": "k", "value": "v"}).status_code == 403

        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "READ")
        _clear_cache()

        assert flat.bob.get(f"{API}/reviewer").status_code == 200
        assert _names(flat.bob.get(API)) == [("", "reviewer")]
        assert flat.bob.post(f"{API}/reviewer/tags", json={"key": "k", "value": "v"}).status_code == 403
        assert flat.bob.delete(f"{API}/reviewer").status_code == 403

    def test_restricted_creation_leaves_creating_to_admins(self, flat, monkeypatch):
        """``RESTRICT_RESOURCE_CREATION`` admits creations through pattern grants; skills have none."""
        monkeypatch.setattr(config, "RESTRICT_RESOURCE_CREATION", True)

        assert flat.alice.post(API, json={"name": "reviewer"}).status_code == 403
        assert flat.alice.post(f"{API}/reviewer/versions", json=REMOTE).status_code == 403
        assert flat.admin.post(API, json={"name": "reviewer"}).status_code == 200
