from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str | None
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    event_metadata: dict[str, Any]
    occurred_at: datetime
