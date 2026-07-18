from __future__ import annotations

import datetime as dt

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.core.rbac import Role
from agile_ci_demo.patients.service import get_patient_by_patient_id
from agile_ci_demo.records.models import ConsultationNote, Diagnosis
from agile_ci_demo.records.schemas import ConsultationNoteCreate
from agile_ci_demo.staff.service import get_staff_by_staff_id

# A small curated reference list of common ICD-10 codes, used to power the diagnosis
# autocomplete search. Not exhaustive - a teaching-app stand-in for a real ICD-10 API.
ICD10_CODES: list[dict[str, str]] = [
    {"code": "A09", "description": "Infectious gastroenteritis and colitis, unspecified"},
    {"code": "B34.9", "description": "Viral infection, unspecified"},
    {"code": "E11", "description": "Type 2 diabetes mellitus"},
    {"code": "E66.9", "description": "Obesity, unspecified"},
    {"code": "E78.5", "description": "Hyperlipidaemia, unspecified"},
    {"code": "F32.9", "description": "Major depressive disorder, single episode, unspecified"},
    {"code": "F41.1", "description": "Generalised anxiety disorder"},
    {"code": "G43.9", "description": "Migraine, unspecified"},
    {"code": "I10", "description": "Essential (primary) hypertension"},
    {"code": "I25.9", "description": "Chronic ischaemic heart disease, unspecified"},
    {"code": "J00", "description": "Acute nasopharyngitis (common cold)"},
    {"code": "J02.9", "description": "Acute pharyngitis, unspecified"},
    {"code": "J03.9", "description": "Acute tonsillitis, unspecified"},
    {"code": "J06.9", "description": "Acute upper respiratory infection, unspecified"},
    {"code": "J18.9", "description": "Pneumonia, unspecified organism"},
    {"code": "J20.9", "description": "Acute bronchitis, unspecified"},
    {"code": "J45.9", "description": "Asthma, unspecified"},
    {"code": "K21.9", "description": "Gastro-oesophageal reflux disease without oesophagitis"},
    {"code": "K29.7", "description": "Gastritis, unspecified"},
    {"code": "K59.0", "description": "Constipation"},
    {"code": "L20.9", "description": "Atopic dermatitis, unspecified"},
    {"code": "L30.9", "description": "Dermatitis, unspecified"},
    {"code": "M25.5", "description": "Joint pain"},
    {"code": "M54.5", "description": "Low back pain"},
    {"code": "M79.1", "description": "Myalgia"},
    {"code": "N39.0", "description": "Urinary tract infection, site not specified"},
    {"code": "R05", "description": "Cough"},
    {"code": "R50.9", "description": "Fever, unspecified"},
    {"code": "R51", "description": "Headache"},
    {"code": "R10.4", "description": "Other and unspecified abdominal pain"},
    {"code": "R11", "description": "Nausea and vomiting"},
    {"code": "R42", "description": "Dizziness and giddiness"},
    {"code": "T78.4", "description": "Allergy, unspecified"},
    {"code": "Z00.0", "description": "General adult medical examination"},
]


class PatientNotFoundError(Exception):
    """Raised when a patient_id does not match any stored patient."""


class DoctorNotFoundError(Exception):
    """Raised when a staff_id does not match an active doctor account."""


class ConsultationNoteNotFoundError(Exception):
    """Raised when a record_id does not match any stored consultation note."""


class ConsultationNoteConflictError(Exception):
    """Raised when a consultation note cannot be created due to a database conflict."""


def search_icd10_codes(query: str, limit: int = 10) -> list[dict[str, str]]:
    """Case-insensitive search over the ICD-10 reference list by code or description."""
    q = query.strip().lower()
    if not q:
        return []
    matches = [
        entry
        for entry in ICD10_CODES
        if q in entry["code"].lower() or q in entry["description"].lower()
    ]
    return matches[:limit]


def create_consultation_note(db: Session, data: ConsultationNoteCreate) -> ConsultationNote:
    """Document a consultation with its diagnoses and assign it a record_id (e.g. R00001)."""
    patient = get_patient_by_patient_id(db, data.patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{data.patient_id}'")

    doctor = get_staff_by_staff_id(db, data.doctor_id)
    if doctor is None or doctor.role != Role.DOCTOR.value:
        raise DoctorNotFoundError(f"No doctor found with staff_id '{data.doctor_id}'")

    note = ConsultationNote(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=dt.datetime.utcnow(),
        notes=data.notes,
        diagnoses=[
            Diagnosis(icd10_code=d.icd10_code, description=d.description) for d in data.diagnoses
        ],
    )
    db.add(note)

    try:
        db.flush()  # assigns note.id (autoincrement) without committing
        note.record_id = f"R{note.id:05d}"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConsultationNoteConflictError(
            "Consultation note could not be created due to a conflict"
        ) from exc

    db.refresh(note)
    return note


def get_consultation_note_by_record_id(db: Session, record_id: str) -> ConsultationNote | None:
    return db.execute(
        select(ConsultationNote).where(ConsultationNote.record_id == record_id)
    ).scalar_one_or_none()


def get_patient_history(
    db: Session, patient_id: str, query: str | None = None
) -> list[ConsultationNote]:
    """A patient's consultation notes, newest first, optionally filtered by a keyword
    matched against the notes body and diagnosis code/description."""
    patient = get_patient_by_patient_id(db, patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{patient_id}'")

    stmt = select(ConsultationNote).where(ConsultationNote.patient_id == patient.id)

    if query and query.strip():
        pattern = f"%{query.strip()}%"
        stmt = (
            stmt.join(ConsultationNote.diagnoses, isouter=True)
            .where(
                or_(
                    ConsultationNote.notes.ilike(pattern),
                    Diagnosis.icd10_code.ilike(pattern),
                    Diagnosis.description.ilike(pattern),
                )
            )
            .distinct()
        )

    stmt = stmt.order_by(ConsultationNote.visit_date.desc(), ConsultationNote.id.desc())
    return list(db.execute(stmt).scalars().all())
