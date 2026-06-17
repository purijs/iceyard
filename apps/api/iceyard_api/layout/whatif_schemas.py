from typing import Literal

from pydantic import BaseModel, Field

WhatIfKind = Literal["repartition", "resort", "refile_size"]


class WhatIfChange(BaseModel):
    kind: WhatIfKind
    # Target of the change, e.g. "hours(occurred_at)", "zorder(user_id, occurred_at)",
    # or a target file size in bytes for refile_size.
    to: str


class WhatIfQuery(BaseModel):
    filter: str
    # Optional fraction of rows the predicate selects; defaults to a conservative 0.05.
    selectivity: float | None = None


class WhatIfRequest(BaseModel):
    change: WhatIfChange
    queries: list[WhatIfQuery] = Field(default_factory=list)


class WhatIfQueryResult(BaseModel):
    filter: str
    current_files: int
    projected_files: int
    current_bytes: int
    projected_bytes: int
    files_reduction_pct: float
    bytes_reduction_pct: float


class WhatIfAggregate(BaseModel):
    typical_files_reduction_pct: float
    best_files_reduction_pct: float
    worst_files_reduction_pct: float
    typical_bytes_reduction_pct: float


class WhatIfResult(BaseModel):
    table_id: str
    table_name: str
    change: WhatIfChange
    queries: list[WhatIfQueryResult]
    aggregate: WhatIfAggregate
    assumptions: str
    note: str = (
        "Projection over indexed per-file stats (assumes within-file uniformity, and "
        "independence for z-order). Use for relative comparison; validate after applying."
    )
