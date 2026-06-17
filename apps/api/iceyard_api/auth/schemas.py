from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BootstrapRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=320)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    password: str = Field(min_length=4, max_length=256)
    workspace_name: str = Field(default="default", min_length=2, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_username(self) -> "BootstrapRequest":
        if not self.username and not self.email:
            raise ValueError("Username is required.")
        return self

    @property
    def username_value(self) -> str:
        return str(self.username or self.email).lower()


class LoginRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode="after")
    def require_username(self) -> "LoginRequest":
        if not self.username and not self.email:
            raise ValueError("Username is required.")
        return self

    @property
    def username_value(self) -> str:
        return str(self.username or self.email).lower()


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=4, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    username: str
    email: str
    display_name: str
    is_active: bool
    is_service_account: bool
    created_at: datetime


class BootstrapResponse(BaseModel):
    workspace_id: str
    user: UserRead
    token: TokenResponse
