from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.core.database import SessionLocal, init_db
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff


init_db()

with SessionLocal() as db:
    patient = db.execute(
        select(Patient).order_by(Patient.id)
    ).scalars().first()
    doctor = db.execute(
        select(Staff).where(Staff.role == "doctor").order_by(Staff.id)
    ).scalars().first()

    if patient is None:
        raise RuntimeError("No patient exists in the database")
    if doctor is None:
        raise RuntimeError("No doctor exists in the database")

    date_today = dt.date.today()
    start_time = dt.time(18, 0)
    end_time = dt.time(18, 30)

    existing = db.execute(
        select(Appointment).where(
            Appointment.patient_id == patient.id,
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == date_today,
            Appointment.start_time == start_time,
        )
    ).scalar_one_or_none()

    if existing is not None:
        print(f"EXISTING {existing.reference_number} | {patient.patient_id} | {doctor.staff_id} | {existing.appointment_date} {existing.start_time}")
        raise SystemExit(0)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date_today,
        start_time=start_time,
        end_time=end_time,
        reason="Consultation",
        status="scheduled",
    )
    db.add(appointment)
    db.flush()
    appointment.reference_number = f"A{appointment.id:05d}"
    db.commit()
    db.refresh(appointment)

    print(f"CREATED {appointment.reference_number} | patient={patient.patient_id} | doctor={doctor.staff_id} | date={appointment.appointment_date} | time={appointment.start_time}")
