"""The workspace group rules API (issue #418): real ``AuthMiddleware``, real store, real router.

The rules it pins:

* every endpoint is admin-only — a signed-in non-admin gets 403 on each, and an anonymous caller
  never reaches the router;
* every endpoint answers 404 while ``MLFLOW_ENABLE_WORKSPACES`` is off, admin or not;
* a rule cannot grant more than ``WORKSPACE_RULES_MAX_PERMISSION``, nor ``NO_PERMISSIONS``;
* a pattern must compile, contain ``(?P<ws>...)`` and be at most 256 characters;
* a preview writes nothing.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.exceptions import register_exception_handlers
from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.routers.workspace_rules import workspace_rules_router
from mlflow_oidc_auth.tests.scim.conftest import basic
from mlflow_oidc_auth.tests.token_helpers import set_known_token

ADMIN = "admin@example.com"
ALICE = "alice@example.com"
ADMIN_PASSWORD = "rules-api-admin"  # not a credential: only ever seeded into a tmp_path database
ALICE_PASSWORD = "rules-api-alice"  # likewise
RULES = "/api/3.0/mlflow/workspace-rules"
VALID = {"name": "tenants", "pattern": r"^team-(?P<ws>[a-z0-9-]+)$", "permission": "EDIT", "mode": "enforce"}

# Every endpoint, with a body valid for it: the 403 must come from the gate, not from validation.
ENDPOINTS = [
    ("get", RULES, None),
    ("post", RULES, VALID),
    ("post", f"{RULES}/preview", {"pattern": VALID["pattern"], "permission": "READ"}),
    ("get", f"{RULES}/1", None),
    ("patch", f"{RULES}/1", {"enabled": False}),
    ("delete", f"{RULES}/1", None),
    ("get", f"{RULES}/1/preview", None),
]


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow.server import handlers

    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", True)
    monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "EDIT")

    class _WorkspaceStore:
        def get_workspace(self, name):
            if name not in {"acme", "beta"}:
                raise MlflowException("not found", RESOURCE_DOES_NOT_EXIST)
            return SimpleNamespace(name=name)

    monkeypatch.setattr(handlers, "_get_workspace_store", lambda *a, **k: _WorkspaceStore())
    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ADMIN, "Admin", is_admin=True)
    s.create_user(ALICE, "Alice")
    set_known_token(s, ADMIN, ADMIN_PASSWORD)
    set_known_token(s, ALICE, ALICE_PASSWORD)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    yield s
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture
def app(store):
    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(workspace_rules_router)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    return application


@pytest.fixture
def admin(app):
    with TestClient(app, headers=basic(ADMIN, ADMIN_PASSWORD)) as c:
        yield c


@pytest.fixture
def alice(app):
    with TestClient(app, headers=basic(ALICE, ALICE_PASSWORD)) as c:
        yield c


def _call(client, method, path, body):
    return client.request(method.upper(), path, json=body) if body is not None else client.request(method.upper(), path)


def _grant_rows(store):
    from mlflow_oidc_auth.db.models import SqlWorkspaceGroupPermission

    with store.ManagedSessionMaker() as session:
        return session.query(SqlWorkspaceGroupPermission).count()


class TestAccess:
    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in ENDPOINTS])
    def test_non_admin_gets_403_on_every_endpoint(self, admin, alice, store, method, path, body):
        result = admin.post(RULES, json=VALID)
        assert result.status_code == 201, "a rule 1 exists, so a 404 cannot stand in for the 403"

        response = _call(alice, method, path, body)

        assert response.status_code == 403, response.text
        assert [r.name for r in store.list_workspace_group_rules()] == ["tenants"]
        assert store.get_workspace_group_rule(1).enabled is True

    def test_anonymous_is_refused(self, app):
        result = TestClient(app).get(RULES)
        assert result.status_code == 401

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in ENDPOINTS])
    def test_endpoints_404_when_workspaces_disabled(self, admin, alice, store, monkeypatch, method, path, body):
        result = admin.post(RULES, json=VALID)
        assert result.status_code == 201
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)

        result = _call(admin, method, path, body)
        assert result.status_code == 404
        result = _call(alice, method, path, body)
        assert result.status_code == 404, "the gate must answer before the admin check"
        assert [r.name for r in store.list_workspace_group_rules()] == ["tenants"]


class TestValidation:
    def test_permission_above_ceiling_rejected_400(self, admin, store, monkeypatch):
        response = admin.post(RULES, json={**VALID, "permission": "MANAGE"})
        assert response.status_code == 400
        assert "WORKSPACE_RULES_MAX_PERMISSION" in response.json()["detail"]

        monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "READ")
        result = admin.post(RULES, json={**VALID, "permission": "USE"})
        assert result.status_code == 400
        result = admin.post(f"{RULES}/preview", json={"pattern": VALID["pattern"], "permission": "USE"})
        assert result.status_code == 400
        assert store.list_workspace_group_rules() == []

        rule_id = admin.post(RULES, json={**VALID, "permission": "READ"}).json()["rule"]["id"]
        result = admin.patch(f"{RULES}/{rule_id}", json={"permission": "EDIT"})
        assert result.status_code == 400
        assert store.get_workspace_group_rule(rule_id).permission == "READ"

    def test_manage_is_allowed_only_when_the_ceiling_is_raised(self, admin, monkeypatch):
        monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "MANAGE")
        result = admin.post(RULES, json={**VALID, "permission": "MANAGE"})
        assert result.status_code == 201

    def test_no_permissions_rejected_400(self, admin, store):
        response = admin.post(RULES, json={**VALID, "permission": "NO_PERMISSIONS"})

        assert response.status_code == 400
        assert store.list_workspace_group_rules() == []

    def test_pattern_without_ws_group_rejected_400(self, admin, store):
        response = admin.post(RULES, json={**VALID, "pattern": r"^team-([a-z]+)$"})

        assert response.status_code == 400
        assert "(?P<ws>...)" in response.json()["detail"]
        assert store.list_workspace_group_rules() == []

    def test_invalid_regex_rejected_400(self, admin, store):
        response = admin.post(RULES, json={**VALID, "pattern": r"^team-(?P<ws>[a-z+$"})

        assert response.status_code == 400
        assert "not a valid regular expression" in response.json()["detail"]

    def test_pattern_over_256_chars_rejected(self, admin, store):
        pattern = "^(?P<ws>" + "a" * 250 + ")$"
        assert len(pattern) > 256

        response = admin.post(RULES, json={**VALID, "pattern": pattern})

        assert response.status_code == 400
        assert "256" in response.json()["detail"]
        result = admin.post(RULES, json={**VALID, "pattern": "^(?P<ws>" + "a" * 246 + ")$"})
        assert result.status_code == 201, "256 itself is allowed"

    def test_unknown_mode_and_unknown_field_rejected(self, admin):
        result = admin.post(RULES, json={**VALID, "mode": "yolo"})
        assert result.status_code == 400
        result = admin.post(RULES, json={**VALID, "is_admin": True})
        assert result.status_code == 422

    def test_blank_name_rejected(self, admin, store):
        result = admin.post(RULES, json={**VALID, "name": "   "})
        assert result.status_code == 422
        assert store.list_workspace_group_rules() == []
        rule_id = admin.post(RULES, json=VALID).json()["rule"]["id"]
        result = admin.patch(f"{RULES}/{rule_id}", json={"name": " "})
        assert result.status_code == 422
        result = admin.post(RULES, json={**VALID, "name": "  ops  "})
        assert result.json()["rule"]["name"] == "ops"

    def test_unknown_rule_is_404_before_validation(self, admin):
        result = admin.patch(f"{RULES}/999", json={"pattern": "no-ws-group"})
        assert result.status_code == 404

    def test_duplicate_name_is_409(self, admin):
        result = admin.post(RULES, json=VALID)
        assert result.status_code == 201
        result = admin.post(RULES, json=VALID)
        assert result.status_code == 409

    def test_unknown_rule_is_404(self, admin):
        result = admin.get(f"{RULES}/999")
        assert result.status_code == 404
        result = admin.patch(f"{RULES}/999", json={"enabled": False})
        assert result.status_code == 404
        result = admin.delete(f"{RULES}/999")
        assert result.status_code == 404


class TestPreview:
    def test_preview_writes_nothing(self, admin, store):
        store.populate_groups(["team-acme", "team-beta", "team-nowhere"])
        rule_id = admin.post(RULES, json={**VALID, "mode": "report"}).json()["rule"]["id"]

        saved = admin.get(f"{RULES}/{rule_id}/preview")
        unsaved = admin.post(f"{RULES}/preview", json={"pattern": VALID["pattern"], "permission": "READ"})

        assert saved.status_code == 200 and unsaved.status_code == 200
        assert _grant_rows(store) == 0
        assert [(c["action"], c["workspace"], c["applied"]) for c in saved.json()["changes"]] == [
            ("grant", "acme", False),
            ("grant", "beta", False),
            ("skip", "nowhere", False),
        ]
        assert [c["action"] for c in unsaved.json()["changes"]] == ["grant", "grant", "skip"]

    def test_unsaved_preview_is_shadowed_by_an_enforcing_rule(self, admin, store):
        store.populate_groups(["team-acme"])
        existing = admin.post(RULES, json=VALID).json()["rule"]["id"]

        [line] = admin.post(f"{RULES}/preview", json={"pattern": r"^team-(?P<ws>acme)$", "permission": "READ"}).json()["changes"]

        assert line["action"] == "shadowed" and line["reason"].startswith(f"rule {existing} ")


class TestEditPreview:
    def test_previewing_changes_to_a_saved_rule_keeps_its_id(self, admin, store):
        """Previewing an edit must not rank the rule after itself: its own grants show as update."""
        store.populate_groups(["team-acme"])
        rule_id = admin.post(RULES, json=VALID).json()["rule"]["id"]

        as_edit = admin.post(f"{RULES}/preview", json={"pattern": VALID["pattern"], "permission": "READ", "rule_id": rule_id}).json()["changes"]
        as_new = admin.post(f"{RULES}/preview", json={"pattern": VALID["pattern"], "permission": "READ"}).json()["changes"]

        assert [(c["action"], c["previous"], c["permission"], c["rule_id"]) for c in as_edit] == [("update", "EDIT", "READ", rule_id)]
        assert [c["action"] for c in as_new] == ["shadowed"]
        result = admin.post(f"{RULES}/preview", json={"pattern": VALID["pattern"], "permission": "READ", "rule_id": 999})
        assert result.status_code == 404


class TestList:
    def test_lists_rules_and_the_ceiling(self, admin, monkeypatch):
        admin.post(RULES, json=VALID)
        admin.post(RULES, json={**VALID, "name": "ops", "pattern": r"^ops-(?P<ws>.+)$", "permission": "READ", "mode": "report"})
        monkeypatch.setattr(config, "WORKSPACE_RULES_MAX_PERMISSION", "USE")

        body = admin.get(RULES).json()

        assert [(r["id"], r["name"], r["mode"], r["created_by"]) for r in body["rules"]] == [(1, "tenants", "enforce", ADMIN), (2, "ops", "report", ADMIN)]
        assert all(r["created_at"].endswith(("Z", "+00:00")) and r["updated_at"].endswith(("Z", "+00:00")) for r in body["rules"]), "timestamps must carry UTC"
        assert body["max_permission"] == "USE"
        assert body["allowed_permissions"] == ["READ", "USE"]
