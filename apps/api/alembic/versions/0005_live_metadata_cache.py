"""live metadata cache"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_live_metadata_cache"
down_revision: str | None = "0004_secret_reference_length"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("iceberg_table", sa.Column("table_uuid", sa.String(length=80), nullable=True))
    op.add_column(
        "iceberg_table", sa.Column("metadata_location", sa.String(length=1200), nullable=True)
    )
    op.add_column(
        "iceberg_table",
        sa.Column("previous_metadata_location", sa.String(length=1200), nullable=True),
    )
    op.add_column(
        "iceberg_table", sa.Column("last_sequence_number", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "iceberg_table", sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("iceberg_table", sa.Column("current_schema_id", sa.Integer(), nullable=True))
    op.add_column("iceberg_table", sa.Column("default_spec_id", sa.Integer(), nullable=True))
    op.add_column(
        "iceberg_table", sa.Column("default_sort_order_id", sa.Integer(), nullable=True)
    )
    op.add_column("iceberg_table", sa.Column("record_count", sa.BigInteger(), nullable=True))

    op.create_table(
        "metadata_sync_run",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column(
            "catalog_connection_id",
            sa.String(length=36),
            sa.ForeignKey("catalog_connection.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsed_table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=False),
    )
    op.create_table(
        "metadata_log_entry",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=True),
        sa.Column("metadata_file", sa.String(length=1200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("table_id", "metadata_file", name="uq_metadata_log_table_file"),
    )
    op.create_table(
        "snapshot_log_entry",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=True),
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "table_id", "snapshot_id", "timestamp_ms", name="uq_snapshot_log_table"
        ),
    )
    op.create_table(
        "manifest_file_cache",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("manifest_path", sa.String(length=1200), nullable=False),
        sa.Column("content", sa.String(length=40), nullable=True),
        sa.Column("partition_spec_id", sa.Integer(), nullable=True),
        sa.Column("sequence_number", sa.BigInteger(), nullable=True),
        sa.Column("manifest_length", sa.BigInteger(), nullable=True),
        sa.Column("added_files_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("existing_files_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_files_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_rows_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("existing_rows_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("deleted_rows_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("partitions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "table_id", "snapshot_id", "manifest_path", name="uq_manifest_table_path"
        ),
    )
    op.create_table(
        "table_file_cache",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("snapshot_id", sa.String(length=80), nullable=True),
        sa.Column("manifest_path", sa.String(length=1200), nullable=True),
        sa.Column("entry_status", sa.String(length=40), nullable=True),
        sa.Column("content", sa.String(length=40), nullable=False),
        sa.Column("file_path", sa.String(length=1600), nullable=False),
        sa.Column("file_format", sa.String(length=40), nullable=True),
        sa.Column("spec_id", sa.Integer(), nullable=True),
        sa.Column("partition", sa.JSON(), nullable=False),
        sa.Column("record_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_size_in_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("column_sizes", sa.JSON(), nullable=False),
        sa.Column("value_counts", sa.JSON(), nullable=False),
        sa.Column("null_value_counts", sa.JSON(), nullable=False),
        sa.Column("nan_value_counts", sa.JSON(), nullable=False),
        sa.Column("lower_bounds", sa.JSON(), nullable=False),
        sa.Column("upper_bounds", sa.JSON(), nullable=False),
        sa.Column("key_metadata_present", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("split_offsets", sa.JSON(), nullable=False),
        sa.Column("equality_ids", sa.JSON(), nullable=False),
        sa.Column("sort_order_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_table_file_cache_table_content", "table_file_cache", ["table_id", "content"])
    op.create_table(
        "partition_summary",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("iceberg_table.id"), nullable=False),
        sa.Column("spec_id", sa.Integer(), nullable=False),
        sa.Column("partition_key", sa.String(length=1000), nullable=False),
        sa.Column("partition", sa.JSON(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("record_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("delete_file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("table_id", "spec_id", "partition_key", name="uq_partition_summary"),
    )


def downgrade() -> None:
    op.drop_table("partition_summary")
    op.drop_index("ix_table_file_cache_table_content", table_name="table_file_cache")
    op.drop_table("table_file_cache")
    op.drop_table("manifest_file_cache")
    op.drop_table("snapshot_log_entry")
    op.drop_table("metadata_log_entry")
    op.drop_table("metadata_sync_run")
    for column in (
        "record_count",
        "default_sort_order_id",
        "default_spec_id",
        "current_schema_id",
        "last_updated_at",
        "last_sequence_number",
        "previous_metadata_location",
        "metadata_location",
        "table_uuid",
    ):
        op.drop_column("iceberg_table", column)
