import os
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

os.environ.setdefault("ICEYARD_DATABASE_URL", "sqlite:///./test_iceyard.db")
os.environ.setdefault("ICEYARD_ENVIRONMENT", "test")
# Tests exercise the full feature surface; gating itself is covered in test_editions.
os.environ.setdefault("ICEYARD_EDITION", "enterprise")

from iceyard_api.connections.service import capabilities_for_catalog
from iceyard_api.core.time import utcnow
from iceyard_api.db.base import Base
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
    User,
)
from iceyard_api.db.session import SessionLocal, engine
from iceyard_api.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        _seed_test_index()
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _seed_test_index() -> None:
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == "admin"))
        if not user:
            return
        dev = Environment(
            workspace_id=user.workspace_id,
            name="dev",
            kind="dev",
            region="eu-central-1",
            posture={"approval_required": False, "protected_branches": ["main"]},
        )
        session.add(dev)
        session.flush()
        catalog = CatalogConnection(
            workspace_id=user.workspace_id,
            environment_id=dev.id,
            name="catalog-a",
            catalog_type="jdbc",
            endpoint="jdbc:postgresql://catalog-db:5432/iceberg",
            warehouse="s3://warehouse-a",
            settings={},
            capabilities=capabilities_for_catalog("jdbc"),
        )
        session.add(catalog)
        session.flush()
        namespaces: dict[str, Namespace] = {}
        for name in ("analytics", "sales"):
            namespace = Namespace(
                workspace_id=user.workspace_id,
                catalog_connection_id=catalog.id,
                name=name,
            )
            session.add(namespace)
            session.flush()
            namespaces[name] = namespace
        _add_test_table(
            session,
            workspace_id=user.workspace_id,
            environment_id=dev.id,
            namespace=namespaces["analytics"],
            name="analytics.events",
            location="s3://warehouse-a/analytics/events",
            health_score=72,
            small_file_ratio=0.61,
            delete_file_count=220,
            snapshot_count=64,
            owner="data-platform",
        )
        _add_test_table(
            session,
            workspace_id=user.workspace_id,
            environment_id=dev.id,
            namespace=namespaces["sales"],
            name="sales.orders",
            location="s3://warehouse-a/sales/orders",
            health_score=48,
            small_file_ratio=0.78,
            delete_file_count=980,
            snapshot_count=210,
            owner="sales-eng",
        )
        session.commit()


def _add_test_table(
    session,
    *,
    workspace_id: str,
    environment_id: str,
    namespace: Namespace,
    name: str,
    location: str,
    health_score: int,
    small_file_ratio: float,
    delete_file_count: int,
    snapshot_count: int,
    owner: str,
) -> None:
    now = utcnow()
    table = IcebergTable(
        workspace_id=workspace_id,
        namespace_id=namespace.id,
        environment_id=environment_id,
        name=name,
        location=location,
        format_version=2,
        current_snapshot_id="8364920157712043",
        owner=owner,
        properties={"write.format.default": "parquet", "format-version": "2"},
        health_score=health_score,
    )
    session.add(table)
    session.flush()
    session.add(
        TableMetrics(
            table_id=table.id,
            file_count=412,
            data_size_bytes=320_000_000_000,
            delete_file_count=delete_file_count,
            snapshot_count=snapshot_count,
            manifest_count=220,
            small_file_ratio=small_file_ratio,
            last_commit_at=now - timedelta(hours=12),
            last_compaction_at=None,
        )
    )
    snapshots = [
        ("8364920157712043", "append", {"added_files": 142, "removed_files": 0}),
        ("7588120049923847", "rewrite", {"added_files": 12, "removed_files": 480}),
        ("7401093847710022", "append", {"added_files": 210, "removed_files": 0}),
    ]
    for offset, (snapshot_id, operation, summary) in enumerate(snapshots):
        session.add(
            Snapshot(
                table_id=table.id,
                snapshot_id=snapshot_id,
                parent_snapshot_id=None,
                operation=operation,
                summary=summary,
                committed_at=now - timedelta(days=offset + 1),
            )
        )
    session.add(
        SchemaVersion(
            table_id=table.id,
            schema_id=1,
            schema={
                "fields": [
                    {"id": 1, "name": "event_id", "type": "long", "required": True},
                    {"id": 2, "name": "user_id", "type": "long", "required": True},
                    {"id": 3, "name": "event_type", "type": "string", "required": True},
                    {"id": 4, "name": "occurred_at", "type": "timestamptz", "required": True},
                ]
            },
        )
    )
    session.add(
        PartitionSpec(
            table_id=table.id,
            spec_id=1,
            spec={"fields": [{"source": "occurred_at", "transform": "days"}]},
            is_current=True,
        )
    )
    session.add(
        SortOrder(
            table_id=table.id,
            order_id=1,
            fields=[{"source": "user_id", "direction": "asc"}],
            is_current=True,
        )
    )
    for ref_type, ref_name, snapshot_id, retention in (
        ("branch", "main", "8364920157712043", {"type": "default"}),
        ("tag", "release", "7401093847710022", {"retain": "30d"}),
        ("tag", "restore", "7588120049923847", {"pinned": True}),
    ):
        session.add(
            TableRef(
                table_id=table.id,
                name=ref_name,
                ref_type=ref_type,
                snapshot_id=snapshot_id,
                retention=retention,
            )
        )
