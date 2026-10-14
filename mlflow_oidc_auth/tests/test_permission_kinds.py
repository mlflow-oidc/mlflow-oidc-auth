"""The grant-kind registry (issue #459, PR 2).

``permission_kinds`` is the one list of grant tables. These tests pin that every grant table belongs
to exactly one kind, that the lists derived from it (orphans, grant-workspace backfill, workspace
cascade, ``PERMISSION_REGISTRY``) cover exactly what they covered when they were hand-maintained,
and — the security guard — that a prompt pattern never matches a registered model, or the reverse.
"""

import inspect

import pytest

from mlflow_oidc_auth.db import models as db_models
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


def test_kind_names_are_the_single_source_of_resource_type_strings():
    from mlflow_oidc_auth.utils import permissions

    assert permissions.EXPERIMENT == permission_kinds.EXPERIMENT.name == "experiment"
    assert permissions.REGISTERED_MODEL == "registered_model"
    assert permissions.PROMPT == "prompt"
    assert permissions.GATEWAY_SECRET == permission_kinds.GATEWAY_VAULT.name == "gateway_secret"
    assert permissions._RESOURCE_TYPE_LOG_NAMES == tuple(kind.name for kind in resource_kinds())


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
        RegisteredModelPermissionGroupRepository,
        RegisteredModelPermissionRegexRepository,
    )

    for repo in (PromptGroupRegexPermissionRepository, PromptPermissionGroupRepository, PromptPermissionRegexRepository):
        assert repo.extra_filter is permission_kinds.PROMPT.extra_filter, repo.__name__
    for repo in (RegisteredModelGroupRegexPermissionRepository, RegisteredModelPermissionRegexRepository):
        assert repo.extra_filter is permission_kinds.REGISTERED_MODEL.extra_filter, repo.__name__
    # Managing registered model group grants sees every row permission checks count: unfiltered.
    assert not RegisteredModelPermissionGroupRepository.extra_filter
    # The user grant table has no prompt column: its grants are shared by both kinds.
    assert {role for role in permission_kinds.ROLES if permission_kinds.PROMPT.filter_for(role)} == {"group", "user_regex", "group_regex"}
    assert {role for role in permission_kinds.ROLES if permission_kinds.REGISTERED_MODEL.filter_for(role)} == {"user_regex", "group_regex"}


def _repository_classes():
    from mlflow_oidc_auth import repository
    from mlflow_oidc_auth.repository._base import _KindFilter

    assert repository.__all__  # importing the package imports every repository module
    found, pending = set(), list(_KindFilter.__subclasses__())
    while pending:
        cls = pending.pop()
        if cls not in found:
            found.add(cls)
            pending.extend(cls.__subclasses__())
    return {cls for cls in found if cls.__module__.startswith("mlflow_oidc_auth.repository.") and not cls.__module__.endswith("._base")}


def test_every_permission_repository_is_bound_to_a_kind():
    """``model_class``, ``workspace_scoped`` and ``extra_filter`` are the kind's, never hand-copied."""
    classes = _repository_classes()

    assert len(classes) >= 30
    for cls in classes:
        kind = cls.grant_kind
        assert kind in GRANT_KINDS, cls.__name__
        assert cls.model_class is kind.model_for(cls.grant_role), cls.__name__
        assert cls.extra_filter is kind.filter_for(cls.grant_role), cls.__name__
        if cls.grant_role in ("user", "group"):
            assert cls.workspace_scoped is kind.workspace_scoped, cls.__name__
    bound_tables = {cls.model_class for cls in classes}
    # Every grant table has a repository except the workspace grant tables, whose repositories
    # (workspace_permission.py, workspace_group_permission.py) predate the shared base classes.
    assert _permission_models() - bound_tables == {db_models.SqlWorkspacePermission, db_models.SqlWorkspaceGroupPermission}


def test_hand_set_derived_attributes_are_refused():
    from mlflow_oidc_auth.repository import BaseRegexPermissionRepository

    for attributes in ({"model_class": db_models.SqlExperimentRegexPermission}, {"extra_filter": {"prompt": True}}, {"workspace_scoped": True}):
        with pytest.raises(TypeError, match="derived from grant_kind"):
            type("Broken", (BaseRegexPermissionRepository,), {"grant_kind": permission_kinds.EXPERIMENT, **attributes})


def test_a_kind_without_the_role_table_is_refused():
    from mlflow_oidc_auth.repository import BaseRegexPermissionRepository

    with pytest.raises(TypeError, match="no user_regex table"):
        type("Broken", (BaseRegexPermissionRepository,), {"grant_kind": permission_kinds.MCP_SERVER})


def test_a_filter_some_tables_only_partly_have_is_refused():
    """Filtering on part of the columns would match the other kind's rows on the rest."""
    with pytest.raises(ValueError, match="has only"):
        permission_kinds.GrantKind(
            "broken",
            db_models.SqlRegisteredModelPermission,
            db_models.SqlRegisteredModelGroupPermission,
            ("name",),
            extra_filter={"prompt": True, "no_such_column": 1},
        )
    with pytest.raises(ValueError, match="no table"):
        permission_kinds.GrantKind(
            "broken", db_models.SqlExperimentPermission, db_models.SqlExperimentGroupPermission, ("experiment_id",), extra_filter={"prompt": True}
        )


def test_unfiltered_roles_must_name_a_filterable_table():
    with pytest.raises(ValueError, match="unfiltered role 'user'"):
        permission_kinds.GrantKind(
            "broken",
            db_models.SqlRegisteredModelPermission,
            db_models.SqlRegisteredModelGroupPermission,
            ("name",),
            db_models.SqlRegisteredModelRegexPermission,
            db_models.SqlRegisteredModelGroupRegexPermission,
            extra_filter={"prompt": True},
            unfiltered_roles=("user",),
        )


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


