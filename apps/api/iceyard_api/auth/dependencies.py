from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from iceyard_api.auth.service import AuthService
from iceyard_api.core.config import Settings, get_settings
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_current_token(
    authorization: Annotated[str | None, Header()] = None,
    iceyard_session: Annotated[str | None, Cookie()] = None,
) -> str:
    token = bearer_token(authorization) or iceyard_session
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        )
    return token


def get_current_user(
    token: str = Depends(get_current_token),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    user = AuthService(session, settings).user_for_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        )
    return user
