"""Validation schemas for consultation notes and diagnoses."""

from __future__ import annotations

import datetime as dt

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class DiagnosisIn(BaseModel):
    """A diagnosis submitted with a consultation."""

    icd10_code: str = Field(
        min_length=2,
        max_length=10,
    )

    description: str = Field(
        min_length=2,
        max_length=255,
    )

    @field_validator("icd10_code")
    @classmethod
    def icd10_code_not_blank(
        cls,
        value: str,
    ) -> str:
        value = value.strip().upper()

        if not value:
            raise ValueError("ICD-10 code is required.")

        return value

    @field_validator("description")
    @classmethod
    def description_not_blank(
        cls,
        value: str,
    ) -> str:
        value = " ".join(value.strip().split())

        if not value:
            raise ValueError("Diagnosis description is required.")

        return value


class DiagnosisOut(BaseModel):
    """A diagnosis returned with its database ID."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    icd10_code: str
    description: str


class ConsultationNoteCreate(BaseModel):
    """Payload used to document a consultation.

    No doctor_id - the doctor is always whoever is logged in (require_role(Role.DOCTOR)
    on the endpoint), not a value the client can choose.
    """

    patient_id: str = Field(
        min_length=1,
    )

    # The appointment this consultation was started from, if any - lets ending
    # the consultation mark that appointment completed instead of leaving it
    # "scheduled" forever. Optional since not every consultation has one.
    appointment_reference: str | None = Field(
        default=None,
        min_length=1,
    )

    notes: str = Field(
        min_length=2,
    )

    diagnoses: list[DiagnosisIn] = Field(
        min_length=1,
    )

    @field_validator("notes")
    @classmethod
    def notes_not_blank(
        cls,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Consultation notes are required.")

        return value


class ConsultationNoteOut(BaseModel):
    """A complete consultation record."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    record_id: str

    patient_id: str
    patient_name: str

    doctor_id: str
    doctor_name: str

    visit_date: dt.datetime
    notes: str

    diagnoses: list[DiagnosisOut]

    started_at: dt.datetime
    ended_at: dt.datetime | None
    status: str

    created_at: dt.datetime


class ConsultationNoteSummary(BaseModel):
    """A consultation summary for medical history."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    record_id: str
    visit_date: dt.datetime
    doctor_name: str
    notes: str
    diagnoses: list[DiagnosisOut]
    status: str


class PatientHistory(BaseModel):
    """A patient's consultation history."""

    items: list[ConsultationNoteSummary]
    total: int


class ConsultationQueueEntry(BaseModel):
    """One of a doctor's non-cancelled appointments for today, paired with its
    linked consultation note's state (if any) - lets the Start Consultation page
    decide whether to offer "Start Consultation", "Continue Consultation", or "Ended"."""

    reference_number: str
    patient_id: str
    patient_name: str
    start_time: dt.time
    end_time: dt.time
    reason: str
    appointment_status: str
    consultation_record_id: str | None
    consultation_status: str | None


class DoctorConsultationQueue(BaseModel):
    """A doctor's today's consultation queue, ordered by appointment start time."""

    doctor_id: str
    doctor_name: str
    appointments: list[ConsultationQueueEntry]


class Icd10Entry(BaseModel):
    """An ICD-10 search result."""

    code: str
    description: str
