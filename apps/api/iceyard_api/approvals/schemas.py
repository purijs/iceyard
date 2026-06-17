from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    operation_request_id: str
    requested_by: str | None
    reviewer_id: str | None
    status: str
    reason: str | None
    compiled_command_snapshot: str
    created_at: datetime
    reviewed_at: datetime | None


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str
