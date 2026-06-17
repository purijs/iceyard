from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from iceyard_api.core.time import utcnow
from iceyard_api.db.models import IcebergTable, Snapshot, TableRef
from iceyard_api.layout.service import LayoutStatsService
from iceyard_api.retention.schemas import (
    CleanupPreviewRequest,
    CleanupPreviewResult,
    CleanupStep,
    ExpiringSnapshot,
    RetentionSimRequest,
    RetentionSimResult,
)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class RetentionService:
    """#6 retention/time-travel simulation and #8 cleanup-TTL preview (READ)."""

    def __init__(self, session: Session):
        self.session = session
        self.layout = LayoutStatsService(session)

    def simulate_expire(
        self, workspace_id: str, table_id: str, payload: RetentionSimRequest
    ) -> RetentionSimResult:
        table = self.layout.get_table_or_404(workspace_id, table_id)
        snapshots = sorted(
            self.layout.index.list_snapshots(table_id),
            key=lambda snap: snap.committed_at,
            reverse=True,
        )
        protected_ids = self._protected_snapshot_ids(table_id)
        cutoff = _aware(payload.older_than)

        retained: list[Snapshot] = snapshots[: payload.retain_last]
        retained_ids = {snap.snapshot_id for snap in retained}

        expiring: list[ExpiringSnapshot] = []
        protected_excluded: list[ExpiringSnapshot] = []
        reclaimable = 0
        for snap in snapshots:
            if snap.snapshot_id in retained_ids:
                continue
            if _aware(snap.committed_at) >= cutoff:
                continue
            entry = ExpiringSnapshot(
                snapshot_id=snap.snapshot_id,
                committed_at=snap.committed_at,
                operation=snap.operation,
                protected_by=protected_ids.get(snap.snapshot_id),
            )
            if snap.snapshot_id in protected_ids:
                protected_excluded.append(entry)
                continue
            expiring.append(entry)
            reclaimable += abs(int(snap.summary.get("bytes", 0)))

        remaining = [snap for snap in snapshots if snap.snapshot_id not in {
            e.snapshot_id for e in expiring
        }]
        earliest = min((s.committed_at for s in remaining), default=None)

        blocked = bool(protected_excluded)
        return RetentionSimResult(
            table_id=table.id,
            table_name=table.name,
            expiring_count=len(expiring),
            retained_count=len(remaining),
            reclaimable_bytes=reclaimable,
            reclaimable_basis="estimate_from_summary",
            earliest_time_travel=earliest,
            protected_excluded=protected_excluded,
            expiring=expiring,
            blocked=blocked,
            block_reason=(
                "Protected/tagged snapshots fall in the expiry window and are excluded."
                if blocked
                else None
            ),
        )

    def cleanup_preview(
        self, workspace_id: str, table_id: str, payload: CleanupPreviewRequest
    ) -> CleanupPreviewResult:
        table = self.layout.get_table_or_404(workspace_id, table_id)
        metrics = table.metrics
        cutoff = utcnow() - timedelta(days=payload.keep_days)

        partition_aligned = self._is_time_partitioned(table, payload.time_column)
        delete_pct, rows_removed, bytes_reclaimed = self._estimate_expired(
            table_id, metrics, payload.keep_days
        )
        guardrail_passed = delete_pct <= payload.max_delete_pct

        return CleanupPreviewResult(
            table_id=table.id,
            table_name=table.name,
            cutoff=cutoff,
            partition_aligned=partition_aligned,
            estimated_delete_pct=round(delete_pct, 1),
            estimated_rows_removed=rows_removed,
            estimated_bytes_reclaimed=bytes_reclaimed,
            guardrail_max_delete_pct=payload.max_delete_pct,
            guardrail_passed=guardrail_passed,
            mode=payload.mode,
            plan=self._plan(payload, partition_aligned),
            recommend_partitioning=not partition_aligned,
        )

    def _protected_snapshot_ids(self, table_id: str) -> dict[str, str]:
        refs = self.session.query(TableRef).filter(TableRef.table_id == table_id).all()
        protected: dict[str, str] = {}
        for ref in refs:
            if ref.ref_type == "tag" or ref.is_protected or ref.retention.get("pinned"):
                protected[ref.snapshot_id] = f"{ref.ref_type}:{ref.name}"
        return protected

    def _is_time_partitioned(self, table: IcebergTable, time_column: str) -> bool:
        for spec in self.layout.index.list_partition_specs(table.id):
            if not spec.is_current:
                continue
            fields = spec.spec.get("fields", []) if isinstance(spec.spec, dict) else []
            if any(field.get("source") == time_column for field in fields):
                return True
        return False

    def _estimate_expired(
        self, table_id: str, metrics: object, keep_days: int
    ) -> tuple[float, int, int]:
        if metrics is None:
            return (0.0, 0, 0)
        snapshots = self.layout.index.list_snapshots(table_id)
        if not snapshots:
            return (0.0, 0, 0)
        oldest = min(_aware(s.committed_at) for s in snapshots)
        span_days = max((utcnow() - oldest).days, 1)
        fraction = max(0.0, min(1.0, (span_days - keep_days) / span_days))
        data_size = getattr(metrics, "data_size_bytes", 0)
        # No row counts in the index; approximate rows from file count as a proxy unit.
        file_count = getattr(metrics, "file_count", 0)
        return (fraction * 100, int(file_count * fraction), int(data_size * fraction))

    def _plan(
        self, payload: CleanupPreviewRequest, partition_aligned: bool
    ) -> list[CleanupStep]:
        delete_detail = (
            "Partition-aligned DELETE resolves to metadata-only file removal."
            if partition_aligned
            else "Row-level DELETE creates delete files / deletion vectors."
        )
        steps = [CleanupStep(name="delete", detail=delete_detail)]
        if payload.mode == "hard":
            steps.append(CleanupStep(name="compact", detail="Compact affected partitions."))
            steps.append(
                CleanupStep(name="expire", detail="Expire snapshots in the window.")
            )
            steps.append(
                CleanupStep(name="verify", detail="Verify no file retains expired data.")
            )
        elif payload.mode == "archive":
            steps.insert(
                0,
                CleanupStep(
                    name="archive",
                    detail=f"Copy expiring partitions to {payload.mode} location first.",
                ),
            )
        return steps
