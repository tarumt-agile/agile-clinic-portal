from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr

from agile_ci_demo.core.rbac import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    staff_id: str
    full_name: str
    role: Role
    must_change_password: bool
