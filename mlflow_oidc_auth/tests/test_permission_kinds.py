"""The grant-kind registry (issue #459, PR 2).

``permission_kinds`` is the one list of grant tables. These tests pin that every grant table belongs
to exactly one kind, that the lists derived from it (orphans, grant-workspace backfill, workspace
cascade, ``PERMISSION_REGISTRY``) cover exactly what they covered when they were hand-maintained,
and — the security guard — that a prompt pattern never matches a registered model, or the reverse.
"""

import inspect

import pytest
from mlflow.exceptions import MlflowException

import mlflow_oidc_auth.db.models as db_models
from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.permission_kinds import GRANT_KINDS, resource_kinds, table_owning_kinds

USER = "alice@example.com"
GROUP = "team"


def _permission_models():
    return {obj for name, obj in vars(db_models).items() if inspect.isclass(obj) and name.startswith("Sql") and name.endswith("Permission")}


# --- the registry covers every grant table, once -----------------------------------------------


def test_every_permission_model_belongs_to_exactly_one_kind():
    referenced = [model for kind in table_owning_kinds() for model in kind.models]

    assert len(referenced) == len(set(referenced)), "a grant table is listed under two kinds"
    assert set(referenced) == _permission_models()


def test_a_kind_sharing_tables_uses_exactly_its_owners_tables():
    owners = {kind.name: kind for kind in table_owning_kinds()}
    sharing = [kind for kind in GRANT_KINDS if kind.shares_tables_of is not None]

    assert [kind.name for kind in sharing] == ["prompt"]
    for kind in sharing:
        owner = owners[kind.shares_tables_of]
        assert kind.models == owner.models
        assert (kind.key_columns, kind.workspace_scoped) == (owner.key_columns, owner.workspace_scoped)


def test_kind_names_are_unique():
    names = [kind.name for kind in GRANT_KINDS]
    assert len(names) == len(set(names))
    assert permission_kinds.kind("prompt") is permission_kinds.PROMPT
    with pytest.raises(KeyError):
        permission_kinds.kind("no-such-kind")


def test_key_columns_exist_on_the_grant_tables():
    for kind in GRANT_KINDS:
        for model in (kind.user_model, kind.group_model):
            for column in kind.key_columns:
                assert hasattr(model, column), (kind.name, model.__name__, column)
        if kind.regex_key_index is not None:
            assert 0 <= kind.regex_key_index < len(kind.key_columns)


# --- extra_filter: the prompt flag -------------------------------------------------------------


def test_kinds_sharing_tables_are_told_apart_by_extra_filter():
    """A kind sharing tables with another must carry a filter, and the two filters must differ."""
    model, prompt = permission_kinds.REGISTERED_MODEL, permission_kinds.PROMPT

    assert dict(model.extra_filter) == {"prompt": False}
    assert dict(prompt.extra_filter) == {"prompt": True}
    for kind in (model, prompt):
        for table in (kind.group_model, *kind.regex_models):
            for column in kind.extra_filter:
                assert hasattr(table, column), (kind.name, table.__name__, column)


def test_filtered_repositories_use_the_registry_filter():
    from mlflow_oidc_auth.repository import (
        PromptGroupRegexPermissionRepository,
        PromptPermissionGroupRepository,
        PromptPermissionRegexRepository,
        RegisteredModelGroupRegexPermissionRepository,
        RegisteredModelPermissionRegexRepository,
    )

    for repo in (PromptGroupRegexPermissionRepository, PromptPermissionGroupRepository, PromptPermissionRegexRepository):
        assert repo.extra_filter is permission_kinds.PROMPT.extra_filter, repo.__name__
    for repo in (RegisteredModelGroupRegexPermissionRepository, RegisteredModelPermissionRegexRepository):
        assert repo.extra_filter is permission_kinds.REGISTERED_MODEL.extra_filter, repo.__name__


def test_extra_filter_on_a_missing_column_is_refused():
    """A filter the table cannot apply would match every row of the shared table: refused at class creation."""
    from mlflow_oidc_auth.db.models import SqlExperimentRegexPermission
    from mlflow_oidc_auth.repository import BaseRegexPermissionRepository

    with pytest.raises(TypeError, match="prompt"):

        class _Broken(BaseRegexPermissionRepository):  # noqa: F841 - defining it is the test
            model_class = SqlExperimentRegexPermission
            extra_filter = {"prompt": True}


# --- derived lists -----------------------------------------------------------------------------


def test_permission_registry_keys_equal_the_registry_kinds():
    from mlflow_oidc_auth.utils.permissions import PERMISSION_REGISTRY

    assert set(PERMISSION_REGISTRY) == {kind.name for kind in resource_kinds()}
    assert set(PERMISSION_REGISTRY) == {
        "experiment",
        "registered_model",
        "prompt",
        "scorer",
        "gateway_endpoint",
        "gateway_secret",
        "gateway_model_definition",
        "mcp_server",
    }


def test_orphan_specs_cover_the_table_owning_kinds():
    from mlflow_oidc_auth.orphans import _specs

    specs = _specs()

    assert [spec.resource_type for spec in specs] == [
        "experiment",
        "registered_model",
        "scorer",
        "gateway_endpoint",
        "gateway_model_definition",
        "gateway_secret",
        "mcp_server",
        "workspace",
    ]
    by_type = {spec.resource_type: spec for spec in specs}
    assert by_type["experiment"].regex_key_index is None
    assert by_type["scorer"].key_columns == ("experiment_id", "scorer_name") and by_type["scorer"].regex_key_index == 1
    assert by_type["mcp_server"].user_regex_model is None and by_type["mcp_server"].group_regex_model is None
    assert {t for t, spec in by_type.items() if spec.workspace_scoped} == {
        "registered_model",
        "gateway_endpoint",
        "gateway_model_definition",
        "gateway_secret",
        "mcp_server",
    }


