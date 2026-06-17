from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.db.models import Role, User


class RbacService:
    def __init__(self, session: Session):
        self.session = session

    def roles_for_workspace(self, workspace_id: str) -> list[Role]:
        return list(self.session.scalars(select(Role).where(Role.workspace_id == workspace_id)))

    def user_actions(self, user: User) -> set[str]:
        actions: set[str] = set()
        for role in user.roles:
            for permission in role.permissions:
                actions.add(permission.action)
        return actions

    def can(self, user: User, action: str) -> bool:
        actions = self.user_actions(user)
        return "*" in actions or action in actions
