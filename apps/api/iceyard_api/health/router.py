from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.health.schemas import DashboardRead, HealthRead
from iceyard_api.health.service import HealthService
from iceyard_api.iceberg.service import IcebergIndexService

router = APIRouter(tags=["health"])


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DashboardRead:
    return HealthService(session).dashboard(current_user.workspace_id)


@router.get("/tables/{table_id}/health", response_model=HealthRead)
def table_health(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HealthRead:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return HealthService(session).evaluate_table(table)
