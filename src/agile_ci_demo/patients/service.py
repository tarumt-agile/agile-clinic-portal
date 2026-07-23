from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.schemas import PatientCreate, PatientUpdate

_IC_GENERATION_ATTEMPTS = 20


class DuplicatePatientError(Exception):
    """Raised when a patient with the same IC/passport number already exists."""


class PatientNotFoundError(Exception):
    """Raised when a patient_id does not match any stored patient."""


def generate_ic(db: Session, date_of_birth: dt.date) -> str:
    """Generate a unique, Malaysia-style simulated IC number: YYMMDD-0X-XXXX.

    YYMMDD is derived from the patient's date_of_birth, the two-digit group
    always starts with 0 (second digit 1-9), and the last four digits are
    random. Retries on the rare chance of a collision with an existing
    patient's IC.
    """
    yymmdd = date_of_birth.strftime("%y%m%d")
    for _ in range(_IC_GENERATION_ATTEMPTS):
        candidate = f"{yymmdd}-0{random.randint(1, 9)}-{random.randint(0, 9999):04d}"
        exists = db.execute(
            select(Patient).where(Patient.ic_or_passport == candidate)
        ).scalar_one_or_none()
        if exists is None:
            return candidate
    raise RuntimeError("Could not generate a unique IC number - please try again")


def create_patient(db: Session, data: PatientCreate) -> Patient:
    """Register a new patient and assign it a unique, sequential patient_id (e.g. P00001)."""
    patient = Patient(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender.value,
        phone_number=data.phone_number,
        email=data.email,
        ic_or_passport=generate_ic(db, data.date_of_birth),
        address=data.address,
    )
    db.add(patient)

    try:
        db.flush()  # assigns patient.id (autoincrement) without committing
        patient.patient_id = f"P{patient.id:05d}"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicatePatientError("Patient could not be created due to a conflict") from exc

    db.refresh(patient)
    return patient


def get_patient_by_patient_id(db: Session, patient_id: str) -> Patient | None:
    return db.execute(select(Patient).where(Patient.patient_id == patient_id)).scalar_one_or_none()


def get_patient_by_ic(db: Session, ic_or_passport: str) -> Patient | None:
    """Look up a patient by their exact IC/passport number - used when front-desk
    staff identify a patient from the IC the patient hands over in person."""
    return db.execute(
        select(Patient).where(Patient.ic_or_passport == ic_or_passport)
    ).scalar_one_or_none()


def search_patients(
    db: Session, query: str | None, page: int, page_size: int
) -> tuple[list[Patient], int]:
    """Search patients by name or patient_id (case-insensitive, partial match).

    Returns (page of results ordered by registration order, total matching count).
    """
    conditions = []
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        conditions.append(or_(Patient.full_name.ilike(pattern), Patient.patient_id.ilike(pattern)))

    count_stmt = select(func.count()).select_from(Patient)
    items_stmt = select(Patient).order_by(Patient.id)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        items_stmt = items_stmt.where(condition)

    total = db.execute(count_stmt).scalar_one()
    items_stmt = items_stmt.offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(items_stmt).scalars().all())
    return items, total


def update_patient(db: Session, patient_id: str, data: PatientUpdate) -> Patient:
    """Update a patient's editable details. IC/passport is system-generated at
    registration and is not editable."""
    patient = get_patient_by_patient_id(db, patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{patient_id}'")

    patient.full_name = data.full_name
    patient.date_of_birth = data.date_of_birth
    patient.gender = data.gender.value
    patient.phone_number = data.phone_number
    patient.email = data.email
    patient.address = data.address

    db.commit()
    db.refresh(patient)
    return patient
