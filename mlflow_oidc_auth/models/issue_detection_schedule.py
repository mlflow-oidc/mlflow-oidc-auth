"""Pydantic response models for the issue detection schedules admin API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class IssueDetectionScheduleModel(BaseModel):
    """The model a stored schedule names, as stored."""

    endpoint_name: Optional[str] = Field(None, description="AI Gateway endpoint the schedule runs through")
    provider: Optional[str] = Field(None, description="Provider of a direct model selection")
    model: Optional[str] = Field(None, description="Model of a direct model selection")
    secret_id: Optional[str] = Field(None, description="Gateway secret a direct selection runs with")
    secret_name: Optional[str] = Field(None, description="Name of that secret, when it still resolves")


class IssueDetectionScheduleEntry(BaseModel):
    """One experiment's stored issue detection schedule and what the guard knows about it."""

    experiment_id: str
    experiment_name: str
    workspace: Optional[str] = None
    readable: bool = Field(..., description="Whether MLflow's scheduler reads this value as a schedule")
    paused: bool
    uses_server_credentials: bool = Field(..., description="Runs on the MLflow server's own provider credentials")
    model: Optional[IssueDetectionScheduleModel] = None
    author: Optional[str] = Field(None, description="Recorded writer of the schedule")
    recorded_at: Optional[str] = None
    guard_paused_at: Optional[str] = Field(None, description="When the guard last paused this schedule")
    guard_reason: Optional[str] = Field(None, description="Why the guard last paused it")
    violation: Optional[str] = Field(None, description="Why the guard would pause this running schedule now, if it would")


class IssueDetectionScheduleListResponse(BaseModel):
    supported: bool = Field(..., description="Whether this MLflow has recurring issue detection")
    guard_running: bool = Field(..., description="Whether this server process runs the background check")
    guard_interval_seconds: int
    server_credentials_admin_only: bool
    schedules: List[IssueDetectionScheduleEntry]


class IssueDetectionSchedulePaused(BaseModel):
    experiment_id: str
    workspace: Optional[str] = None
    reason: str


class IssueDetectionScheduleSweepResponse(BaseModel):
    checked: int = Field(..., description="Running schedules checked")
    paused: List[IssueDetectionSchedulePaused]
    failed: List[str] = Field(..., description="Experiments whose schedule could not be checked or paused")
