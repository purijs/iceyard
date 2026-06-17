from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from iceyard_api.connections.service import capabilities_for_catalog
from iceyard_api.core.time import utcnow
from iceyard_api.db.models import (
    CatalogConnection,
    Environment,
    IcebergTable,
    Namespace,
    PartitionSpec,
    SchemaVersion,
    Snapshot,
    SortOrder,
    TableMetrics,
    TableRef,
)

TABLE_FIXTURES = [
    (
        "dev",
        "analytics",
        "events",
        3,
        72,
        1840,
        1_400_000_000_000,
        220,
        64,
        120,
        0.61,
        "data-platform",
    ),
    ("dev", "analytics", "sessions", 2, 91, 96, 210_000_000_000, 4, 22, 12, 0.08, "data-platform"),
    ("dev", "sales", "orders", 2, 48, 412, 320_000_000_000, 980, 210, 220, 0.78, "sales-eng"),
    ("dev", "sales", "order_items", 2, 63, 308, 540_000_000_000, 120, 88, 90, 0.41, "sales-eng"),
    ("dev", "marketing", "campaigns", 3, 88, 54, 44_000_000_000, 12, 19, 8, 0.10, "growth"),
    (
        "dev",
        "staging",
        "raw_clickstream",
        2,
        35,
        5200,
        2_100_000_000_000,
        40,
        1240,
        640,
        0.92,
        None,
    ),
    (
        "prod",
        "analytics",
        "events",
        2,
        95,
        120,
        9_600_000_000_000,
        8,
        30,
        10,
        0.05,
        "data-platform",
    ),
    (
        "prod",
        "sales",
        "order_items",
        2,
        69,
        420,
        4_100_000_000_000,
        210,
        96,
        110,
        0.38,
        "sales-eng",
    ),
    (
        "prod",
        "analytics",
        "sessions",
        2,
        90,
        140,
        1_200_000_000_000,
        10,
        28,
        12,
        0.11,
        "data-platform",
    ),
    ("prod", "sales", "orders", 2, 86, 180, 2_400_000_000_000, 60, 44, 32, 0.14, "sales-eng"),
    ("prod", "marketing", "campaigns", 2, 83, 72, 81_000_000_000, 6, 16, 7, 0.07, "growth"),
    ("prod", "finance", "ledger", 2, 81, 210, 780_000_000_000, 30, 52, 42, 0.19, "finance-eng"),
]


