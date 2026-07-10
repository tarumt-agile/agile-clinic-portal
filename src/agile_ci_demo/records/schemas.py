from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiagnosisIn(BaseModel):
    """A single diagnosis entry submitted as part of a consultation note."""

    icd10_code: str = Field(min_length=2, max_length=10)
    description: str = Field(min_length=2, max_length=255)

    @field_validator("icd10_code")
    @classmethod
    def icd10_code_not_blank(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ICD-10 code is required")
        return v

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Diagnosis description is required")
        return v


class DiagnosisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    icd10_code: str
    description: str


class ConsultationNoteCreate(BaseModel):
    """Payload for documenting a consultation. At least one diagnosis is required."""

    patient_id: str = Field(min_length=1, description="Patient's public patient_id, e.g. P00001")
    doctor_id: str = Field(min_length=1, description="Doctor's public staff_id, e.g. S00001")
    notes: str = Field(min_length=2, description="Consultation note body")
    diagnoses: list[DiagnosisIn] = Field(min_length=1)

    @field_validator("notes")
    @classmethod
    def notes_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Consultation notes are required")
        return v


class ConsultationNoteOut(BaseModel):
    """Full consultation note, including patient/doctor display names and diagnoses."""

    model_config = ConfigDict(from_attributes=True)

    record_id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    visit_date: dt.datetime
    notes: str
    diagnoses: list[DiagnosisOut]
    created_at: dt.datetime


class ConsultationNoteSummary(BaseModel):
    """Lightweight shape used for a patient's medical history list."""

    model_config = ConfigDict(from_attributes=True)

    record_id: str
    visit_date: dt.datetime
    doctor_name: str
    notes: str
    diagnoses: list[DiagnosisOut]


class PatientHistory(BaseModel):
    """A patient's medical history, optionally filtered by a search keyword."""

    items: list[ConsultationNoteSummary]
    total: int


class Icd10Entry(BaseModel):
    """A single ICD-10 code/description pair returned by the autocomplete search."""

    code: str
    description: str
