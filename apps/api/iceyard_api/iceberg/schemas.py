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
    environment_id: str
    name: str
    location: str
    format_version: int
    current_snapshot_id: str | None
    owner: str | None
    properties: dict[str, Any]
    health_score: int
    indexed_at: datetime
    metrics: TableMetricsRead | None = None


class TableIndexRefreshRequest(BaseModel):
    catalog_connection_id: str | None = None


class TableIndexRefreshResult(BaseModel):
    catalog_connection_id: str | None
    namespace_count: int
    table_count: int
    refreshed_at: datetime


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
