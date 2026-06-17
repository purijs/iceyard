from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_token, get_current_user
from iceyard_api.auth.schemas import (
    BootstrapRequest,
    BootstrapResponse,
    LoginRequest,
    TokenResponse,
    UserRead,
)
from iceyard_api.auth.service import AuthService
from iceyard_api.core.config import Settings, get_settings
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        "iceyard_session",
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
    )


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap(
    payload: BootstrapRequest,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> BootstrapResponse:
    service = AuthService(session, settings)
    workspace, user, raw_token, session_token = service.bootstrap(payload)
    AuditService(session).record(
        action="auth.bootstrap",
        resource_type="workspace",
        resource_id=workspace.id,
        workspace_id=workspace.id,
        actor_id=user.id,
        after_state={"workspace": workspace.name, "user": user.email},
    )
    session.commit()
    set_session_cookie(response, raw_token, settings)
    return BootstrapResponse(
        workspace_id=workspace.id,
        user=UserRead.model_validate(user),
        token=TokenResponse(access_token=raw_token, expires_at=session_token.expires_at),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    service = AuthService(session, settings)
    user = service.authenticate(payload.email, payload.password)
    raw_token, session_token = service.create_session(user)
    AuditService(session).record(
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        workspace_id=user.workspace_id,
        actor_id=user.id,
    )
    session.commit()
    set_session_cookie(response, raw_token, settings)
    return TokenResponse(access_token=raw_token, expires_at=session_token.expires_at)


@router.post("/logout")
def logout(
    response: Response,
    token: str = Depends(get_current_token),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    AuthService(session, settings).logout(token)
    AuditService(session).record(
        action="auth.logout",
        resource_type="user",
        resource_id=current_user.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
    )
    session.commit()
    response.delete_cookie("iceyard_session")
    return {"status": "ok"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
