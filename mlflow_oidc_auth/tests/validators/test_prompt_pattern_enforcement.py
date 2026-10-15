"""MLflow prompt calls are authorized with prompt permissions (#479).

A prompt is a registered model tagged ``mlflow.prompt.is_prompt = "true"``, so every prompt call
reaches the plugin as a registered-model or model-version request. Prompt patterns and model
patterns are kept apart (exact-name grants are shared), and the resolver follows the target's kind.
These tests use a real permission store; only MLflow's registry lookup is stubbed.
"""

from unittest.mock import patch

import pytest
from flask import Flask
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INTERNAL_ERROR, RESOURCE_DOES_NOT_EXIST

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.validators import registered_model as rm_validators

ALICE = "alice@example.com"
PROMPTS = {"greeting"}  # registered model names that are prompts
MODELS = {"churn"}


def _entity(name, prompt):
    """A real MLflow registry entity: its public ``tags`` hides the prompt tag, as MLflow returns it."""
    from mlflow.entities.model_registry import RegisteredModel, RegisteredModelTag

    tags = [RegisteredModelTag("mlflow.prompt.is_prompt", "true")] if prompt else []
    return RegisteredModel(name, tags=tags + [RegisteredModelTag("team", "a")])


class _Registry:
    """MLflow's model registry, reduced to what the kind lookup reads; it returns real entities."""

    def __init__(self, failing=False):
        self.failing = failing
        self.calls = []

    def get_registered_model(self, name):
        self.calls.append(name)
        if self.failing:
            raise MlflowException("registry down", INTERNAL_ERROR)
        if name in PROMPTS or name in MODELS:
            return _entity(name, name in PROMPTS)
        raise MlflowException(f"no model {name}", RESOURCE_DOES_NOT_EXIST)


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils import permissions, workspace_cache

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ALICE, "Alice")
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    permissions.flush_permission_cache()
    workspace_cache.flush_workspace_cache()
    yield s
    permissions.flush_permission_cache()
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


def _decide(validator, name, registry=None):
    """Run a registry validator for a request naming ``name``, with a fresh request memo."""
    registry = registry or _Registry()
    with (
        Flask(__name__).test_request_context(f"/api/2.0/mlflow/registered-models/get?name={name}"),
        patch("mlflow.server.handlers._get_model_registry_store", return_value=registry),
        patch.object(rm_validators, "get_model_names", return_value=[name]),
    ):
        return validator(ALICE)


VALIDATORS = {
    "read": rm_validators.validate_can_read_registered_model,
    "update": rm_validators.validate_can_update_registered_model,
    "delete": rm_validators.validate_can_delete_registered_model,
    "manage": rm_validators.validate_can_manage_registered_model,
    "model-version-artifact": rm_validators.validate_can_read_model_version_artifact,
}


@pytest.mark.parametrize("family", VALIDATORS)
def test_prompt_pattern_denial_beats_a_model_pattern_on_a_prompt(store, family):
    """A prompt-pattern NO_PERMISSIONS denies a prompt even when a model pattern grants MANAGE."""
    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    store.create_prompt_regex_permission("^greet", 1, "NO_PERMISSIONS", ALICE)
    assert _decide(VALIDATORS[family], "greeting") is False


@pytest.mark.parametrize("family", VALIDATORS)
def test_a_model_pattern_alone_gives_nothing_on_a_prompt(store, family):
    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    assert _decide(VALIDATORS[family], "greeting") is False


@pytest.mark.parametrize("family", VALIDATORS)
def test_a_prompt_pattern_grants_on_a_prompt(store, family):
    store.create_prompt_regex_permission("^greet", 1, "MANAGE", ALICE)
    assert _decide(VALIDATORS[family], "greeting") is True


def test_a_prompt_pattern_read_allows_reading_but_not_editing_a_prompt(store):
    store.create_prompt_regex_permission("^greet", 1, "READ", ALICE)
    assert _decide(VALIDATORS["read"], "greeting") is True
    assert _decide(VALIDATORS["update"], "greeting") is False


