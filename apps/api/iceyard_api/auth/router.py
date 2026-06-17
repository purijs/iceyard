import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_token, get_current_user
from iceyard_api.auth.schemas import (
    BootstrapRequest,
    BootstrapResponse,
    LoginRequest,
    PasswordChangeRequest,
    TokenResponse,
    UserRead,
)
from iceyard_api.auth.service import AuthService
from iceyard_api.core.config import Settings, get_settings
from iceyard_api.core.ratelimit import FixedWindowRateLimiter
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()
_auth_rate_limiter = FixedWindowRateLimiter(
    max_attempts=_settings.auth_rate_limit_attempts,
    window_seconds=_settings.auth_rate_limit_window_seconds,
)


def _enforce_auth_rate_limit(request: Request, settings: Settings) -> None:
    if settings.environment == "test":
        return
    client_host = request.client.host if request.client else "unknown"
    if not _auth_rate_limiter.allow(client_host):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please retry shortly.",
        )


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        "iceyard_session",
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
    )


def set_csrf_cookie(response: Response, settings: Settings) -> str:
    """Issue a double-submit CSRF token (readable by JS, echoed via X-CSRF-Token)."""
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        "iceyard_csrf",
        token,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
    )
    return token


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> BootstrapResponse:
    _enforce_auth_rate_limit(request, settings)
    service = AuthService(session, settings)
    workspace, user, raw_token, session_token = service.bootstrap(payload)
    AuditService(session).record(
        action="auth.bootstrap",
        resource_type="workspace",
        resource_id=workspace.id,
        workspace_id=workspace.id,
        actor_id=user.id,
        after_state={"workspace": workspace.name, "username": user.username},
    )
    session.commit()
    set_session_cookie(response, raw_token, settings)
    set_csrf_cookie(response, settings)
    return BootstrapResponse(
        workspace_id=workspace.id,
        user=UserRead.model_validate(user),
        token=TokenResponse(access_token=raw_token, expires_at=session_token.expires_at),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    _enforce_auth_rate_limit(request, settings)
    service = AuthService(session, settings)
    service.ensure_default_admin()
    user = service.authenticate(payload.username_value, payload.password)
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
    set_csrf_cookie(response, settings)
    return TokenResponse(access_token=raw_token, expires_at=session_token.expires_at)


@router.get("/csrf")
def issue_csrf_token(
    response: Response,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    _ = current_user
    token = set_csrf_cookie(response, settings)
    return {"csrf_token": token}


@router.post("/password")
def change_password(
    payload: PasswordChangeRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    AuthService(session, settings).change_password(
        current_user, payload.current_password, payload.new_password
    )
    AuditService(session).record(
        action="auth.password.change",
        resource_type="user",
        resource_id=current_user.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
    )
    session.commit()
    return {"status": "ok"}


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
