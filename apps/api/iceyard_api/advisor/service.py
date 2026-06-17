from sqlalchemy.orm import Session

from iceyard_api.advisor.schemas import (
    ClusteringAdvice,
    ClusteringAdviceRequest,
    ClusteringRecommendation,
    MaterializedViewAdvice,
)
from iceyard_api.layout.schemas import ClusteringCandidate, LayoutProfileRead
from iceyard_api.layout.service import LayoutStatsService
from iceyard_api.layout.whatif_schemas import WhatIfChange, WhatIfQuery, WhatIfRequest
from iceyard_api.layout.whatif_service import WhatIfService

_CARDINALITY_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.2}


class AdvisorService:
    """#1a clustering/sort advisor and #1b MV recommendation."""

    def __init__(self, session: Session):
        self.session = session
        self.layout = LayoutStatsService(session)
        self.whatif = WhatIfService(session)

    def clustering_advice(
        self, workspace_id: str, table_id: str, payload: ClusteringAdviceRequest
    ) -> ClusteringAdvice:
        profile = self.layout.profile(workspace_id, table_id)
        filter_cols = set(payload.hints.filter_cols)

        ranked = sorted(
            profile.clustering,
            key=lambda c: self._score(c, filter_cols),
            reverse=True,
        )
        recommendations: list[ClusteringRecommendation] = []
        if ranked:
            recommendations.append(
                self._recommend(workspace_id, table_id, profile, ranked, payload)
            )

        basis = "workload hints" if filter_cols else "layout hygiene (no workload)"
        return ClusteringAdvice(
            table_id=profile.table_id,
            table_name=profile.table_name,
            workload_basis=basis,
            recommendations=recommendations,
        )

    def _score(self, candidate: ClusteringCandidate, filter_cols: set[str]) -> float:
        freq = 1.0 if candidate.column in filter_cols else 0.3
        cardinality = _CARDINALITY_WEIGHT.get(candidate.cardinality_hint, 0.5)
        poor_clustering = candidate.clustering_depth / 10.0
        return freq * cardinality * poor_clustering

    def _recommend(
        self,
        workspace_id: str,
        table_id: str,
        profile: LayoutProfileRead,
        ranked: list[ClusteringCandidate],
        payload: ClusteringAdviceRequest,
    ) -> ClusteringRecommendation:
        filter_cols = [c for c in payload.hints.filter_cols if c]
        # Multiple independent filter columns favour z-order; otherwise a linear sort.
        multi = [c.column for c in ranked if c.column in filter_cols]
        if len(multi) >= 2:
            strategy = "zorder"
            columns = multi[:3]
            sort_order_expr = f"zorder({', '.join(columns)})"
        else:
            strategy = "sort"
            columns = [ranked[0].column]
            sort_order_expr = columns[0]

        current_depth = next(
            (c.clustering_depth for c in ranked if c.column == columns[0]), 0.0
        )
        projected_depth = round(1.0 + profile.small_file_ratio * 2.0, 2)

        projection = self.whatif.simulate(
            workspace_id,
            table_id,
            WhatIfRequest(
                change=WhatIfChange(kind="resort", to=sort_order_expr),
                queries=[WhatIfQuery(filter=f"{col} = <value>") for col in columns],
            ),
        )
        return ClusteringRecommendation(
            strategy=strategy,
            columns=columns,
            sort_order_expr=sort_order_expr,
            current_clustering_depth=current_depth,
            projected_clustering_depth=projected_depth,
            projected_scan_reduction_pct=projection.aggregate.typical_files_reduction_pct,
            apply_params={
                "strategy": "sort",
                "sort_order": sort_order_expr,
                "target_file_size_bytes": payload.target_file_size_bytes,
            },
            rationale=(
                f"{strategy} on {', '.join(columns)} (cardinality + filter frequency); "
                f"clustering depth {current_depth} → ~{projected_depth}."
            ),
        )

    def materialized_view_advice(
        self, workspace_id: str, table_id: str, engine: str
    ) -> MaterializedViewAdvice:
        profile = self.layout.profile(workspace_id, table_id)
        native = engine in {"glue", "starrocks", "hive", "trino"}
        group_cols = [c.column for c in profile.clustering if c.cardinality_hint == "low"][:2]
        group_expr = ", ".join(group_cols) or "1"
        definition = (
            f"SELECT {group_expr}, count(*) AS rows FROM {profile.table_name} GROUP BY {group_expr}"
        )
        return MaterializedViewAdvice(
            table_id=profile.table_id,
            table_name=profile.table_name,
            engine_native_supported=native,
            recommended_definition=definition,
            refresh_mode="incremental" if native else "full",
            rationale=(
                "Recurring aggregation candidate from low-cardinality group-by columns."
                if group_cols
                else "No strong aggregate candidate; review query history."
            ),
        )
