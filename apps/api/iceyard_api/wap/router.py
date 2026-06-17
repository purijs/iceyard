from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.dependencies import require_permission
from iceyard_api.wap.schemas import WapRunRequest, WapRunResult
from iceyard_api.wap.service import WapService

router = APIRouter(prefix="/tables", tags=["wap"])


@router.post("/{table_id}/wap/run", response_model=WapRunResult)
def run_wap_pipeline(
    table_id: str,
    payload: WapRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("operations.execute")),
) -> WapRunResult:
    return WapService(session).run(current_user.workspace_id, table_id, payload, current_user)
