from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=4, max_length=256)
    role_ids: list[str] = Field(default_factory=list)
    is_service_account: bool = False


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=320)
    is_active: bool | None = None
    role_ids: list[str] | None = None


class UserRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class UserDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    username: str
    email: str
    display_name: str
    is_active: bool
    is_service_account: bool
    created_at: datetime
    roles: list[UserRoleRead]
