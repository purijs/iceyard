from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    operation_request_id: str | None
    operation_id: str | None = None
    table_id: str | None = None
    table_name: str | None = None
    environment_id: str | None = None
    catalog_connection_id: str | None = None
    kind: str
    status: str
    correlation_id: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class JobRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    status: str
    engine: str
    compiled_command: str
    dry_run: bool
    pre_op_restore_ref: str | None
    started_at: datetime | None
    ended_at: datetime | None
    metrics: dict[str, object]
    error: str | None


class JobLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_run_id: str
    level: str
    message: str
    created_at: datetime
