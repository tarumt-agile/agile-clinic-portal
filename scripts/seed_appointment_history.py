r"""Populate a year of appointment history (2025-10-01 to 2026-09-30).

Adds a couple of new doctors (different specialties from the existing three)
and a batch of new patients with realistic names/phone/IC/email/address, all
built to satisfy the exact same validation rules as the registration forms -
then generates the appointment/consultation history using only that
freshly-generated, well-formed data (not the placeholder "Demo Patient NNNNN"
rows already in the database from earlier ad-hoc testing).

Usage from the project root:

    .\.venv\Scripts\python.exe scripts\seed_appointment_history.py
    .\.venv\Scripts\python.exe scripts\seed_appointment_history.py --force

Weekdays only, 4-6 appointments per doctor per day, at 30-minute slots within
each doctor's working hours. Appointments dated before today are given a
realistic completed/cancelled split; completed ones also get a linked
consultation note with a diagnosis. Appointments from today onward are left
scheduled/cancelled, since they haven't happened yet.

The normal command exits without changes if this looks like it already ran
(more than 500 appointments already exist). ``--force`` runs anyway.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.consultations.models import ConsultationNote, Diagnosis
from agile_ci_demo.core.database import SessionLocal, init_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.security import hash_password
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import DoctorProfile, Staff

START_DATE = dt.date(2025, 10, 1)
END_DATE = dt.date(2026, 9, 30)

WORKING_HOURS_START = dt.time(9, 0)
WORKING_HOURS_END = dt.time(17, 0)
SLOT_MINUTES = 30

APPOINTMENTS_PER_DOCTOR_PER_DAY = (4, 6)  # inclusive random range
NEW_PATIENT_COUNT = 90

PAST_STATUS_WEIGHTS = {"completed": 0.85, "cancelled": 0.15}
FUTURE_STATUS_WEIGHTS = {"scheduled": 0.9, "cancelled": 0.1}

CANCELLATION_REASONS = [
    "Patient requested a different appointment date.",
    "Patient was unable to attend.",
    "Doctor became unavailable.",
    "Rescheduled at the clinic's request.",
]

CONSULTATION_DURATION_MINUTES = (10, 25)  # inclusive random range

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

# --- New doctors (different specialties from the existing three) --------------

NEW_DOCTORS = [
    {
        "full_name": "Dr. Farah Iskandar",
        "email": "farah.iskandar@clinic.com",
        "password": "farah123",
        "specialty": "Dermatology",
    },
    {
        "full_name": "Dr. Wong Kah Meng",
        "email": "wong.kahmeng@clinic.com",
        "password": "kahmeng123",
        "specialty": "Orthopaedics",
    },
]

# --- Realistic patient name/address generation ---------------------------------

CHINESE_MALE_FIRST = [
    "David",
    "Kevin",
    "Michael",
    "Eric",
    "Jason",
    "Bryan",
    "Wei Jian",
    "Kah Wai",
    "Yong Han",
    "Zhi Hao",
]
CHINESE_FEMALE_FIRST = [
    "Grace",
    "Michelle",
    "Amy",
    "Jasmine",
    "Serene",
    "Yee Ling",
    "Xin Yi",
    "Jia Hui",
    "Li Wen",
    "Kai Xin",
]
CHINESE_SURNAMES = [
    "Tan",
    "Lee",
    "Lim",
    "Wong",
    "Ng",
    "Chong",
    "Chua",
    "Yap",
    "Goh",
    "Ong",
    "Teoh",
    "Loh",
    "Koh",
    "Tay",
    "Sim",
]

MALAY_MALE_FIRST = [
    "Ahmad",
    "Muhammad",
    "Amir",
    "Faiz",
    "Hafiz",
    "Rizal",
    "Azman",
    "Farid",
    "Iskandar",
    "Zulkifli",
]
MALAY_FEMALE_FIRST = [
    "Nurul",
    "Siti",
    "Aina",
    "Nadia",
    "Farah",
    "Aida",
    "Sofia",
    "Zainab",
    "Aisyah",
    "Fatimah",
]
MALAY_SECOND = [
    "Firdaus",
    "Rahman",
    "Hassan",
    "Ismail",
    "Bakar",
    "Aziz",
    "Yusof",
    "Kassim",
    "Salleh",
    "Halim",
]

INDIAN_MALE_FIRST = [
    "Muthu",
    "Ravi",
    "Suresh",
    "Anand",
    "Vijay",
    "Raj",
    "Kannan",
    "Ganesh",
    "Prakash",
    "Sivam",
]
INDIAN_FEMALE_FIRST = [
    "Priya",
    "Kavitha",
    "Lakshmi",
    "Meena",
    "Shanti",
    "Geetha",
    "Devi",
    "Anitha",
    "Malar",
    "Revathi",
]
INDIAN_SECOND = [
    "Samy",
    "Kumar",
    "Raju",
    "Naidu",
    "Pillai",
    "Nair",
    "Krishnan",
    "Rao",
    "Segaran",
    "Muniandy",
]

STREETS = [
    "Jalan Ampang",
    "Jalan Bukit Bintang",
    "Jalan Sultan Ismail",
    "Jalan Klang Lama",
    "Jalan Tun Razak",
    "Jalan Ipoh",
    "Jalan Pudu",
    "Jalan Cheras",
    "Jalan Kepong",
    "Jalan Damansara",
    "Jalan Segambut",
    "Jalan Genting Klang",
    "Jalan Kuching",
    "Jalan Gombak",
    "Jalan Petaling",
    "Jalan Imbi",
]
CITIES = ["Kuala Lumpur", "Petaling Jaya", "Shah Alam", "Subang Jaya"]

IC_STATE_CODES = ["01", "02", "10", "11", "14", "21", "30", "42"]


def _generate_name_and_gender(rng: random.Random) -> tuple[str, str]:
    """A (full_name, gender) pair - full_name is always exactly two words, so
    an email can be derived from it trivially."""
    group = rng.choice(["chinese", "malay", "indian"])
    gender = rng.choice(["male", "female"])

    if group == "chinese":
        first = rng.choice(CHINESE_MALE_FIRST if gender == "male" else CHINESE_FEMALE_FIRST)
        second = rng.choice(CHINESE_SURNAMES)
    elif group == "malay":
        first = rng.choice(MALAY_MALE_FIRST if gender == "male" else MALAY_FEMALE_FIRST)
        second = rng.choice(MALAY_SECOND)
    else:
        first = rng.choice(INDIAN_MALE_FIRST if gender == "male" else INDIAN_FEMALE_FIRST)
        second = rng.choice(INDIAN_SECOND)

    return f"{first} {second}", gender


def _generate_date_of_birth(rng: random.Random, today: dt.date) -> dt.date:
    age_years = rng.randint(1, 89)
    latest = today.replace(year=today.year - age_years)
    earliest = latest - dt.timedelta(days=364)
    span_days = (latest - earliest).days
    return earliest + dt.timedelta(days=rng.randint(0, span_days))


def _generate_ic(
    rng: random.Random, date_of_birth: dt.date, gender: str, used_ics: set[str]
) -> str:
    dob_digits = date_of_birth.strftime("%y%m%d")
    while True:
        state_code = rng.choice(IC_STATE_CODES)
        sequence = rng.randint(0, 999)
        last_digit = rng.randrange(0, 10, 2) if gender == "female" else rng.randrange(1, 10, 2)
        ic = f"{dob_digits}-{state_code}-{sequence:03d}{last_digit}"
        if ic not in used_ics:
            used_ics.add(ic)
            return ic


def _generate_phone(rng: random.Random) -> str:
    prefix = rng.choice(["10", "11", "12", "13", "14", "16", "17", "18", "19"])
    subscriber = rng.randint(0, 9_999_999)
    return f"0{prefix}-{subscriber:07d}"


def _generate_email(full_name: str, used_emails: set[str]) -> str | None:
    base = full_name.lower().replace(" ", ".")
    email = f"{base}@example.com"
    suffix = 2
    while email in used_emails:
        email = f"{base}{suffix}@example.com"
        suffix += 1
    used_emails.add(email)
    return email


def _generate_address(rng: random.Random) -> str:
    return f"{rng.randint(1, 99)} {rng.choice(STREETS)}, {rng.choice(CITIES)}"


def _create_new_doctors(db: Session) -> list[Staff]:
    max_staff_id = db.execute(select(func.max(Staff.id))).scalar_one() or 0
    max_doctor_id = db.execute(select(func.max(DoctorProfile.id))).scalar_one() or 0

    created: list[Staff] = []
    for offset, data in enumerate(NEW_DOCTORS, start=1):
        staff = Staff(
            staff_id=f"S{max_staff_id + offset:05d}",
            full_name=data["full_name"],
            email=data["email"],
            role=Role.DOCTOR.value,
            password_hash=hash_password(data["password"]),
            must_change_password=False,
            is_active=True,
        )
        db.add(staff)
        db.flush()

        profile = DoctorProfile(
            doctor_id=f"D{max_doctor_id + offset:05d}",
            staff_account_id=staff.id,
            license_number=f"MMC-1{max_doctor_id + offset:04d}",
            specialty=data["specialty"],
            department="Clinical Services",
            status="active",
            start_time=WORKING_HOURS_START,
            end_time=WORKING_HOURS_END,
        )
        db.add(profile)
        created.append(staff)

    db.flush()
    return created


def _create_new_patients(db: Session, today: dt.date) -> list[Patient]:
    rng = random.Random()
    max_patient_id = db.execute(select(func.max(Patient.id))).scalar_one() or 0

    used_ics: set[str] = set()
    used_emails: set[str] = set()

    created: list[Patient] = []
    for offset in range(1, NEW_PATIENT_COUNT + 1):
        full_name, gender = _generate_name_and_gender(rng)
        date_of_birth = _generate_date_of_birth(rng, today)
        ic = _generate_ic(rng, date_of_birth, gender, used_ics)

        patient = Patient(
            patient_id=f"P{max_patient_id + offset:05d}",
            full_name=full_name,
            date_of_birth=date_of_birth,
            gender=gender,
            phone_number=_generate_phone(rng),
            email=_generate_email(full_name, used_emails),
            ic_or_passport=ic,
            address=_generate_address(rng),
            created_at=dt.datetime.combine(today, dt.time(9, 0))
            - dt.timedelta(days=rng.randint(1, 400)),
        )

        # ic_or_passport carries a DB-level UNIQUE constraint on the encrypted
        # value - collisions against the pre-existing 1400+ patients are
        # possible (if astronomically unlikely). Each attempt runs in its own
        # SAVEPOINT (begin_nested), so a collision only rolls back this one
        # patient, not the whole batch flushed so far.
        for attempt in range(5):
            try:
                with db.begin_nested():
                    db.add(patient)
                    db.flush()
                break
            except IntegrityError:
                if attempt == 4:
                    raise RuntimeError(f"Could not generate a unique IC for patient #{offset}")
                patient.ic_or_passport = _generate_ic(rng, date_of_birth, gender, used_ics)

        created.append(patient)

    db.flush()
    return created


# --- Appointment/consultation history generation --------------------------------


def _working_slots() -> list[dt.time]:
    slots = []
    current = dt.datetime.combine(dt.date.today(), WORKING_HOURS_START)
    end = dt.datetime.combine(dt.date.today(), WORKING_HOURS_END)
    while current < end:
        slots.append(current.time())
        current += dt.timedelta(minutes=SLOT_MINUTES)
    return slots


ALL_SLOTS = _working_slots()


def _weekdays_in_range(start: dt.date, end: dt.date) -> list[dt.date]:
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday-Friday
            days.append(current)
        current += dt.timedelta(days=1)
    return days


def _weighted_status(weights: dict[str, float]) -> str:
    statuses = list(weights.keys())
    return random.choices(statuses, weights=list(weights.values()), k=1)[0]


def _existing_booked_slots(db: Session) -> set[tuple[int, dt.date, dt.time]]:
    rows = db.execute(
        select(Appointment.doctor_id, Appointment.appointment_date, Appointment.start_time)
    )
    return {(row.doctor_id, row.appointment_date, row.start_time) for row in rows}


def seed(force: bool) -> None:
    init_db()

    with SessionLocal() as db:
        existing_count = db.execute(select(func.count()).select_from(Appointment)).scalar_one()
        if existing_count > 500 and not force:
            print(
                f"Database already has {existing_count} appointments - this looks like it "
                "already ran. Run with --force to add another batch anyway."
            )
            return

    today = dt.date.today()
    weekdays = _weekdays_in_range(START_DATE, END_DATE)

    with SessionLocal() as db:
        new_doctors = _create_new_doctors(db)
        new_patients = _create_new_patients(db, today)
        db.commit()

        existing_doctors = list(
            db.execute(
                select(Staff).where(Staff.role == Role.DOCTOR.value, Staff.is_active.is_(True))
            )
            .scalars()
            .all()
        )
        patient_ids = [p.id for p in new_patients]

        booked_slots = _existing_booked_slots(db)

        appointment_total = 0
        completed_total = 0
        cancelled_total = 0
        scheduled_total = 0

        try:
            for appointment_date in weekdays:
                is_past = appointment_date < today
                for doctor in existing_doctors:
                    slot_count = random.randint(*APPOINTMENTS_PER_DOCTOR_PER_DAY)
                    available_slots = [
                        slot
                        for slot in ALL_SLOTS
                        if (doctor.id, appointment_date, slot) not in booked_slots
                    ]
                    random.shuffle(available_slots)
                    chosen_slots = available_slots[:slot_count]

                    for start_time in chosen_slots:
                        booked_slots.add((doctor.id, appointment_date, start_time))
                        end_time = (
                            dt.datetime.combine(appointment_date, start_time)
                            + dt.timedelta(minutes=SLOT_MINUTES)
                        ).time()

                        status = _weighted_status(
                            PAST_STATUS_WEIGHTS if is_past else FUTURE_STATUS_WEIGHTS
                        )
                        patient_id = random.choice(patient_ids)

                        appointment = Appointment(
                            patient_id=patient_id,
                            doctor_id=doctor.id,
                            appointment_date=appointment_date,
                            start_time=start_time,
                            end_time=end_time,
                            reason=random.choice(APPOINTMENT_REASONS),
                            status=status,
                            cancellation_reason=(
                                random.choice(CANCELLATION_REASONS)
                                if status == "cancelled"
                                else None
                            ),
                            created_at=dt.datetime.combine(appointment_date, dt.time(8, 0))
                            - dt.timedelta(days=random.randint(1, 10)),
                        )
                        db.add(appointment)
                        db.flush()  # assigns appointment.id, needed for its reference_number and the linked note
                        appointment.reference_number = f"A{appointment.id:05d}"
                        appointment_total += 1

                        if status == "completed":
                            completed_total += 1
                            visit_started = dt.datetime.combine(appointment_date, start_time)
                            visit_ended = visit_started + dt.timedelta(
                                minutes=random.randint(*CONSULTATION_DURATION_MINUTES)
                            )
                            diagnosis_code, diagnosis_description = random.choice(DIAGNOSES)
                            note = ConsultationNote(
                                patient_id=patient_id,
                                doctor_id=doctor.id,
                                appointment_id=appointment.id,
                                visit_date=visit_started,
                                notes=random.choice(CONSULTATION_NOTES),
                                started_at=visit_started,
                                ended_at=visit_ended,
                                status="completed",
                                created_at=visit_started,
                                updated_at=visit_ended,
                                diagnoses=[
                                    Diagnosis(
                                        icd10_code=diagnosis_code,
                                        description=diagnosis_description,
                                        created_at=visit_started,
                                    )
                                ],
                            )
                            db.add(note)
                            db.flush()  # assigns note.id, needed for its record_id
                            note.record_id = f"R{note.id:05d}"
                        elif status == "cancelled":
                            cancelled_total += 1
                        else:
                            scheduled_total += 1

                db.flush()

            db.commit()
        except Exception:
            db.rollback()
            raise

    print(
        f"Added {len(new_doctors)} new doctors and {len(new_patients)} new patients.\n"
        "Appointment history seeded: "
        f"{appointment_total} appointments across {len(weekdays)} weekdays "
        f"({START_DATE.isoformat()} to {END_DATE.isoformat()}) for "
        f"{len(existing_doctors)} doctors.\n"
        f"  completed: {completed_total} (each with a linked consultation note + diagnosis)\n"
        f"  cancelled: {cancelled_total}\n"
        f"  scheduled: {scheduled_total}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Seed appointment history even if the database already looks populated.",
    )
    arguments = parser.parse_args()
    seed(force=arguments.force)