@pytest.mark.parametrize("family", VALIDATORS)
def test_a_model_pattern_still_governs_a_model_and_a_prompt_pattern_does_not(store, family):
    store.create_prompt_regex_permission(".*", 1, "MANAGE", ALICE)
    assert _decide(VALIDATORS[family], "churn") is False
    store.create_registered_model_regex_permission("^chu", 1, "MANAGE", ALICE)
    from mlflow_oidc_auth.utils import permissions

    permissions.flush_permission_cache()
    assert _decide(VALIDATORS[family], "churn") is True


def test_an_exact_grant_is_shared_by_both_kinds(store):
    """Exact-name grants live in one table for models and prompts, as before."""
    store.create_registered_model_permission("greeting", ALICE, "READ")
    assert _decide(VALIDATORS["read"], "greeting") is True


def test_kind_lookup_fails_closed(store):
    """A registry error while finding the model's kind denies; no grant set is guessed."""
    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    store.create_prompt_regex_permission(".*", 1, "MANAGE", ALICE)
    for validator in VALIDATORS.values():
        assert _decide(validator, "churn", _Registry(failing=True)) is False


def test_an_unknown_name_is_judged_as_a_model(store):
    """A name MLflow does not know is not a prompt; MLflow answers the request with its own 404."""
    store.create_registered_model_regex_permission("^new", 1, "READ", ALICE)
    assert _decide(VALIDATORS["read"], "new-model") is True


def test_the_kind_is_looked_up_once_per_name_per_request(store):
    store.create_prompt_regex_permission(".*", 1, "MANAGE", ALICE)
    registry = _Registry()
    with (
        Flask(__name__).test_request_context("/"),
        patch("mlflow.server.handlers._get_model_registry_store", return_value=registry),
        patch.object(rm_validators, "get_model_names", return_value=["greeting", "greeting"]),
    ):
        assert rm_validators.validate_can_update_registered_model(ALICE) is True
        assert rm_validators.validate_can_read_registered_model(ALICE) is True
    assert registry.calls == ["greeting"]


def test_a_copy_source_that_is_a_prompt_needs_read_by_prompt_grants(store):
    """CreateModelVersion reading ``models:/<prompt>/1`` checks the source with prompt grants."""
    from mlflow_oidc_auth.utils.prompt_kind import effective_registry_permission

    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    with (
        Flask(__name__).test_request_context("/"),
        patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry()),
    ):
        assert effective_registry_permission("greeting", ALICE).permission.can_read is False
        assert effective_registry_permission("churn", ALICE).permission.can_read is True


# ---------------------------------------------------------------------------
# Search filters: rows are judged by their own kind
# ---------------------------------------------------------------------------


def _search_ctx():
    from mlflow_oidc_auth.utils.grant_context import load_grant_context

    return load_grant_context(ALICE, bulk=True)


@pytest.mark.parametrize("shape", ["proto", "entity"])
def test_search_rows_of_registered_models_are_judged_by_their_kind(store, shape):
    """A search row's own kind decides, with no registry lookup.

    The first page is protos, which carry the prompt tag; top-up pages are MLflow entities, whose
    public ``tags`` hides it. Both must be read as MLflow does.
    """
    from mlflow_oidc_auth.hooks import after_request

    store.create_registered_model_regex_permission(".*", 1, "READ", ALICE)
    store.create_prompt_regex_permission("^greet", 1, "NO_PERMISSIONS", ALICE)
    prompt_row, model_row = _entity("greeting", True), _entity("churn", False)
    if shape == "proto":
        prompt_row, model_row = prompt_row.to_proto(), model_row.to_proto()
    registry = _Registry()
    with Flask(__name__).test_request_context("/"), patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        ctx = _search_ctx()
        assert after_request._can_read_registered_model_row(ctx, prompt_row) is False
        assert after_request._can_read_registered_model_row(ctx, model_row) is True
    assert registry.calls == []


def test_search_rows_of_prompt_versions_follow_their_prompt(store):
    """A model-version row of a prompt is judged as a prompt; its kind is looked up once per name."""
    from mlflow_oidc_auth.hooks import after_request

    store.create_registered_model_regex_permission(".*", 1, "READ", ALICE)
    registry = _Registry()
    with Flask(__name__).test_request_context("/"), patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        ctx = _search_ctx()
        for _version in range(3):
            assert after_request._can_read_registered_model(ctx, "greeting") is False
        assert after_request._can_read_registered_model(ctx, "churn") is True
    assert registry.calls == ["greeting", "churn"]


