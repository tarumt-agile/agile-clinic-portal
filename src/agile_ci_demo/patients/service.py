from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.attachments.models import Attachment
from agile_ci_demo.core.config import settings
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.schemas import PatientCreate, PatientUpdate
from agile_ci_demo.consultations.models import ConsultationNote, Diagnosis
from agile_ci_demo.prescriptions.models import Prescription, PrescriptionHistory


class DuplicatePatientError(Exception):
    """Raised when a patient with the same IC/passport number already exists."""


class PatientNotFoundError(Exception):
    """Raised when a patient_id does not match any stored patient."""


def create_patient(db: Session, data: PatientCreate) -> Patient:
    """Register a new patient and assign it a unique, sequential patient_id (e.g. P00001)."""
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


def get_patient_by_ic(db: Session, ic_or_passport: str) -> Patient | None:
    """Look up a patient by their exact IC/passport number - used when front-desk
    staff identify a patient from the IC the patient hands over in person."""
    return db.execute(
        select(Patient).where(Patient.ic_or_passport == ic_or_passport)
    ).scalar_one_or_none()


def search_patients_by_ic_prefix(db: Session, prefix: str, limit: int = 8) -> list[Patient]:
    """Patients whose IC/passport number starts with the given digits/characters -
    powers the autocomplete suggestions on the appointment booking form, so
    front-desk staff don't need to type the full IC before anything resolves."""
    prefix = prefix.strip()
    if not prefix:
        return []
    stmt = (
        select(Patient)
        .where(Patient.ic_or_passport.like(f"{prefix}%"))
        .order_by(Patient.ic_or_passport)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def _local_day_bounds_utc(date: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """The UTC datetime range covering a local calendar day.

    Patient.created_at is stored in UTC (dt.datetime.utcnow(), like every other
    timestamp column in this codebase), but registered_from/registered_to come
    from a receptionist's date picker and mean their own local "today" - not the
    UTC day, which is a different date for several hours around local midnight in
    any timezone ahead of UTC. Converting the boundary (not the stored timestamps)
    keeps created_at's storage convention untouched everywhere else.
    """
    start_local = dt.datetime.combine(date, dt.time.min)
    end_local = dt.datetime.combine(date, dt.time.max)
    # astimezone() on a naive datetime presumes it's in the system's local
    # timezone and resolves the correct UTC offset for that specific date
    # (handling DST correctly, unlike a fixed offset computed from "now").
    start_utc = start_local.astimezone(dt.timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def search_patients(
    db: Session,
    query: str | None,
    page: int,
    page_size: int,
    registered_from: dt.date | None = None,
    registered_to: dt.date | None = None,
) -> tuple[list[Patient], int]:
    """Search patients by name or patient_id (case-insensitive, partial match), optionally
    narrowed to a registration date range.

    Returns (page of results ordered by registration order, total matching count).
    """
    conditions = []
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        conditions.append(or_(Patient.full_name.ilike(pattern), Patient.patient_id.ilike(pattern)))
    if registered_from is not None:
        start, _ = _local_day_bounds_utc(registered_from)
        conditions.append(Patient.created_at >= start)
    if registered_to is not None:
        _, end = _local_day_bounds_utc(registered_to)
        conditions.append(Patient.created_at <= end)

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


def delete_patient(db: Session, patient_id: str) -> None:
    """Permanently remove a patient and all of their appointments, consultation
    notes, diagnoses, and prescriptions (cascading hard delete)."""
    patient = get_patient_by_patient_id(db, patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{patient_id}'")

    prescription_ids = (
        db.execute(select(Prescription.id).where(Prescription.patient_id == patient.id))
        .scalars()
        .all()
    )
    if prescription_ids:
        db.execute(
            delete(PrescriptionHistory).where(
                PrescriptionHistory.prescription_id.in_(prescription_ids)
            )
        )
        db.execute(delete(Prescription).where(Prescription.id.in_(prescription_ids)))

    note_ids = (
        db.execute(select(ConsultationNote.id).where(ConsultationNote.patient_id == patient.id))
        .scalars()
        .all()
    )
    if note_ids:
        attachments = (
            db.execute(select(Attachment).where(Attachment.consultation_note_id.in_(note_ids)))
            .scalars()
            .all()
        )
        for attachment in attachments:
            (settings.attachments_dir / attachment.stored_filename).unlink(missing_ok=True)
        db.execute(delete(Attachment).where(Attachment.consultation_note_id.in_(note_ids)))

        db.execute(delete(Diagnosis).where(Diagnosis.consultation_note_id.in_(note_ids)))
        db.execute(delete(ConsultationNote).where(ConsultationNote.id.in_(note_ids)))

    db.execute(delete(Appointment).where(Appointment.patient_id == patient.id))
    db.delete(patient)
    db.commit()
