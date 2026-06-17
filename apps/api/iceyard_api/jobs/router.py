from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.core.time import utcnow
from iceyard_api.db.models import Job, JobLog, JobRun, User
from iceyard_api.db.session import get_session
from iceyard_api.jobs.schemas import JobLogRead, JobRead, JobRunRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[JobRead]:
    return list(
        session.scalars(
            select(Job)
            .where(Job.workspace_id == current_user.workspace_id)
            .order_by(Job.created_at.desc())
        )
    )


@router.get("/{job_id}/runs", response_model=list[JobRunRead])
def list_job_runs(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[JobRunRead]:
    job = session.scalar(
        select(Job).where(Job.id == job_id, Job.workspace_id == current_user.workspace_id)
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return list(session.scalars(select(JobRun).where(JobRun.job_id == job_id)))


@router.get("/{job_id}/logs", response_model=list[JobLogRead])
def list_job_logs(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[JobLogRead]:
    job = session.scalar(
        select(Job).where(Job.id == job_id, Job.workspace_id == current_user.workspace_id)
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    run_ids = [run.id for run in session.scalars(select(JobRun).where(JobRun.job_id == job_id))]
    if not run_ids:
        return []
    return list(session.scalars(select(JobLog).where(JobLog.job_run_id.in_(run_ids))))


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    job = session.scalar(
        select(Job).where(Job.id == job_id, Job.workspace_id == current_user.workspace_id)
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status in {"succeeded", "failed", "cancelled"}:
        return job
    job.status = "cancelled"
    job.updated_at = utcnow()
    for run in session.scalars(select(JobRun).where(JobRun.job_id == job.id)):
        run.status = "cancelled"
        run.ended_at = utcnow()
    AuditService(session).record(
        action="job.cancel",
        resource_type="job",
        resource_id=job.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
    )
    session.commit()
    return job
