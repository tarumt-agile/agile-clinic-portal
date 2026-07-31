from __future__ import annotations

import datetime as dt

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.appointments.service import get_appointment_by_reference
from agile_ci_demo.patients.service import get_patient_by_patient_id
from agile_ci_demo.consultations.models import ConsultationNote, Diagnosis
from agile_ci_demo.consultations.schemas import ConsultationNoteCreate
from agile_ci_demo.staff.models import Staff

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


class ConsultationNoteNotFoundError(Exception):
    """Raised when a record_id does not match any stored consultation note."""


class ConsultationNoteConflictError(Exception):
    """Raised when a consultation note cannot be created due to a database conflict."""


class ConsultationAlreadyEndedError(Exception):
    """Raised when trying to end a consultation that's already completed."""


class NotYourConsultationError(Exception):
    """Raised when a doctor tries to end a consultation that belongs to another doctor."""


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


def create_consultation_note(
    db: Session, data: ConsultationNoteCreate, doctor: Staff
) -> ConsultationNote:
    """Document a consultation with its diagnoses and assign it a record_id (e.g. R00001).

    The doctor is always the logged-in session (require_role(Role.DOCTOR) on the
    endpoint already guarantees it's a real, active doctor) - saving the note is
    the "start" of the consultation; ended_at/status are finalised later by
    end_consultation.
    """
    patient = get_patient_by_patient_id(db, data.patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{data.patient_id}'")

    # Best-effort link back to the appointment this was started from, so ending
    # the consultation can mark that appointment completed. An unknown/missing
    # reference just means no link - it never blocks documenting the visit.
    appointment_id = None
    if data.appointment_reference:
        appointment = get_appointment_by_reference(db, data.appointment_reference)
        if appointment is not None:
            appointment_id = appointment.id

    now = dt.datetime.utcnow()
    note = ConsultationNote(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_id=appointment_id,
        visit_date=now,
        notes=data.notes,
        started_at=now,
        status="in_progress",
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


def end_consultation(db: Session, record_id: str, doctor: Staff) -> ConsultationNote:
    """Mark a consultation as ended - only the doctor who documented it can end it."""
    note = get_consultation_note_by_record_id(db, record_id)
    if note is None:
        raise ConsultationNoteNotFoundError(f"No consultation note found with record_id '{record_id}'")

    if note.doctor_id != doctor.id:
        raise NotYourConsultationError("You can only end your own consultations")

    if note.status == "completed":
        raise ConsultationAlreadyEndedError("This consultation has already ended")

    note.ended_at = dt.datetime.utcnow()
    note.status = "completed"

    if note.appointment_id is not None:
        appointment = db.get(Appointment, note.appointment_id)
        if appointment is not None and appointment.status == "scheduled":
            appointment.status = "completed"

    db.commit()
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
