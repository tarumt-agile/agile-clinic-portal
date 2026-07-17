from __future__ import annotations

import datetime as dt
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from agile_ci_demo.core.rbac import Role


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


class StaffCreate(BaseModel):
    """Create any staff account. Doctor-only fields are conditional."""

    full_name: str = Field(max_length=120)
    email: EmailStr
    role: Role
    license_number: str | None = None
    specialty: Specialty | None = None
    status: DoctorStatus = DoctorStatus.ACTIVE

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("Full name must be filled in.")
        if len(value.split()) < 2:
            raise ValueError("Full name must contain at least 2 words.")
        if not all(
            word.replace("-", "").replace("'", "").replace(".", "").isalpha()
            for word in value.split()
        ):
            raise ValueError(
                "Full name may only contain letters, spaces, apostrophes, periods and hyphens."
            )
        return value

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("license_number")
    @classmethod
    def validate_license_number(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        value = value.strip().upper()
        if not re.fullmatch(r"MMC-\d{5}", value):
            raise ValueError("Registration number must use the format MMC-12345.")
        return value

    @model_validator(mode="after")
    def validate_doctor_fields(self):
        if self.role == Role.DOCTOR:
            if self.license_number is None:
                raise ValueError("MMC registration number is required for a doctor.")
            if self.specialty is None:
                raise ValueError("Specialty is required for a doctor.")
        else:
            self.license_number = None
            self.specialty = None
            self.status = DoctorStatus.ACTIVE
        return self


class StaffOut(BaseModel):
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
    is_active: bool


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
        if not value or len(value.split()) < 2:
            raise ValueError("Doctor full name must contain at least 2 words.")
        return value

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("license_number")
    @classmethod
    def validate_license_number(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"MMC-\d{5}", value):
            raise ValueError("Registration number must use the format MMC-12345.")
        return value


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doctor_id: str
    staff_id: str
    full_name: str
    email: EmailStr
    license_number: str
    specialty: str
    department: str
    status: str
    created_at: dt.datetime


class DoctorUpdate(DoctorRegister):
    pass
