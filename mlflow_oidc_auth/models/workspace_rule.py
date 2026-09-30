"""Pydantic request/response models for workspace group rules (issue #418)."""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("name must not be blank")
    return value


class WorkspaceRuleCreateRequest(BaseModel):
    """Create a rule. ``mode`` defaults to ``report``: a new rule says what it would do before it does it."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="Unique label")
    pattern: str = Field(..., description="Python regex, matched with re.fullmatch against the local group name; must contain (?P<ws>...)")
    permission: str = Field(..., description="READ, USE, EDIT or MANAGE, at most WORKSPACE_RULES_MAX_PERMISSION")
    mode: str = Field("report", description="report (write nothing) or enforce")
    enabled: bool = Field(True, description="A disabled rule holds no grants")

    _name = field_validator("name")(classmethod(lambda cls, v: _clean_name(v)))


class WorkspaceRuleUpdateRequest(BaseModel):
    """Change a rule. Omitted fields keep their value."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    pattern: Optional[str] = None
    permission: Optional[str] = None
    mode: Optional[str] = None
    enabled: Optional[bool] = None

    _name = field_validator("name")(classmethod(lambda cls, v: _clean_name(v)))


class WorkspaceRulePreviewRequest(BaseModel):
    """A rule that is not saved yet, to preview before creating it."""

    model_config = ConfigDict(extra="forbid")

    pattern: str
    permission: str
    rule_id: Optional[int] = Field(None, description="An existing rule being edited: preview under its id and with the grants it holds")


class WorkspaceRuleResponse(BaseModel):
    """One rule."""

    id: int
    name: str
    pattern: str
    permission: str
    mode: str
    enabled: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        """Stored naive in UTC; sent with its offset so a browser does not read it as local time."""
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class WorkspaceRuleListResponse(BaseModel):
    """Every rule, lowest id (highest precedence) first, and the ceiling that caps their permission."""

    rules: List[WorkspaceRuleResponse]
    max_permission: str = Field(..., description="WORKSPACE_RULES_MAX_PERMISSION")
    allowed_permissions: List[str] = Field(..., description="The permissions a rule may grant under the ceiling, lowest first")


class WorkspaceRuleChange(BaseModel):
    """One line of a plan. See :class:`mlflow_oidc_auth.entities.workspace_rule.RuleGrantChange`."""

    action: str = Field(..., description="grant, update, keep, remove, skip or shadowed")
    group: str
    workspace: str
    permission: Optional[str] = None
    reason: Optional[str] = None
    previous: Optional[str] = None
    applied: bool = Field(..., description="Whether this was written; false for a preview and for a report-mode rule")
    rule_id: Optional[int] = Field(None, description="The rule this line belongs to")


class WorkspaceRulePlanResponse(BaseModel):
    """What a rule did, or would do."""

    rule: Optional[WorkspaceRuleResponse] = None
    changes: List[WorkspaceRuleChange]
    error: Optional[str] = Field(None, description="Set when the rule was saved but its grants could not be brought in line; save it again to retry")
