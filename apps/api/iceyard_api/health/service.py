from sqlalchemy import func, select
from sqlalchemy.orm import Session

from iceyard_api.db.models import IcebergTable, Job, TableMetrics
from iceyard_api.health.schemas import DashboardRead, HealthDimension, HealthFinding, HealthRead
from iceyard_api.iceberg.service import IcebergIndexService


def severity_for_score(score: int) -> str:
    if score >= 80:
        return "healthy"
    if score >= 55:
        return "warning"
    return "critical"


class HealthService:
    def __init__(self, session: Session):
        self.session = session

    def evaluate_table(self, table: IcebergTable) -> HealthRead:
        metrics = table.metrics
        if not metrics:
            return HealthRead(
                table_id=table.id,
                score=0,
                severity="unknown",
                dimensions=[],
                findings=[],
                recommended_actions=[],
            )
        file_score = max(0, int(100 - metrics.small_file_ratio * 100))
        delete_ratio = metrics.delete_file_count / max(metrics.file_count, 1)
        delete_score = max(0, int(100 - min(delete_ratio, 1) * 100))
        metadata_score = max(0, 100 - max(metrics.manifest_count - 100, 0) // 5)
        snapshot_score = max(0, 100 - max(metrics.snapshot_count - 50, 0) // 4)
        owner_score = 100 if table.owner else 30
        format_score = 70 if table.format_version == 3 else 90
        weighted = round(
            file_score * 0.25
            + delete_score * 0.20
            + metadata_score * 0.20
            + snapshot_score * 0.15
            + owner_score * 0.10
            + format_score * 0.10
        )
        findings: list[HealthFinding] = []
        actions: list[str] = []
        if metrics.small_file_ratio >= 0.4:
            findings.append(
                HealthFinding(
                    severity="warning",
                    message=f"Small-file ratio is {metrics.small_file_ratio:.2f}.",
                    operation_ids=["rewrite_data_files"],
                )
            )
            actions.append("Compact data files")
        if delete_ratio >= 0.5:
            findings.append(
                HealthFinding(
                    severity="warning",
                    message="Delete-file pressure is high.",
                    operation_ids=["rewrite_position_deletes"],
                )
            )
            actions.append("Compact delete files")
        if metrics.snapshot_count >= 100:
            findings.append(
                HealthFinding(
                    severity="warning",
                    message=f"Snapshot count is {metrics.snapshot_count}.",
                    operation_ids=["expire_snapshots"],
                )
            )
            actions.append("Expire snapshots")
        if not table.owner:
            findings.append(
                HealthFinding(
                    severity="warning",
                    message="Table has no assigned owner.",
                    operation_ids=[],
                )
            )
        if table.format_version == 3:
            findings.append(
                HealthFinding(
                    severity="info",
                    message="Format v3 requires reader compatibility checks before promotion.",
                    operation_ids=["upgrade_format"],
                )
            )
        score = min(weighted, table.health_score or weighted)
        return HealthRead(
            table_id=table.id,
            score=score,
            severity=severity_for_score(score),
            dimensions=[
                HealthDimension(
                    name="File sizing",
                    weight=25,
                    score=file_score,
                    details={"small_file_ratio": metrics.small_file_ratio},
                ),
                HealthDimension(
                    name="Delete-file load",
                    weight=20,
                    score=delete_score,
                    details={"delete_file_count": metrics.delete_file_count},
                ),
                HealthDimension(
                    name="Metadata hygiene",
                    weight=20,
                    score=metadata_score,
                    details={"manifest_count": metrics.manifest_count},
                ),
                HealthDimension(
                    name="Snapshot hygiene",
                    weight=15,
                    score=snapshot_score,
                    details={"snapshot_count": metrics.snapshot_count},
                ),
                HealthDimension(
                    name="Ownership", weight=10, score=owner_score, details={"owner": table.owner}
                ),
                HealthDimension(
                    name="Format risk",
                    weight=10,
                    score=format_score,
                    details={"format_version": table.format_version},
                ),
            ],
            findings=findings,
            recommended_actions=actions,
        )

    def dashboard(self, workspace_id: str) -> DashboardRead:
        tables = IcebergIndexService(self.session).list_tables(workspace_id)
        if not tables:
            return DashboardRead(
                table_count=0,
                average_health=0,
                needs_attention=0,
                active_jobs=0,
                storage_bytes=0,
                top_risks=[],
            )
        storage_bytes = int(
            self.session.scalar(
                select(func.coalesce(func.sum(TableMetrics.data_size_bytes), 0)).join(IcebergTable)
            )
            or 0
        )
        active_jobs = int(
            self.session.scalar(
                select(func.count(Job.id)).where(
                    Job.workspace_id == workspace_id, Job.status.in_(["queued", "running"])
                )
            )
            or 0
        )
        top_risks = [
            {
                "table_id": table.id,
                "name": table.name,
                "health_score": table.health_score,
                "owner": table.owner,
                "recommended_actions": self.evaluate_table(table).recommended_actions,
            }
            for table in sorted(tables, key=lambda item: item.health_score)[:5]
        ]
        return DashboardRead(
            table_count=len(tables),
            average_health=round(sum(table.health_score for table in tables) / len(tables)),
            needs_attention=len([table for table in tables if table.health_score < 80]),
            active_jobs=active_jobs,
            storage_bytes=storage_bytes,
            top_risks=top_risks,
        )
