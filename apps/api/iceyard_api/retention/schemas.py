from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CleanupMode = Literal["soft", "hard", "archive"]


# ---- #6 Retention / time-travel simulation -------------------------------------------------


class RetentionSimRequest(BaseModel):
    older_than: datetime
    retain_last: int = 5


class ExpiringSnapshot(BaseModel):
    snapshot_id: str
    committed_at: datetime
    operation: str
    protected_by: str | None = None


class RetentionSimResult(BaseModel):
    table_id: str
    table_name: str
    expiring_count: int
    retained_count: int
    reclaimable_bytes: int
    reclaimable_basis: str
    earliest_time_travel: datetime | None
    protected_excluded: list[ExpiringSnapshot]
    expiring: list[ExpiringSnapshot]
    blocked: bool
    block_reason: str | None = None
    apply_operation_id: str = "expire_snapshots"
    note: str = (
        "Reclaimable bytes are estimated from snapshot summaries (no per-file membership "
        "index yet). Re-validate at execution time; concurrent writes can change the set."
    )


# ---- #8 Cleanup old data (TTL) -------------------------------------------------------------


class CleanupPreviewRequest(BaseModel):
    time_column: str = "occurred_at"
    keep_days: int = 90
    mode: CleanupMode = "soft"
    max_delete_pct: int = 10


class CleanupStep(BaseModel):
    name: str
    detail: str


class CleanupPreviewResult(BaseModel):
    table_id: str
    table_name: str
    cutoff: datetime
    partition_aligned: bool
    estimated_delete_pct: float
    estimated_rows_removed: int
    estimated_bytes_reclaimed: int
    guardrail_max_delete_pct: int
    guardrail_passed: bool
    mode: CleanupMode
    plan: list[CleanupStep]
    apply_operation_id: str = "cleanup_old_data"
    recommend_partitioning: bool
    note: str = (
        "Estimates derive from snapshot age and table totals. Partition-aligned deletes are "
        "metadata-only; row-level deletes create delete files needing later compaction."
    )
