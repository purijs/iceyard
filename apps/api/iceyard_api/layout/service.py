from datetime import UTC

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from iceyard_api.core.time import utcnow
from iceyard_api.db.models import IcebergTable
from iceyard_api.iceberg.service import IcebergIndexService
from iceyard_api.layout.schemas import (
    ClusteringCandidate,
    LayoutDimension,
    LayoutProfileRead,
)

TARGET_FILE_SIZE_BYTES = 536_870_912  # 512 MB


def _cardinality_hint(column: str) -> str:
    """Heuristic cardinality bucket from the column name/type signal."""
    lowered = column.lower()
    if lowered.endswith("_id") or lowered in {"id", "user_id", "event_id"}:
        return "high"
    if "type" in lowered or "status" in lowered or "region" in lowered:
        return "low"
    return "medium"


class LayoutStatsService:
    """S1 — per-table layout & stats model, derived from the local index."""

    def __init__(self, session: Session):
        self.session = session
        self.index = IcebergIndexService(session)

    def get_table_or_404(self, workspace_id: str, table_id: str) -> IcebergTable:
        table = self.index.get_table(workspace_id, table_id)
        if not table:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
        return table

    def profile(self, workspace_id: str, table_id: str) -> LayoutProfileRead:
        table = self.get_table_or_404(workspace_id, table_id)
        metrics = table.metrics
        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Table has not been indexed yet.",
            )

        file_count = metrics.file_count
        avg_file_size = metrics.data_size_bytes // file_count if file_count else 0
        delete_density = round(metrics.delete_file_count / max(file_count, 1), 4)
        metadata_weight = metrics.manifest_count + metrics.snapshot_count

        snapshots = self.index.list_snapshots(table_id)
        oldest_age_days: int | None = None
        if snapshots:
            oldest = min(snapshots, key=lambda snap: snap.committed_at)
            committed = oldest.committed_at
            if committed.tzinfo is None:
                committed = committed.replace(tzinfo=UTC)
            oldest_age_days = max((utcnow() - committed).days, 0)

        partition_skew = self._partition_skew(metrics.small_file_ratio, file_count)
        clustering = self._clustering_candidates(workspace_id, table_id, metrics.small_file_ratio)

        dimensions = [
            LayoutDimension(
                name="Small-file ratio",
                value=round(metrics.small_file_ratio, 4),
                unit="ratio",
                detail=f"{avg_file_size / 1_048_576:.0f} MB avg vs 512 MB target",
            ),
            LayoutDimension(
                name="Delete density",
                value=delete_density,
                unit="deletes/file",
                detail=f"{metrics.delete_file_count} delete files over {file_count} data files",
            ),
            LayoutDimension(
                name="Metadata weight",
                value=float(metadata_weight),
                unit="files",
                detail=f"{metrics.manifest_count} manifests + {metrics.snapshot_count} snapshots",
            ),
            LayoutDimension(
                name="Partition skew",
                value=partition_skew,
                unit="ratio",
                detail="Heuristic from file distribution",
            ),
        ]

        return LayoutProfileRead(
            table_id=table.id,
            table_name=table.name,
            environment_id=table.environment_id,
            format_version=table.format_version,
            file_count=file_count,
            avg_file_size_bytes=avg_file_size,
            small_file_ratio=round(metrics.small_file_ratio, 4),
            delete_density=delete_density,
            metadata_weight=metadata_weight,
            snapshot_count=metrics.snapshot_count,
            oldest_snapshot_age_days=oldest_age_days,
            partition_skew=partition_skew,
            dimensions=dimensions,
            clustering=clustering,
        )

    def _partition_skew(self, small_file_ratio: float, file_count: int) -> float:
        # More small files relative to a large file count implies uneven layout.
        skew = small_file_ratio * min(file_count / 1000, 1.0)
        return round(min(skew, 1.0), 4)

    def _clustering_candidates(
        self, workspace_id: str, table_id: str, small_file_ratio: float
    ) -> list[ClusteringCandidate]:
        schema_versions = self.index.list_schema_versions(table_id)
        sort_orders = self.index.list_sort_orders(table_id)
        sort_columns = {
            field.get("source")
            for order in sort_orders
            if order.is_current
            for field in order.fields
        }
        if not schema_versions:
            return []
        current_schema = schema_versions[-1].schema
        fields = current_schema.get("fields", []) if isinstance(current_schema, dict) else []

        candidates: list[ClusteringCandidate] = []
        for field in fields[:6]:
            name = field.get("name")
            if not name:
                continue
            in_sort = name in sort_columns
            # Sorted columns have near-disjoint file ranges (low depth); unsorted
            # columns inherit the table's overlap, scaled by the small-file ratio.
            if in_sort:
                depth = round(1.0 + small_file_ratio * 2.0, 2)
            else:
                depth = round(2.0 + small_file_ratio * 8.0, 2)
            candidates.append(
                ClusteringCandidate(
                    column=name,
                    in_sort_order=in_sort,
                    clustering_depth=depth,
                    cardinality_hint=_cardinality_hint(name),
                    basis="heuristic",
                )
            )
        return candidates
