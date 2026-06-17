import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from iceyard_api.core.time import utcnow
from iceyard_api.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


class Workspace(Base):
    __tablename__ = "workspace"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_service_account: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped[Workspace] = relationship()
    roles: Mapped[list["Role"]] = relationship(secondary="user_role", back_populates="users")


class Role(Base):
    __tablename__ = "role"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_role_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(secondary="user_role", back_populates="roles")


class Permission(Base):
    __tablename__ = "permission"
    __table_args__ = (UniqueConstraint("role_id", "action", name="uq_permission_role_action"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    role_id: Mapped[str] = mapped_column(ForeignKey("role.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_selector: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    role: Mapped[Role] = relationship(back_populates="permissions")


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("role.id"), primary_key=True)


class SessionToken(Base):
    __tablename__ = "session_token"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspace.id"), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class Environment(Base):
    __tablename__ = "environment"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_environment_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    posture: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecretReference(Base):
    __tablename__ = "secret_reference"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_secret_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    reference: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def has_reference(self) -> bool:
        return bool(self.reference)


class CatalogConnection(Base):
    __tablename__ = "catalog_connection"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_catalog_connection_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environment.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    catalog_type: Mapped[str] = mapped_column(String(40), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    warehouse: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auth_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    environment: Mapped[Environment] = relationship()


class ObjectStoreConnection(Base):
    __tablename__ = "object_store_connection"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environment.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    store_type: Mapped[str] = mapped_column(String(40), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    auth_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ComputeBackend(Base):
    __tablename__ = "compute_backend"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environment.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    backend_type: Mapped[str] = mapped_column(String(40), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Namespace(Base):
    __tablename__ = "namespace"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    catalog_connection_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_connection.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    catalog_connection: Mapped[CatalogConnection] = relationship()


class IcebergTable(Base):
    __tablename__ = "iceberg_table"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    namespace_id: Mapped[str] = mapped_column(ForeignKey("namespace.id"), nullable=False)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environment.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(700), nullable=False)
    format_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_snapshot_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    health_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    namespace: Mapped[Namespace] = relationship()
    environment: Mapped[Environment] = relationship()
    metrics: Mapped["TableMetrics"] = relationship(back_populates="table", uselist=False)
    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="table")
    refs: Mapped[list["TableRef"]] = relationship(back_populates="table")


class TableMetrics(Base):
    __tablename__ = "table_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(
        ForeignKey("iceberg_table.id"), unique=True, nullable=False
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    data_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    delete_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    small_file_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_compaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    table: Mapped[IcebergTable] = relationship(back_populates="metrics")


class Snapshot(Base):
    __tablename__ = "snapshot"
    __table_args__ = (
        UniqueConstraint("table_id", "snapshot_id", name="uq_snapshot_table_snapshot_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("iceberg_table.id"), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_snapshot_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    table: Mapped[IcebergTable] = relationship(back_populates="snapshots")


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("iceberg_table.id"), nullable=False)
    schema_id: Mapped[int] = mapped_column(Integer, nullable=False)
    schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PartitionSpec(Base):
    __tablename__ = "partition_spec"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("iceberg_table.id"), nullable=False)
    spec_id: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SortOrder(Base):
    __tablename__ = "sort_order"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("iceberg_table.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TableRef(Base):
    __tablename__ = "table_ref"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("iceberg_table.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    ref_type: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(80), nullable=False)
    retention: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    table: Mapped[IcebergTable] = relationship(back_populates="refs")


class OperationDescriptorModel(Base):
    __tablename__ = "operation_descriptor"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OperationRequest(Base):
    __tablename__ = "operation_request"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    table_id: Mapped[str | None] = mapped_column(ForeignKey("iceberg_table.id"), nullable=True)
    operation_id: Mapped[str] = mapped_column(String(120), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    compiled_command: Mapped[str] = mapped_column(Text, nullable=False)
    safety_class: Mapped[str] = mapped_column(String(40), nullable=False)
    dry_run_status: Mapped[str] = mapped_column(String(40), nullable=False)
    gate_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    operation_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("operation_request.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRun(Base):
    __tablename__ = "job_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("job.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    engine: Mapped[str] = mapped_column(String(80), nullable=False)
    compiled_command: Mapped[str] = mapped_column(Text, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pre_op_restore_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobLog(Base):
    __tablename__ = "job_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_run_id: Mapped[str] = mapped_column(ForeignKey("job_run.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_request"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    operation_request_id: Mapped[str] = mapped_column(
        ForeignKey("operation_request.id"), nullable=False
    )
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    compiled_command_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RestorePoint(Base):
    __tablename__ = "restore_point"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("iceberg_table.id"), nullable=False)
    operation_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("operation_request.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(80), nullable=False)
    retention: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
