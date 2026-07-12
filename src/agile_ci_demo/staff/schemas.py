from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator

from agile_ci_demo.core.rbac import Role, Specialty


class StaffCreate(BaseModel):
    """Payload for creating a new staff account. A temporary password is generated
    server-side and emailed to the staff member - it is never supplied by the caller."""

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: Role
    # validate_default=True: the "specialty required for doctors" check must still
    # run even when the field is omitted entirely (Pydantic skips validators on
    # unset defaults otherwise).
    specialty: Specialty | None = Field(default=None, validate_default=True)

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required")
        return v

    @field_validator("specialty")
    @classmethod
    def specialty_matches_role(cls, v: Specialty | None, info: ValidationInfo) -> Specialty | None:
        role = info.data.get("role")
        if role == Role.DOCTOR and v is None:
            raise ValueError("Specialty is required for doctors")
        if role is not None and role != Role.DOCTOR and v is not None:
            raise ValueError("Only doctors may have a specialty")
        return v


class StaffOut(BaseModel):
    """Staff account details returned by the API. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    staff_id: str
    full_name: str
    email: EmailStr
    role: Role
    specialty: Specialty | None
    is_active: bool
    must_change_password: bool
    created_at: dt.datetime


class StaffStatusUpdate(BaseModel):
    """Payload for activating/deactivating a staff account from the user management page."""

    is_active: bool
