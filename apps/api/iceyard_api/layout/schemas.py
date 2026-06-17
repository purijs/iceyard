from pydantic import BaseModel


class ClusteringCandidate(BaseModel):
    """Per-column clustering estimate. Lower depth = better pruning."""

    column: str
    in_sort_order: bool
    clustering_depth: float
    cardinality_hint: str  # high | medium | low
    basis: str


class LayoutDimension(BaseModel):
    name: str
    value: float
    unit: str
    detail: str


class LayoutProfileRead(BaseModel):
    """Compact physical-state profile for a table (S1).

    Derived from the indexed metadata (TableMetrics + snapshots). It is a
    rebuildable cache substrate, not a live catalog read; values flagged with
    ``basis="heuristic"`` are directional projections, not measured facts.
    """

    table_id: str
    table_name: str
    environment_id: str
    format_version: int
    file_count: int
    avg_file_size_bytes: int
    small_file_ratio: float
    delete_density: float
    metadata_weight: int
    snapshot_count: int
    oldest_snapshot_age_days: int | None
    partition_skew: float
    dimensions: list[LayoutDimension]
    clustering: list[ClusteringCandidate]
    derived: bool = True
    note: str = (
        "Derived from the local index; clustering depth and skew are heuristics "
        "until per-file bounds are available from a live catalog connection."
    )
