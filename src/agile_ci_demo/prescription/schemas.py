from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class PrescriptionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MedicationOption(BaseModel):
    value: str
    label: str


class PrescriptionOptionsOut(BaseModel):
    medications: list[MedicationOption]
    dosages: list[str]
    frequencies: list[str]
    durations: list[str]


class PrescriptionCreate(BaseModel):
    consultation_record_id: str = Field(
        min_length=1,
        max_length=12,
    )

    diagnosis_id: int = Field(
        gt=0,
    )

    medication: str = Field(
        min_length=2,
        max_length=150,
    )

    dosage: str = Field(
        min_length=1,
        max_length=120,
    )

    frequency: str = Field(
        min_length=1,
        max_length=120,
    )

    duration: str = Field(
        min_length=1,
        max_length=120,
    )

    @field_validator(
        "consultation_record_id",
        "medication",
        "dosage",
        "frequency",
        "duration",
    )
    @classmethod
    def fields_must_not_be_blank(
        cls,
        value: str,
    ) -> str:
        value = " ".join(
            value.strip().split()
        )

        if not value:
            raise ValueError(
                "This field is required."
            )

        return value


class PrescriptionDosageUpdate(BaseModel):
    dosage: str = Field(
        min_length=1,
        max_length=120,
    )

    change_reason: str = Field(
        min_length=3,
        max_length=500,
    )

    @field_validator(
        "dosage",
        "change_reason",
    )
    @classmethod
    def fields_must_not_be_blank(
        cls,
        value: str,
    ) -> str:
        value = " ".join(
            value.strip().split()
        )

        if not value:
            raise ValueError(
                "This field is required."
            )

        return value


class PrescriptionHistoryOut(BaseModel):
    previous_dosage: str
    new_dosage: str
    change_reason: str

    changed_by_doctor_id: str
    changed_by_doctor_name: str

    changed_at: dt.datetime


class PrescriptionOut(BaseModel):
    prescription_id: str

    consultation_record_id: str

    diagnosis_id: int
    diagnosis_code: str
    diagnosis_description: str

    patient_id: str
    patient_name: str

    prescribing_doctor_id: str
    prescribing_doctor_name: str

    medication: str
    dosage: str
    frequency: str
    duration: str

    status: PrescriptionStatus

    issued_at: dt.datetime
    updated_at: dt.datetime

    can_edit: bool

    history: list[
        PrescriptionHistoryOut
    ] = []


class PrescriptionList(BaseModel):
    items: list[PrescriptionOut]
    total: int