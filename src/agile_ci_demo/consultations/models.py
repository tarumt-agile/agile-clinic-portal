from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.core.database import Base
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff

MALAYSIA_OFFSET = dt.timedelta(hours=8)


def malaysia_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone(MALAYSIA_OFFSET))


class ConsultationNote(Base):
    __tablename__ = "consultation_notes"

    # Internal auto-increment primary key, used only to derive record_id.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Public-facing, human-readable unique identifier, e.g. "R00001".
    # Nullable at the DB level only because it is derived from `id` after the
    # initial flush (see consultations.service.create_consultation_note) - the service
    # layer guarantees it is always set before commit.
    record_id: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)

    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    # The appointment this consultation was started from, if any (nullable - not
    # every consultation necessarily originates from a scheduled appointment).
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True, index=True
    )

    visit_date: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=malaysia_now, index=True
    )
    notes: Mapped[str] = mapped_column(Text)

    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=malaysia_now)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # "in_progress" | "completed"
    status: Mapped[str] = mapped_column(String(20), default="in_progress")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=malaysia_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=malaysia_now, onupdate=malaysia_now
    )

    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Staff] = relationship()
    appointment: Mapped[Appointment | None] = relationship()
    diagnoses: Mapped[list["Diagnosis"]] = relationship(
        back_populates="consultation_note",
        cascade="all, delete-orphan",
        order_by="Diagnosis.id",
    )


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    consultation_note_id: Mapped[int] = mapped_column(
        ForeignKey("consultation_notes.id"), index=True
    )

    icd10_code: Mapped[str] = mapped_column(String(10), index=True)
    description: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=malaysia_now)

    consultation_note: Mapped[ConsultationNote] = relationship(back_populates="diagnoses")


class MedicalAccessLog(Base):
    __tablename__ = "medical_access_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    consultation_note_id: Mapped[int] = mapped_column(
        ForeignKey("consultation_notes.id"), index=True
    )
    record_id: Mapped[str | None] = mapped_column(String(10), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    accessed_by_staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)

    # "read" | "create" | "update" | "end"
    action: Mapped[str] = mapped_column(String(20), index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=malaysia_now, index=True
    )