def test_search_rows_fail_closed_when_the_kind_is_unknown(store):
    from mlflow_oidc_auth.hooks import after_request

    store.create_registered_model_regex_permission(".*", 1, "READ", ALICE)
    store.create_prompt_regex_permission(".*", 1, "READ", ALICE)
    with Flask(__name__).test_request_context("/"), patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry(failing=True)):
        assert after_request._can_read_registered_model(_search_ctx(), "churn") is False


# ---------------------------------------------------------------------------
# Grant routes
# ---------------------------------------------------------------------------


GRANT_GATES = (
    ("check_user_prompt_manage_permission", "name"),
    ("check_prompt_manage_permission", "prompt_name"),
    ("check_group_prompt_manage_permission", "prompt_name"),
    ("check_registered_model_manage_permission", "name"),
    ("check_group_registered_model_manage_permission", "name"),
)


async def _gate_allows(gate_name, param, name):
    from fastapi import HTTPException

    from mlflow_oidc_auth import dependencies

    try:
        await getattr(dependencies, gate_name)(**{param: name}, current_username=ALICE, is_admin=False)
        return True
    except HTTPException as exc:
        assert exc.status_code == 403
        return False


@pytest.mark.parametrize("gate_name, param", GRANT_GATES, ids=[g for g, _ in GRANT_GATES])
async def test_every_grant_gate_judges_a_prompt_by_prompt_grants(store, gate_name, param):
    """Whichever grant route is used, a prompt is judged by prompt grants and a model by model grants.

    The registered-model and prompt grant routes write the same exact-name grant table, so a gate
    that judged by the route could grant on a target of the other kind (#479).
    """
    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    store.create_prompt_regex_permission("^greet", 1, "NO_PERMISSIONS", ALICE)
    with Flask(__name__).test_request_context("/"), patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry()):
        # A model pattern MANAGE never lets anyone manage grants on a prompt the prompt patterns deny.
        assert await _gate_allows(gate_name, param, "greeting") is False
        # ...and it still governs a registered model, through every route.
        assert await _gate_allows(gate_name, param, "churn") is True


@pytest.mark.parametrize("gate_name, param", GRANT_GATES, ids=[g for g, _ in GRANT_GATES])
async def test_a_prompt_pattern_never_lets_a_user_manage_a_models_grants(store, gate_name, param):
    store.create_prompt_regex_permission(".*", 1, "MANAGE", ALICE)
    with Flask(__name__).test_request_context("/"), patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry()):
        assert await _gate_allows(gate_name, param, "churn") is False
        assert await _gate_allows(gate_name, param, "greeting") is True


# ---------------------------------------------------------------------------
# Creating a prompt (RESTRICT_RESOURCE_CREATION)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tags, patterns, allowed",
    [
        # A prompt create is judged by prompt patterns...
        ([{"key": "mlflow.prompt.is_prompt", "value": "true"}], {"prompt": "EDIT"}, True),
        ([{"key": "mlflow.prompt.is_prompt", "value": "true"}], {"model": "EDIT"}, False),
        # ...and a model create by model patterns, as before.
        ([], {"model": "EDIT"}, True),
        ([], {"prompt": "EDIT"}, False),
    ],
    ids=["prompt-by-prompt-pattern", "prompt-not-by-model-pattern", "model-by-model-pattern", "model-not-by-prompt-pattern"],
)
def test_creating_a_prompt_is_judged_by_prompt_patterns(store, monkeypatch, tags, patterns, allowed):
    monkeypatch.setattr(config, "RESTRICT_RESOURCE_CREATION", True)
    if "prompt" in patterns:
        store.create_prompt_regex_permission("^new", 1, patterns["prompt"], ALICE)
    if "model" in patterns:
        store.create_registered_model_regex_permission("^new", 1, patterns["model"], ALICE)
    with (
        Flask(__name__).test_request_context("/api/2.0/mlflow/registered-models/create", method="POST", json={"name": "new-thing", "tags": tags}),
        patch.object(rm_validators, "get_model_names", return_value=["new-thing"]),
    ):
        assert rm_validators.validate_can_create_registered_model(ALICE) is allowed


