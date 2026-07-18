from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agile_ci_demo.core.database import Base
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff


class ConsultationNote(Base):
    __tablename__ = "consultation_notes"

    # Internal auto-increment primary key, used only to derive record_id.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Public-facing, human-readable unique identifier, e.g. "R00001".
    # Nullable at the DB level only because it is derived from `id` after the
    # initial flush (see records.service.create_consultation_note) - the service
    # layer guarantees it is always set before commit.
    record_id: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)

    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)

    visit_date: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, index=True
    )
    notes: Mapped[str] = mapped_column(Text)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Staff] = relationship()
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

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    consultation_note: Mapped[ConsultationNote] = relationship(back_populates="diagnoses")
