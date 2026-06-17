from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.layout.schemas import LayoutProfileRead
from iceyard_api.layout.service import LayoutStatsService
from iceyard_api.layout.whatif_schemas import WhatIfRequest, WhatIfResult
from iceyard_api.layout.whatif_service import WhatIfService
from iceyard_api.rbac.dependencies import require_permission

router = APIRouter(prefix="/tables", tags=["layout"])


@router.get("/{table_id}/layout-profile", response_model=LayoutProfileRead)
def get_layout_profile(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> LayoutProfileRead:
    return LayoutStatsService(session).profile(current_user.workspace_id, table_id)


@router.post("/{table_id}/whatif", response_model=WhatIfResult)
def simulate_layout_change(
    table_id: str,
    payload: WhatIfRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> WhatIfResult:
    return WhatIfService(session).simulate(current_user.workspace_id, table_id, payload)
