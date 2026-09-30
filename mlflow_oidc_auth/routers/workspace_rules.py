"""Admin API for group → workspace rules (issue #418).

Mounted at ``/api/3.0/mlflow/workspace-rules``. Every endpoint is admin-only, and every endpoint
answers 404 unless ``MLFLOW_ENABLE_WORKSPACES`` is on — the feature-gate check runs before the admin
check, so a deployment without workspaces does not reveal that the API exists. See
:mod:`mlflow_oidc_auth.workspace_rules` for what a rule does.
"""

from dataclasses import asdict
from typing import List

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
        name=body.name.strip(), pattern=body.pattern, permission=body.permission, mode=body.mode, enabled=body.enabled, created_by=admin
    )
    emit_audit_event("workspace_rule.create", admin, resource_type="workspace_rule", resource_id=str(rule.id), detail=_rule_audit_detail(rule))
    changes = workspace_rules.backfill(rule, actor=admin) if rule.enabled else []
    return WorkspaceRulePlanResponse(rule=_rule_response(rule), changes=_changes(changes))


@workspace_rules_router.post(PREVIEW, response_model=WorkspaceRulePlanResponse, summary="Preview an unsaved workspace group rule")
async def preview_unsaved_workspace_rule(body: WorkspaceRulePreviewRequest) -> WorkspaceRulePlanResponse:
    """What a rule with this pattern and permission would do if it were created now and enforced. Writes nothing.

    It ranks after every existing rule, as a new rule would, so the preview shows where an existing
    rule shadows it.
    """
    try:
        workspace_rules.validate_pattern(body.pattern)
        workspace_rules.validate_permission(body.permission)
    except workspace_rules.RuleValidationError as exc:
        raise _bad_request(exc)
    changes = workspace_rules.preview_unsaved(body.pattern, body.permission)
    return WorkspaceRulePlanResponse(rule=None, changes=_changes(changes))


@workspace_rules_router.get(RULE, response_model=WorkspaceRuleResponse, summary="Get a workspace group rule")
async def get_workspace_rule(rule_id: int = Path(..., description="The rule id")) -> WorkspaceRuleResponse:
    return _rule_response(store.get_workspace_group_rule(rule_id))


@workspace_rules_router.patch(RULE, response_model=WorkspaceRulePlanResponse, summary="Update a workspace group rule")
async def update_workspace_rule(
    body: WorkspaceRuleUpdateRequest,
    rule_id: int = Path(..., description="The rule id"),
    admin: str = Depends(check_admin_permission),
) -> WorkspaceRulePlanResponse:
    """Change a rule, then bring its grants in line.

    A rule that is still enabled and enforcing is backfilled — it grants what it now matches and
    removes what it no longer does. A rule that is disabled or switched to ``report`` has every
    grant it held removed, in the same transaction as the change.
    """
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
    if "name" in fields:
        fields["name"] = fields["name"].strip()

    before = store.get_workspace_group_rule(rule_id)
    enforcing = workspace_rules.is_enforcing(WorkspaceGroupRule(**{**asdict(before), **{k: v for k, v in fields.items() if k in ("mode", "enabled")}}))
    rule, removed = store.update_workspace_group_rule(rule_id, fields, clear_grants=not enforcing)
    emit_audit_event(
        "workspace_rule.update",
        admin,
        resource_type="workspace_rule",
        resource_id=str(rule.id),
        detail={"before": _rule_audit_detail(before), "after": _rule_audit_detail(rule)},
    )
    workspace_rules.audit_removed(rule, removed, actor=admin)
    changes = removed + (workspace_rules.backfill(rule, actor=admin) if rule.enabled else [])
    return WorkspaceRulePlanResponse(rule=_rule_response(rule), changes=_changes(changes))


@workspace_rules_router.delete(RULE, response_model=WorkspaceRulePlanResponse, summary="Delete a workspace group rule")
async def delete_workspace_rule(rule_id: int = Path(..., description="The rule id"), admin: str = Depends(check_admin_permission)) -> WorkspaceRulePlanResponse:
    """Delete a rule and every grant it created — and nothing else. Manual grants stay."""
    rule = store.get_workspace_group_rule(rule_id)
    removed = store.delete_workspace_group_rule(rule_id)
    emit_audit_event("workspace_rule.delete", admin, resource_type="workspace_rule", resource_id=str(rule.id), detail=_rule_audit_detail(rule))
    workspace_rules.audit_removed(rule, removed, actor=admin)
    return WorkspaceRulePlanResponse(rule=None, changes=_changes(removed))


@workspace_rules_router.get(RULE_PREVIEW, response_model=WorkspaceRulePlanResponse, summary="Preview a workspace group rule")
async def preview_workspace_rule(rule_id: int = Path(..., description="The rule id")) -> WorkspaceRulePlanResponse:
    """What enforcing the rule now would grant, update, keep, skip or remove, over every current group. Writes nothing."""
    rule = store.get_workspace_group_rule(rule_id)
    return WorkspaceRulePlanResponse(rule=_rule_response(rule), changes=_changes(workspace_rules.preview(rule)))
