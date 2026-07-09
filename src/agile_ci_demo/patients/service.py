from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.schemas import PatientCreate


class DuplicatePatientError(Exception):
    """Raised when a patient with the same IC/passport number already exists."""


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