# ---------------------------------------------------------------------------
# The kind tag cannot be changed by non-admins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["true", "false", "TRUE"])
@pytest.mark.parametrize(
    "validator",
    [rm_validators.validate_can_set_registered_model_tag, rm_validators.validate_can_delete_registered_model_tag],
    ids=["set-or-delete-model-tag", "delete-version-tag"],
)
def test_writing_the_kind_tag_is_refused_even_with_manage(store, validator, value):
    """``mlflow.prompt.is_prompt`` decides which grants apply, so it is never writable by a non-admin."""
    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    store.create_prompt_regex_permission(".*", 1, "MANAGE", ALICE)
    for body in ({"name": "churn", "key": "mlflow.prompt.is_prompt", "value": value}, {"name": "greeting", "key": "mlflow.prompt.is_prompt"}):
        with (
            Flask(__name__).test_request_context("/api/2.0/mlflow/registered-models/set-tag", method="POST", json=body),
            patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry()),
            patch.object(rm_validators, "get_model_names", return_value=[body["name"]]),
        ):
            assert validator(ALICE) is False


def test_the_kind_tag_cannot_hide_in_the_query_string(store):
    """Every request source is checked (#285): a harmless body key does not hide a kind-tag query key."""
    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    with (
        Flask(__name__).test_request_context(
            "/api/2.0/mlflow/registered-models/set-tag?key=mlflow.prompt.is_prompt", method="POST", json={"name": "churn", "key": "team", "value": "a"}
        ),
        patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry()),
        patch.object(rm_validators, "get_model_names", return_value=["churn"]),
    ):
        assert rm_validators.validate_can_set_registered_model_tag(ALICE) is False


def test_other_tags_still_need_only_update(store):
    store.create_registered_model_regex_permission(".*", 1, "EDIT", ALICE)
    with (
        Flask(__name__).test_request_context("/api/2.0/mlflow/registered-models/set-tag", method="POST", json={"name": "churn", "key": "team", "value": "a"}),
        patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry()),
        patch.object(rm_validators, "get_model_names", return_value=["churn"]),
    ):
        assert rm_validators.validate_can_set_registered_model_tag(ALICE) is True


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


def test_a_model_listing_judges_its_prompt_rows_by_prompt_grants(store):
    """Registry listings return prompts too; each row is judged by its own tags, without a lookup."""
    from mlflow_oidc_auth.utils.batch_permissions import batch_resolve_model_permissions, filter_manageable_models

    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    store.create_prompt_regex_permission("^greet", 1, "NO_PERMISSIONS", ALICE)
    rows = [_entity("greeting", True), _entity("churn", False)]  # as fetch_all_registered_models returns them
    registry = _Registry()
    with Flask(__name__).test_request_context("/"), patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        results = batch_resolve_model_permissions(ALICE, rows)
        assert results["greeting"].permission.name == "NO_PERMISSIONS"
        assert results["churn"].permission.can_manage
        assert [r.name for r in filter_manageable_models(ALICE, rows)] == ["churn"]
    assert registry.calls == []


@pytest.mark.parametrize("key", ["MLFLOW.PROMPT.IS_PROMPT", "Mlflow.Prompt.Is_Prompt", " mlflow.prompt.is_prompt ", "mlflow.prompt.is_prompt\t"])
def test_the_kind_tag_is_refused_in_any_spelling(store, key):
    """MySQL and SQL Server compare tag keys ignoring case: every spelling reaches the stored kind tag."""
    store.create_registered_model_regex_permission(".*", 1, "MANAGE", ALICE)
    store.create_prompt_regex_permission(".*", 1, "MANAGE", ALICE)
    with (
        Flask(__name__).test_request_context("/api/2.0/mlflow/registered-models/delete-tag", method="DELETE", json={"name": "greeting", "key": key}),
        patch("mlflow.server.handlers._get_model_registry_store", return_value=_Registry()),
        patch.object(rm_validators, "get_model_names", return_value=["greeting"]),
    ):
        assert rm_validators.validate_can_set_registered_model_tag(ALICE) is False
        assert rm_validators.validate_can_delete_registered_model_tag(ALICE) is False


