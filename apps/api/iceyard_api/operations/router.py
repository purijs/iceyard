from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.operations.schemas import (
    OperationDescriptor,
    OperationDryRunRead,
    OperationDryRunRequest,
    OperationExecuteRead,
    OperationExecuteRequest,
)
from iceyard_api.operations.service import OperationService

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/descriptors", response_model=list[OperationDescriptor])
def list_operation_descriptors(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[OperationDescriptor]:
    _ = current_user
    return OperationService(session).list_descriptors()


@router.post("/dry-run", response_model=OperationDryRunRead)
def dry_run_operation(
    payload: OperationDryRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OperationDryRunRead:
    return OperationService(session).dry_run(payload=payload, actor=current_user)


@router.post("/execute", response_model=OperationExecuteRead)
def execute_operation(
    payload: OperationExecuteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OperationExecuteRead:
    return OperationService(session).execute(
        dry_run_id=payload.dry_run_id,
        actor=current_user,
        confirmation=payload.confirmation,
    )
