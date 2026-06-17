from sqlalchemy.orm import Session

from iceyard_api.db.models import IcebergTable
from iceyard_api.layout.service import LayoutStatsService
from iceyard_api.tuning.schemas import DistributionAdvice, ParquetAdvice

DEFAULT_ROW_GROUP_BYTES = 134_217_728  # 128 MB


class TuningService:
    """#3/#4 — Parquet and write-distribution recommendations from the stats model."""

    def __init__(self, session: Session):
        self.session = session
        self.layout = LayoutStatsService(session)

    def parquet_advice(self, workspace_id: str, table_id: str) -> ParquetAdvice:
        table = self.layout.get_table_or_404(workspace_id, table_id)
        profile = self.layout.profile(workspace_id, table_id)
        current_codec = str(
            table.properties.get("write.parquet.compression-codec", "snappy")
        )

        # Read-heavy / cold tables favour zstd (better ratio); the default heuristic
        # without a workload profile is read-heavy. High-cardinality columns benefit
        # from dictionary encoding; large scans favour bigger row groups.
        recommended_codec = "zstd"
        has_high_cardinality = any(
            candidate.cardinality_hint == "high" for candidate in profile.clustering
        )
        row_group = DEFAULT_ROW_GROUP_BYTES
        if profile.small_file_ratio > 0.5:
            row_group = DEFAULT_ROW_GROUP_BYTES // 2  # smaller groups for selective reads

        rationale = (
            f"Codec is {current_codec}; zstd improves compression ratio for read-heavy "
            f"tables. Dictionary {'on' if has_high_cardinality else 'off'} based on column "
            "cardinality."
        )
        return ParquetAdvice(
            table_id=table.id,
            table_name=table.name,
            current_codec=current_codec,
            recommended_codec=recommended_codec,
            recommended_level=3,
            dictionary_enabled=has_high_cardinality,
            row_group_size_bytes=row_group,
            rationale=rationale,
        )

    def distribution_advice(self, workspace_id: str, table_id: str) -> DistributionAdvice:
        table = self.layout.get_table_or_404(workspace_id, table_id)
        profile = self.layout.profile(workspace_id, table_id)
        current_mode = str(table.properties.get("write.distribution-mode", "none"))

        has_sort_order = any(candidate.in_sort_order for candidate in profile.clustering)
        is_partitioned = self._is_partitioned(table)

        if is_partitioned and has_sort_order:
            recommended = "range"
            reduction = 70.0
            rationale = (
                "Partitioned with a sort order; range distribution writes sorted, larger files."
            )
        elif is_partitioned and profile.small_file_ratio > 0.3:
            recommended = "hash"
            reduction = round(profile.small_file_ratio * 80, 1)
            rationale = (
                "Partitioned table creating small files; hash shuffles to ~one "
                "writer per partition."
            )
        else:
            recommended = "none"
            reduction = 0.0
            rationale = "Unpartitioned or already well-sized; no shuffle needed."

        return DistributionAdvice(
            table_id=table.id,
            table_name=table.name,
            current_mode=current_mode,
            recommended_mode=recommended,
            projected_small_file_reduction_pct=reduction,
            ingestion_hint=(
                f"Set write.distribution-mode={recommended} on the writing engine "
                "(e.g. Spark write options) so it is honored at write time."
            ),
            rationale=rationale,
        )

    def _is_partitioned(self, table: IcebergTable) -> bool:
        specs = self.layout.index.list_partition_specs(table.id)
        for spec in specs:
            if not spec.is_current:
                continue
            fields = spec.spec.get("fields", []) if isinstance(spec.spec, dict) else []
            if fields:
                return True
        return False