# ---------------------------------------------------------------------------
# A new prompt starts with only its creator's grant
# ---------------------------------------------------------------------------


def _create_hook(name, tags, creator):
    import json

    from mlflow_oidc_auth.hooks import after_request

    response = Flask(__name__).response_class(response=json.dumps({"registered_model": {"name": name, "tags": tags}}), mimetype="application/json")
    with Flask(__name__).test_request_context("/"), patch.object(after_request, "get_fastapi_username", return_value=creator):
        after_request._set_can_manage_registered_model_permission(response)


def test_a_grant_planted_on_a_free_name_does_not_survive_a_prompt_created_there(store):
    """An exact grant on a name nobody has created yet is judged under model rules; it must not reach a prompt."""
    from mlflow_oidc_auth.utils import permissions

    victim = "victor@example.com"
    store.create_user(victim, "Victor")
    store.populate_groups(["crew"])
    store.create_registered_model_permission("team-secret", ALICE, "MANAGE")  # planted before the prompt exists
    store.create_group_model_permission("crew", "team-secret", "MANAGE")
    _create_hook("team-secret", [{"key": "mlflow.prompt.is_prompt", "value": "true"}], victim)
    permissions.flush_permission_cache()

    assert store.list_registered_model_permissions(ALICE) == []
    assert store.get_group_models("crew") == []
    assert [p.permission for p in store.list_registered_model_permissions(victim)] == ["MANAGE"]


def test_a_registered_model_keeps_grants_made_before_it_existed(store):
    """Pre-granting a model name is a common admin practice; only prompts start clean."""
    store.create_user("victor@example.com", "Victor")
    store.create_registered_model_permission("churn-v2", ALICE, "READ")
    _create_hook("churn-v2", [], "victor@example.com")
    assert [p.permission for p in store.list_registered_model_permissions(ALICE)] == ["READ"]
    assert [p.permission for p in store.list_registered_model_permissions("victor@example.com")] == ["MANAGE"]


def test_readable_registered_models_judge_prompts_by_prompt_grants(store):
    """``fetch_readable_registered_models`` gets real registry entities, whose ``tags`` hide the prompt tag."""
    from mlflow_oidc_auth.utils import data_fetching

    store.create_registered_model_regex_permission(".*", 1, "READ", ALICE)
    store.create_prompt_regex_permission("^greet", 1, "NO_PERMISSIONS", ALICE)
    rows = [_entity("greeting", True), _entity("churn", False)]
    with Flask(__name__).test_request_context("/"), patch.object(data_fetching, "fetch_all_registered_models", return_value=rows):
        assert [m.name for m in data_fetching.fetch_readable_registered_models(username=ALICE)] == ["churn"]


@pytest.mark.parametrize("key", ["MLFLOW.PROMPT.IS_PROMPT", " mlflow.prompt.is_prompt", "Mlflow.Prompt.Is_Prompt"])
def test_creating_a_model_with_a_kind_tag_lookalike_is_refused(store, monkeypatch, key):
    """MLflow's SQL filter would read the look-alike as the kind tag and the plugin would not; refuse it."""
    for restrict in (False, True):
        monkeypatch.setattr(config, "RESTRICT_RESOURCE_CREATION", restrict)
        with (
            Flask(__name__).test_request_context(
                "/api/2.0/mlflow/registered-models/create", method="POST", json={"name": "m", "tags": [{"key": key, "value": "true"}]}
            ),
            patch.object(rm_validators, "get_model_names", return_value=["m"]),
        ):
            assert rm_validators.validate_can_create_registered_model(ALICE) is False


def test_creating_a_prompt_with_the_exact_kind_tag_is_allowed(store, monkeypatch):
    """MLflow's own client creates a prompt with the exact tag; that stays possible."""
    monkeypatch.setattr(config, "RESTRICT_RESOURCE_CREATION", False)
    with (
        Flask(__name__).test_request_context(
            "/api/2.0/mlflow/registered-models/create", method="POST", json={"name": "p", "tags": [{"key": "mlflow.prompt.is_prompt", "value": "true"}]}
        ),
        patch.object(rm_validators, "get_model_names", return_value=["p"]),
    ):
        assert rm_validators.validate_can_create_registered_model(ALICE) is True


