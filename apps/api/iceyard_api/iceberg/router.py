from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.iceberg.schemas import SchemaVersionRead, SnapshotRead, TableRead, TableRefRead
from iceyard_api.iceberg.service import IcebergIndexService

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("", response_model=list[TableRead])
def list_tables(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[TableRead]:
    return IcebergIndexService(session).list_tables(current_user.workspace_id)


@router.get("/{table_id}", response_model=TableRead)
def get_table(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TableRead:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return table


@router.get("/{table_id}/snapshots", response_model=list[SnapshotRead])
def list_snapshots(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[SnapshotRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_snapshots(table_id)


@router.get("/{table_id}/refs", response_model=list[TableRefRead])
def list_refs(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[TableRefRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_refs(table_id)


@router.get("/{table_id}/schema", response_model=list[SchemaVersionRead])
def list_schema_versions(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[SchemaVersionRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_schema_versions(table_id)
