r"""Populate the local SQLite database with connected clinic demo data.

Usage from the project root:

    .\.venv\Scripts\python.exe scripts\seed_db.py
    .\.venv\Scripts\python.exe scripts\seed_db.py --force

The normal command exits without changes when clinic data already exists.
``--force`` deletes the current database rows and rebuilds all demo data.
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.consultations.models import ConsultationNote, Diagnosis
from agile_ci_demo.core.database import Base, SessionLocal, engine, init_db
from agile_ci_demo.core.security import hash_password
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.pharmacy.models import Medication, StockTransaction
from agile_ci_demo.pharmacy.service import seed_default_medications
from agile_ci_demo.prescriptions.models import Prescription
from agile_ci_demo.staff.models import DoctorProfile, Staff


@dataclass(frozen=True)
class DemoStaff:
    full_name: str
    email: str
    password: str
    role: str
    license_number: str | None = None
    specialty: str | None = None


DEMO_STAFF = [
    DemoStaff(
        full_name="Admin User",
        email="admin@clinic.com",
        password="admin123",
        role="admin",
    ),
    DemoStaff(
        full_name="Dr. Alan Chua",
        email="alan.chua@clinic.com",
        password="alan123",
        role="doctor",
        license_number="MMC-10001",
        specialty="General Medicine",
    ),
    DemoStaff(
        full_name="Dr. Betty Lim",
        email="betty.lim@clinic.com",
        password="betty123",
        role="doctor",
        license_number="MMC-10002",
        specialty="Paediatrics",
    ),
    DemoStaff(
        full_name="Dr. Chandran Raj",
        email="chandran.raj@clinic.com",
        password="chandran123",
        role="doctor",
        license_number="MMC-10003",
        specialty="Cardiology",
    ),
    DemoStaff(
        full_name="Amy Wong",
        email="amy.wong@clinic.com",
        password="amy123",
        role="receptionist",
    ),
    DemoStaff(
        full_name="Siti Rahman",
        email="siti.rahman@clinic.com",
        password="siti123",
        role="receptionist",
    ),
]


PATIENTS = [
    {
        "full_name": "Jane Tan",
        "date_of_birth": dt.date(1990, 5, 20),
        "gender": "female",
        "phone_number": "012-3456789",
        "email": "jane.tan@example.com",
        "ic_or_passport": "900520-10-1234",
        "address": "1 Jalan Ampang, Kuala Lumpur",
    },
    {
        "full_name": "John Lee",
        "date_of_birth": dt.date(1985, 3, 11),
        "gender": "male",
        "phone_number": "013-2345678",
        "email": "john.lee@example.com",
        "ic_or_passport": "850311-10-1235",
        "address": "12 Jalan Bukit Bintang, Kuala Lumpur",
    },
    {
        "full_name": "Ah Kow",
        "date_of_birth": dt.date(1995, 1, 1),
        "gender": "male",
        "phone_number": "014-3456781",
        "email": None,
        "ic_or_passport": "950101-10-1237",
        "address": None,
    },
    {
        "full_name": "Janet Wong",
        "date_of_birth": dt.date(1992, 12, 12),
        "gender": "female",
        "phone_number": "016-4567890",
        "email": "janet.wong@example.com",
        "ic_or_passport": "921212-10-1238",
        "address": "45 Jalan Sultan Ismail, Kuala Lumpur",
    },
    {
        "full_name": "Muthu Samy",
        "date_of_birth": dt.date(1978, 7, 23),
        "gender": "male",
        "phone_number": "017-5678901",
        "email": "muthu.samy@example.com",
        "ic_or_passport": "780723-10-1239",
        "address": "8 Jalan Klang Lama, Kuala Lumpur",
    },
    {
        "full_name": "Nurul Aisyah",
        "date_of_birth": dt.date(2000, 2, 14),
        "gender": "female",
        "phone_number": "018-6789012",
        "email": "nurul.aisyah@example.com",
        "ic_or_passport": "000214-10-1240",
        "address": "22 Jalan Tun Razak, Kuala Lumpur",
    },
    {
        "full_name": "Kevin Tan",
        "date_of_birth": dt.date(1988, 9, 9),
        "gender": "male",
        "phone_number": "019-7890123",
        "email": None,
        "ic_or_passport": "880909-10-1241",
        "address": None,
    },
    {
        "full_name": "Priya Devi",
        "date_of_birth": dt.date(1993, 6, 30),
        "gender": "female",
        "phone_number": "012-8901234",
        "email": "priya.devi@example.com",
        "ic_or_passport": "930630-10-1242",
        "address": "5 Jalan Ipoh, Kuala Lumpur",
    },
    {
        "full_name": "Ahmad Firdaus",
        "date_of_birth": dt.date(1982, 11, 18),
        "gender": "male",
        "phone_number": "013-9012345",
        "email": "ahmad.firdaus@example.com",
        "ic_or_passport": "821118-10-1243",
        "address": "17 Jalan Pudu, Kuala Lumpur",
    },
    {
        "full_name": "Lim Wei Ling",
        "date_of_birth": dt.date(1975, 4, 25),
        "gender": "female",
        "phone_number": "014-0123456",
        "email": None,
        "ic_or_passport": "750425-10-1244",
        "address": None,
    },
    {
        "full_name": "Ravi Kumar",
        "date_of_birth": dt.date(1999, 8, 8),
        "gender": "male",
        "phone_number": "016-1234567",
        "email": "ravi.kumar@example.com",
        "ic_or_passport": "990808-10-1245",
        "address": "9 Jalan Cheras, Kuala Lumpur",
    },
    {
        "full_name": "Chong Mei Yee",
        "date_of_birth": dt.date(1991, 10, 10),
        "gender": "female",
        "phone_number": "017-2345678",
        "email": "meiyee.chong@example.com",
        "ic_or_passport": "911010-10-1246",
        "address": "31 Jalan Kepong, Kuala Lumpur",
    },
    {
        "full_name": "Hafiz Rahman",
        "date_of_birth": dt.date(1987, 5, 5),
        "gender": "male",
        "phone_number": "018-3456789",
        "email": None,
        "ic_or_passport": "870505-10-1247",
        "address": None,
    },
    {
        "full_name": "Sarah Lim",
        "date_of_birth": dt.date(1996, 3, 3),
        "gender": "female",
        "phone_number": "019-4567890",
        "email": "sarah.lim@example.com",
        "ic_or_passport": "960303-10-1248",
        "address": "3 Jalan Damansara, Kuala Lumpur",
    },
    {
        "full_name": "Tan Chee Keong",
        "date_of_birth": dt.date(1983, 12, 25),
        "gender": "male",
        "phone_number": "012-5678901",
        "email": "cheekeong.tan@example.com",
        "ic_or_passport": "831225-10-1249",
        "address": "28 Jalan Segambut, Kuala Lumpur",
    },
]


DIAGNOSES = [
    ("J06.9", "Acute upper respiratory infection, unspecified"),
    ("I10", "Essential (primary) hypertension"),
    ("J00", "Acute nasopharyngitis (common cold)"),
    ("L30.9", "Dermatitis, unspecified"),
    ("G43.9", "Migraine, unspecified"),
    ("Z00.0", "General adult medical examination"),
    ("K29.7", "Gastritis, unspecified"),
    ("M54.5", "Low back pain"),
    ("E11", "Type 2 diabetes mellitus"),
    ("J45.9", "Asthma, unspecified"),
    ("N39.0", "Urinary tract infection, site not specified"),
    ("J02.9", "Acute pharyngitis, unspecified"),
    ("R42", "Dizziness and giddiness"),
    ("T78.4", "Allergy, unspecified"),
    ("E78.5", "Hyperlipidaemia, unspecified"),
]


CONSULTATION_NOTES = [
    "Fever, nasal congestion and cough for three days. Hydration and rest advised.",
    "Blood pressure remains elevated. Discussed diet, exercise and home monitoring.",
    "Mild sore throat and runny nose with no breathing difficulty.",
    "Itchy rash over both forearms after changing laundry detergent.",
    "Recurring unilateral headache with light sensitivity and mild nausea.",
    "Routine health screening completed. No acute symptoms reported.",
    "Upper abdominal discomfort after meals with intermittent heartburn.",
    "Lower back discomfort after lifting boxes at work.",
    "Diabetes follow-up. Reviewed glucose diary and medication adherence.",
    "Intermittent wheezing triggered by exercise and cold air.",
    "Painful urination and increased urinary frequency for two days.",
    "Sore throat with mild fever and tender cervical lymph nodes.",
    "Brief dizziness when standing quickly. Hydration status reviewed.",
    "Seasonal sneezing, itchy eyes and clear nasal discharge.",
    "Reviewed lipid results and cardiovascular risk reduction plan.",
]


APPOINTMENT_REASONS = [
    "Fever and cough",
    "Follow-up checkup",
    "Annual health screening",
    "Skin rash",
    "Headache and dizziness",
    "Vaccination consultation",
    "Blood pressure check",
    "Stomach pain",
    "Back pain consultation",
    "Diabetes management review",
]


PRESCRIPTION_INSTRUCTIONS = [
    ("1 tablet", "Three times daily", "5 days"),
    ("1 tablet", "Once daily", "30 days"),
    ("1 capsule", "Three times daily", "7 days"),
    ("1 tablet", "At night", "7 days"),
    ("1 tablet", "As needed", "5 days"),
    ("1 tablet", "Once daily", "14 days"),
    ("1 capsule", "Once daily", "14 days"),
    ("1 tablet", "Twice daily", "7 days"),
    ("1 tablet", "Twice daily", "30 days"),
    ("2 puffs", "As needed", "30 days"),
    ("1 tablet", "Twice daily", "7 days"),
    ("1 tablet", "Three times daily", "5 days"),
    ("1 tablet", "As needed", "3 days"),
    ("1 tablet", "Once daily", "14 days"),
    ("1 tablet", "Once daily", "30 days"),
]


STOCK_LEVELS = [120, 85, 60, 45, 30, 25, 70, 55, 18, 90, 40, 150, 12, 8, 5]


def _create_staff(db: Session) -> tuple[list[Staff], list[Staff]]:
    staff_accounts: list[Staff] = []
    doctors: list[Staff] = []

    for number, data in enumerate(DEMO_STAFF, start=1):
        staff = Staff(
            staff_id=f"S{number:05d}",
            full_name=data.full_name,
            email=data.email,
            role=data.role,
            password_hash=hash_password(data.password),
            must_change_password=False,
            is_active=True,
        )
        db.add(staff)
        db.flush()

        if data.role == "doctor":
            profile = DoctorProfile(
                doctor_id=f"D{len(doctors) + 1:05d}",
                staff_account_id=staff.id,
                license_number=data.license_number or "",
                specialty=data.specialty or "",
                department="Clinical Services",
                status="active",
                start_time=dt.time(9, 0),
                end_time=dt.time(17, 0),
            )
            db.add(profile)
            doctors.append(staff)

        staff_accounts.append(staff)

    return staff_accounts, doctors


def _create_patients(db: Session, today: dt.date) -> list[Patient]:
    patients: list[Patient] = []

    for number, data in enumerate(PATIENTS, start=1):
        registered_at = dt.datetime.combine(
            today - dt.timedelta(days=number * 2),
            dt.time(8 + number % 8, 15),
        )
        patient = Patient(
            patient_id=f"P{number:05d}",
            created_at=registered_at,
            updated_at=registered_at,
            **data,
        )
        db.add(patient)
        patients.append(patient)

    db.flush()
    return patients


def _create_appointments(
    db: Session,
    patients: list[Patient],
    doctors: list[Staff],
    today: dt.date,
) -> list[Appointment]:
    appointments: list[Appointment] = []
    week_start = today - dt.timedelta(days=today.weekday())
    appointment_days = [week_start + dt.timedelta(days=offset) for offset in range(14)]
    start_times = [dt.time(9, 0), dt.time(10, 0), dt.time(11, 0)]

    for day_index, appointment_date in enumerate(appointment_days):
        for doctor_index, doctor in enumerate(doctors):
            number = len(appointments) + 1
            patient = patients[(number - 1) % len(patients)]
            is_cancelled = number % 10 == 0
            start_time = start_times[doctor_index]
            appointment = Appointment(
                reference_number=f"A{number:05d}",
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=appointment_date,
                start_time=start_time,
                end_time=(
                    dt.datetime.combine(appointment_date, start_time) + dt.timedelta(minutes=30)
                ).time(),
                reason=APPOINTMENT_REASONS[(number - 1) % len(APPOINTMENT_REASONS)],
                status="cancelled" if is_cancelled else "scheduled",
                cancellation_reason=(
                    "Patient requested a different appointment date." if is_cancelled else None
                ),
                created_at=dt.datetime.combine(
                    min(appointment_date, today),
                    dt.time(8, 0),
                )
                - dt.timedelta(days=2),
            )
            db.add(appointment)
            appointments.append(appointment)

    db.flush()
    return appointments


def _create_consultations(
    db: Session,
    patients: list[Patient],
    doctors: list[Staff],
    today: dt.date,
) -> list[ConsultationNote]:
    consultations: list[ConsultationNote] = []

    for index, patient in enumerate(patients):
        doctor = doctors[index % len(doctors)]
        visit_date = dt.datetime.combine(
            today - dt.timedelta(days=index + 1),
            dt.time(10 + index % 6, 0),
        )
        diagnosis_code, diagnosis_description = DIAGNOSES[index]
        consultation = ConsultationNote(
            record_id=f"R{index + 1:05d}",
            patient_id=patient.id,
            doctor_id=doctor.id,
            visit_date=visit_date,
            notes=CONSULTATION_NOTES[index],
            created_at=visit_date,
            updated_at=visit_date,
            diagnoses=[
                Diagnosis(
                    icd10_code=diagnosis_code,
                    description=diagnosis_description,
                    created_at=visit_date,
                )
            ],
        )
        db.add(consultation)
        consultations.append(consultation)

    db.flush()
    return consultations


def _stock_medications(
    db: Session,
    medications: list[Medication],
    admin: Staff,
    today: dt.date,
) -> None:
    for index, medication in enumerate(medications):
        stock_level = STOCK_LEVELS[index % len(STOCK_LEVELS)]
        medication.stock_quantity = stock_level
        medication.reorder_level = 10

        transaction = StockTransaction(
            transaction_id=f"ST{index + 1:07d}",
            medication_id=medication.id,
            transaction_type="initial_stock",
            quantity_change=stock_level,
            balance_after=stock_level,
            reason="Opening demo stock balance.",
            performed_by_staff_id=admin.id,
            performed_by_staff_public_id=admin.staff_id or "",
            performed_by_staff_name=admin.full_name,
            created_at=dt.datetime.combine(
                today - dt.timedelta(days=20 - index),
                dt.time(9, 0),
            ),
        )
        db.add(transaction)


def _create_prescriptions(
    db: Session,
    consultations: list[ConsultationNote],
    medications: list[Medication],
) -> list[Prescription]:
    prescriptions: list[Prescription] = []

    for index, consultation in enumerate(consultations):
        diagnosis = consultation.diagnoses[0]
        medication = medications[index % len(medications)]
        dosage, frequency, duration = PRESCRIPTION_INSTRUCTIONS[index]
        issued_at = consultation.visit_date + dt.timedelta(minutes=20)
        prescription = Prescription(
            prescription_id=f"RX{index + 1:05d}",
            consultation_note_id=consultation.id,
            diagnosis_id=diagnosis.id,
            patient_id=consultation.patient_id,
            prescribing_doctor_id=consultation.doctor_id,
            medication_id=medication.id,
            medication=medication.prescription_value,
            dosage=dosage,
            frequency=frequency,
            duration=duration,
            status="active",
            issued_at=issued_at,
            updated_at=issued_at,
        )
        db.add(prescription)
        prescriptions.append(prescription)

    db.flush()
    return prescriptions


def seed(force: bool) -> None:
    init_db()

    with SessionLocal() as db:
        existing_count = db.execute(select(func.count()).select_from(Patient)).scalar_one()
        if existing_count > 0 and not force:
            print("Database already contains clinic data. " "Run with --force to replace it.")
            return

    if force:
        print("Removing existing clinic data...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        today = dt.date.today()
        seed_default_medications(db)

        try:
            staff_accounts, doctors = _create_staff(db)
            patients = _create_patients(db, today)
            appointments = _create_appointments(
                db,
                patients,
                doctors,
                today,
            )
            consultations = _create_consultations(
                db,
                patients,
                doctors,
                today,
            )
            medications = list(db.execute(select(Medication).order_by(Medication.id)).scalars())
            _stock_medications(
                db,
                medications,
                staff_accounts[0],
                today,
            )
            prescriptions = _create_prescriptions(
                db,
                consultations,
                medications,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    print(
        "Seed complete: "
        f"{len(staff_accounts)} staff, "
        f"{len(patients)} patients, "
        f"{len(appointments)} appointments, "
        f"{len(consultations)} consultations, "
        f"{len(prescriptions)} prescriptions, and "
        f"{len(medications)} medications."
    )
    print("\nDemo logins:")
    for staff in DEMO_STAFF:
        print(f"  {staff.role.title():12} {staff.email:28} {staff.password}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing rows and rebuild the complete demo database.",
    )
    arguments = parser.parse_args()
    seed(force=arguments.force)
