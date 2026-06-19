import os
import tempfile
from contextlib import suppress

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
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
    TableMetrics,
    TableRef,
)


class IcebergIndexService:
    def __init__(self, session: Session):
        self.session = session

    def refresh_index(
        self, workspace_id: str, catalog_connection_id: str | None = None
    ) -> dict[str, object]:
        discovered = 0
        removed = 0
        mode = "refresh"
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
            if catalog.catalog_type == "jdbc":
                sync = self._sync_jdbc_catalog(workspace_id, catalog)
                discovered = sync["discovered"]
                removed = sync["removed"]
                mode = "jdbc-discovery"
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
            "discovered_table_count": discovered,
            "removed_table_count": removed,
            "mode": mode,
            "refreshed_at": refreshed_at,
        }

    def _sync_jdbc_catalog(self, workspace_id: str, catalog: CatalogConnection) -> dict[str, int]:
        if not catalog.endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JDBC URI is missing.",
            )
        uri = catalog.endpoint.removeprefix("jdbc:")
        if not uri.startswith(("postgresql://", "postgres://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Live table sync currently supports PostgreSQL JDBC catalogs.",
            )

        settings = catalog.settings if isinstance(catalog.settings, dict) else {}
        auth = (
            settings.get("catalog_auth")
            if isinstance(settings.get("catalog_auth"), dict)
            else {}
        )
        secret = self._read_inline_secret(
            workspace_id, self._auth_secret_id(auth, catalog.auth_ref)
        )
        rows = self._read_postgres_jdbc_catalog_rows(
            uri=uri,
            username=str(auth.get("username") or secret.get("username") or ""),
            password=secret.get("password"),
            jdbc_options=(
                settings.get("jdbc_options")
                if isinstance(settings.get("jdbc_options"), dict)
                else {}
            ),
        )
        refreshed_at = utcnow()
        namespace_ids: dict[str, str] = {}
        for namespace_name in sorted({row["namespace"] for row in rows}):
            namespace = self.session.scalar(
                select(Namespace).where(
                    Namespace.workspace_id == workspace_id,
                    Namespace.catalog_connection_id == catalog.id,
                    Namespace.name == namespace_name,
                )
            )
            if not namespace:
                namespace = Namespace(
                    workspace_id=workspace_id,
                    catalog_connection_id=catalog.id,
                    name=namespace_name,
                )
                self.session.add(namespace)
                self.session.flush()
            namespace_ids[namespace_name] = namespace.id

        seen_table_names: set[str] = set()
        discovered = 0
        for row in rows:
            table_name = f"{row['namespace']}.{row['table_name']}"
            seen_table_names.add(table_name)
            namespace_id = namespace_ids[row["namespace"]]
            metadata_location = row["metadata_location"]
            properties = {
                "catalog_name": row["catalog_name"],
                "iceberg_type": row["iceberg_type"],
                "metadata_location": metadata_location,
                "previous_metadata_location": row["previous_metadata_location"],
                "sync_source": "jdbc_catalog",
            }
            table = self.session.scalar(
                select(IcebergTable).where(
                    IcebergTable.workspace_id == workspace_id,
                    IcebergTable.namespace_id == namespace_id,
                    IcebergTable.name == table_name,
                )
            )
            if not table:
                table = IcebergTable(
                    workspace_id=workspace_id,
                    namespace_id=namespace_id,
                    environment_id=catalog.environment_id,
                    name=table_name,
                    location=self._table_location_from_metadata(metadata_location),
                    format_version=2,
                    current_snapshot_id=None,
                    owner=row["owner"],
                    properties=properties,
                    indexed_at=refreshed_at,
                )
                self.session.add(table)
                self.session.flush()
                self.session.add(
                    TableMetrics(
                        table_id=table.id,
                        file_count=0,
                        data_size_bytes=0,
                        delete_file_count=0,
                        snapshot_count=0,
                        manifest_count=0,
                        small_file_ratio=0,
                        last_commit_at=None,
                        last_compaction_at=None,
                    )
                )
                discovered += 1
            else:
                table.environment_id = catalog.environment_id
                table.location = self._table_location_from_metadata(metadata_location)
                table.owner = row["owner"] or table.owner
                table.properties = {**(table.properties or {}), **properties}
                table.indexed_at = refreshed_at

        existing_tables = list(
            self.session.scalars(
                select(IcebergTable)
                .join(Namespace, IcebergTable.namespace_id == Namespace.id)
                .where(
                    IcebergTable.workspace_id == workspace_id,
                    Namespace.catalog_connection_id == catalog.id,
                )
            )
        )
        stale_ids = [table.id for table in existing_tables if table.name not in seen_table_names]
        if stale_ids:
            self.session.execute(delete(TableRef).where(TableRef.table_id.in_(stale_ids)))
            self.session.execute(delete(SortOrder).where(SortOrder.table_id.in_(stale_ids)))
            self.session.execute(delete(PartitionSpec).where(PartitionSpec.table_id.in_(stale_ids)))
            self.session.execute(delete(SchemaVersion).where(SchemaVersion.table_id.in_(stale_ids)))
            self.session.execute(delete(Snapshot).where(Snapshot.table_id.in_(stale_ids)))
            self.session.execute(delete(TableMetrics).where(TableMetrics.table_id.in_(stale_ids)))
            self.session.execute(delete(IcebergTable).where(IcebergTable.id.in_(stale_ids)))

        self.session.flush()
        return {"discovered": discovered, "removed": len(stale_ids)}

    def _read_postgres_jdbc_catalog_rows(
        self,
        *,
        uri: str,
        username: str,
        password: str | None,
        jdbc_options: dict[str, object],
    ) -> list[dict[str, str | None]]:
        try:
            import psycopg
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="psycopg is required for PostgreSQL JDBC catalog sync.",
            ) from exc

        root_cert_path: str | None = None
        connect_kwargs: dict[str, object] = {"connect_timeout": 10}
        if username:
            connect_kwargs["user"] = username
        if password:
            connect_kwargs["password"] = password.strip()
        sslmode = jdbc_options.get("sslmode")
        if isinstance(sslmode, str) and sslmode:
            connect_kwargs["sslmode"] = sslmode
        root_cert = jdbc_options.get("ssl_root_cert")
        if isinstance(root_cert, str) and root_cert.strip():
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="iceyard-pg-ca-",
                suffix=".pem",
                delete=False,
            ) as cert_file:
                cert_file.write(root_cert)
                root_cert_path = cert_file.name
            connect_kwargs["sslrootcert"] = root_cert_path
        elif sslmode == "require":
            connect_kwargs["sslrootcert"] = os.path.join(
                tempfile.gettempdir(), "iceyard-no-postgres-root-ca.pem"
            )
        try:
            with (
                psycopg.connect(uri, **connect_kwargs) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    """
                    select
                      t.catalog_name,
                      t.table_namespace,
                      t.table_name,
                      t.metadata_location,
                      t.previous_metadata_location,
                      t.iceberg_type,
                      max(case when p.property_key = 'owner' then p.property_value end) as owner
                    from public.iceberg_tables t
                    left join public.iceberg_namespace_properties p
                      on p.catalog_name = t.catalog_name
                     and p.namespace = t.table_namespace
                    where coalesce(t.iceberg_type, 'TABLE') = 'TABLE'
                    group by
                      t.catalog_name,
                      t.table_namespace,
                      t.table_name,
                      t.metadata_location,
                      t.previous_metadata_location,
                      t.iceberg_type
                    order by t.table_namespace, t.table_name
                    """
                )
                return [
                    {
                        "catalog_name": row[0],
                        "namespace": row[1],
                        "table_name": row[2],
                        "metadata_location": row[3],
                        "previous_metadata_location": row[4],
                        "iceberg_type": row[5],
                        "owner": row[6],
                    }
                    for row in cursor.fetchall()
                    if row[1] and row[2] and row[3]
                ]
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Catalog sync failed: {exc}",
            ) from exc
        finally:
            if root_cert_path:
                with suppress(OSError):
                    os.unlink(root_cert_path)

    def _auth_secret_id(self, auth_settings: dict[str, object], auth_ref: str | None) -> str | None:
        secret_id = auth_settings.get("secret_ref_id")
        return secret_id if isinstance(secret_id, str) and secret_id else auth_ref

    def _read_inline_secret(self, workspace_id: str, secret_id: str | None) -> dict[str, str]:
        if not secret_id:
            return {}
        from iceyard_api.connections.service import ConnectionService

        return ConnectionService(self.session)._read_inline_secret(workspace_id, secret_id)

    def _table_location_from_metadata(self, metadata_location: str | None) -> str:
        if not metadata_location:
            return ""
        marker = "/metadata/"
        if marker in metadata_location:
            return metadata_location.split(marker, 1)[0]
        if "/" in metadata_location:
            return metadata_location.rsplit("/", 1)[0]
        return metadata_location

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
