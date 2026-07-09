from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from agile_ci_demo.core.rbac import Role


class StaffCreate(BaseModel):
    """Payload for creating a new staff account. A temporary password is generated
    server-side and emailed to the staff member - it is never supplied by the caller."""

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: Role

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required")
        return v


class StaffOut(BaseModel):
    """Staff account details returned by the API. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    staff_id: str
    full_name: str
    email: EmailStr
    role: Role
    is_active: bool
    must_change_password: bool
    created_at: dt.datetime


class StaffStatusUpdate(BaseModel):
    """Payload for activating/deactivating a staff account from the user management page."""

    is_active: bool
