from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.db.models import Permission, Role, User


class RbacService:
    def __init__(self, session: Session):
        self.session = session

    def roles_for_workspace(self, workspace_id: str) -> list[Role]:
        return list(self.session.scalars(select(Role).where(Role.workspace_id == workspace_id)))

    def get_role(self, workspace_id: str, role_id: str) -> Role:
        role = self.session.get(Role, role_id)
        if not role or role.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
        return role

    def create_role(
        self,
        workspace_id: str,
        name: str,
        permissions: list[tuple[str, dict[str, object]]],
    ) -> Role:
        exists = self.session.scalar(
            select(Role).where(Role.workspace_id == workspace_id, Role.name == name)
        )
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role already exists.")
        role = Role(workspace_id=workspace_id, name=name)
        self.session.add(role)
        self.session.flush()
        self.replace_permissions(role, permissions)
        return role

    def update_role(
        self,
        workspace_id: str,
        role_id: str,
        *,
        name: str | None = None,
        permissions: list[tuple[str, dict[str, object]]] | None = None,
    ) -> Role:
        role = self.get_role(workspace_id, role_id)
        if name and name != role.name:
            exists = self.session.scalar(
                select(Role).where(Role.workspace_id == workspace_id, Role.name == name)
            )
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Role already exists."
                )
            role.name = name
        if permissions is not None:
            self.replace_permissions(role, permissions)
        self.session.flush()
        return role

    def delete_role(self, workspace_id: str, role_id: str) -> None:
        role = self.get_role(workspace_id, role_id)
        if role.name == "platform_admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The platform_admin role cannot be deleted.",
            )
        self.session.delete(role)

    def replace_permissions(
        self, role: Role, permissions: list[tuple[str, dict[str, object]]]
    ) -> None:
        role.permissions.clear()
        self.session.flush()
        seen: set[str] = set()
        for action, selector in permissions:
            if action in seen:
                continue
            seen.add(action)
            role.permissions.append(
                Permission(action=action, resource_selector=selector or {"scope": "*"})
            )

    def get_user(self, workspace_id: str, user_id: str) -> User:
        user = self.session.get(User, user_id)
        if not user or user.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    def roles_by_ids(self, workspace_id: str, role_ids: list[str]) -> list[Role]:
        if not role_ids:
            return []
        roles = list(
            self.session.scalars(
                select(Role).where(Role.workspace_id == workspace_id, Role.id.in_(role_ids))
            )
        )
        if len(roles) != len(set(role_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role id.")
        return roles

    def replace_user_roles(self, workspace_id: str, user_id: str, role_ids: list[str]) -> User:
        user = self.get_user(workspace_id, user_id)
        user.roles = self.roles_by_ids(workspace_id, role_ids)
        self.session.flush()
        return user

    def user_actions(self, user: User) -> set[str]:
        actions: set[str] = set()
        for role in user.roles:
            for permission in role.permissions:
                actions.add(permission.action)
        return actions

    def can(self, user: User, action: str) -> bool:
        actions = self.user_actions(user)
        return "*" in actions or action in actions
