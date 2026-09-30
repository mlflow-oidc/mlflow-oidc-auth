"""Admin API for group → workspace rules (issue #418).

Mounted at ``/api/3.0/mlflow/workspace-rules``. Every endpoint is admin-only, and every endpoint
answers 404 unless ``MLFLOW_ENABLE_WORKSPACES`` is on — the feature-gate check runs before the admin
check, so a deployment without workspaces does not reveal that the API exists. See
:mod:`mlflow_oidc_auth.workspace_rules` for what a rule does.
"""

from dataclasses import asdict, replace
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Path

from mlflow_oidc_auth import workspace_rules
from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.entities.workspace_rule import RuleGrantChange, WorkspaceGroupRule
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.workspace_rule import (
    WorkspaceRuleChange,
    WorkspaceRuleCreateRequest,
    WorkspaceRuleListResponse,
    WorkspaceRulePlanResponse,
    WorkspaceRulePreviewRequest,
    WorkspaceRuleResponse,
    WorkspaceRuleUpdateRequest,
)
from mlflow_oidc_auth.store import store

from ._prefix import WORKSPACE_RULES_ROUTER_PREFIX

logger = get_logger()


async def require_workspaces_enabled() -> None:
    """404 unless workspaces are enabled: rules are inert, and invisible, without them."""
    if not config.MLFLOW_ENABLE_WORKSPACES:
        raise HTTPException(status_code=404, detail="Not Found")


workspace_rules_router = APIRouter(
    prefix=WORKSPACE_RULES_ROUTER_PREFIX,
    tags=["workspace rules"],
    # Order matters: the feature gate answers before the admin check does.
    dependencies=[Depends(require_workspaces_enabled), Depends(check_admin_permission)],
    responses={
        400: {"description": "Invalid rule"},
        403: {"description": "Forbidden - administrators only"},
        404: {"description": "Rule not found, or workspaces are disabled"},
    },
)

RULE = "/{rule_id}"
RULE_PREVIEW = "/{rule_id}/preview"
PREVIEW = "/preview"


def _rule_response(rule: WorkspaceGroupRule) -> WorkspaceRuleResponse:
    return WorkspaceRuleResponse(**asdict(rule))


def _changes(changes: List[RuleGrantChange]) -> List[WorkspaceRuleChange]:
    return [WorkspaceRuleChange(**asdict(c)) for c in changes]


