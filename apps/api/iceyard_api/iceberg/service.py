from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from iceyard_api.core.time import utcnow
from iceyard_api.db.models import (
    CatalogConnection,
    IcebergTable,
    Namespace,
    PartitionSpec,
    SchemaVersion,
    Snapshot,
    SortOrder,
    TableRef,
)


class IcebergIndexService:
    def __init__(self, session: Session):
        self.session = session

    def refresh_index(
        self, workspace_id: str, catalog_connection_id: str | None = None
    ) -> dict[str, object]:
        if catalog_connection_id:
            catalog = self.session.scalar(
                select(CatalogConnection).where(
                    CatalogConnection.workspace_id == workspace_id,
                    CatalogConnection.id == catalog_connection_id,
                )
            )
            if not catalog:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Catalog connection not found."
                )
        refreshed_at = utcnow()
        table_stmt = (
            select(IcebergTable)
            .join(Namespace, IcebergTable.namespace_id == Namespace.id)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                IcebergTable.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
            )
        )
        if catalog_connection_id:
            table_stmt = table_stmt.where(Namespace.catalog_connection_id == catalog_connection_id)
        tables = list(self.session.scalars(table_stmt))
        for table in tables:
            table.indexed_at = refreshed_at
        namespace_stmt = select(func.count(Namespace.id)).where(
            Namespace.workspace_id == workspace_id
        )
        if catalog_connection_id:
            namespace_stmt = namespace_stmt.where(
                Namespace.catalog_connection_id == catalog_connection_id
            )
        self.session.flush()
        return {
            "catalog_connection_id": catalog_connection_id,
            "namespace_count": int(self.session.scalar(namespace_stmt) or 0),
            "table_count": len(tables),
            "refreshed_at": refreshed_at,
        }

    def list_namespaces(
        self, workspace_id: str, catalog_connection_id: str | None = None
    ) -> list[Namespace]:
        stmt = (
            select(Namespace)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                Namespace.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
            )
        )
        if catalog_connection_id:
            stmt = stmt.where(Namespace.catalog_connection_id == catalog_connection_id)
        return list(self.session.scalars(stmt.order_by(Namespace.name.asc())))

    def list_tables(
        self,
        workspace_id: str,
        *,
        environment_id: str | None = None,
        catalog_connection_id: str | None = None,
        namespace_id: str | None = None,
        min_health: int | None = None,
        max_health: int | None = None,
    ) -> list[IcebergTable]:
        stmt = (
            select(IcebergTable)
            .join(Namespace, IcebergTable.namespace_id == Namespace.id)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                IcebergTable.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
            )
        )
        if environment_id:
            stmt = stmt.where(IcebergTable.environment_id == environment_id)
        if catalog_connection_id:
            stmt = stmt.where(Namespace.catalog_connection_id == catalog_connection_id)
        if namespace_id:
            stmt = stmt.where(IcebergTable.namespace_id == namespace_id)
        if min_health is not None:
            stmt = stmt.where(IcebergTable.health_score >= min_health)
        if max_health is not None:
            stmt = stmt.where(IcebergTable.health_score <= max_health)
        return list(
            self.session.scalars(
                stmt.order_by(IcebergTable.health_score.asc(), IcebergTable.name.asc())
            )
        )

    def get_table(self, workspace_id: str, table_id: str) -> IcebergTable | None:
        return self.session.scalar(
            select(IcebergTable)
            .join(Namespace, IcebergTable.namespace_id == Namespace.id)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                IcebergTable.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
                IcebergTable.id == table_id,
            )
        )

    def list_snapshots(self, table_id: str) -> list[Snapshot]:
        return list(
            self.session.scalars(
                select(Snapshot)
                .where(Snapshot.table_id == table_id)
                .order_by(Snapshot.committed_at.desc())
            )
        )

    def list_refs(self, table_id: str) -> list[TableRef]:
        return list(self.session.scalars(select(TableRef).where(TableRef.table_id == table_id)))

    def list_schema_versions(self, table_id: str) -> list[SchemaVersion]:
        return list(
            self.session.scalars(
                select(SchemaVersion)
                .where(SchemaVersion.table_id == table_id)
                .order_by(SchemaVersion.schema_id)
            )
        )

    def list_partition_specs(self, table_id: str) -> list[PartitionSpec]:
        return list(
            self.session.scalars(
                select(PartitionSpec)
                .where(PartitionSpec.table_id == table_id)
                .order_by(PartitionSpec.spec_id)
            )
        )

    def list_sort_orders(self, table_id: str) -> list[SortOrder]:
        return list(
            self.session.scalars(
                select(SortOrder).where(SortOrder.table_id == table_id).order_by(SortOrder.order_id)
            )
        )

    def preview_table_resource(self, table: IcebergTable, resource: str) -> dict[str, object]:
        resource = resource.lower().replace("-", "_")
        table_name = table.name
        schema = self.list_schema_versions(table.id)
        latest_schema = schema[-1].schema if schema else {"fields": []}
        row_columns = [
            str(field.get("name"))
            for field in latest_schema.get("fields", [])
            if isinstance(field, dict) and field.get("name")
        ]
        resources = {
            "rows": {
                "query": f"SELECT * FROM {table_name} LIMIT 5",
                "columns": row_columns,
                "rows": [],
                "masked_columns": [],
            },
            "files": {
                "query": f"SELECT * FROM {table_name}.files LIMIT 5",
                "columns": [
                    "content",
                    "file_path",
                    "record_count",
                    "file_size_in_bytes",
                    "partition",
                ],
                "rows": [],
                "masked_columns": ["file_path"],
            },
            "manifests": {
                "query": f"SELECT * FROM {table_name}.manifests LIMIT 5",
                "columns": [
                    "manifest_path",
                    "added_files_count",
                    "existing_files_count",
                    "deleted_files_count",
                ],
                "rows": [],
                "masked_columns": ["manifest_path"],
            },
            "snapshots": {
                "query": f"SELECT * FROM {table_name}.snapshots LIMIT 5",
                "columns": ["snapshot_id", "operation", "committed_at", "summary"],
                "rows": [
                    {
                        "snapshot_id": snapshot.snapshot_id,
                        "operation": snapshot.operation,
                        "committed_at": snapshot.committed_at.isoformat(),
                        "summary": snapshot.summary,
                    }
                    for snapshot in self.list_snapshots(table.id)[:5]
                ],
                "masked_columns": [],
            },
            "partitions": {
                "query": f"SELECT * FROM {table_name}.partitions LIMIT 5",
                "columns": ["partition", "record_count", "file_count", "total_size"],
                "rows": [],
                "masked_columns": [],
            },
            "refs": {
                "query": f"SELECT * FROM {table_name}.refs",
                "columns": ["type", "name", "snapshot_id", "retention"],
                "rows": [
                    {
                        "type": ref.ref_type,
                        "name": ref.name,
                        "snapshot_id": ref.snapshot_id,
                        "retention": ref.retention,
                    }
                    for ref in self.list_refs(table.id)
                ],
                "masked_columns": [],
            },
            "position_deletes": {
                "query": f"SELECT * FROM {table_name}.position_deletes LIMIT 5",
                "columns": ["delete_file_path", "deleted_rows", "referenced_data_file"],
                "rows": [],
                "masked_columns": ["delete_file_path"],
            },
        }
        selected = resources.get(resource, resources["rows"])
        return {
            "resource": resource if resource in resources else "rows",
            "rate_limited": True,
            **selected,
        }