def test_orphan_report_walks_the_table_owning_kinds_in_mains_order():
    """The orphan report walks ``table_owning_kinds()``: the order its hand-maintained list had."""
    specs = table_owning_kinds()

    assert [spec.name for spec in specs] == [
        "experiment",
        "registered_model",
        "scorer",
        "gateway_endpoint",
        "gateway_model_definition",
        "gateway_secret",
        "mcp_server",
        "workspace",
    ]
    by_type = {spec.name: spec for spec in specs}
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


def test_workspace_scoped_grant_tables_are_the_hand_maintained_list_in_order():
    """The order is the one the hand-maintained list had, so backfill order and its logs do not change."""
    from mlflow_oidc_auth.utils.grant_workspace import workspace_scoped_grant_tables

    assert workspace_scoped_grant_tables() == (
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
    )
    for model, *_ in workspace_scoped_grant_tables():
        assert hasattr(model, "workspace")


def test_workspace_scoped_pattern_tables_are_the_hand_maintained_list_in_order():
    from mlflow_oidc_auth.utils.grant_workspace import workspace_scoped_pattern_tables

    tables = workspace_scoped_pattern_tables()

    assert tables == (
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
    )
    for model in tables:
        assert hasattr(model, "workspace")


def test_workspace_cascade_deletes_from_the_registry_tables(tmp_path):
    """Deleting a workspace removes the grants on it and every grant and pattern recorded in it."""
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    try:
        s.create_user(USER, "Alice")
        user_id = s.user_repo.get(USER).id
        s.group_repo.create_group(GROUP)
        expected = 0
        with s.ManagedSessionMaker(read_only=False) as session:
            group_id = session.query(db_models.SqlGroup.id).filter(db_models.SqlGroup.group_name == GROUP).scalar()
            for kind in table_owning_kinds():
                if kind.workspace_level:
                    session.add(kind.user_model(workspace="ws", user_id=user_id, permission="READ"))
                    session.add(kind.group_model(workspace="ws", group_id=group_id, permission="READ"))
                    expected += 2
                    continue
                if kind.workspace_scoped:
                    (column,) = kind.key_columns
                    session.add(kind.user_model(**{column: "r"}, workspace="ws", user_id=user_id, permission="READ"))
                    session.add(kind.group_model(**{column: "r"}, workspace="ws", group_id=group_id, permission="READ"))
                    expected += 2
                for model in kind.regex_models:
                    owner = {"user_id": user_id} if hasattr(model, "user_id") else {"group_id": group_id}
                    session.add(model(regex=".*", priority=0, permission="READ", workspace="ws", **owner))
                    expected += 1

        assert s.wipe_workspace_permissions("ws") == expected == 2 + 10 + 12
    finally:
        s.engine.dispose()


# --- negative: a pattern of one kind never resolves the other ----------------------------------


@pytest.fixture
def store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(USER, "Alice")
    s.group_repo.create_group(GROUP)
    s.add_user_to_group(USER, GROUP)
    # The request-time resolvers read the module-level store singleton; the grant context
    # (issue #460) reads it through ``grant_context._store``.
    monkeypatch.setattr("mlflow_oidc_auth.utils.permissions.store", s)
    monkeypatch.setattr("mlflow_oidc_auth.utils.grant_context._store", lambda: s)
    yield s
    s.engine.dispose()


def _regex_sources(resource_type: str, name: str):
    """The user and group pattern sources the resolver walks for one resource (``grant_context``)."""
    from mlflow_oidc_auth.utils.grant_context import _lookups, load_grant_context

    sources = _lookups(load_grant_context(USER), resource_type, name, None)
    return sources["regex"], sources["group-regex"]


def _assert_no_match(source):
    # A source with no grant returns None, which the source walk reads as "not found".
    assert source() is None


def test_prompt_regex_does_not_match_model(store):
    from mlflow_oidc_auth.utils.batch_permissions import build_user_permission_context
    from mlflow_oidc_auth.utils.grant_context import best_matching_regex

    store.create_prompt_regex_permission(".*", 0, "MANAGE", USER)
    store.create_group_prompt_regex_permission(".*", 0, "MANAGE", GROUP)

    user_regex, group_regex = _regex_sources("registered_model", "churn")
    _assert_no_match(user_regex)
    _assert_no_match(group_regex)
    patterns = build_user_permission_context(USER).patterns("registered_model")
    assert patterns.regex == () and patterns.group_regex == ()
    assert best_matching_regex(patterns.regex, "churn", "model name") is None
    # The same grants do resolve the prompt they were made for.
    user_regex, group_regex = _regex_sources("prompt", "churn")
    assert user_regex() == "MANAGE" and group_regex() == "MANAGE"


def test_model_regex_does_not_match_prompt(store):
    from mlflow_oidc_auth.utils.batch_permissions import build_user_permission_context
    from mlflow_oidc_auth.utils.grant_context import best_matching_regex

    store.create_registered_model_regex_permission(".*", 0, "MANAGE", USER)
    store.create_group_registered_model_regex_permission(GROUP, ".*", 0, "MANAGE")

    user_regex, group_regex = _regex_sources("prompt", "churn")
    _assert_no_match(user_regex)
    _assert_no_match(group_regex)
    patterns = build_user_permission_context(USER).patterns("prompt")
    assert patterns.regex == () and patterns.group_regex == ()
    assert best_matching_regex(patterns.regex, "churn", "prompt name") is None
    user_regex, group_regex = _regex_sources("registered_model", "churn")
    assert user_regex() == "MANAGE" and group_regex() == "MANAGE"
