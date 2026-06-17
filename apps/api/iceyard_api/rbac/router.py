from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.dependencies import require_permission
from iceyard_api.rbac.schemas import RoleAssignment, RoleCreate, RoleRead, RoleUpdate
from iceyard_api.rbac.service import RbacService

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleRead])
def list_roles(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RoleRead]:
    return RbacService(session).roles_for_workspace(current_user.workspace_id)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("roles.manage")),
) -> RoleRead:
    role = RbacService(session).create_role(
        current_user.workspace_id,
        payload.name,
        [(permission.action, permission.resource_selector) for permission in payload.permissions],
    )
    AuditService(session).record(
        action="roles.create",
        resource_type="role",
        resource_id=role.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"name": role.name, "permissions": [item.action for item in role.permissions]},
    )
    session.commit()
    return RoleRead.model_validate(role)


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("roles.manage")),
) -> RoleRead:
    service = RbacService(session)
    before = service.get_role(current_user.workspace_id, role_id)
    before_state = {
        "name": before.name,
        "permissions": [permission.action for permission in before.permissions],
    }
    role = service.update_role(
        current_user.workspace_id,
        role_id,
        name=payload.name,
        permissions=None
        if payload.permissions is None
        else [
            (permission.action, permission.resource_selector)
            for permission in payload.permissions
        ],
    )
    AuditService(session).record(
        action="roles.update",
        resource_type="role",
        resource_id=role.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={"name": role.name, "permissions": [item.action for item in role.permissions]},
    )
    session.commit()
    return RoleRead.model_validate(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("roles.manage")),
) -> Response:
    service = RbacService(session)
    role = service.get_role(current_user.workspace_id, role_id)
    before_state = {"name": role.name, "permissions": [item.action for item in role.permissions]}
    service.delete_role(current_user.workspace_id, role_id)
    AuditService(session).record(
        action="roles.delete",
        resource_type="role",
        resource_id=role_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/users/{user_id}", response_model=RoleAssignment)
def replace_user_roles(
    user_id: str,
    payload: RoleAssignment,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("roles.manage")),
) -> RoleAssignment:
    user = RbacService(session).replace_user_roles(
        current_user.workspace_id, user_id, payload.role_ids
    )
    AuditService(session).record(
        action="roles.assign",
        resource_type="user",
        resource_id=user.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"roles": [role.name for role in user.roles]},
    )
    session.commit()
    return RoleAssignment(role_ids=[role.id for role in user.roles])
