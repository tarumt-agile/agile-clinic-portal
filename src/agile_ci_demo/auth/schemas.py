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


class PatientLoginRequest(BaseModel):
    ic_or_passport: str
    phone_number: str


class PatientLoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    full_name: str
