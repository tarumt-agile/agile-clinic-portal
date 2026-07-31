from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.templates import templates
from agile_ci_demo.consultations.models import ConsultationNote
from agile_ci_demo.consultations.schemas import (
    ConsultationNoteCreate,
    ConsultationNoteOut,
    ConsultationNoteSummary,
    ConsultationNoteUpdate,
    ConsultationQueueEntry,
    ConsultationStart,
    DiagnosisOut,
    DoctorConsultationQueue,
    Icd10Entry,
    PatientHistory,
)
from agile_ci_demo.consultations.service import (
    ConsultationAlreadyEndedError,
    ConsultationNoteConflictError,
    ConsultationNoteNotFoundError,
    NotYourConsultationError,
    PatientNotFoundError,
    create_consultation_note,
    end_consultation,
    get_consultation_note_by_record_id,
    get_patient_history,
    get_todays_consultation_queue,
    search_icd10_codes,
    start_consultation,
    update_consultation_note,
)
from agile_ci_demo.staff.models import Staff

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/consultations", tags=["consultations"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/consultations", tags=["consultation-pages"])


def _serialize(note: ConsultationNote) -> ConsultationNoteOut:
    return ConsultationNoteOut(
        record_id=note.record_id or "",
        patient_id=note.patient.patient_id or "",
        patient_name=note.patient.full_name,
        doctor_id=note.doctor.staff_id or "",
        doctor_name=note.doctor.full_name,
        visit_date=note.visit_date,
        notes=note.notes,
        diagnoses=[DiagnosisOut.model_validate(d) for d in note.diagnoses],
        started_at=note.started_at,
        ended_at=note.ended_at,
        status=note.status,
        created_at=note.created_at,
    )


def _serialize_summary(note: ConsultationNote) -> ConsultationNoteSummary:
    return ConsultationNoteSummary(
        record_id=note.record_id or "",
        visit_date=note.visit_date,
        doctor_name=note.doctor.full_name,
        notes=note.notes,
        diagnoses=[DiagnosisOut.model_validate(d) for d in note.diagnoses],
        status=note.status,
    )


@api_router.post("", response_model=ConsultationNoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: ConsultationNoteCreate,
    db: Session = Depends(get_db),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
) -> ConsultationNoteOut:
    """Document a consultation. At least one diagnosis is required (enforced by the schema).

    Saving the note is the "start" of the consultation - it's created in_progress
    and finalised later via PATCH /{record_id}/end.
    """
    try:
        note = create_consultation_note(db, payload, doctor)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConsultationNoteConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(note)


@api_router.post("/start", response_model=ConsultationNoteOut)
def start_consultation_endpoint(
    payload: ConsultationStart,
    db: Session = Depends(get_db),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
) -> ConsultationNoteOut:
    """Open (or resume) a consultation. Creates an empty in_progress note right
    away, before any notes/diagnoses are written - see start_consultation for why."""
    try:
        note, _created = start_consultation(
            db, payload.patient_id, payload.appointment_reference, doctor
        )
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConsultationNoteConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(note)


@api_router.put("/{record_id}", response_model=ConsultationNoteOut)
def update_note(
    record_id: str,
    payload: ConsultationNoteUpdate,
    db: Session = Depends(get_db),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
) -> ConsultationNoteOut:
    """Fill in or revise an in-progress consultation's notes and diagnoses."""
    try:
        note = update_consultation_note(db, record_id, payload.notes, payload.diagnoses, doctor)
    except ConsultationNoteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NotYourConsultationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ConsultationAlreadyEndedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(note)


@api_router.patch("/{record_id}/end", response_model=ConsultationNoteOut)
def end_consultation_endpoint(
    record_id: str,
    db: Session = Depends(get_db),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
) -> ConsultationNoteOut:
    """End a consultation - only the doctor who documented it can end it."""
    try:
        note = end_consultation(db, record_id, doctor)
    except ConsultationNoteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NotYourConsultationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ConsultationAlreadyEndedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(note)


@api_router.get("/icd10", response_model=list[Icd10Entry])
def autocomplete_icd10(
    q: str = Query(default="", description="Search term matched against code or description"),
) -> list[Icd10Entry]:
    return [Icd10Entry(**entry) for entry in search_icd10_codes(q)]


@api_router.get("/today-queue", response_model=DoctorConsultationQueue)
def get_todays_queue(
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
    db: Session = Depends(get_db),
) -> DoctorConsultationQueue:
    """The logged-in doctor's non-cancelled appointments for today, each paired with
    its consultation state - powers the Start Consultation page's work queue."""
    entries = get_todays_consultation_queue(db, doctor.id)
    return DoctorConsultationQueue(
        doctor_id=doctor.staff_id or "",
        doctor_name=doctor.full_name,
        appointments=[
            ConsultationQueueEntry(
                reference_number=appointment.reference_number or "",
                patient_id=appointment.patient.patient_id or "",
                patient_name=appointment.patient.full_name,
                start_time=appointment.start_time,
                end_time=appointment.end_time,
                reason=appointment.reason,
                appointment_status=appointment.status,
                consultation_record_id=note.record_id if note else None,
                consultation_status=note.status if note else None,
            )
            for appointment, note in entries
        ],
    )


@api_router.get("", response_model=PatientHistory)
def patient_history(
    patient_id: str = Query(..., description="Patient's public patient_id, e.g. P00001"),
    q: str | None = Query(default=None, description="Filter by diagnosis or note keyword"),
    db: Session = Depends(get_db),
) -> PatientHistory:
    """A patient's medical history, newest first, optionally filtered by keyword."""
    try:
        notes = get_patient_history(db, patient_id, q)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PatientHistory(items=[_serialize_summary(n) for n in notes], total=len(notes))


@api_router.get("/{record_id}", response_model=ConsultationNoteOut)
def get_note(record_id: str, db: Session = Depends(get_db)) -> ConsultationNoteOut:
    note = get_consultation_note_by_record_id(db, record_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return _serialize(note)


@pages_router.get("/new", response_class=HTMLResponse)
def new_note_page(
    request: Request,
    patient_id: str = Query(..., description="Patient to document a visit for"),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "consultations/consultation_form.html",
        {"patient_id": patient_id, "doctor_name": doctor.full_name},
    )


@pages_router.get("/{record_id}", response_class=HTMLResponse)
def note_detail_page(
    request: Request,
    record_id: str,
    _staff=Depends(require_role(Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "consultations/consultation_detail.html",
        {"record_id": record_id},
    )
