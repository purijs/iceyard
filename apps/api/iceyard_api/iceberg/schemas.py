from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TableMetricsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_count: int
    data_size_bytes: int
    delete_file_count: int
    snapshot_count: int
    manifest_count: int
    small_file_ratio: float
    last_commit_at: datetime | None
    last_compaction_at: datetime | None


class TableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    namespace_id: str
    catalog_connection_id: str | None = None
    environment_id: str
    name: str
    location: str
    format_version: int
    current_snapshot_id: str | None
    table_uuid: str | None = None
    metadata_location: str | None = None
    previous_metadata_location: str | None = None
    last_sequence_number: int | None = None
    last_updated_at: datetime | None = None
    current_schema_id: int | None = None
    default_spec_id: int | None = None
    default_sort_order_id: int | None = None
    record_count: int | None = None
    owner: str | None
    properties: dict[str, Any]
    health_score: int
    indexed_at: datetime
    metrics: TableMetricsRead | None = None


class TableIndexRefreshRequest(BaseModel):
    catalog_connection_id: str | None = None
    force: bool = False


class TableIndexRefreshResult(BaseModel):
    catalog_connection_id: str | None
    namespace_count: int
    table_count: int
    discovered_table_count: int = 0
    removed_table_count: int = 0
    parsed_table_count: int = 0
    skipped_table_count: int = 0
    failed_table_count: int = 0
    mode: str = "refresh"
    sync_run_id: str | None = None
    refreshed_at: datetime
    errors: list[dict[str, str]] = []
    worker_count: int = 1
    parse_job_count: int = 0


class MetadataSyncRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    catalog_connection_id: str
    status: str
    mode: str
    started_at: datetime
    finished_at: datetime | None
    table_count: int
    discovered_table_count: int
    removed_table_count: int
    parsed_table_count: int
    skipped_table_count: int
    failed_table_count: int
    error: str | None
    stats: dict[str, Any]


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    table_id: str
    snapshot_id: str
    parent_snapshot_id: str | None
    operation: str
    summary: dict[str, Any]
    committed_at: datetime


class TableRefRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    table_id: str
    name: str
    ref_type: str
    snapshot_id: str
    retention: dict[str, Any]
    is_protected: bool


class SchemaVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    table_id: str
    schema_id: int
    table_schema: dict[str, Any] = Field(alias="schema")
    created_at: datetime


class NamespaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    catalog_connection_id: str
    name: str


class PartitionSpecRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    table_id: str
    spec_id: int
    spec: dict[str, Any]
    is_current: bool


class SortOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    table_id: str
    order_id: int
    fields: list[dict[str, Any]]
    is_current: bool


class TablePreviewRead(BaseModel):
    resource: str
    query: str
    columns: list[str]
    rows: list[dict[str, Any]]
    rate_limited: bool = True
    masked_columns: list[str] = []


class RowPreviewRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=100)
    selected_fields: list[str] = Field(default_factory=lambda: ["*"])
    snapshot_id: int | None = None


class TableMetadataRead(BaseModel):
    table: TableRead
    snapshots: list[SnapshotRead]
    refs: list[TableRefRead]
    schemas: list[SchemaVersionRead]
    partitions: list[PartitionSpecRead]
    sort_orders: list[SortOrderRead]
    metadata_log: list[dict[str, Any]]
    snapshot_log: list[dict[str, Any]]
    metrics: TableMetricsRead | None = None
