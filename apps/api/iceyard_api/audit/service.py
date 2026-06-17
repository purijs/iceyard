from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.core.logging import redact
from iceyard_api.db.models import AuditEvent


class AuditService:
    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        *,
        action: str,
        resource_type: str,
        workspace_id: str | None = None,
        actor_id: str | None = None,
        resource_id: str | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=redact(before_state) if before_state else None,
            after_state=redact(after_state) if after_state else None,
            event_metadata=redact(metadata or {}),
        )
        self.session.add(event)
        return event

    def list_events(self, *, workspace_id: str | None = None, limit: int = 100) -> list[AuditEvent]:
        stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit)
        if workspace_id:
            stmt = stmt.where(AuditEvent.workspace_id == workspace_id)
        return list(self.session.scalars(stmt))
