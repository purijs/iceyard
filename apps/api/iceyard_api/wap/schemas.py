from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PublishMode = Literal["auto_if_green", "require_approval"]
CheckStatus = Literal["passed", "failed", "skipped"]
RunStatus = Literal["published", "held", "requires_approval"]


class WapCheck(BaseModel):
    type: str  # rowcount | freshness | not_null | distribution | contract | sql
    params: dict[str, object] = Field(default_factory=dict)


class WapRunRequest(BaseModel):
    branch: str = "ingest-run"
    checks: list[WapCheck] = Field(default_factory=list)
    publish: PublishMode = "auto_if_green"
    tag_on_publish: str | None = None


class WapCheckResult(BaseModel):
    type: str
    status: CheckStatus
    detail: str


class WapStep(BaseModel):
    name: str
    state: str


class WapRunResult(BaseModel):
    job_id: str
    table_id: str
    table_name: str
    branch: str
    status: RunStatus
    green: bool
    check_results: list[WapCheckResult]
    steps: list[WapStep]
    published_snapshot_id: str | None
    publish_tag: str | None
    compiled_publish_command: str | None
    evaluated_at: datetime
    note: str = (
        "The control plane does not ingest; ingestion writes to the WAP branch and signals "
        "this audit+publish step. Engine-only checks (not_null/distribution/contract/sql) are "
        "marked skipped until a query engine is connected."
    )
