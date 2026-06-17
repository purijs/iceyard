"""initial schema"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "app_user",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_service_account", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "role",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_role_workspace_name"),
    )
    op.create_table(
        "permission",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("role_id", sa.String(length=36), sa.ForeignKey("role.id"), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_selector", sa.JSON(), nullable=False),
        sa.UniqueConstraint("role_id", "action", name="uq_permission_role_action"),
    )
    op.create_table(
        "user_role",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("role_id", sa.String(length=36), sa.ForeignKey("role.id"), primary_key=True),
    )
    op.create_table(
        "session_token",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=True),
        sa.Column("actor_id", sa.String(length=36), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    op.create_table(
        "environment",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=True),
        sa.Column("posture", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_environment_workspace_name"),
    )
    op.create_table(
        "secret_reference",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("reference", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_secret_workspace_name"),
    )
    op.create_table(
        "catalog_connection",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("environment_id", sa.String(length=36), sa.ForeignKey("environment.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("catalog_type", sa.String(length=40), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=True),
        sa.Column("warehouse", sa.String(length=500), nullable=True),
        sa.Column("auth_ref", sa.String(length=500), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_catalog_connection_workspace_name"),
    )
    op.create_table(
        "object_store_connection",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("environment_id", sa.String(length=36), sa.ForeignKey("environment.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("store_type", sa.String(length=40), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=True),
        sa.Column("region", sa.String(length=80), nullable=True),
        sa.Column("auth_ref", sa.String(length=500), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "compute_backend",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("environment_id", sa.String(length=36), sa.ForeignKey("environment.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("backend_type", sa.String(length=40), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "namespace",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("catalog_connection_id", sa.String(length=36), sa.ForeignKey("catalog_connection.id"), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "iceberg_table",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("namespace_id", sa.String(length=36), sa.ForeignKey("namespace.id"), nullable=False),
        sa.Column("environment_id", sa.String(length=36), sa.ForeignKey("environment.id"), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False, index=True),
        sa.Column("location", sa.String(length=700), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("current_snapshot_id", sa.String(length=80), nullable=True),
        sa.Column("owner", sa.String(length=160), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "table_metrics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False, unique=True),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("data_size_bytes", sa.Integer(), nullable=False),
        sa.Column("delete_file_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_count", sa.Integer(), nullable=False),
        sa.Column("manifest_count", sa.Integer(), nullable=False),
        sa.Column("small_file_ratio", sa.Float(), nullable=False),
        sa.Column("last_commit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_compaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "snapshot",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("parent_snapshot_id", sa.String(length=80), nullable=True),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("table_id", "snapshot_id", name="uq_snapshot_table_snapshot_id"),
    )
    op.create_table(
        "schema_version",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("schema_id", sa.Integer(), nullable=False),
        sa.Column("schema", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "partition_spec",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("spec_id", sa.Integer(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "sort_order",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "table_ref",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("ref_type", sa.String(length=40), nullable=False),
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("retention", sa.JSON(), nullable=False),
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "operation_descriptor",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "operation_request",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("actor_id", sa.String(length=36), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=True),
        sa.Column("operation_id", sa.String(length=120), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("compiled_command", sa.Text(), nullable=False),
        sa.Column("safety_class", sa.String(length=40), nullable=False),
        sa.Column("dry_run_status", sa.String(length=40), nullable=False),
        sa.Column("gate_results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "job",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("operation_request_id", sa.String(length=36), sa.ForeignKey("operation_request.id"), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "job_run",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("job.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("engine", sa.String(length=80), nullable=False),
        sa.Column("compiled_command", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("pre_op_restore_ref", sa.String(length=160), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_table(
        "job_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_run_id", sa.String(length=36), sa.ForeignKey("job_run.id"), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "approval_request",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("operation_request_id", sa.String(length=36), sa.ForeignKey("operation_request.id"), nullable=False),
        sa.Column("requested_by", sa.String(length=36), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("reviewer_id", sa.String(length=36), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("compiled_command_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "restore_point",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("operation_request_id", sa.String(length=36), sa.ForeignKey("operation_request.id"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("retention", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table_name in [
        "restore_point",
        "approval_request",
        "job_log",
        "job_run",
        "job",
        "operation_request",
        "operation_descriptor",
        "table_ref",
        "sort_order",
        "partition_spec",
        "schema_version",
        "snapshot",
        "table_metrics",
        "iceberg_table",
        "namespace",
        "compute_backend",
        "object_store_connection",
        "catalog_connection",
        "secret_reference",
        "environment",
        "audit_event",
        "session_token",
        "user_role",
        "permission",
        "role",
        "app_user",
        "workspace",
    ]:
        op.drop_table(table_name)
