from pydantic import BaseModel, ConfigDict, Field


class PermissionCreate(BaseModel):
    action: str = Field(min_length=1, max_length=120)
    resource_selector: dict[str, object] = Field(default_factory=dict)


class PermissionUpdate(BaseModel):
    action: str | None = Field(default=None, min_length=1, max_length=120)
    resource_selector: dict[str, object] | None = None


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    resource_selector: dict[str, object]


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    permissions: list[PermissionRead]


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    permissions: list[PermissionCreate] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    permissions: list[PermissionCreate] | None = None


class RoleAssignment(BaseModel):
    role_ids: list[str]
