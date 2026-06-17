from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CatalogType = Literal["rest", "glue", "nessie", "hive", "jdbc", "hadoop", "custom", "s3_tables"]
StoreType = Literal["s3", "gcs", "adls", "hdfs", "local"]
ComputeType = Literal["embedded", "spark", "trino", "flink", "duckdb", "custom"]


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="custom", max_length=40)
    region: str | None = Field(default=None, max_length=80)
    posture: dict[str, object] = Field(default_factory=dict)


class EnvironmentRead(EnvironmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    created_at: datetime


class CatalogConnectionCreate(BaseModel):
    environment_id: str
    name: str = Field(min_length=1, max_length=120)
    catalog_type: CatalogType
    endpoint: str | None = None
    warehouse: str | None = None
    auth_ref: str | None = None
    settings: dict[str, object] = Field(default_factory=dict)


class CatalogConnectionRead(CatalogConnectionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    capabilities: dict[str, object]
    is_enabled: bool
    last_tested_at: datetime | None
    created_at: datetime


class ConnectionTestResult(BaseModel):
    connection_id: str
    status: Literal["ok", "warning", "failed"]
    message: str
    capabilities: dict[str, object]


class ObjectStoreConnectionCreate(BaseModel):
    environment_id: str
    name: str
    store_type: StoreType
    endpoint: str | None = None
    region: str | None = None
    auth_ref: str | None = None
    settings: dict[str, object] = Field(default_factory=dict)


class ObjectStoreConnectionRead(ObjectStoreConnectionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    created_at: datetime


class ComputeBackendCreate(BaseModel):
    environment_id: str
    name: str
    backend_type: ComputeType
    settings: dict[str, object] = Field(default_factory=dict)


class ComputeBackendRead(ComputeBackendCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    is_enabled: bool
    created_at: datetime
