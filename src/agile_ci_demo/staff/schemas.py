from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from agile_ci_demo.core.rbac import Role


class StaffCreate(BaseModel):
    """Payload for creating a new staff account."""

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

    license_number: str | None = None
    specialty: str | None = None
    department: str | None = None
    doctor_status: str | None = None


class StaffStatusUpdate(BaseModel):
    """Payload for activating/deactivating a staff account."""

    is_active: bool


class DoctorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Specialty(str, Enum):
    GENERAL_MEDICINE = "General Medicine"
    FAMILY_MEDICINE = "Family Medicine"
    INTERNAL_MEDICINE = "Internal Medicine"
    CARDIOLOGY = "Cardiology"
    DERMATOLOGY = "Dermatology"
    EMERGENCY_MEDICINE = "Emergency Medicine"
    ENDOCRINOLOGY = "Endocrinology"
    GASTROENTEROLOGY = "Gastroenterology"
    GENERAL_SURGERY = "General Surgery"
    NEUROLOGY = "Neurology"
    OBSTETRICS_GYNAECOLOGY = "Obstetrics and Gynaecology"
    ONCOLOGY = "Oncology"
    OPHTHALMOLOGY = "Ophthalmology"
    ORTHOPAEDICS = "Orthopaedics"
    OTORHINOLARYNGOLOGY = "Otorhinolaryngology"
    PAEDIATRICS = "Paediatrics"
    PSYCHIATRY = "Psychiatry"
    RADIOLOGY = "Radiology"
    UROLOGY = "Urology"


class DoctorRegister(BaseModel):
    full_name: str = Field(max_length=120)
    email: EmailStr
    license_number: str
    specialty: Specialty
    status: DoctorStatus

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = " ".join(value.strip().split())

        if not value:
            raise ValueError("Doctor full name must be filled in.")

        words = value.split()

        if len(words) < 2:
            raise ValueError(
                "Doctor full name must contain at least 2 words."
            )

        if not all(
            word.replace("-", "")
            .replace("'", "")
            .replace(".", "")
            .isalpha()
            for word in words
        ):
            raise ValueError(
                "Full name may only contain letters, spaces, "
                "apostrophes, periods and hyphens."
            )

        return value

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("license_number")
    @classmethod
    def validate_license_number(cls, value: str) -> str:
        value = value.strip().upper()

        if not value:
            raise ValueError(
                "MMC registration number must be filled in."
            )

        if not re.fullmatch(r"MMC-\d{5}", value):
            raise ValueError(
                "Registration number must use the format MMC-12345."
            )

        return value