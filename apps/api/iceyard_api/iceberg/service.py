from datetime import timedelta

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
                    snapshot_id="7588120049923847",
                    parent_snapshot_id=None,
                    operation="rewrite",
                    summary={"added_files": 12, "removed_files": 480, "bytes": -400_000_000},
                    committed_at=now - timedelta(days=7),
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
                            {"id": 4, "name": "payload", "type": "variant", "required": False},
                            {
                                "id": 5,
                                "name": "occurred_at",
                                "type": "timestamptz",
                                "required": True,
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
                    name="pre-compaction-restore",
                    ref_type="tag",
                    snapshot_id="7588120049923847",
                    retention={"pinned": True},
                )
            )
        self.session.flush()
        self.session.commit()

    def list_tables(self, workspace_id: str) -> list[IcebergTable]:
        self.ensure_mock_data(workspace_id)
        return list(
            self.session.scalars(
                select(IcebergTable)
                .where(IcebergTable.workspace_id == workspace_id)
                .order_by(IcebergTable.health_score.asc(), IcebergTable.name.asc())
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
