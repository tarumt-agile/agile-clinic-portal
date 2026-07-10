from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    """Payload for booking a new appointment. Mirrors the appointment creation form fields."""

    patient_id: str = Field(min_length=1, description="Patient's public patient_id, e.g. P00001")
    doctor_id: str = Field(min_length=1, description="Doctor's public staff_id, e.g. S00001")
    appointment_date: dt.date
    start_time: dt.time
    reason: str = Field(min_length=2, max_length=255)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Reason for visit is required")
        return v


class AppointmentOut(BaseModel):
    """Appointment details returned by the API, including patient/doctor display names."""

    model_config = ConfigDict(from_attributes=True)

    reference_number: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    appointment_date: dt.date
    start_time: dt.time
    end_time: dt.time
    reason: str
    status: str
    cancellation_reason: str | None
    created_at: dt.datetime
