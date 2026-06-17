from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.auth.password import hash_password
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.dependencies import require_permission
from iceyard_api.rbac.service import RbacService
from iceyard_api.users.schemas import UserCreate, UserDetailRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserDetailRead])
def list_users(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    return list(session.scalars(select(User).where(User.workspace_id == current_user.workspace_id)))


@router.post("", response_model=UserDetailRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("users.manage")),
) -> UserDetailRead:
    email = payload.email.lower()
    existing = session.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists.")
    user = User(
        workspace_id=current_user.workspace_id,
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        is_service_account=payload.is_service_account,
    )
    user.roles = RbacService(session).roles_by_ids(current_user.workspace_id, payload.role_ids)
    session.add(user)
    session.flush()
    AuditService(session).record(
        action="users.create",
        resource_type="user",
        resource_id=user.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={
            "email": user.email,
            "display_name": user.display_name,
            "roles": [role.name for role in user.roles],
            "is_service_account": user.is_service_account,
        },
    )
    session.commit()
    return UserDetailRead.model_validate(user)


@router.get("/{user_id}", response_model=UserDetailRead)
def get_user(
    user_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UserDetailRead:
    return UserDetailRead.model_validate(
        RbacService(session).get_user(current_user.workspace_id, user_id)
    )


@router.patch("/{user_id}", response_model=UserDetailRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("users.manage")),
) -> UserDetailRead:
    service = RbacService(session)
    user = service.get_user(current_user.workspace_id, user_id)
    before_state = {
        "display_name": user.display_name,
        "is_active": user.is_active,
        "roles": [role.name for role in user.roles],
    }
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.is_active is not None:
        if user.id == current_user.id and payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Users cannot deactivate their own account.",
            )
        user.is_active = payload.is_active
    if payload.role_ids is not None:
        user.roles = service.roles_by_ids(current_user.workspace_id, payload.role_ids)
    session.flush()
    AuditService(session).record(
        action="users.update",
        resource_type="user",
        resource_id=user.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={
            "display_name": user.display_name,
            "is_active": user.is_active,
            "roles": [role.name for role in user.roles],
        },
    )
    session.commit()
    return UserDetailRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("users.manage")),
) -> Response:
    user = RbacService(session).get_user(current_user.workspace_id, user_id)
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Users cannot deactivate their own account.",
        )
    before_state = {"is_active": user.is_active}
    user.is_active = False
    AuditService(session).record(
        action="users.deactivate",
        resource_type="user",
        resource_id=user.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={"is_active": user.is_active},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
