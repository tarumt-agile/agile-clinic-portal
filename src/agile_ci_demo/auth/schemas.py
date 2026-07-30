from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

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
    redirect_url: str
    session_token: str


class PatientLoginRequest(BaseModel):
    ic_or_passport: str
    phone_number: str


class PatientLoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    full_name: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
