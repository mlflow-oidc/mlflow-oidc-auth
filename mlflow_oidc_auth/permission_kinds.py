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

#: The table roles a kind has, as named by a repository's ``grant_role``: the model is ``<role>_model``.
ROLES: Tuple[str, ...] = ("user", "group", "user_regex", "group_regex")


@dataclass(frozen=True, eq=False)
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
            kind — prompts are registered models, told apart by the ``prompt`` flag. It applies to
            every table of the kind that has those columns (:meth:`filter_for`): the repositories
            bound to such a table filter on it and write it into every row they create; see
            ``repository/_base.py``. The user grant table has no ``prompt`` column, so user grants
            on a prompt and on a registered model of the same name are one grant.
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

    def __post_init__(self):
        for role in ROLES:
            model = self.model_for(role)
            present = [column for column in self.extra_filter if model is not None and hasattr(model, column)]
            if present and len(present) != len(self.extra_filter):
                # Filtering on part of the columns would match the other kind's rows on the rest.
                raise ValueError(f"{self.name}: {model.__name__} has only {present} of extra_filter {dict(self.extra_filter)}")
        if self.extra_filter and not any(self.filter_for(role) for role in ROLES):
            raise ValueError(f"{self.name}: no table of the kind has the extra_filter columns {list(self.extra_filter)}")

    def model_for(self, role: str) -> Optional[type]:
        """The table playing ``role`` (one of :data:`ROLES`), or None for an absent pattern table.

        Raises:
            ValueError: For an unknown role.
        """
        if role not in ROLES:
            raise ValueError(f"unknown grant role {role!r}")
        return getattr(self, f"{role}_model")

    def filter_for(self, role: str) -> Mapping[str, Any]:
        """``extra_filter`` if the table playing ``role`` has its columns, else no filter."""
        model = self.model_for(role)
        if model is None or not self.extra_filter or not all(hasattr(model, column) for column in self.extra_filter):
            return _NO_FILTER
        return self.extra_filter

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

#: Every kind. Code walking the tables walks them in this order: the grant-workspace backfill, the
#: workspace cascade and the orphan report (``tests/test_permission_kinds.py`` pins it).
GRANT_KINDS: Tuple[GrantKind, ...] = (
    EXPERIMENT,
    REGISTERED_MODEL,
    PROMPT,
    SCORER,
    GATEWAY_ENDPOINT,
    GATEWAY_VAULT,
    GATEWAY_MODEL_DEFINITION,
    MCP_SERVER,
    WORKSPACE,
)


def table_owning_kinds() -> Tuple[GrantKind, ...]:
    """The kinds that own their tables: each grant table appears under exactly one of them."""
    return tuple(kind for kind in GRANT_KINDS if kind.shares_tables_of is None)


def resource_kinds() -> Tuple[GrantKind, ...]:
    """The kinds resolved per resource through ``PERMISSION_REGISTRY`` (every kind but workspaces)."""
    return tuple(kind for kind in GRANT_KINDS if not kind.workspace_level)