def _bad_request(exc: workspace_rules.RuleValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _rule_audit_detail(rule: WorkspaceGroupRule) -> dict:
    return {"name": rule.name, "pattern": rule.pattern, "permission": rule.permission, "mode": rule.mode, "enabled": rule.enabled}


@workspace_rules_router.get("", response_model=WorkspaceRuleListResponse, summary="List workspace group rules")
async def list_workspace_rules() -> WorkspaceRuleListResponse:
    """Every rule, lowest id (highest precedence) first, with the permission ceiling."""
    return WorkspaceRuleListResponse(
        rules=[_rule_response(r) for r in store.list_workspace_group_rules()],
        max_permission=workspace_rules.max_permission(),
        allowed_permissions=workspace_rules.allowed_permissions(),
    )


def _apply(rule: WorkspaceGroupRule, admin: str) -> Tuple[List[RuleGrantChange], Optional[str]]:
    """Backfill a rule that was just saved. The save stands whatever happens here.

    A failure — MLflow's workspace store unreachable, say — writes nothing further, is audited, and
    is returned as the response's ``error`` rather than a 500 that would hide that the rule was
    saved. Saving the rule again retries.
    """
    try:
        return workspace_rules.backfill(rule, actor=admin), None
    except Exception as exc:
        logger.error("Workspace group rule %s was saved but its backfill failed: %s", rule.id, type(exc).__name__)
        emit_audit_event(
            "workspace_rule.failed",
            admin,
            resource_type="workspace_rule",
            resource_id=str(rule.id),
            detail={"operation": "backfill", "error": type(exc).__name__},
            status="denied",
        )
        if isinstance(exc, workspace_rules.WorkspaceStoreUnavailable):
            return (
                [],
                "The rule was saved, but its grants were not updated: MLflow's workspace store is unavailable. Save the rule again, with any of its pattern, permission, mode or enabled, to retry.",
            )
        return [], "The rule was saved, but its grants were not updated. Save the rule again, with any of its pattern, permission, mode or enabled, to retry."


def _preview_or_503(fn, *args, **kwargs) -> List[RuleGrantChange]:
    try:
        return fn(*args, **kwargs)
    except workspace_rules.WorkspaceStoreUnavailable:
        raise HTTPException(status_code=503, detail="MLflow's workspace store is unavailable; try the preview again")


@workspace_rules_router.post("", response_model=WorkspaceRulePlanResponse, status_code=201, summary="Create a workspace group rule")
async def create_workspace_rule(body: WorkspaceRuleCreateRequest, admin: str = Depends(check_admin_permission)) -> WorkspaceRulePlanResponse:
    """Create a rule and backfill it over every existing group.

    An ``enforce`` rule writes its grants now; a ``report`` rule writes nothing and returns what it
    would do.
    """
    try:
        workspace_rules.validate_pattern(body.pattern)
        workspace_rules.validate_permission(body.permission)
        workspace_rules.validate_mode(body.mode)
    except workspace_rules.RuleValidationError as exc:
        raise _bad_request(exc)
    rule = store.create_workspace_group_rule(
        name=body.name, pattern=body.pattern, permission=body.permission, mode=body.mode, enabled=body.enabled, created_by=admin
    )
    emit_audit_event("workspace_rule.create", admin, resource_type="workspace_rule", resource_id=str(rule.id), detail=_rule_audit_detail(rule))
    changes, error = _apply(rule, admin) if rule.enabled else ([], None)
    return WorkspaceRulePlanResponse(rule=_rule_response(rule), changes=_changes(changes), error=error)


@workspace_rules_router.post(PREVIEW, response_model=WorkspaceRulePlanResponse, summary="Preview an unsaved workspace group rule")
async def preview_unsaved_workspace_rule(body: WorkspaceRulePreviewRequest) -> WorkspaceRulePlanResponse:
    """What a rule with this pattern and permission would do if it were saved now and enforced. Writes nothing.

    Without ``rule_id`` it ranks after every existing rule, as a new rule would, so the preview shows
    where an existing rule shadows it. With ``rule_id`` it previews unsaved changes to that rule: its
    precedence and the grants it already holds are kept.
    """
    try:
        workspace_rules.validate_pattern(body.pattern)
        workspace_rules.validate_permission(body.permission)
    except workspace_rules.RuleValidationError as exc:
        raise _bad_request(exc)
    changes = _preview_or_503(workspace_rules.preview_unsaved, body.pattern, body.permission, rule_id=body.rule_id)
    return WorkspaceRulePlanResponse(rule=None, changes=_changes(changes))


@workspace_rules_router.get(RULE, response_model=WorkspaceRuleResponse, summary="Get a workspace group rule")
async def get_workspace_rule(rule_id: int = Path(..., description="The rule id")) -> WorkspaceRuleResponse:
    return _rule_response(store.get_workspace_group_rule(rule_id))


# The fields that decide what a rule grants. A change to anything else (its name) touches no grant.
_GRANT_FIELDS = ("pattern", "permission", "mode", "enabled")


@workspace_rules_router.patch(RULE, response_model=WorkspaceRulePlanResponse, summary="Update a workspace group rule")
async def update_workspace_rule(
    body: WorkspaceRuleUpdateRequest,
    rule_id: int = Path(..., description="The rule id"),
    admin: str = Depends(check_admin_permission),
) -> WorkspaceRulePlanResponse:
    """Change a rule, then bring its grants in line.

    A rule that is still enabled and enforcing is backfilled — it grants what it now matches and
    removes what it no longer does. A rule that is disabled or switched to ``report`` has every
    grant it held removed, in the same transaction as the change, and a rule it shadowed takes those
    groups over. A change that only renames the rule touches no grant.
    """
    before = store.get_workspace_group_rule(rule_id)
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    try:
        if "pattern" in fields:
            workspace_rules.validate_pattern(fields["pattern"])
        if "permission" in fields:
            workspace_rules.validate_permission(fields["permission"])
        if "mode" in fields:
            workspace_rules.validate_mode(fields["mode"])
    except workspace_rules.RuleValidationError as exc:
        raise _bad_request(exc)

    after = replace(before, **fields)
    grants_change = any(getattr(before, f) != getattr(after, f) for f in _GRANT_FIELDS)
    # Sending a grant field — even unchanged — asks for the grants to be brought in line: that is how
    # an admin retries after a backfill failed. A rename alone touches nothing.
    reconcile = grants_change or any(f in fields for f in _GRANT_FIELDS)
    enforcing = workspace_rules.is_enforcing(after)
    rule, removed = store.update_workspace_group_rule(rule_id, fields, clear_grants=grants_change and not enforcing)
    emit_audit_event(
        "workspace_rule.update",
        admin,
        resource_type="workspace_rule",
        resource_id=str(rule.id),
        detail={"before": _rule_audit_detail(before), "after": _rule_audit_detail(rule)},
    )
    workspace_rules.audit_removed(rule, removed, actor=admin)
    changes: List[RuleGrantChange] = list(removed)
    error = None
    if removed:
        changes += workspace_rules.reapply_after_removal(removed, actor=admin)
    if reconcile and rule.enabled:
        applied, error = _apply(rule, admin)
        changes += applied
    return WorkspaceRulePlanResponse(rule=_rule_response(rule), changes=_changes(changes), error=error)


@workspace_rules_router.delete(RULE, response_model=WorkspaceRulePlanResponse, summary="Delete a workspace group rule")
async def delete_workspace_rule(rule_id: int = Path(..., description="The rule id"), admin: str = Depends(check_admin_permission)) -> WorkspaceRulePlanResponse:
    """Delete a rule and every grant it created — and nothing else. Manual grants stay.

    A rule the deleted one shadowed then takes those groups over; its grants are in ``changes``
    with their own ``rule_id``.
    """
    rule = store.get_workspace_group_rule(rule_id)
    removed = store.delete_workspace_group_rule(rule_id)
    emit_audit_event("workspace_rule.delete", admin, resource_type="workspace_rule", resource_id=str(rule.id), detail=_rule_audit_detail(rule))
    workspace_rules.audit_removed(rule, removed, actor=admin)
    changes = removed + workspace_rules.reapply_after_removal(removed, actor=admin)
    return WorkspaceRulePlanResponse(rule=None, changes=_changes(changes))


@workspace_rules_router.get(RULE_PREVIEW, response_model=WorkspaceRulePlanResponse, summary="Preview a workspace group rule")
async def preview_workspace_rule(rule_id: int = Path(..., description="The rule id")) -> WorkspaceRulePlanResponse:
    """What enforcing the rule now would grant, update, keep, skip or remove, over every current group. Writes nothing."""
    rule = store.get_workspace_group_rule(rule_id)
    return WorkspaceRulePlanResponse(rule=_rule_response(rule), changes=_changes(_preview_or_503(workspace_rules.preview, rule)))
