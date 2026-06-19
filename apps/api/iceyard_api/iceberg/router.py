from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.iceberg.schemas import (
    NamespaceRead,
    PartitionSpecRead,
    SchemaVersionRead,
    SnapshotRead,
    SortOrderRead,
    TableIndexRefreshRequest,
    TableIndexRefreshResult,
    TablePreviewRead,
    TableRead,
    TableRefRead,
)
from iceyard_api.iceberg.service import IcebergIndexService
from iceyard_api.rbac.dependencies import require_permission

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("", response_model=list[TableRead])
def list_tables(
    environment_id: str | None = Query(default=None),
    catalog_connection_id: str | None = Query(default=None),
    namespace_id: str | None = Query(default=None),
    min_health: int | None = Query(default=None, ge=0, le=100),
    max_health: int | None = Query(default=None, ge=0, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[TableRead]:
    return IcebergIndexService(session).list_tables(
        current_user.workspace_id,
        environment_id=environment_id,
        catalog_connection_id=catalog_connection_id,
        namespace_id=namespace_id,
        min_health=min_health,
        max_health=max_health,
    )


@router.post("/index/refresh", response_model=TableIndexRefreshResult)
def refresh_table_index(
    payload: TableIndexRefreshRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> TableIndexRefreshResult:
    result = IcebergIndexService(session).refresh_index(
        current_user.workspace_id,
        catalog_connection_id=payload.catalog_connection_id,
    )
    AuditService(session).record(
        action="tables.index.refresh",
        resource_type="catalog_connection",
        resource_id=payload.catalog_connection_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state=result,
    )
    session.commit()
    return TableIndexRefreshResult.model_validate(result)


@router.get("/namespaces", response_model=list[NamespaceRead])
def list_namespaces(
    catalog_connection_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[NamespaceRead]:
    return IcebergIndexService(session).list_namespaces(
        current_user.workspace_id,
        catalog_connection_id=catalog_connection_id,
    )


@router.get("/{table_id}", response_model=TableRead)
def get_table(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> TableRead:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return table


@router.get("/{table_id}/snapshots", response_model=list[SnapshotRead])
def list_snapshots(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[SnapshotRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_snapshots(table_id)


@router.get("/{table_id}/refs", response_model=list[TableRefRead])
def list_refs(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[TableRefRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_refs(table_id)


@router.get(
    "/{table_id}/schema",
    response_model=list[SchemaVersionRead],
    response_model_by_alias=False,
)
def list_schema_versions(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[SchemaVersionRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_schema_versions(table_id)


@router.get("/{table_id}/partitions", response_model=list[PartitionSpecRead])
def list_partition_specs(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[PartitionSpecRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_partition_specs(table_id)


@router.get("/{table_id}/sort-orders", response_model=list[SortOrderRead])
def list_sort_orders(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[SortOrderRead]:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return IcebergIndexService(session).list_sort_orders(table_id)


@router.get("/{table_id}/preview", response_model=TablePreviewRead)
def preview_table_resource(
    table_id: str,
    resource: str = Query(default="rows"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> TablePreviewRead:
    table = IcebergIndexService(session).get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return TablePreviewRead.model_validate(
        IcebergIndexService(session).preview_table_resource(table, resource)
    )
