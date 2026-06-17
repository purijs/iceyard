from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.operations.schemas import (
    OperationCategoryRead,
    OperationDescriptor,
    OperationDescriptorSeedResult,
    OperationDryRunRead,
    OperationDryRunRequest,
    OperationExecuteRead,
    OperationExecuteRequest,
)
from iceyard_api.operations.service import OperationService
from iceyard_api.rbac.dependencies import require_permission

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/descriptors", response_model=list[OperationDescriptor])
def list_operation_descriptors(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.read")),
) -> list[OperationDescriptor]:
    _ = current_user
    return OperationService(session).list_descriptors()


@router.get("/descriptors/categories", response_model=list[OperationCategoryRead])
def list_operation_categories(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.read")),
) -> list[OperationCategoryRead]:
    _ = current_user
    return OperationService(session).list_categories()


@router.get("/descriptors/{operation_id}", response_model=OperationDescriptor)
def get_operation_descriptor(
    operation_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.read")),
) -> OperationDescriptor:
    _ = current_user
    return OperationService(session).get_descriptor(operation_id)


@router.post("/descriptors/seed", response_model=OperationDescriptorSeedResult)
def seed_operation_descriptors(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.manage")),
) -> OperationDescriptorSeedResult:
    result = OperationService(session).seed_descriptors()
    AuditService(session).record(
        action="operation_descriptors.seed",
        resource_type="operation_descriptor",
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state=result.model_dump(),
    )
    session.commit()
    return result


@router.post("/dry-run", response_model=OperationDryRunRead)
def dry_run_operation(
    payload: OperationDryRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.execute")),
) -> OperationDryRunRead:
    return OperationService(session).dry_run(payload=payload, actor=current_user)


@router.post("/execute", response_model=OperationExecuteRead)
def execute_operation(
    payload: OperationExecuteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.execute")),
) -> OperationExecuteRead:
    return OperationService(session).execute(
        dry_run_id=payload.dry_run_id,
        actor=current_user,
        confirmation=payload.confirmation,
        idempotency_key=payload.idempotency_key,
    )
