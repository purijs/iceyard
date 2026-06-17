from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User, Workspace
from iceyard_api.db.session import get_session
from iceyard_api.rbac.dependencies import require_permission
from iceyard_api.tenants.schemas import WorkspaceRead, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/current", response_model=WorkspaceRead)
def current_workspace(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WorkspaceRead:
    workspace = session.get(Workspace, current_user.workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
        )
    return WorkspaceRead.model_validate(workspace)


@router.patch("/current", response_model=WorkspaceRead)
def update_current_workspace(
    payload: WorkspaceUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("workspace.manage")),
) -> WorkspaceRead:
    workspace = session.get(Workspace, current_user.workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
        )
    existing = session.scalar(
        select(Workspace).where(Workspace.name == payload.name, Workspace.id != workspace.id)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Workspace name already exists."
        )
    before_state = {"name": workspace.name}
    workspace.name = payload.name
    AuditService(session).record(
        action="workspaces.update",
        resource_type="workspace",
        resource_id=workspace.id,
        workspace_id=workspace.id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={"name": workspace.name},
    )
    session.commit()
    return WorkspaceRead.model_validate(workspace)
