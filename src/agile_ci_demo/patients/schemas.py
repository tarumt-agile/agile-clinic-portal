from __future__ import annotations

import datetime as dt
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_PHONE_RE = re.compile(r"^\+?\d[\d\s-]{6,19}$")


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class PatientCreate(BaseModel):
    """Payload for registering a new patient. Mirrors the registration form fields."""

    full_name: str = Field(min_length=2, max_length=120)
    date_of_birth: dt.date
    gender: Gender
    phone_number: str = Field(min_length=7, max_length=20)
    email: EmailStr | None = None
    ic_or_passport: str = Field(min_length=5, max_length=30)
    address: str | None = Field(default=None, max_length=255)

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_not_in_future(cls, v: dt.date) -> dt.date:
        if v > dt.date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v

    @field_validator("phone_number")
    @classmethod
    def phone_number_is_valid(cls, v: str) -> str:
        v = v.strip()
        if not _PHONE_RE.fullmatch(v):
            raise ValueError("Phone number must be 7-20 digits, optionally starting with '+'")
        return v

    @field_validator("ic_or_passport")
    @classmethod
    def ic_or_passport_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("IC / passport number is required")
        return v

    @field_validator("address")
    @classmethod
    def blank_address_is_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class PatientOut(BaseModel):
    """Patient details returned by the API, including the generated patient ID."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    full_name: str
    date_of_birth: dt.date
    gender: Gender
    phone_number: str
    email: EmailStr | None
    ic_or_passport: str
    address: str | None
    created_at: dt.datetime


class PaginatedPatients(BaseModel):
    """Paginated search results for the patient list page."""

    items: list[PatientOut]
    total: int
    page: int
    page_size: int
    total_pages: int
