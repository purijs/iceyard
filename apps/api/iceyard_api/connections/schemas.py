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


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=80)
    posture: dict[str, object] | None = None


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


class CatalogConnectionUpdate(BaseModel):
    environment_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    catalog_type: CatalogType | None = None
    endpoint: str | None = None
    warehouse: str | None = None
    auth_ref: str | None = None
    settings: dict[str, object] | None = None
    is_enabled: bool | None = None


class CatalogConnectionRead(CatalogConnectionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    capabilities: dict[str, object]
    is_enabled: bool
    last_tested_at: datetime | None
    created_at: datetime


class ConnectionTestComponent(BaseModel):
    name: str
    status: Literal["ok", "warning", "failed"]
    message: str


class ConnectionTestResult(BaseModel):
    connection_id: str
    status: Literal["ok", "warning", "failed"]
    message: str
    capabilities: dict[str, object] = Field(default_factory=dict)
    components: list[ConnectionTestComponent] = Field(default_factory=list)


class ObjectStoreConnectionCreate(BaseModel):
    environment_id: str
    name: str
    store_type: StoreType
    endpoint: str | None = None
    region: str | None = None
    auth_ref: str | None = None
    settings: dict[str, object] = Field(default_factory=dict)


class ObjectStoreConnectionUpdate(BaseModel):
    environment_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    store_type: StoreType | None = None
    endpoint: str | None = None
    region: str | None = None
    auth_ref: str | None = None
    settings: dict[str, object] | None = None


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


class ComputeBackendUpdate(BaseModel):
    environment_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    backend_type: ComputeType | None = None
    settings: dict[str, object] | None = None
    is_enabled: bool | None = None


class ComputeBackendRead(ComputeBackendCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    is_enabled: bool
    created_at: datetime


class SecretReferenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=80)
    reference: str = Field(min_length=1, max_length=2000)


class SecretReferenceUpdate(BaseModel):
    provider: str | None = Field(default=None, min_length=1, max_length=80)
    reference: str | None = Field(default=None, min_length=1, max_length=2000)


class SecretReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    provider: str
    has_reference: bool
    created_at: datetime
