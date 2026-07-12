from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.schemas import PatientCreate, PatientUpdate


class DuplicatePatientError(Exception):
    """Raised when a patient with the same IC/passport number already exists."""


class PatientNotFoundError(Exception):
    """Raised when a patient_id does not match any stored patient."""


def create_patient(db: Session, data: PatientCreate) -> Patient:
    """Register a new patient and assign it a unique, sequential patient_id (e.g. P00001)."""
    existing = db.execute(
        select(Patient).where(Patient.ic_or_passport == data.ic_or_passport)
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicatePatientError(
            f"A patient with IC/passport '{data.ic_or_passport}' is already registered"
        )

    patient = Patient(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender.value,
        phone_number=data.phone_number,
        email=data.email,
        ic_or_passport=data.ic_or_passport,
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


def get_current_patient(db: Session) -> Patient | None:
    """Stand-in for real authentication: returns the first patient on record as "the
    logged-in patient" for self-service booking. There is no session/token yet -
    swap this for a real Depends(get_current_user) once patient login exists."""
    return db.execute(select(Patient).order_by(Patient.id)).scalars().first()


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
    """Update every field of an existing patient. Re-validates uniqueness of IC/passport."""
    patient = get_patient_by_patient_id(db, patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{patient_id}'")

    conflict = db.execute(
        select(Patient).where(
            Patient.ic_or_passport == data.ic_or_passport,
            Patient.id != patient.id,
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise DuplicatePatientError(
            f"A patient with IC/passport '{data.ic_or_passport}' is already registered"
        )

    patient.full_name = data.full_name
    patient.date_of_birth = data.date_of_birth
    patient.gender = data.gender.value
    patient.phone_number = data.phone_number
    patient.email = data.email
    patient.ic_or_passport = data.ic_or_passport
    patient.address = data.address

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicatePatientError("Patient could not be updated due to a conflict") from exc

    db.refresh(patient)
    return patient
