from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from agile_ci_demo.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    # Internal auto-increment primary key, used only to derive patient_id.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Public-facing, human-readable unique identifier, e.g. "P00001".
    # Nullable at the DB level only because it is derived from `id` after the
    # initial flush (see patients.service.create_patient) - the service layer
    # guarantees it is always set before commit.
    patient_id: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)

    full_name: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[dt.date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(20))
    phone_number: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ic_or_passport: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )
