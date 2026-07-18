from __future__ import annotations

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from agile_ci_demo.appointments.service import (
    get_current_doctor,
)
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.patients.service import (
    get_patient_by_patient_id,
)
from agile_ci_demo.prescription.models import (
    Prescription,
    PrescriptionHistory,
)
from agile_ci_demo.prescription.schemas import (
    PrescriptionCreate,
    PrescriptionInstructionUpdate,
)
from agile_ci_demo.records.models import Diagnosis
from agile_ci_demo.records.service import (
    get_consultation_note_by_record_id,
)

MEDICATION_OPTIONS = [
    {
        "value": "Amoxicillin 250 mg Capsule",
        "label": "Amoxicillin 250 mg Capsule",
    },
    {
        "value": "Amoxicillin 500 mg Capsule",
        "label": "Amoxicillin 500 mg Capsule",
    },
    {
        "value": "Azithromycin 250 mg Tablet",
        "label": "Azithromycin 250 mg Tablet",
    },
    {
        "value": "Cetirizine 10 mg Tablet",
        "label": "Cetirizine 10 mg Tablet",
    },
    {
        "value": "Chlorpheniramine 4 mg Tablet",
        "label": "Chlorpheniramine 4 mg Tablet",
    },
    {
        "value": "Diclofenac 50 mg Tablet",
        "label": "Diclofenac 50 mg Tablet",
    },
    {
        "value": "Ibuprofen 200 mg Tablet",
        "label": "Ibuprofen 200 mg Tablet",
    },
    {
        "value": "Ibuprofen 400 mg Tablet",
        "label": "Ibuprofen 400 mg Tablet",
    },
    {
        "value": "Loratadine 10 mg Tablet",
        "label": "Loratadine 10 mg Tablet",
    },
    {
        "value": "Metformin 500 mg Tablet",
        "label": "Metformin 500 mg Tablet",
    },
    {
        "value": "Omeprazole 20 mg Capsule",
        "label": "Omeprazole 20 mg Capsule",
    },
    {
        "value": "Paracetamol 500 mg Tablet",
        "label": "Paracetamol 500 mg Tablet",
    },
    {
        "value": "Salbutamol 100 mcg Inhaler",
        "label": "Salbutamol 100 mcg Inhaler",
    },
    {
        "value": "Cough Mixture",
        "label": "Cough Mixture",
    },
    {
        "value": "Oral Rehydration Salts",
        "label": "Oral Rehydration Salts",
    },
]


DOSAGE_OPTIONS = [
    "Half tablet",
    "1 tablet",
    "2 tablets",
    "1 capsule",
    "2 capsules",
    "2.5 mL",
    "5 mL",
    "10 mL",
    "1 puff",
    "2 puffs",
    "Apply a thin layer",
    "1 sachet",
]


FREQUENCY_OPTIONS = [
    "Once daily",
    "Twice daily",
    "Three times daily",
    "Four times daily",
    "Every 4 hours",
    "Every 6 hours",
    "Every 8 hours",
    "Every 12 hours",
    "At night",
    "As needed",
]


DURATION_OPTIONS = [
    "1 day",
    "3 days",
    "5 days",
    "7 days",
    "10 days",
    "14 days",
    "21 days",
    "30 days",
    "Until finished",
    "Ongoing",
]


class PrescriptionNotFoundError(Exception):
    """Raised when a prescription is not found."""


class ConsultationRecordNotFoundError(Exception):
    """Raised when a consultation record is not found."""


class DiagnosisNotFoundError(Exception):
    """Raised when a diagnosis is not found."""


class CurrentDoctorNotFoundError(Exception):
    """Raised when a current doctor is not found."""


class PrescriptionPermissionError(Exception):
    """Raised when a doctor lacks permission."""


class PrescriptionConflictError(Exception):
    """Raised when prescription data conflicts."""


class PrescriptionOptions(TypedDict):
    medications: list[dict[str, str]]
    dosages: list[str]
    frequencies: list[str]
    durations: list[str]


def get_prescription_options() -> PrescriptionOptions:
    """Return selectable prescription form options."""

    return {
        "medications": MEDICATION_OPTIONS,
        "dosages": DOSAGE_OPTIONS,
        "frequencies": FREQUENCY_OPTIONS,
        "durations": DURATION_OPTIONS,
    }


def _prescription_load_options():
    """Return relationship-loading options."""

    return (
        selectinload(Prescription.consultation_note),
        selectinload(Prescription.diagnosis),
        selectinload(Prescription.patient),
        selectinload(Prescription.prescribing_doctor),
        selectinload(Prescription.history).selectinload(PrescriptionHistory.changed_by_doctor),
    )