def test_the_kind_is_memoized_per_request_under_fastapi_too(store):
    """FastAPI routes and dependencies have no Flask request; the memo follows the request's AuthContext.

    Each name is looked up once within a request, and a new request starts a new memo.
    """
    from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
    from mlflow_oidc_auth.entities.auth_context import AuthContext
    from mlflow_oidc_auth.utils import prompt_kind

    registry = _Registry()
    with patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        token = set_auth_context(AuthContext(username=ALICE, is_admin=False))
        try:
            for _ in range(5):
                assert prompt_kind.is_prompt("greeting") is True
                assert prompt_kind.is_prompt("churn") is False
        finally:
            clear_auth_context(token)
        assert registry.calls == ["greeting", "churn"]

        # A new request (a new AuthContext) does not reuse the previous request's answers.
        token = set_auth_context(AuthContext(username=ALICE, is_admin=False))
        try:
            assert prompt_kind.is_prompt("greeting") is True
        finally:
            clear_auth_context(token)
        assert registry.calls == ["greeting", "churn", "greeting"]


def test_without_a_request_nothing_is_remembered(store):
    from mlflow_oidc_auth.utils import prompt_kind

    registry = _Registry()
    with patch("mlflow.server.handlers._get_model_registry_store", return_value=registry):
        prompt_kind.is_prompt("greeting")
        prompt_kind.is_prompt("greeting")
    assert registry.calls == ["greeting", "greeting"]


# ---------------------------------------------------------------------------
# Nothing new resolves a registered-model name without its kind
# ---------------------------------------------------------------------------

# Production calls of the kind-blind resolvers, each one deliberate (#479). A new call on a name that
# can be either kind must go through ``prompt_kind.effective_registry_permission`` instead.
KIND_BLIND_CALLS_ALLOWED = {
    ("utils/prompt_kind.py", "effective_prompt_permission"),  # the dispatcher itself
    ("utils/prompt_kind.py", "effective_registered_model_permission"),  # the dispatcher itself
    ("utils/batch_permissions.py", "resolve_prompt_permission_from_context"),  # rows known to be prompts
    ("utils/batch_permissions.py", "resolve_model_permission_from_context"),  # dispatched by each row's kind
    ("validators/prompt_optimization_job.py", "effective_prompt_permission"),  # a prompts:/ URI
    ("utils/permissions.py", "effective_registered_model_permission"),  # the can_*_registered_model helpers
}
KIND_BLIND = (
    "effective_registered_model_permission",
    "effective_prompt_permission",
    "resolve_model_permission_from_context",
    "resolve_prompt_permission_from_context",
    "can_read_registered_model",
    "can_update_registered_model",
    "can_delete_registered_model",
    "can_manage_registered_model",
)


def test_no_new_kind_blind_resolution_of_a_registered_model_name():
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    found = set()
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("tests/") or rel.startswith("ui/"):
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                if name in KIND_BLIND:
                    found.add((rel, name))
    unexpected = found - KIND_BLIND_CALLS_ALLOWED
    assert not unexpected, f"resolve these registered-model names by kind (prompt_kind.effective_registry_permission): {sorted(unexpected)}"


def test_a_grant_planted_on_a_free_name_does_not_survive_a_rename_onto_it(store):
    """A grant written on a name nobody holds is cleared when a model or prompt is renamed onto it."""
    from mlflow_oidc_auth.hooks import after_request
    from mlflow_oidc_auth.utils import permissions

    owner = "victor@example.com"
    store.create_user(owner, "Victor")
    store.create_registered_model_permission("old-name", owner, "MANAGE")
    store.create_registered_model_permission("landing", ALICE, "MANAGE")  # planted on a free name
    with Flask(__name__).test_request_context("/api/2.0/mlflow/registered-models/rename", method="POST", json={"name": "old-name", "new_name": "landing"}):
        after_request._rename_registered_model_permission(None)
    permissions.flush_permission_cache()

    assert store.list_registered_model_permissions(ALICE) == []
    assert [(p.name, p.permission) for p in store.list_registered_model_permissions(owner)] == [("landing", "MANAGE")]
