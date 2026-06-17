import math
import re

from sqlalchemy.orm import Session

from iceyard_api.layout.schemas import LayoutProfileRead
from iceyard_api.layout.service import LayoutStatsService
from iceyard_api.layout.whatif_schemas import (
    WhatIfAggregate,
    WhatIfQuery,
    WhatIfQueryResult,
    WhatIfRequest,
    WhatIfResult,
)

DEFAULT_SELECTIVITY = 0.05
_COLUMN_RE = re.compile(r"([a-zA-Z_][\w.]*)\s*(=|>=|<=|>|<|IN|in)")


def _columns_in_predicate(predicate: str) -> list[str]:
    return [match.group(1) for match in _COLUMN_RE.finditer(predicate)]


class WhatIfService:
    """#2 — project files/bytes scanned under a proposed layout change (READ)."""

    def __init__(self, session: Session):
        self.session = session
        self.layout = LayoutStatsService(session)

    def simulate(self, workspace_id: str, table_id: str, payload: WhatIfRequest) -> WhatIfResult:
        profile = self.layout.profile(workspace_id, table_id)
        queries = payload.queries or self._representative_queries(profile)

        results = [self._project_query(profile, payload, query) for query in queries]
        files_reductions = [result.files_reduction_pct for result in results]
        bytes_reductions = [result.bytes_reduction_pct for result in results]
        aggregate = WhatIfAggregate(
            typical_files_reduction_pct=round(_median(files_reductions), 1),
            best_files_reduction_pct=round(max(files_reductions, default=0.0), 1),
            worst_files_reduction_pct=round(min(files_reductions, default=0.0), 1),
            typical_bytes_reduction_pct=round(_median(bytes_reductions), 1),
        )
        return WhatIfResult(
            table_id=profile.table_id,
            table_name=profile.table_name,
            change=payload.change,
            queries=results,
            aggregate=aggregate,
            assumptions=self._assumptions(payload),
        )

    def _representative_queries(self, profile: LayoutProfileRead) -> list[WhatIfQuery]:
        cols = [candidate.column for candidate in profile.clustering[:2]] or ["occurred_at"]
        return [WhatIfQuery(filter=f"{col} = <value>") for col in cols]

    def _project_query(
        self, profile: LayoutProfileRead, payload: WhatIfRequest, query: WhatIfQuery
    ) -> WhatIfQueryResult:
        file_count = max(profile.file_count, 1)
        avg_size = profile.avg_file_size_bytes
        selectivity = query.selectivity if query.selectivity is not None else DEFAULT_SELECTIVITY
        cols = _columns_in_predicate(query.filter)
        target_col = cols[0] if cols else None

        current_files = self._current_files(profile, target_col)
        projected_files = self._projected_files(
            profile, payload, target_col, selectivity, current_files
        )
        projected_files = max(1, min(projected_files, file_count))

        # File size only changes for refile_size; otherwise bytes scale with files.
        current_bytes = current_files * avg_size
        projected_avg = self._projected_avg_size(payload, avg_size, profile)
        projected_bytes = projected_files * projected_avg

        return WhatIfQueryResult(
            filter=query.filter,
            current_files=current_files,
            projected_files=projected_files,
            current_bytes=current_bytes,
            projected_bytes=projected_bytes,
            files_reduction_pct=_reduction_pct(current_files, projected_files),
            bytes_reduction_pct=_reduction_pct(current_bytes, projected_bytes),
        )

    def _current_files(self, profile: LayoutProfileRead, column: str | None) -> int:
        """Files a predicate currently touches, from clustering overlap."""
        file_count = max(profile.file_count, 1)
        depth = 2.0 + profile.small_file_ratio * 8.0
        for candidate in profile.clustering:
            if candidate.column == column:
                depth = candidate.clustering_depth
                break
        # Higher clustering depth => more overlapping files touched.
        fraction = min(1.0, depth / 10.0)
        return max(1, math.ceil(file_count * fraction))

    def _projected_files(
        self,
        profile: LayoutProfileRead,
        payload: WhatIfRequest,
        column: str | None,
        selectivity: float,
        current_files: int,
    ) -> int:
        file_count = max(profile.file_count, 1)
        change = payload.change
        if change.kind == "resort":
            # After sorting on the column, files become near-disjoint ranges.
            return max(1, math.ceil(selectivity * file_count))
        if change.kind == "repartition":
            factor = self._granularity_factor(change.to)
            return max(1, math.ceil(current_files / factor))
        if change.kind == "refile_size":
            target = _parse_int(change.to) or 536_870_912
            new_count = max(1, math.ceil((file_count * profile.avg_file_size_bytes) / target))
            ratio = new_count / file_count
            return max(1, math.ceil(current_files * ratio))
        return current_files

    def _projected_avg_size(
        self, payload: WhatIfRequest, avg_size: int, profile: LayoutProfileRead
    ) -> int:
        if payload.change.kind == "refile_size":
            return _parse_int(payload.change.to) or avg_size
        return avg_size

    def _granularity_factor(self, target: str) -> float:
        target = target.lower()
        if "hour" in target:
            return 24.0
        if "day" in target:
            return 7.0
        if "month" in target:
            return 0.25  # coarser → fewer partitions, more files each
        return 4.0

    def _assumptions(self, payload: WhatIfRequest) -> str:
        if payload.change.kind == "resort":
            return (
                "Linear/z-order sort makes per-file ranges near-disjoint; "
                "files touched approx selectivity x file_count."
            )
        if payload.change.kind == "repartition":
            return "Repartition rebuckets value ranges into the proposed granularity."
        return "File-size change recomputes file_count = total_size / target."


def _reduction_pct(current: int, projected: int) -> float:
    if current <= 0:
        return 0.0
    return round(max(0.0, (current - projected) / current) * 100, 1)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
