from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.service import RbacService


def require_permission(action: str) -> Callable[..., User]:
    def dependency(
        current_user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> User:
        if not RbacService(session).can(current_user, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        return current_user

    return dependency
