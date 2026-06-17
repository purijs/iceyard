from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.auth.schemas import UserRead
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    return list(session.scalars(select(User).where(User.workspace_id == current_user.workspace_id)))