def create_prescription(
    db: Session,
    data: PrescriptionCreate,
) -> Prescription:
    """Create a prescription for one diagnosis."""

    consultation = get_consultation_note_by_record_id(
        db,
        data.consultation_record_id,
    )

    if consultation is None:
        raise ConsultationRecordNotFoundError("Consultation record not found.")

    diagnosis = db.execute(
        select(Diagnosis)
        .where(Diagnosis.id == data.diagnosis_id)
        .where(Diagnosis.consultation_note_id == consultation.id)
    ).scalar_one_or_none()

    if diagnosis is None:
        raise DiagnosisNotFoundError(
            "The selected diagnosis does not belong " "to this consultation."
        )

    current_doctor = get_current_doctor(db)

    if current_doctor is None:
        raise CurrentDoctorNotFoundError("No current doctor account was found.")

    if current_doctor.role != Role.DOCTOR.value:
        raise PrescriptionPermissionError("Only a doctor can create a prescription.")

    if consultation.doctor_id != current_doctor.id:
        raise PrescriptionPermissionError(
            "Only the doctor who created this " "consultation can add medication."
        )

    prescription = Prescription(
        consultation_note_id=consultation.id,
        diagnosis_id=diagnosis.id,
        patient_id=consultation.patient_id,
        prescribing_doctor_id=current_doctor.id,
        medication=data.medication,
        dosage=data.dosage,
        frequency=data.frequency,
        duration=data.duration,
        status="active",
    )

    db.add(prescription)

    try:
        db.flush()

        prescription.prescription_id = f"RX{prescription.id:05d}"

        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise PrescriptionConflictError("The prescription could not be created.") from exc

    return (
        get_prescription_by_public_id(
            db,
            prescription.prescription_id,
        )
        or prescription
    )


def get_prescription_by_public_id(
    db: Session,
    prescription_id: str,
) -> Prescription | None:
    """Return one prescription by public ID."""

    statement = (
        select(Prescription)
        .options(*_prescription_load_options())
        .where(Prescription.prescription_id == prescription_id)
    )

    return db.execute(statement).scalar_one_or_none()


def get_patient_prescriptions(
    db: Session,
    patient_id: str,
) -> list[Prescription]:
    """Return a patient's prescriptions newest first."""

    patient = get_patient_by_patient_id(
        db,
        patient_id,
    )

    if patient is None:
        raise PrescriptionNotFoundError(f"No patient found with patient_id " f"'{patient_id}'.")

    statement = (
        select(Prescription)
        .options(*_prescription_load_options())
        .where(Prescription.patient_id == patient.id)
        .order_by(
            Prescription.issued_at.desc(),
            Prescription.id.desc(),
        )
    )

    return list(db.execute(statement).scalars().all())


def get_consultation_prescriptions(
    db: Session,
    record_id: str,
) -> list[Prescription]:
    """Return prescriptions for one consultation."""

    consultation = get_consultation_note_by_record_id(
        db,
        record_id,
    )

    if consultation is None:
        raise ConsultationRecordNotFoundError("Consultation record not found.")

    statement = (
        select(Prescription)
        .options(*_prescription_load_options())
        .where(Prescription.consultation_note_id == consultation.id)
        .order_by(
            Prescription.diagnosis_id.asc(),
            Prescription.issued_at.asc(),
            Prescription.id.asc(),
        )
    )

    return list(db.execute(statement).scalars().all())


def update_prescription_instructions(
    db: Session,
    prescription_id: str,
    data: PrescriptionInstructionUpdate,
) -> Prescription:
    """Update prescription instructions and save history."""

    prescription = get_prescription_by_public_id(
        db,
        prescription_id,
    )

    if prescription is None:
        raise PrescriptionNotFoundError("Prescription not found.")

    current_doctor = get_current_doctor(db)

    if current_doctor is None:
        raise CurrentDoctorNotFoundError("No current doctor account was found.")

    if prescription.prescribing_doctor_id != current_doctor.id:
        raise PrescriptionPermissionError(
            "Only the prescribing doctor can " "update this prescription."
        )

    if prescription.status != "active":
        raise PrescriptionConflictError("Only an active prescription can be updated.")

    no_change = (
        data.dosage == prescription.dosage
        and data.frequency == prescription.frequency
        and data.duration == prescription.duration
    )

    if no_change:
        raise PrescriptionConflictError("No prescription instruction was changed.")

    revision = PrescriptionHistory(
        prescription_id=prescription.id,
        previous_dosage=prescription.dosage,
        new_dosage=data.dosage,
        previous_frequency=prescription.frequency,
        new_frequency=data.frequency,
        previous_duration=prescription.duration,
        new_duration=data.duration,
        change_reason=data.change_reason,
        changed_by_doctor_id=current_doctor.id,
    )

    db.add(revision)

    prescription.dosage = data.dosage
    prescription.frequency = data.frequency
    prescription.duration = data.duration

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise PrescriptionConflictError("The prescription update could not be saved.") from exc

    return (
        get_prescription_by_public_id(
            db,
            prescription_id,
        )
        or prescription
    )