class IcebergIndexService:
    def __init__(self, session: Session):
        self.session = session

    def ensure_mock_data(self, workspace_id: str) -> None:
        existing = self.session.scalar(
            select(func.count(IcebergTable.id)).where(IcebergTable.workspace_id == workspace_id)
        )
        if existing:
            return
        envs: dict[str, Environment] = {}
        for env_name in {"dev", "prod"}:
            env = self.session.scalar(
                select(Environment).where(
                    Environment.workspace_id == workspace_id,
                    Environment.name == env_name,
                )
            )
            if not env:
                env = Environment(
                    workspace_id=workspace_id,
                    name=env_name,
                    kind=env_name,
                    region="eu-central-1",
                    posture={
                        "approval_required": env_name == "prod",
                        "protected_branches": ["main"],
                    },
                )
                self.session.add(env)
                self.session.flush()
            envs[env_name] = env
        catalogs: dict[str, CatalogConnection] = {}
        for env_name, env in envs.items():
            catalog = self.session.scalar(
                select(CatalogConnection).where(
                    CatalogConnection.workspace_id == workspace_id,
                    CatalogConnection.name == f"{env_name}-catalog",
                )
            )
            if not catalog:
                catalog = CatalogConnection(
                    workspace_id=workspace_id,
                    environment_id=env.id,
                    name=f"{env_name}-catalog",
                    catalog_type="jdbc",
                    endpoint=f"jdbc:postgresql://{env_name}-postgres:5432/iceberg_catalog",
                    warehouse=f"s3://{env_name}-lakehouse",
                    settings={},
                    capabilities=capabilities_for_catalog("jdbc"),
                )
                self.session.add(catalog)
                self.session.flush()
            catalogs[env_name] = catalog
        namespaces: dict[tuple[str, str], Namespace] = {}
        for env_name, namespace_name, *_ in TABLE_FIXTURES:
            key = (env_name, namespace_name)
            if key not in namespaces:
                namespace = Namespace(
                    workspace_id=workspace_id,
                    catalog_connection_id=catalogs[env_name].id,
                    name=namespace_name,
                )
                self.session.add(namespace)
                self.session.flush()
                namespaces[key] = namespace
        now = utcnow()
        for (
            env_name,
            namespace_name,
            table_name,
            format_version,
            health,
            file_count,
            data_size_bytes,
            delete_count,
            snapshot_count,
            manifest_count,
            small_file_ratio,
            owner,
        ) in TABLE_FIXTURES:
            full_name = f"{namespace_name}.{table_name}"
            table = IcebergTable(
                workspace_id=workspace_id,
                namespace_id=namespaces[(env_name, namespace_name)].id,
                environment_id=envs[env_name].id,
                name=full_name,
                location=f"s3://{env_name}-lakehouse/{namespace_name}/{table_name}",
                format_version=format_version,
                current_snapshot_id="8364920157712043",
                owner=owner,
                properties={
                    "write.format.default": "parquet",
                    "format-version": str(format_version),
                },
                health_score=health,
            )
            self.session.add(table)
            self.session.flush()
            self.session.add(
                TableMetrics(
                    table_id=table.id,
                    file_count=file_count,
                    data_size_bytes=data_size_bytes,
                    delete_file_count=delete_count,
                    snapshot_count=snapshot_count,
                    manifest_count=manifest_count,
                    small_file_ratio=small_file_ratio,
                    last_commit_at=now - timedelta(hours=12),
                    last_compaction_at=now - timedelta(days=6) if health >= 55 else None,
                )
            )
            self.session.add(
                Snapshot(
                    table_id=table.id,
                    snapshot_id="8364920157712043",
                    parent_snapshot_id="7588120049923847",
                    operation="append",
                    summary={"added_files": 142, "removed_files": 0, "bytes": 6_100_000_000},
                    committed_at=now - timedelta(days=3),
                )
            )
            self.session.add(
                Snapshot(
                    table_id=table.id,
                    snapshot_id="7711203948855120",
                    parent_snapshot_id="7610288471002934",
                    operation="append",
                    summary={"added_files": 96, "removed_files": 0, "bytes": 4_000_000_000},
                    committed_at=now - timedelta(days=3, hours=6),
                )
            )
            self.session.add(
                Snapshot(
                    table_id=table.id,
                    snapshot_id="7610288471002934",
                    parent_snapshot_id="7588120049923847",
                    operation="delete",
                    summary={"added_files": 0, "removed_files": 38, "bytes": -1_200_000_000},
                    committed_at=now - timedelta(days=4),
                )
            )
            self.session.add(
                Snapshot(
                    table_id=table.id,
                    snapshot_id="7588120049923847",
                    parent_snapshot_id=None,
                    operation="rewrite",
                    summary={"added_files": 12, "removed_files": 480, "bytes": -400_000_000},
                    committed_at=now - timedelta(days=7),
                )
            )
            self.session.add(
                Snapshot(
                    table_id=table.id,
                    snapshot_id="7401093847710022",
                    parent_snapshot_id=None,
                    operation="append",
                    summary={"added_files": 210, "removed_files": 0, "bytes": 9_400_000_000},
                    committed_at=now - timedelta(days=9),
                )
            )
            self.session.add(
                SchemaVersion(
                    table_id=table.id,
                    schema_id=1,
                    schema={
                        "fields": [
                            {"id": 1, "name": "event_id", "type": "long", "required": True},
                            {"id": 2, "name": "user_id", "type": "long", "required": True},
                            {"id": 3, "name": "event_type", "type": "string", "required": True},
                            {
                                "id": 4,
                                "name": "payload",
                                "type": "variant",
                                "required": False,
                                "note": "v3 semi-structured",
                            },
                            {
                                "id": 5,
                                "name": "device_type",
                                "type": "string",
                                "required": False,
                                "note": "Added 2026-05-30",
                            },
                            {
                                "id": 6,
                                "name": "occurred_at",
                                "type": "timestamptz",
                                "required": True,
                                "note": "Partition source",
                            },
                        ]
                    },
                )
            )
            self.session.add(
                PartitionSpec(
                    table_id=table.id,
                    spec_id=1,
                    spec={"fields": [{"source": "occurred_at", "transform": "days"}]},
                    is_current=True,
                )
            )
            self.session.add(
                SortOrder(
                    table_id=table.id,
                    order_id=1,
                    fields=[{"source": "user_id", "direction": "asc"}],
                    is_current=True,
                )
            )
            self.session.add(
                TableRef(
                    table_id=table.id,
                    name="main",
                    ref_type="branch",
                    snapshot_id="8364920157712043",
                    retention={"type": "default"},
                    is_protected=env_name == "prod",
                )
            )
            self.session.add(
                TableRef(
                    table_id=table.id,
                    name="audit-2026-06",
                    ref_type="branch",
                    snapshot_id="7711203948855120",
                    retention={"max_ref_age": "7d"},
                    is_protected=False,
                )
            )
            self.session.add(
                TableRef(
                    table_id=table.id,
                    name="release-2026.06.09",
                    ref_type="tag",
                    snapshot_id="7401093847710022",
                    retention={"retain": "30d"},
                )
            )
            self.session.add(
                TableRef(
                    table_id=table.id,
                    name="pre-compaction-restore",
                    ref_type="tag",
                    snapshot_id="7588120049923847",
                    retention={"pinned": True},
                )
            )
        self.session.flush()
        self.session.commit()

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
        self.ensure_mock_data(workspace_id)
        refreshed_at = utcnow()
        table_stmt = select(IcebergTable).where(IcebergTable.workspace_id == workspace_id)
        if catalog_connection_id:
            table_stmt = table_stmt.join(Namespace).where(
                Namespace.catalog_connection_id == catalog_connection_id
            )
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
        self.ensure_mock_data(workspace_id)
        stmt = select(Namespace).where(Namespace.workspace_id == workspace_id)
        if catalog_connection_id:
            stmt = stmt.where(Namespace.catalog_connection_id == catalog_connection_id)
        return list(self.session.scalars(stmt.order_by(Namespace.name.asc())))

    def list_tables(
        self,
        workspace_id: str,
        *,
        environment_id: str | None = None,
        namespace_id: str | None = None,
        min_health: int | None = None,
        max_health: int | None = None,
    ) -> list[IcebergTable]:
        self.ensure_mock_data(workspace_id)
        stmt = select(IcebergTable).where(IcebergTable.workspace_id == workspace_id)
        if environment_id:
            stmt = stmt.where(IcebergTable.environment_id == environment_id)
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
        self.ensure_mock_data(workspace_id)
        return self.session.scalar(
            select(IcebergTable).where(
                IcebergTable.workspace_id == workspace_id,
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
        rows = {
            "rows": {
                "query": f"SELECT * FROM {table_name} LIMIT 5",
                "columns": ["event_id", "user_id", "event_type", "device_type", "occurred_at"],
                "rows": [
                    {
                        "event_id": 4820193,
                        "user_id": 771,
                        "event_type": "page_view",
                        "device_type": "ios",
                        "occurred_at": "2026-06-14 09:40:11",
                    },
                    {
                        "event_id": 4820194,
                        "user_id": 118,
                        "event_type": "add_to_cart",
                        "device_type": "web",
                        "occurred_at": "2026-06-14 09:40:13",
                    },
                    {
                        "event_id": 4820195,
                        "user_id": 771,
                        "event_type": "checkout",
                        "device_type": "ios",
                        "occurred_at": "2026-06-14 09:40:20",
                    },
                    {
                        "event_id": 4820196,
                        "user_id": 552,
                        "event_type": "page_view",
                        "device_type": "android",
                        "occurred_at": "2026-06-14 09:40:22",
                    },
                    {
                        "event_id": 4820197,
                        "user_id": 118,
                        "event_type": "purchase",
                        "device_type": "web",
                        "occurred_at": "2026-06-14 09:40:31",
                    },
                ],
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
                "rows": [
                    {
                        "content": "data",
                        "file_path": f"{table.location}/data/00001.parquet",
                        "record_count": 181220,
                        "file_size_in_bytes": 532_800_000,
                        "partition": "2026-06-14",
                    },
                    {
                        "content": "data",
                        "file_path": f"{table.location}/data/00002.parquet",
                        "record_count": 177044,
                        "file_size_in_bytes": 518_200_000,
                        "partition": "2026-06-14",
                    },
                ],
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
                "rows": [
                    {
                        "manifest_path": f"{table.location}/metadata/manifest-0001.avro",
                        "added_files_count": 142,
                        "existing_files_count": 884,
                        "deleted_files_count": 0,
                    },
                    {
                        "manifest_path": f"{table.location}/metadata/manifest-0002.avro",
                        "added_files_count": 12,
                        "existing_files_count": 480,
                        "deleted_files_count": 38,
                    },
                ],
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
                "rows": [
                    {
                        "partition": "days(occurred_at)=2026-06-14",
                        "record_count": 2_118_420,
                        "file_count": 84,
                        "total_size": 6_100_000_000,
                    },
                    {
                        "partition": "days(occurred_at)=2026-06-13",
                        "record_count": 1_902_011,
                        "file_count": 79,
                        "total_size": 4_000_000_000,
                    },
                ],
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
                "rows": [
                    {
                        "delete_file_path": f"{table.location}/delete/00001.parquet",
                        "deleted_rows": 812,
                        "referenced_data_file": "data/00041.parquet",
                    },
                    {
                        "delete_file_path": f"{table.location}/delete/00002.parquet",
                        "deleted_rows": 128,
                        "referenced_data_file": "data/00042.parquet",
                    },
                ],
                "masked_columns": ["delete_file_path"],
            },
        }
        selected = rows.get(resource, rows["rows"])
        return {
            "resource": resource if resource in rows else "rows",
            "rate_limited": True,
            **selected,
        }
