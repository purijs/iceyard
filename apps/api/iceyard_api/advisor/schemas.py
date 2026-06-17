from typing import Literal

from pydantic import BaseModel, Field

WorkloadSource = Literal["hints", "none"]
AdviceMode = Literal["recommend", "auto_apply"]


class WorkloadHints(BaseModel):
    filter_cols: list[str] = Field(default_factory=list)
    join_keys: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)


class ClusteringAdviceRequest(BaseModel):
    workload_source: WorkloadSource = "none"
    hints: WorkloadHints = Field(default_factory=WorkloadHints)
    mode: AdviceMode = "recommend"
    target_file_size_bytes: int = 536_870_912


class ClusteringRecommendation(BaseModel):
    strategy: Literal["sort", "zorder"]
    columns: list[str]
    sort_order_expr: str
    current_clustering_depth: float
    projected_clustering_depth: float
    projected_scan_reduction_pct: float
    apply_operation_id: str = "rewrite_data_files"
    apply_params: dict[str, object]
    rationale: str


class ClusteringAdvice(BaseModel):
    table_id: str
    table_name: str
    workload_basis: str
    recommendations: list[ClusteringRecommendation]
    note: str = (
        "Projection is directional (z-order assumes independent dimensions). Without query "
        "history the advisor uses hints + layout hygiene; confirm with a replay after applying."
    )


class MaterializedViewAdvice(BaseModel):
    table_id: str
    table_name: str
    engine_native_supported: bool
    recommended_definition: str
    refresh_mode: str
    fallback_operation_id: str = "create_summary_table"
    rationale: str
    note: str = (
        "Engine-native MVs (Glue, StarRocks, Hive) are delegated; without support the tool "
        "maintains a self-managed summary table (no transparent rewrite)."
    )
