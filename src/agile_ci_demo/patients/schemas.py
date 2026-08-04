from __future__ import annotations

import datetime as dt
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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
    ic_or_passport: str = Field(min_length=1, max_length=30)
    email: EmailStr | None = None
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
    def date_of_birth_in_valid_range(cls, v: dt.date) -> dt.date:
        today = dt.date.today()
        if v > today:
            raise ValueError("Date of birth cannot be in the future")
        try:
            earliest = today.replace(year=today.year - 100)
        except ValueError:
            # today is Feb 29 and (today.year - 100) isn't a leap year.
            earliest = today.replace(year=today.year - 100, day=28)
        if v < earliest:
            raise ValueError("Date of birth cannot be more than 100 years ago")
        return v

    @field_validator("phone_number")
    @classmethod
    def phone_number_is_valid(cls, v: str) -> str:
        v = v.strip()
        if not _PHONE_RE.fullmatch(v):
            raise ValueError("Phone number must be 7-20 characters, optionally starting with '+'")
        return v

    @field_validator("address")
    @classmethod
    def blank_address_is_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def validate_ic_or_passport(self) -> "PatientCreate":
        ic = self.ic_or_passport
        if ic is None:
            return self

        if re.fullmatch(r"\d{6}-\d{2}-\d{4}", ic):
            dob_digits = self.date_of_birth.strftime("%y%m%d")
            if ic[:6] != dob_digits:
                raise ValueError("IC number does not match the date of birth.")

            last_digit = int(ic[-1])
            if self.gender == Gender.MALE and last_digit % 2 == 0:
                raise ValueError("IC number's last digit does not match a male patient.")
            if self.gender == Gender.FEMALE and last_digit % 2 != 0:
                raise ValueError("IC number's last digit does not match a female patient.")
        elif not re.match(r"^[A-Za-z]", ic):
            raise ValueError("Enter a valid IC number (xxxxxx-xx-xxxx) or passport number.")

        return self


class PatientUpdate(PatientCreate):
    """Payload for editing an existing patient. Same shape and validation as PatientCreate -
    every field is re-validated on save, per the "validate every patient field" requirement.
    ic_or_passport is the one exception: it's optional here and always ignored by
    update_patient() - IC/passport is fixed at registration and never changes."""

    ic_or_passport: str | None = None  # type: ignore[assignment]


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


class PatientIcSuggestion(BaseModel):
    """A lightweight patient match for the IC autocomplete suggestion dropdown."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    full_name: str
    ic_or_passport: str


class PaginatedPatients(BaseModel):
    """Paginated search results for the patient list page."""

    items: list[PatientOut]
    total: int
    page: int
    page_size: int
    total_pages: int
