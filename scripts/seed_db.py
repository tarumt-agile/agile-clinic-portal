"""Populate the local SQLite DB with sample patients, staff, and appointments.

Usage (from the project root, with the venv activated):
    python scripts/seed_db.py

Safe to re-run: it exits without changes if any patients already exist, unless
--force is passed, in which case it wipes and recreates every table first.
"""

from __future__ import annotations

import argparse
import datetime as dt

from sqlalchemy import func, select

from agile_ci_demo.appointments.schemas import AppointmentCreate
from agile_ci_demo.appointments.service import create_appointment, get_appointment_by_reference
from agile_ci_demo.core.database import Base, SessionLocal, engine, init_db
from agile_ci_demo.patients.schemas import PatientCreate
from agile_ci_demo.patients.service import create_patient
from agile_ci_demo.staff.schemas import StaffCreate
from agile_ci_demo.staff.service import create_staff

PATIENTS = [
    (
        "Jane Tan",
        "1990-05-20",
        "female",
        "012-3456789",
        "jane.tan@example.com",
        "1 Jalan Ampang, Kuala Lumpur",
    ),
    (
        "John Lee",
        "1985-03-11",
        "male",
        "013-2345678",
        "john.lee@example.com",
        "12 Jalan Bukit Bintang, Kuala Lumpur",
    ),
    ("Ah Kow", "1995-01-01", "male", "014-3456781", None, None),
    (
        "Janet Wong",
        "1992-12-12",
        "female",
        "016-4567890",
        "janet.wong@example.com",
        "45 Jalan Sultan Ismail, Kuala Lumpur",
    ),
    (
        "Muthu Samy",
        "1978-07-23",
        "male",
        "017-5678901",
        "muthu.samy@example.com",
        "8 Jalan Klang Lama, Kuala Lumpur",
    ),
    (
        "Nurul Aisyah",
        "2000-02-14",
        "female",
        "018-6789012",
        "nurul.aisyah@example.com",
        "22 Jalan Tun Razak, Kuala Lumpur",
    ),
    ("Kevin Tan", "1988-09-09", "male", "019-7890123", None, None),
    (
        "Priya Devi",
        "1993-06-30",
        "female",
        "012-8901234",
        "priya.devi@example.com",
        "5 Jalan Ipoh, Kuala Lumpur",
    ),
    (
        "Ahmad Firdaus",
        "1982-11-18",
        "male",
        "013-9012345",
        "ahmad.firdaus@example.com",
        "17 Jalan Pudu, Kuala Lumpur",
    ),
    ("Lim Wei Ling", "1975-04-25", "female", "014-0123456", None, None),
    (
        "Ravi Kumar",
        "1999-08-08",
        "male",
        "016-1234567",
        "ravi.kumar@example.com",
        "9 Jalan Cheras, Kuala Lumpur",
    ),
    (
        "Chong Mei Yee",
        "1991-10-10",
        "female",
        "017-2345678",
        "meiyee.chong@example.com",
        "31 Jalan Kepong, Kuala Lumpur",
    ),
    ("Hafiz Rahman", "1987-05-05", "male", "018-3456789", None, None),
    (
        "Sarah Lim",
        "1996-03-03",
        "female",
        "019-4567890",
        "sarah.lim@example.com",
        "3 Jalan Damansara, Kuala Lumpur",
    ),
    (
        "Tan Chee Keong",
        "1983-12-25",
        "male",
        "012-5678901",
        "cheekeong.tan@example.com",
        "28 Jalan Segambut, Kuala Lumpur",
    ),
]

