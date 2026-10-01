"""Assign a workspace to grants recorded before grants carried one (see utils/grant_workspace.py).

Grants on registered models (prompts included), gateway endpoints, gateway secrets and gateway
model definitions used to be keyed by name alone. The migration that added their ``workspace``
column cannot know which workspace a name belongs to — that is in MLflow's database, not this
plugin's — so existing grants start with ``workspace IS NULL`` and this runs at startup, where
MLflow's stores are available. It is idempotent: once every grant has a workspace it only counts.

With workspaces disabled every resource lives in the default workspace, so every legacy grant gets
``default``. With workspaces enabled each grant's name is looked up in MLflow:

* the grant is kept, once per workspace holding the name, only where the grantee already has at
  least ``READ`` on that workspace. A name-only grant reached every workspace's resource of that
  name, including ones created later by another tenant, so the grant alone is no evidence of which
  one it was meant for;
* the ``default`` workspace is the exception: it holds the resources from before workspaces were
  enabled, which those grants were made for, so a grant on a name found there that the grantee
  reaches in no workspace at all is kept there. A grantee who does reach another workspace holding
  the name gets the grant only there (and in ``default`` only with a permission on it): a tenant who
  created a same-named resource in their own workspace must not come away owning ``default``'s;
* no such workspace, or the name exists nowhere (the resource was deleted) → marked unresolved
  (:data:`~mlflow_oidc_auth.utils.grant_workspace.UNRESOLVED_WORKSPACE`) and reported.

An unresolved grant matches nothing and is never placed later: a resource created afterwards —
in ``default`` or anywhere else — does not pick it up. An administrator can re-grant it in the
right workspace and delete the unresolved row. If MLflow's resources cannot be read at all, nothing
is marked and the next start tries again. Where a grant for the same workspace,
resource and principal already exists, the explicit one is kept and the legacy row dropped.

Never raises: a failure is logged, and the unassigned grants stay inert until the next start.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils.grant_workspace import UNRESOLVED_WORKSPACE, workspace_scoped_grant_tables

logger = get_logger()


@dataclass
class BackfillReport:
    """What one run did, per grant table."""

    assigned: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    copied: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    merged: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    unresolved: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))

    @property
    def unresolved_count(self) -> int:
        return sum(len(v) for v in self.unresolved.values())


def _mlflow_resource_workspaces() -> Optional[Dict[str, Dict[str, Set[str]]]]:
    """``{kind: {name: {workspace, ...}}}`` from MLflow's own tables, or None if they cannot be read.

    Read through the stores' own sessions straight from the ORM tables, so every workspace is seen
    at once (the stores' query helpers see only the active workspace). Prompts are registered
    models, so they share the ``registered_model`` map.
    """
    try:
        from mlflow.server.handlers import _get_model_registry_store, _get_tracking_store
        from mlflow.store.model_registry.dbmodels.models import SqlRegisteredModel
        from mlflow.store.tracking.dbmodels.models import SqlGatewayEndpoint, SqlGatewayModelDefinition, SqlGatewaySecret

        registry, tracking = _get_model_registry_store(), _get_tracking_store()
        found: Dict[str, Dict[str, Set[str]]] = {
            "registered_model": defaultdict(set),
            "gateway_endpoint": defaultdict(set),
            "gateway_secret": defaultdict(set),
            "gateway_model_definition": defaultdict(set),
            "mcp_server": defaultdict(set),
        }
        with registry.ManagedSessionMaker() as session:
            for workspace, name in session.query(SqlRegisteredModel.workspace, SqlRegisteredModel.name).all():
                found["registered_model"][name].add(workspace)
        with tracking.ManagedSessionMaker() as session:
            for kind, column in (
                ("gateway_endpoint", SqlGatewayEndpoint.name),
                ("gateway_secret", SqlGatewaySecret.secret_name),
                ("gateway_model_definition", SqlGatewayModelDefinition.name),
            ):
                model = column.class_
                for workspace, name in session.query(model.workspace, column).all():
                    if name:
                        found[kind][name].add(workspace)
            # MLflow 3.15+: the MCP server registry. Its grant tables are created with the workspace
            # column already written, so they only hold unassigned rows if written by hand; older
            # MLflow releases have no registry, and such rows are left with no candidate workspace.
            try:
                from mlflow.store.tracking.dbmodels.models import SqlMCPServer
            except ImportError:
                SqlMCPServer = None
            if SqlMCPServer is not None:
                for workspace, name in session.query(SqlMCPServer.workspace, SqlMCPServer.name).all():
                    if name:
                        found["mcp_server"][name].add(workspace)
        return found
    except Exception as exc:
        logger.warning("Grant workspace backfill: MLflow's resources could not be read (%s); legacy grants stay unassigned", type(exc).__name__)
        return None


def _principal_can_reach(session) -> Callable[[str, int, str], Optional[object]]:
    """``can_reach(principal_column, principal_id, workspace)``: the grantee's permission there, when it reads it.

    Returns the workspace permission (at least ``READ``), or None.

    A user is judged by the full workspace resolution (user, group, regex, group-regex grants and
    rule-owned group grants). A group by its own group grants on the workspace.
    """
    from mlflow_oidc_auth.db.models import SqlUser, SqlWorkspaceGroupPermission
    from mlflow_oidc_auth.permissions import get_permission
    from mlflow_oidc_auth.utils.workspace_cache import _lookup_workspace_permission

    usernames: Dict[int, Optional[str]] = {}
    reached: Dict[Tuple[str, int, str], Optional[object]] = {}

    def can_reach(principal: str, principal_id: int, workspace: str):
        # Memoised: a grantee with many legacy grants is judged once per workspace.
        key = (principal, principal_id, workspace)
        if key not in reached:
            reached[key] = _reaches(principal, principal_id, workspace)
        return reached[key]

    def _reaches(principal: str, principal_id: int, workspace: str):
        try:
            if principal == "user_id":
                if principal_id not in usernames:
                    row = session.query(SqlUser.username).filter(SqlUser.id == principal_id).one_or_none()
                    usernames[principal_id] = row[0] if row else None
                username = usernames[principal_id]
                permission = _lookup_workspace_permission(username, workspace) if username else None
                return permission if permission is not None and permission.can_read else None
            row = (
                session.query(SqlWorkspaceGroupPermission.permission)
                .filter(SqlWorkspaceGroupPermission.group_id == principal_id, SqlWorkspaceGroupPermission.workspace == workspace)
                .one_or_none()
            )
            permission = get_permission(row[0]) if row is not None else None
            return permission if permission is not None and permission.can_read else None
        except Exception:
            return None

    return can_reach


def backfill_grant_workspaces(store=None) -> Optional[BackfillReport]:
    """Assign workspaces to legacy grants. See the module docstring. Never raises.

    Returns:
        The report, or None when the run failed before it could produce one.
    """
    try:
        if store is None:
            from mlflow_oidc_auth.store import store as store_singleton

            store = store_singleton
        return _backfill(store)
    except Exception as e:
        # Several workers starting at once each run the backfill; the one that loses the race on
        # the unique constraint rolls back, and the grants are placed by the winner. The store's
        # session wraps the database error, so the cause is what says so.
        if isinstance(e, IntegrityError) or isinstance(e.__cause__, IntegrityError) or isinstance(getattr(e, "__context__", None), IntegrityError):
            logger.info("Grant workspace backfill: another process placed the same grants first; nothing changed here")
            return None
        logger.exception("Grant workspace backfill failed; legacy grants stay unassigned until the next start")
        return None


def _backfill(store) -> BackfillReport:
    report = BackfillReport()
    tables = workspace_scoped_grant_tables()
    with store.ManagedSessionMaker() as session:
        pending = any(session.query(model.id).filter(model.workspace.is_(None)).first() is not None for model, *_ in tables)
    if not pending:
        return report

    workspaces_enabled = config.MLFLOW_ENABLE_WORKSPACES
    resources = _mlflow_resource_workspaces() if workspaces_enabled else None
    if workspaces_enabled and resources is None:
        return report

    with store.ManagedSessionMaker(read_only=False) as session:
        can_reach = _principal_can_reach(session)
        for model, resource_col, principal_col, kind in tables:
            table = model.__tablename__
            rows = session.query(model).filter(model.workspace.is_(None)).order_by(model.id).all()
            for row in rows:
                name, principal_id = getattr(row, resource_col), getattr(row, principal_col)
                caps = {}
                if not workspaces_enabled:
                    targets = [DEFAULT_WORKSPACE_NAME]
                else:
                    candidates = sorted(resources.get(kind, {}).get(name, set()))
                    levels = {ws: can_reach(principal_col, principal_id, ws) for ws in candidates}
                    targets = [ws for ws in candidates if levels[ws] is not None]
                    if not targets and DEFAULT_WORKSPACE_NAME in candidates:
                        targets = [DEFAULT_WORKSPACE_NAME]
                    # When several workspaces hold the name, which tenant's resource the name-only
                    # grant was made for is unknowable: a copy placed in a workspace other than
                    # default carries no more than the grantee already holds on that workspace.
                    if len(candidates) > 1:
                        caps = {ws: levels[ws] for ws in targets if ws != DEFAULT_WORKSPACE_NAME and levels.get(ws) is not None}
                    if not targets:
                        reason = "not found in any workspace" if not candidates else f"in {len(candidates)} workspace(s), grantee reaches none"
                        report.unresolved[table].append(f"{name} ({reason})")
                        duplicate = (
                            session.query(model.id)
                            .filter(
                                model.workspace == UNRESOLVED_WORKSPACE,
                                getattr(model, resource_col) == name,
                                getattr(model, principal_col) == principal_id,
                            )
                            .first()
                        )
                        if duplicate is not None:
                            # A copy written during a rolling upgrade: one unresolved grant is enough.
                            session.delete(row)
                        else:
                            row.workspace = UNRESOLVED_WORKSPACE
                        session.flush()
                        continue
                _place(session, model, row, resource_col, principal_col, targets, report, table, caps)
            session.flush()

    _log(report, workspaces_enabled)
    return report


def _place(session, model, row, resource_col: str, principal_col: str, targets: List[str], report: BackfillReport, table: str, caps=None) -> None:
    """Give ``row`` the first target workspace and copy it to the others, skipping any that exist.

    ``caps`` maps a target workspace to the most the grant may carry there (see the caller).
    """
    from mlflow_oidc_auth.permissions import compare_permissions

    caps = caps or {}
    original = row.permission

    def capped(workspace: str) -> str:
        cap = caps.get(workspace)
        if cap is None or compare_permissions(original, cap.name):
            return original
        return cap.name

    def exists(workspace: str) -> bool:
        return (
            session.query(model.id)
            .filter(
                model.workspace == workspace,
                getattr(model, resource_col) == getattr(row, resource_col),
                getattr(model, principal_col) == getattr(row, principal_col),
            )
            .first()
            is not None
        )

    placed_row = False
    for workspace in targets:
        if exists(workspace):
            report.merged[table] += 1
            continue
        if not placed_row:
            row.workspace = workspace
            row.permission = capped(workspace)
            session.flush()
            placed_row = True
            report.assigned[table] += 1
            continue
        copy = model(**{c.key: getattr(row, c.key) for c in model.__table__.columns if c.key not in ("id", "workspace", "permission")})
        copy.workspace = workspace
        copy.permission = capped(workspace)
        session.add(copy)
        session.flush()
        report.copied[table] += 1
    if not placed_row:
        # Every target already had an explicit grant for this principal: the legacy row is redundant.
        session.delete(row)


def _log(report: BackfillReport, workspaces_enabled: bool) -> None:
    assigned, copied, merged = sum(report.assigned.values()), sum(report.copied.values()), sum(report.merged.values())
    if assigned or copied or merged:
        logger.info("Grant workspace backfill: %d grant(s) assigned, %d copied to further workspaces, %d merged into existing grants", assigned, copied, merged)
    if report.unresolved_count:
        logger.warning(
            "Grant workspace backfill: %d grant(s) could not be assigned a workspace; they are marked unresolved and match nothing. "
            "Re-grant them in the right workspace. %s",
            report.unresolved_count,
            "; ".join(f"{table}: {', '.join(items[:10])}{' …' if len(items) > 10 else ''}" for table, items in report.unresolved.items()),
        )
        try:
            from mlflow_oidc_auth.audit import emit_audit_event

            for table, items in report.unresolved.items():
                emit_audit_event(
                    "permission.workspace_unresolved",
                    "system:grant-workspace-backfill",
                    resource_type=table,
                    detail={"count": len(items), "grants": items[:50]},
                )
        except Exception:
            logger.debug("Could not audit unresolved grant workspaces")