def test_workspace_scoped_grant_tables_are_the_hand_maintained_set():
    from mlflow_oidc_auth.utils.grant_workspace import workspace_scoped_grant_tables

    assert set(workspace_scoped_grant_tables()) == {
        (db_models.SqlRegisteredModelPermission, "name", "user_id", "registered_model"),
        (db_models.SqlRegisteredModelGroupPermission, "name", "group_id", "registered_model"),
        (db_models.SqlGatewayEndpointPermission, "endpoint_id", "user_id", "gateway_endpoint"),
        (db_models.SqlGatewayEndpointGroupPermission, "endpoint_id", "group_id", "gateway_endpoint"),
        (db_models.SqlGatewaySecretPermission, "secret_id", "user_id", "gateway_secret"),
        (db_models.SqlGatewaySecretGroupPermission, "secret_id", "group_id", "gateway_secret"),
        (db_models.SqlGatewayModelDefinitionPermission, "model_definition_id", "user_id", "gateway_model_definition"),
        (db_models.SqlGatewayModelDefinitionGroupPermission, "model_definition_id", "group_id", "gateway_model_definition"),
        (db_models.SqlMCPServerPermission, "name", "user_id", "mcp_server"),
        (db_models.SqlMCPServerGroupPermission, "name", "group_id", "mcp_server"),
    }
    assert len(workspace_scoped_grant_tables()) == 10
    for model, *_ in workspace_scoped_grant_tables():
        assert hasattr(model, "workspace")


def test_workspace_scoped_pattern_tables_are_the_hand_maintained_set():
    from mlflow_oidc_auth.utils.grant_workspace import workspace_scoped_pattern_tables

    tables = workspace_scoped_pattern_tables()

    assert len(tables) == len(set(tables)) == 12
    assert set(tables) == {
        db_models.SqlExperimentRegexPermission,
        db_models.SqlExperimentGroupRegexPermission,
        db_models.SqlRegisteredModelRegexPermission,
        db_models.SqlRegisteredModelGroupRegexPermission,
        db_models.SqlScorerRegexPermission,
        db_models.SqlScorerGroupRegexPermission,
        db_models.SqlGatewayEndpointRegexPermission,
        db_models.SqlGatewayEndpointGroupRegexPermission,
        db_models.SqlGatewaySecretRegexPermission,
        db_models.SqlGatewaySecretGroupRegexPermission,
        db_models.SqlGatewayModelDefinitionRegexPermission,
        db_models.SqlGatewayModelDefinitionGroupRegexPermission,
    }
    for model in tables:
        assert hasattr(model, "workspace")


# --- negative: a pattern of one kind never resolves the other ----------------------------------


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(USER, "Alice")
    s.group_repo.create_group(GROUP)
    s.add_user_to_group(USER, GROUP)
    # The request-time resolvers read the module-level store singleton.
    monkeypatch.setattr("mlflow_oidc_auth.utils.permissions.store", s)
    monkeypatch.setattr("mlflow_oidc_auth.utils.batch_permissions.store", s)
    yield s
    s.engine.dispose()


def _regex_sources(resource_type: str, name: str):
    from mlflow_oidc_auth.utils.permissions import PERMISSION_REGISTRY

    sources = PERMISSION_REGISTRY[resource_type](name, USER)
    return sources["regex"], sources["group-regex"]


def _assert_no_match(source):
    with pytest.raises(MlflowException) as exc:
        source()
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test_prompt_regex_does_not_match_model(store):
    from mlflow_oidc_auth.utils.batch_permissions import _match_regex_permission_or_none, build_user_permission_context

    store.create_prompt_regex_permission(".*", 0, "MANAGE", USER)
    store.create_group_prompt_regex_permission(".*", 0, "MANAGE", GROUP)

    user_regex, group_regex = _regex_sources("registered_model", "churn")
    _assert_no_match(user_regex)
    _assert_no_match(group_regex)
    ctx = build_user_permission_context(USER)
    assert ctx.model_regex_permissions == [] and ctx.group_model_regex_permissions == []
    assert _match_regex_permission_or_none(ctx.model_regex_permissions, "churn", "model name") is None
    # The same grants do resolve the prompt they were made for.
    user_regex, group_regex = _regex_sources("prompt", "churn")
    assert user_regex() == "MANAGE" and group_regex() == "MANAGE"


def test_model_regex_does_not_match_prompt(store):
    from mlflow_oidc_auth.utils.batch_permissions import _match_regex_permission_or_none, build_user_permission_context

    store.create_registered_model_regex_permission(".*", 0, "MANAGE", USER)
    store.create_group_registered_model_regex_permission(GROUP, ".*", 0, "MANAGE")

    user_regex, group_regex = _regex_sources("prompt", "churn")
    _assert_no_match(user_regex)
    _assert_no_match(group_regex)
    ctx = build_user_permission_context(USER)
    assert ctx.prompt_regex_permissions == [] and ctx.group_prompt_regex_permissions == []
    assert _match_regex_permission_or_none(ctx.prompt_regex_permissions, "churn", "prompt name") is None
    user_regex, group_regex = _regex_sources("registered_model", "churn")
    assert user_regex() == "MANAGE" and group_regex() == "MANAGE"
