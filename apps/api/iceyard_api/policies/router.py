from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.policies.schemas import (
    PolicyCreate,
    PolicyMatch,
    PolicyRead,
    PolicyUpdate,
)
from iceyard_api.policies.service import PolicyService
from iceyard_api.rbac.dependencies import require_permission

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=list[PolicyRead])
def list_policies(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.read")),
) -> list[PolicyRead]:
    return PolicyService(session).list_policies(current_user.workspace_id)


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: PolicyCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.manage")),
) -> PolicyRead:
    service = PolicyService(session)
    policy = service.create_policy(current_user.workspace_id, payload, current_user.id)
    AuditService(session).record(
        action="automation_policy.create",
        resource_type="automation_policy",
        resource_id=policy.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"name": policy.name, "kind": policy.kind},
    )
    session.commit()
    return policy


@router.get("/{policy_id}", response_model=PolicyRead)
def get_policy(
    policy_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.read")),
) -> PolicyRead:
    service = PolicyService(session)
    return service._to_read(service.get_policy(current_user.workspace_id, policy_id))


@router.get("/{policy_id}/match", response_model=PolicyMatch)
def match_policy(
    policy_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.read")),
) -> PolicyMatch:
    return PolicyService(session).match(current_user.workspace_id, policy_id)


@router.patch("/{policy_id}", response_model=PolicyRead)
def update_policy(
    policy_id: str,
    payload: PolicyUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.manage")),
) -> PolicyRead:
    policy = PolicyService(session).update_policy(current_user.workspace_id, policy_id, payload)
    AuditService(session).record(
        action="automation_policy.update",
        resource_type="automation_policy",
        resource_id=policy_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"enabled": policy.enabled},
    )
    session.commit()
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.manage")),
) -> None:
    PolicyService(session).delete_policy(current_user.workspace_id, policy_id)
    AuditService(session).record(
        action="automation_policy.delete",
        resource_type="automation_policy",
        resource_id=policy_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
    )
    session.commit()
