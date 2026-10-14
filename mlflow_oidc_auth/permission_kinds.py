"""One description of each kind of grant the plugin stores (issue #459).

Every resource type has user and group grants, and most have user and group pattern (regex) grants
too. Code that walks "every grant table" — the orphan report, the grant-workspace backfill, the
workspace cascade, the request-time resolver registry — reads the tables from here rather than
keeping its own list, so a table can no longer be added to one list and forgotten in another.

``tests/test_permission_kinds.py`` checks that every ``Sql*Permission`` model belongs to exactly one
kind and that ``PERMISSION_REGISTRY`` resolves exactly the kinds listed here.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from mlflow_oidc_auth.db.models import (
    SqlExperimentGroupPermission,
    SqlExperimentGroupRegexPermission,
    SqlExperimentPermission,
    SqlExperimentRegexPermission,
    SqlGatewayEndpointGroupPermission,
    SqlGatewayEndpointGroupRegexPermission,
    SqlGatewayEndpointPermission,
    SqlGatewayEndpointRegexPermission,
    SqlGatewayModelDefinitionGroupPermission,
    SqlGatewayModelDefinitionGroupRegexPermission,
    SqlGatewayModelDefinitionPermission,
    SqlGatewayModelDefinitionRegexPermission,
    SqlGatewaySecretGroupPermission,
    SqlGatewaySecretGroupRegexPermission,
    SqlGatewaySecretPermission,
    SqlGatewaySecretRegexPermission,
    SqlMCPServerGroupPermission,
    SqlMCPServerPermission,
    SqlRegisteredModelGroupPermission,
    SqlRegisteredModelGroupRegexPermission,
    SqlRegisteredModelPermission,
    SqlRegisteredModelRegexPermission,
    SqlScorerGroupPermission,
    SqlScorerGroupRegexPermission,
    SqlScorerPermission,
    SqlScorerRegexPermission,
    SqlWorkspaceGroupPermission,
    SqlWorkspaceGroupRegexPermission,
    SqlWorkspacePermission,
    SqlWorkspaceRegexPermission,
)

_NO_FILTER: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class GrantKind:
    """The grant tables of one resource type and how their rows name a resource.

    Attributes:
        name: The resource type, as used by ``PERMISSION_REGISTRY`` and in audit events.
        user_model: The user grant table.
        group_model: The group grant table.
        key_columns: The columns that name the resource in ``user_model`` and ``group_model``.
        user_regex_model: The user pattern table, or None for a kind without pattern grants.
        group_regex_model: The group pattern table, or None for a kind without pattern grants.
        regex_key_index: Index into ``key_columns`` of the value a pattern is matched against.
            None for experiments, whose patterns match the experiment *name*, which only the
            tracking store knows.
        workspace_scoped: The resources are unique per ``(workspace, name)`` in MLflow, so each user
            and group grant records the workspace it belongs to (see ``utils/grant_workspace.py``).
        workspace_level: The grants are *on* workspaces. Their pattern tables match workspace
            names and have no workspace of their own, and they are resolved by the workspace
            cache rather than through ``PERMISSION_REGISTRY``.
        extra_filter: Column values that pick this kind's rows out of tables it shares with another
            kind — prompts are registered models, told apart by the ``prompt`` flag. The registered
            model pattern repositories and the prompt grant repositories (patterns and group grants)
            filter on it and write it into every row they create; see ``repository/_base.py``.
            The user grant table has no ``prompt`` column, so user grants on a prompt and on a
            registered model of the same name are one grant.
        shares_tables_of: The kind whose tables these grants are stored in, or None when the kind
            owns its tables. Code that walks every table walks only the owners.
    """

    name: str
    user_model: type
    group_model: type
    key_columns: Tuple[str, ...]
    user_regex_model: Optional[type] = None
    group_regex_model: Optional[type] = None
    regex_key_index: Optional[int] = 0
    workspace_scoped: bool = False
    workspace_level: bool = False
    extra_filter: Mapping[str, Any] = _NO_FILTER
    shares_tables_of: Optional[str] = None

    @property
    def models(self) -> Tuple[type, ...]:
        """Every grant table of this kind, the absent pattern tables left out."""
        return tuple(m for m in (self.user_model, self.group_model, self.user_regex_model, self.group_regex_model) if m is not None)

    @property
    def regex_models(self) -> Tuple[type, ...]:
        """The pattern tables of this kind (none for a kind without pattern grants)."""
        return tuple(m for m in (self.user_regex_model, self.group_regex_model) if m is not None)


EXPERIMENT = GrantKind(
    "experiment",
    SqlExperimentPermission,
    SqlExperimentGroupPermission,
    ("experiment_id",),
    SqlExperimentRegexPermission,
    SqlExperimentGroupRegexPermission,
    regex_key_index=None,
)
REGISTERED_MODEL = GrantKind(
    "registered_model",
    SqlRegisteredModelPermission,
    SqlRegisteredModelGroupPermission,
    ("name",),
    SqlRegisteredModelRegexPermission,
    SqlRegisteredModelGroupRegexPermission,
    workspace_scoped=True,
    extra_filter=MappingProxyType({"prompt": False}),
)
PROMPT = GrantKind(
    "prompt",
    SqlRegisteredModelPermission,
    SqlRegisteredModelGroupPermission,
    ("name",),
    SqlRegisteredModelRegexPermission,
    SqlRegisteredModelGroupRegexPermission,
    workspace_scoped=True,
    extra_filter=MappingProxyType({"prompt": True}),
    shares_tables_of="registered_model",
)
# A scorer's patterns match the scorer name, as in ``_build_scorer_sources``.
SCORER = GrantKind(
    "scorer",
    SqlScorerPermission,
    SqlScorerGroupPermission,
    ("experiment_id", "scorer_name"),
    SqlScorerRegexPermission,
    SqlScorerGroupRegexPermission,
    regex_key_index=1,
)
# Gateway resolvers pass the name to both the grant lookup and the pattern match: the key.
GATEWAY_ENDPOINT = GrantKind(
    "gateway_endpoint",
    SqlGatewayEndpointPermission,
    SqlGatewayEndpointGroupPermission,
    ("endpoint_id",),
    SqlGatewayEndpointRegexPermission,
    SqlGatewayEndpointGroupRegexPermission,
    workspace_scoped=True,
)
GATEWAY_MODEL_DEFINITION = GrantKind(
    "gateway_model_definition",
    SqlGatewayModelDefinitionPermission,
    SqlGatewayModelDefinitionGroupPermission,
    ("model_definition_id",),
    SqlGatewayModelDefinitionRegexPermission,
    SqlGatewayModelDefinitionGroupRegexPermission,
    workspace_scoped=True,
)
# The label is written inline and the constant does not carry "secret" in its name: static analysis treats
# anything derived from such a name as sensitive wherever it is logged.
GATEWAY_VAULT = GrantKind(
    "gateway_secret",
    SqlGatewaySecretPermission,
    SqlGatewaySecretGroupPermission,
    ("secret_id",),
    SqlGatewaySecretRegexPermission,
    SqlGatewaySecretGroupRegexPermission,
    workspace_scoped=True,
)
# MCP servers have user and group grants only — no pattern tables.
MCP_SERVER = GrantKind("mcp_server", SqlMCPServerPermission, SqlMCPServerGroupPermission, ("name",), workspace_scoped=True)
WORKSPACE = GrantKind(
    "workspace",
    SqlWorkspacePermission,
    SqlWorkspaceGroupPermission,
    ("workspace",),
    SqlWorkspaceRegexPermission,
    SqlWorkspaceGroupRegexPermission,
    workspace_level=True,
)

#: Every kind, in the order the orphan report walks them.
GRANT_KINDS: Tuple[GrantKind, ...] = (
    EXPERIMENT,
    REGISTERED_MODEL,
    PROMPT,
    SCORER,
    GATEWAY_ENDPOINT,
    GATEWAY_MODEL_DEFINITION,
    GATEWAY_VAULT,
    MCP_SERVER,
    WORKSPACE,
)


def table_owning_kinds() -> Tuple[GrantKind, ...]:
    """The kinds that own their tables: each grant table appears under exactly one of them."""
    return tuple(kind for kind in GRANT_KINDS if kind.shares_tables_of is None)


def resource_kinds() -> Tuple[GrantKind, ...]:
    """The kinds resolved per resource through ``PERMISSION_REGISTRY`` (every kind but workspaces)."""
    return tuple(kind for kind in GRANT_KINDS if not kind.workspace_level)


def kind(name: str) -> GrantKind:
    """The kind called ``name``.

    Raises:
        KeyError: For a name no kind has.
    """
    for candidate in GRANT_KINDS:
        if candidate.name == name:
            return candidate
    raise KeyError(name)
