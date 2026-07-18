from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from agile_ci_demo.core.database import Base
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.records.models import (
    ConsultationNote,
    Diagnosis,
)
from agile_ci_demo.staff.models import Staff


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    prescription_id: Mapped[str | None] = mapped_column(
        String(12),
        unique=True,
        index=True,
    )

    consultation_note_id: Mapped[int] = mapped_column(
        ForeignKey("consultation_notes.id"),
        index=True,
    )

    diagnosis_id: Mapped[int] = mapped_column(
        ForeignKey("diagnoses.id"),
        index=True,
    )

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
        index=True,
    )

    prescribing_doctor_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id"),
        index=True,
    )

    medication: Mapped[str] = mapped_column(
        String(150),
    )

    dosage: Mapped[str] = mapped_column(
        String(120),
    )

    frequency: Mapped[str] = mapped_column(
        String(120),
    )

    duration: Mapped[str] = mapped_column(
        String(120),
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        index=True,
    )

    issued_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=dt.datetime.utcnow,
        index=True,
    )

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )

    consultation_note: Mapped[ConsultationNote] = relationship()

    diagnosis: Mapped[Diagnosis] = relationship()

    patient: Mapped[Patient] = relationship()

    prescribing_doctor: Mapped[Staff] = relationship(
        foreign_keys=[prescribing_doctor_id],
    )

    history: Mapped[list["PrescriptionHistory"]] = relationship(
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by=("PrescriptionHistory.changed_at.desc()"),
    )


class PrescriptionHistory(Base):
    __tablename__ = "prescription_history"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id"),
        index=True,
    )

    previous_dosage: Mapped[str] = mapped_column(
        String(120),
    )

    new_dosage: Mapped[str] = mapped_column(
        String(120),
    )

    previous_frequency: Mapped[str] = mapped_column(
        String(120),
    )

    new_frequency: Mapped[str] = mapped_column(
        String(120),
    )

    previous_duration: Mapped[str] = mapped_column(
        String(120),
    )

    new_duration: Mapped[str] = mapped_column(
        String(120),
    )

    change_reason: Mapped[str] = mapped_column(
        Text,
    )

    changed_by_doctor_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id"),
        index=True,
    )

    changed_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=dt.datetime.utcnow,
        index=True,
    )

    prescription: Mapped[Prescription] = relationship(
        back_populates="history",
    )

    changed_by_doctor: Mapped[Staff] = relationship(
        foreign_keys=[changed_by_doctor_id],
    )
