from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.approvals.schemas import ApprovalDecision, ApprovalRead
from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.core.time import utcnow
from iceyard_api.db.models import ApprovalRequest, User
from iceyard_api.db.session import get_session

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalRead])
def list_approvals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ApprovalRead]:
    return list(
        session.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.workspace_id == current_user.workspace_id)
            .order_by(ApprovalRequest.created_at.desc())
        )
    )


@router.post("/{approval_id}/decision", response_model=ApprovalRead)
def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApprovalRead:
    approval = session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.workspace_id == current_user.workspace_id,
        )
    )
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    approval.status = payload.decision
    approval.reason = payload.reason
    approval.reviewer_id = current_user.id
    approval.reviewed_at = utcnow()
    AuditService(session).record(
        action=f"approval.{payload.decision}",
        resource_type="approval_request",
        resource_id=approval.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"status": approval.status, "reason": approval.reason},
    )
    session.commit()
    return approval
