from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from iceyard_api.audit.schemas import AuditEventRead
from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
def list_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[AuditEventRead]:
    return AuditService(session).list_events(workspace_id=current_user.workspace_id, limit=limit)
