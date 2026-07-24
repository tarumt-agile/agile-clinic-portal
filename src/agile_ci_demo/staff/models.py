from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Time
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
        if self.doctor_profile is None:
            return None
        return self.doctor_profile.license_number

    @property
    def specialty(self) -> str | None:
        if self.doctor_profile is None:
            return None
        return self.doctor_profile.specialty

    @property
    def department(self) -> str | None:
        if self.doctor_profile is None:
            return None
        return self.doctor_profile.department

    @property
    def doctor_status(self) -> str | None:
        if self.doctor_profile is None:
            return None
        return self.doctor_profile.status

    @property
    def start_time(self) -> dt.time | None:
        if self.doctor_profile is None:
            return None
        return get_doctor_hours(self.doctor_profile, dt.date.today())[0]

    @property
    def end_time(self) -> dt.time | None:
        if self.doctor_profile is None:
            return None
        return get_doctor_hours(self.doctor_profile, dt.date.today())[1]


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

    # Working hours in effect right now (used for today and any date without a
    # newer change queued). New doctors default to the clinic's old 9-5 hours.
    start_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(9, 0))
    end_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(17, 0))

    # A queued future change, set when an admin edits a doctor's hours. Only one
    # change can be queued at a time - see get_doctor_hours() below.
    next_start_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    next_end_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    next_effective_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    staff: Mapped[Staff] = relationship(back_populates="doctor_profile")


def get_doctor_hours(profile: DoctorProfile, date: dt.date) -> tuple[dt.time, dt.time]:
    """The doctor's working hours in effect on the given date. A queued change
    (next_start_time/next_end_time) only applies from next_effective_date onward -
    before that, the current start_time/end_time pair still applies."""
    if profile.next_effective_date is not None and date >= profile.next_effective_date:
        return profile.next_start_time, profile.next_end_time  # type: ignore[return-value]
    return profile.start_time, profile.end_time
