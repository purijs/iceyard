from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SafetyClass = Literal["READ", "METADATA", "WRITE", "REWRITE", "DESTRUCTIVE", "MIGRATION_ADMIN"]


class OperationParam(BaseModel):
    name: str
    type: str
    required: bool = False
    default: object | None = None
    options: list[str] | None = None
    placeholder: str | None = None
    advanced: bool = False
    show_if: dict[str, object] | None = None


class OperationDescriptor(BaseModel):
    id: str
    name: str
    description: str
    category: str
    safety_class: SafetyClass
    supported_engines: list[str]
    required_permissions: list[str]
    params: list[OperationParam]
    sql_template: str
    dry_run_supported: bool
    approval_required: bool
    restore_point_required: bool
    gates: list[str]
    docs_url: str | None = None
    scope: Literal[
        "catalog",
        "namespace",
        "table",
        "none",
        "governance",
        "maintenance",
        "migration",
    ] = "table"
    requires_table: bool = True
    requires_catalog: bool = False
    writes_data: bool = False
    writes_metadata: bool = False
    native_metadata: bool = False
    native_preview: bool = False
    spark_required: bool = False
    trino_supported: bool = False
    flink_supported: bool = False


class OperationCategoryRead(BaseModel):
    name: str
    operation_count: int
    safety_classes: list[SafetyClass]


class OperationDescriptorSeedResult(BaseModel):
    inserted: int
    updated: int


class OperationDryRunRequest(BaseModel):
    operation_id: str
    table_id: str | None = None
    engine: str | None = None
    params: dict[str, object] = Field(default_factory=dict)


class GateResult(BaseModel):
    id: str
    label: str
    status: Literal["passed", "blocked", "pending"]
    detail: str


class OperationDryRunRead(BaseModel):
    id: str
    operation_id: str
    table_id: str | None
    compiled_command: str
    safety_class: SafetyClass
    gate_results: list[GateResult]
    metrics: dict[str, object]
    created_at: datetime


class OperationExecuteRequest(BaseModel):
    dry_run_id: str
    idempotency_key: str | None = None
    confirmation: str | None = None


class OperationExecuteRead(BaseModel):
    status: Literal["queued", "requires_approval", "blocked"]
    job_id: str | None = None
    approval_request_id: str | None = None
    message: str
