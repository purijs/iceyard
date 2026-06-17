from datetime import UTC

from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.core.logging import current_correlation_id
from iceyard_api.core.time import utcnow
from iceyard_api.db.models import IcebergTable, Job, JobLog, JobRun, User
from iceyard_api.layout.service import LayoutStatsService
from iceyard_api.wap.schemas import (
    WapCheck,
    WapCheckResult,
    WapRunRequest,
    WapRunResult,
    WapStep,
)

# Checks that need a query engine to evaluate against the branch.
_ENGINE_ONLY_CHECKS = {"not_null", "distribution", "contract", "sql"}


def _as_number(value: object, default: float) -> float:
    return float(value) if isinstance(value, int | float | str) else default


class WapService:
    """#5 — Write-Audit-Publish: audit a staged branch, then publish if green."""

    def __init__(self, session: Session):
        self.session = session
        self.layout = LayoutStatsService(session)

    def run(
        self, workspace_id: str, table_id: str, payload: WapRunRequest, actor: User
    ) -> WapRunResult:
        table = self.layout.get_table_or_404(workspace_id, table_id)

        job = Job(
            workspace_id=workspace_id,
            kind="wap",
            status="running",
            created_by=actor.id,
            correlation_id=current_correlation_id(),
        )
        self.session.add(job)
        self.session.flush()

        check_results = [self._evaluate_check(table, check) for check in payload.checks]
        green = all(result.status != "failed" for result in check_results)

        run = JobRun(
            job_id=job.id,
            status="running",
            engine="control-plane",
            compiled_command="",
            dry_run=False,
            metrics={},
        )
        self.session.add(run)
        self.session.flush()
        self._log(run.id, f"staged branch '{payload.branch}' for {table.name}")
        for result in check_results:
            self._log(run.id, f"check {result.type}: {result.status} — {result.detail}")

        status, published_snapshot, tag, compiled = self._decide_publish(
            table, payload, green
        )

        job.status = "succeeded" if status == "published" else "queued"
        run.status = job.status
        run.compiled_command = compiled or ""
        run.ended_at = utcnow() if status == "published" else None
        if compiled:
            self._log(run.id, f"publish: {compiled}")
        else:
            self._log(run.id, f"held: status={status}")

        AuditService(self.session).record(
            action="wap.run",
            resource_type="job",
            resource_id=job.id,
            workspace_id=workspace_id,
            actor_id=actor.id,
            after_state={"table": table.name, "branch": payload.branch, "status": status},
        )
        self.session.commit()

        return WapRunResult(
            job_id=job.id,
            table_id=table.id,
            table_name=table.name,
            branch=payload.branch,
            status=status,
            green=green,
            check_results=check_results,
            steps=self._steps(status),
            published_snapshot_id=published_snapshot,
            publish_tag=tag,
            compiled_publish_command=compiled,
            evaluated_at=utcnow(),
        )

    def _evaluate_check(self, table: IcebergTable, check: WapCheck) -> WapCheckResult:
        if check.type == "rowcount":
            min_files = int(_as_number(check.params.get("min", 1), 1))
            file_count = table.metrics.file_count if table.metrics else 0
            ok = file_count >= min_files
            return WapCheckResult(
                type=check.type,
                status="passed" if ok else "failed",
                detail=f"{file_count} files indexed (proxy for volume; min={min_files})",
            )
        if check.type == "freshness":
            max_lag_hours = _as_number(check.params.get("max_lag_hours", 24), 24)
            last_commit = table.metrics.last_commit_at if table.metrics else None
            if not last_commit:
                return WapCheckResult(
                    type=check.type, status="skipped", detail="no commit timestamp indexed"
                )
            committed = last_commit if last_commit.tzinfo else last_commit.replace(tzinfo=UTC)
            lag_hours = (utcnow() - committed).total_seconds() / 3600
            ok = lag_hours <= max_lag_hours
            return WapCheckResult(
                type=check.type,
                status="passed" if ok else "failed",
                detail=f"last commit {lag_hours:.1f}h ago (max {max_lag_hours}h)",
            )
        if check.type in _ENGINE_ONLY_CHECKS:
            return WapCheckResult(
                type=check.type,
                status="skipped",
                detail="requires a connected query engine to evaluate against the branch",
            )
        return WapCheckResult(
            type=check.type, status="skipped", detail="unknown check type"
        )

    def _decide_publish(
        self, table: IcebergTable, payload: WapRunRequest, green: bool
    ) -> tuple[str, str | None, str | None, str | None]:
        if not green:
            return ("held", None, None, None)
        if payload.publish == "require_approval":
            return ("requires_approval", None, None, None)
        snapshot = table.current_snapshot_id
        tag = payload.tag_on_publish
        compiled = f"CALL system.fast_forward('{table.name}', 'main', '{payload.branch}')"
        if tag:
            compiled += f"\nALTER TABLE {table.name} CREATE TAG {tag}"
        return ("published", snapshot, tag, compiled)

    def _steps(self, status: str) -> list[WapStep]:
        published = status == "published"
        return [
            WapStep(name="stage", state="done"),
            WapStep(name="audit", state="done"),
            WapStep(
                name="publish",
                state="done" if published else "pending",
            ),
        ]

    def _log(self, job_run_id: str, message: str) -> None:
        self.session.add(JobLog(job_run_id=job_run_id, level="info", message=message))
