from pydantic import BaseModel


class HealthDimension(BaseModel):
    name: str
    weight: int
    score: int
    details: dict[str, object]


class HealthFinding(BaseModel):
    severity: str
    message: str
    operation_ids: list[str]


class HealthRead(BaseModel):
    table_id: str
    score: int
    severity: str
    dimensions: list[HealthDimension]
    findings: list[HealthFinding]
    recommended_actions: list[str]


class DashboardRead(BaseModel):
    table_count: int
    average_health: int
    needs_attention: int
    active_jobs: int
    storage_bytes: int
    top_risks: list[dict[str, object]]
