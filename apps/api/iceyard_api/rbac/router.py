from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.schemas import RoleRead
from iceyard_api.rbac.service import RbacService

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleRead])
def list_roles(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RoleRead]:
    return RbacService(session).roles_for_workspace(current_user.workspace_id)
