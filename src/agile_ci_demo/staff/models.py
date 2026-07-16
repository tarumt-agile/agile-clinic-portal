from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agile_ci_demo.core.database import Base


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    staff_id: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)

    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    doctor_profile: Mapped["DoctorProfile | None"] = relationship(
        back_populates="staff",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def license_number(self) -> str | None:
        return self.doctor_profile.license_number if self.doctor_profile else None

    @property
    def specialty(self) -> str | None:
        return self.doctor_profile.specialty if self.doctor_profile else None

    @property
    def department(self) -> str | None:
        return self.doctor_profile.department if self.doctor_profile else None

    @property
    def doctor_status(self) -> str | None:
        return self.doctor_profile.status if self.doctor_profile else None


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    doctor_id: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)

    staff_account_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id"),
        unique=True,
        index=True,
    )

    license_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    specialty: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    staff: Mapped[Staff] = relationship(back_populates="doctor_profile")