from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import DoctorProfile, Staff


def get_admin_dashboard_stats(db: Session) -> dict[str, int]:
    """Clinic-wide counts for the admin dashboard's stat cards."""
    total_patients = db.execute(select(func.count()).select_from(Patient)).scalar_one()

    total_staff = db.execute(select(func.count()).select_from(Staff)).scalar_one()

    active_doctors = db.execute(
        select(func.count()).select_from(DoctorProfile).where(DoctorProfile.status == "active")
    ).scalar_one()

    appointments_today = db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.status == "scheduled",
            Appointment.appointment_date == dt.date.today(),
        )
    ).scalar_one()

    return {
        "total_patients": total_patients,
        "total_staff": total_staff,
        "active_doctors": active_doctors,
        "appointments_today": appointments_today,
    }
