from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BootstrapRequest(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    email: str
    display_name: str
    is_active: bool
    is_service_account: bool
    created_at: datetime


class BootstrapResponse(BaseModel):
    workspace_id: str
    user: UserRead
    token: TokenResponse
