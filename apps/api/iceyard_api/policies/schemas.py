from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PolicyKind = Literal[
    "clustering",
    "parquet",
    "distribution",
    "retention",
    "cleanup",
    "wap",
    "materialized_view",
]
TriggerKind = Literal["schedule", "threshold", "event"]
ApprovalMode = Literal["first_run", "always", "none"]


class PolicySelector(BaseModel):
    env: str | None = None
    namespace: str | None = None
    name_glob: str | None = None
    min_size_gb: float | None = None


class PolicyThreshold(BaseModel):
    metric: str
    op: Literal[">", ">=", "<", "<=", "=="]
    value: float


class PolicyTrigger(BaseModel):
    kind: TriggerKind = "schedule"
    schedule: str | None = None  # cron
    threshold: PolicyThreshold | None = None


class PolicyAction(BaseModel):
    op: str  # an operation descriptor id
    params: dict[str, object] = Field(default_factory=dict)


class PolicyGuardrails(BaseModel):
    dry_run_first: bool = True
    max_change_pct: int | None = 25
    off_peak_only: bool = True
    approval: ApprovalMode = "first_run"


class PolicyAlerting(BaseModel):
    on: list[str] = Field(default_factory=lambda: ["failed", "gate_blocked"])
    channel: str | None = None


class PolicyBase(BaseModel):
    name: str
    kind: PolicyKind
    enabled: bool = True
    selector: PolicySelector = Field(default_factory=PolicySelector)
    trigger: PolicyTrigger = Field(default_factory=PolicyTrigger)
    action: PolicyAction
    guardrails: PolicyGuardrails = Field(default_factory=PolicyGuardrails)
    alerting: PolicyAlerting = Field(default_factory=PolicyAlerting)


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    enabled: bool | None = None
    selector: PolicySelector | None = None
    trigger: PolicyTrigger | None = None
    action: PolicyAction | None = None
    guardrails: PolicyGuardrails | None = None
    alerting: PolicyAlerting | None = None


class PolicyRead(PolicyBase):
    id: str
    created_at: datetime
    updated_at: datetime


class PolicyMatch(BaseModel):
    policy_id: str
    policy_name: str
    matched_table_ids: list[str]
    matched_table_names: list[str]
