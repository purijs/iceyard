from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.iceberg.schemas import (
    MetadataSyncRunRead,
    NamespaceRead,
    PartitionSpecRead,
    RowPreviewRequest,
    SchemaVersionRead,
    SnapshotRead,
    SortOrderRead,
    TableIndexRefreshRequest,
    TableIndexRefreshResult,
    TableMetadataRead,
    TablePreviewRead,
    TableRead,
    TableRefRead,
)
from iceyard_api.iceberg.service import IcebergIndexService
from iceyard_api.rbac.dependencies import require_permission

router = APIRouter(prefix="/tables", tags=["tables"])
catalog_router = APIRouter(prefix="/catalogs", tags=["catalogs"])


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
        force=payload.force,
    )
    AuditService(session).record(
        action="tables.metadata.sync",
        resource_type="catalog_connection",
        resource_id=payload.catalog_connection_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state=result,
    )
    session.commit()
    return TableIndexRefreshResult.model_validate(result)


@catalog_router.post("/{catalog_connection_id}/sync", response_model=TableIndexRefreshResult)
def sync_catalog_metadata(
    catalog_connection_id: str,
    payload: TableIndexRefreshRequest | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> TableIndexRefreshResult:
    body = payload or TableIndexRefreshRequest(catalog_connection_id=catalog_connection_id)
    result = IcebergIndexService(session).sync_catalog_metadata(
        current_user.workspace_id,
        catalog_connection_id,
        force=body.force,
    )
    AuditService(session).record(
        action="catalog.metadata.sync",
        resource_type="catalog_connection",
        resource_id=catalog_connection_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state=result,
    )
    session.commit()
    return TableIndexRefreshResult.model_validate(result)


@catalog_router.get("/{catalog_connection_id}/database-schema")
def get_catalog_database_schema(
    catalog_connection_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> dict[str, object]:
    return IcebergIndexService(session).database_schema(
        current_user.workspace_id, catalog_connection_id
    )


@router.get("/sync-runs", response_model=list[MetadataSyncRunRead])
def list_sync_runs(
    catalog_connection_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> list[MetadataSyncRunRead]:
    return IcebergIndexService(session).list_sync_runs(
        current_user.workspace_id, catalog_connection_id
    )


@router.get("/sync-runs/{sync_run_id}", response_model=MetadataSyncRunRead)
def get_sync_run(
    sync_run_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> MetadataSyncRunRead:
    run = IcebergIndexService(session).get_sync_run(current_user.workspace_id, sync_run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found.")
    return run


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


@router.get(
    "/{table_id}/metadata",
    response_model=TableMetadataRead,
    response_model_by_alias=False,
)
def get_table_metadata(
    table_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> TableMetadataRead:
    service = IcebergIndexService(session)
    table = service.get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    metadata_log = [
        {
            "timestamp_ms": item.timestamp_ms,
            "metadata_file": item.metadata_file,
        }
        for item in service.list_metadata_log(table.id)
    ]
    snapshot_log = [
        {
            "timestamp_ms": item.timestamp_ms,
            "snapshot_id": item.snapshot_id,
        }
        for item in service.list_snapshot_log(table.id)
    ]
    return TableMetadataRead(
        table=TableRead.model_validate(table),
        snapshots=[SnapshotRead.model_validate(item) for item in service.list_snapshots(table.id)],
        refs=[TableRefRead.model_validate(item) for item in service.list_refs(table.id)],
        schemas=[
            SchemaVersionRead.model_validate(item)
            for item in service.list_schema_versions(table.id)
        ],
        partitions=[
            PartitionSpecRead.model_validate(item)
            for item in service.list_partition_specs(table.id)
        ],
        sort_orders=[
            SortOrderRead.model_validate(item)
            for item in service.list_sort_orders(table.id)
        ],
        metadata_log=metadata_log if isinstance(metadata_log, list) else [],
        snapshot_log=snapshot_log,
        metrics=table.metrics,
    )


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


@router.post("/{table_id}/row-preview", response_model=TablePreviewRead)
def preview_table_rows(
    table_id: str,
    payload: RowPreviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("tables.read")),
) -> TablePreviewRead:
    service = IcebergIndexService(session)
    table = service.get_table(current_user.workspace_id, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    preview = service.preview_rows(
        table,
        limit=payload.limit,
        selected_fields=tuple(payload.selected_fields),
        snapshot_id=payload.snapshot_id,
    )
    return TablePreviewRead(
        resource="rows",
        query=str(preview.get("query") or f"SELECT * FROM {table.name} LIMIT {payload.limit}"),
        columns=[str(column) for column in preview.get("columns", [])],
        rows=preview.get("rows", []),
        rate_limited=True,
        masked_columns=[],
    )
