import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from iceyard_api.auth.password import hash_password, verify_password
from iceyard_api.auth.schemas import BootstrapRequest
from iceyard_api.core.config import Settings
from iceyard_api.core.time import utcnow
from iceyard_api.db.models import Permission, Role, SessionToken, User, Workspace

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "platform_admin": ["*"],
    "workspace_admin": [
        "workspace.read",
        "workspace.manage",
        "users.manage",
        "roles.manage",
        "connections.manage",
        "tables.read",
        "operations.read",
        "operations.execute",
        "jobs.read",
        "audit.read",
    ],
    "maintainer": [
        "connections.read",
        "tables.read",
        "operations.read",
        "operations.execute",
        "jobs.read",
    ],
    "analyst": ["connections.read", "tables.read", "operations.read", "jobs.read"],
    "viewer": ["connections.read", "tables.read", "jobs.read"],
}


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings

    def has_users(self) -> bool:
        return bool(self.session.scalar(select(func.count(User.id))))

    def bootstrap(self, payload: BootstrapRequest) -> tuple[Workspace, User, str, SessionToken]:
        if self.has_users():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bootstrap is only available before the first user exists.",
            )
        workspace = Workspace(name=payload.workspace_name)
        self.session.add(workspace)
        self.session.flush()
        roles = self._seed_roles(workspace.id)
        user = User(
            workspace_id=workspace.id,
            email=payload.email.lower(),
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
        )
        user.roles.append(roles["platform_admin"])
        self.session.add(user)
        self.session.flush()
        raw_token, session_token = self.create_session(user)
        return workspace, user, raw_token, session_token

    def _seed_roles(self, workspace_id: str) -> dict[str, Role]:
        roles: dict[str, Role] = {}
        for role_name, actions in ROLE_PERMISSIONS.items():
            role = Role(workspace_id=workspace_id, name=role_name)
            self.session.add(role)
            self.session.flush()
            for action in actions:
                self.session.add(
                    Permission(role_id=role.id, action=action, resource_selector={"scope": "*"})
                )
            roles[role_name] = role
        return roles

    def authenticate(self, email: str, password: str) -> User:
        user = self.session.scalar(select(User).where(User.email == email.lower()))
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        return user

    def create_session(self, user: User) -> tuple[str, SessionToken]:
        raw_token = secrets.token_urlsafe(48)
        expires_at = utcnow() + timedelta(minutes=self.settings.session_ttl_minutes)
        session_token = SessionToken(
            user_id=user.id,
            token_hash=token_digest(raw_token),
            expires_at=expires_at,
        )
        self.session.add(session_token)
        self.session.flush()
        return raw_token, session_token

    def user_for_token(self, raw_token: str) -> User | None:
        digest = token_digest(raw_token)
        session_token = self.session.scalar(
            select(SessionToken).where(
                SessionToken.token_hash == digest,
                SessionToken.expires_at > utcnow(),
            )
        )
        if not session_token:
            return None
        return self.session.get(User, session_token.user_id)

    def logout(self, raw_token: str) -> None:
        digest = token_digest(raw_token)
        session_token = self.session.scalar(
            select(SessionToken).where(SessionToken.token_hash == digest)
        )
        if session_token:
            self.session.delete(session_token)
