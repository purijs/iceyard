from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.dependencies import require_permission
from iceyard_api.tuning.schemas import DistributionAdvice, ParquetAdvice
from iceyard_api.tuning.service import TuningService

router = APIRouter(prefix="/tables", tags=["tuning"])


@router.get("/{table_id}/parquet-advice", response_model=ParquetAdvice)
def get_parquet_advice(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> ParquetAdvice:
    return TuningService(session).parquet_advice(current_user.workspace_id, table_id)


@router.get("/{table_id}/distribution-advice", response_model=DistributionAdvice)
def get_distribution_advice(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> DistributionAdvice:
    return TuningService(session).distribution_advice(current_user.workspace_id, table_id)