# NOTE: "Siti Rahman" below still seeds role="receptionist", which the current
# (narrowed) core.rbac.Role enum no longer accepts - seeding will fail on this
# row until the team decides whether receptionist is restored as a role or
# folded into "nurse". See appointment-module-status notes / ask the teammate
# who refactored the staff module.
STAFF = [
    ("Dr. Alan Chua", "alan.chua@clinic.com", "doctor", "General Medicine"),
    ("Dr. Betty Lim", "betty.lim@clinic.com", "doctor", "Paediatrics"),
    ("Dr. Chandran Raj", "chandran.raj@clinic.com", "doctor", "Cardiology"),
    ("Nurse Amy Wong", "amy.wong@clinic.com", "nurse", None),
    ("Siti Rahman", "siti.rahman@clinic.com", "receptionist", None),
    ("Admin User", "admin@clinic.com", "admin", None),
]

REASONS = [
    "Fever and cough",
    "Follow-up checkup",
    "Annual health screening",
    "Skin rash",
    "Headache and dizziness",
    "Vaccination",
    "Blood pressure check",
    "Stomach pain",
    "Back pain consultation",
    "Diabetes management review",
]

SLOTS = [dt.time(9, 0), dt.time(9, 30), dt.time(10, 0), dt.time(10, 30), dt.time(11, 0)]
CANCELLED_REASONS = ["Patient requested reschedule", "Doctor unavailable"]


def seed(force: bool) -> None:
    init_db()
    db = SessionLocal()

    try:
        from agile_ci_demo.patients.models import Patient

        existing_count = db.execute(select(func.count()).select_from(Patient)).scalar_one()
        if existing_count > 0:
            if not force:
                print("Database already has patients - skipping. Pass --force to wipe and reseed.")
                return
            print("Wiping existing tables...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)

        print(f"Seeding {len(PATIENTS)} patients...")
        patient_ids = []
        for full_name, dob, gender, phone, email, address in PATIENTS:
            patient = create_patient(
                db,
                PatientCreate(
                    full_name=full_name,
                    date_of_birth=dt.date.fromisoformat(dob),
                    gender=gender,
                    phone_number=phone,
                    email=email,
                    address=address,
                ),
            )
            patient_ids.append(patient.patient_id)

        print(f"Seeding {len(STAFF)} staff accounts...")
        doctor_ids = []
        for full_name, email, role, specialty in STAFF:
            staff = create_staff(
                db, StaffCreate(full_name=full_name, email=email, role=role, specialty=specialty)
            )
            if role == "doctor":
                doctor_ids.append(staff.staff_id)

        print("Seeding appointments...")
        today = dt.date.today()
        # Start from tomorrow - today's earlier slots may already be in the past.
        days = [
            today + dt.timedelta(days=1),
            today + dt.timedelta(days=2),
            today + dt.timedelta(days=3),
        ]
        reference_numbers = []
        patient_cycle = 0
        reason_cycle = 0
        for day in days:
            for doctor_id in doctor_ids:
                for slot_index in range(3):
                    patient_id = patient_ids[patient_cycle % len(patient_ids)]
                    reason = REASONS[reason_cycle % len(REASONS)]
                    patient_cycle += 1
                    reason_cycle += 1
                    appointment = create_appointment(
                        db,
                        AppointmentCreate(
                            patient_id=patient_id,
                            doctor_id=doctor_id,
                            appointment_date=day,
                            start_time=SLOTS[slot_index],
                            reason=reason,
                        ),
                    )
                    reference_numbers.append(appointment.reference_number)

        print(f"Cancelling {len(CANCELLED_REASONS)} sample appointments...")
        for reference_number, cancellation_reason in zip(reference_numbers, CANCELLED_REASONS):
            appointment = get_appointment_by_reference(db, reference_number)
            assert appointment is not None
            appointment.status = "cancelled"
            appointment.cancellation_reason = cancellation_reason
        db.commit()

        print(
            f"\nDone: {len(patient_ids)} patients, {len(STAFF)} staff "
            f"({len(doctor_ids)} doctors), {len(reference_numbers)} appointments "
            f"({len(CANCELLED_REASONS)} cancelled)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Wipe all tables and reseed from scratch"
    )
    args = parser.parse_args()
    seed(force=args.force)
