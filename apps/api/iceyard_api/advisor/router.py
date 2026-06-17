from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.advisor.schemas import (
    ClusteringAdvice,
    ClusteringAdviceRequest,
    MaterializedViewAdvice,
)
from iceyard_api.advisor.service import AdvisorService
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.dependencies import require_permission

router = APIRouter(prefix="/tables", tags=["advisor"])


@router.post("/{table_id}/clustering-advice", response_model=ClusteringAdvice)
def clustering_advice(
    table_id: str,
    payload: ClusteringAdviceRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> ClusteringAdvice:
    return AdvisorService(session).clustering_advice(current_user.workspace_id, table_id, payload)


@router.get("/{table_id}/materialized-view-advice", response_model=MaterializedViewAdvice)
def materialized_view_advice(
    table_id: str,
    engine: str = "trino",
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> MaterializedViewAdvice:
    return AdvisorService(session).materialized_view_advice(
        current_user.workspace_id, table_id, engine
    )
