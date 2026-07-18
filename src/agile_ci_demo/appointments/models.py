from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agile_ci_demo.core.database import Base
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff


class Appointment(Base):
    __tablename__ = "appointments"

    # Internal auto-increment primary key, used only to derive reference_number.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Public-facing, human-readable unique identifier, e.g. "A00001".
    # Nullable at the DB level only because it is derived from `id` after the
    # initial flush (see appointments.service.create_appointment) - the service
    # layer guarantees it is always set before commit.
    reference_number: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)

    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)

    appointment_date: Mapped[dt.date] = mapped_column(Date, index=True)
    start_time: Mapped[dt.time] = mapped_column(Time)
    end_time: Mapped[dt.time] = mapped_column(Time)

    reason: Mapped[str] = mapped_column(String(255))
    # "scheduled" | "cancelled"
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Staff] = relationship()
