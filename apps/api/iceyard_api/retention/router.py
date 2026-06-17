from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.editions.service import require_feature
from iceyard_api.rbac.dependencies import require_permission
from iceyard_api.retention.schemas import (
    CleanupPreviewRequest,
    CleanupPreviewResult,
    RetentionSimRequest,
    RetentionSimResult,
)
from iceyard_api.retention.service import RetentionService

router = APIRouter(prefix="/tables", tags=["retention"])


@router.post(
    "/{table_id}/retention/simulate",
    response_model=RetentionSimResult,
    dependencies=[Depends(require_feature("retention_simulation"))],
)
def simulate_retention(
    table_id: str,
    payload: RetentionSimRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> RetentionSimResult:
    return RetentionService(session).simulate_expire(current_user.workspace_id, table_id, payload)


@router.post(
    "/{table_id}/cleanup/preview",
    response_model=CleanupPreviewResult,
    dependencies=[Depends(require_feature("data_retention"))],
)
def preview_cleanup(
    table_id: str,
    payload: CleanupPreviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> CleanupPreviewResult:
    return RetentionService(session).cleanup_preview(current_user.workspace_id, table_id, payload)
