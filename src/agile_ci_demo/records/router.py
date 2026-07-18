from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.templates import templates
from agile_ci_demo.records.models import ConsultationNote
from agile_ci_demo.records.schemas import (
    ConsultationNoteCreate,
    ConsultationNoteOut,
    ConsultationNoteSummary,
    DiagnosisOut,
    Icd10Entry,
    PatientHistory,
)
from agile_ci_demo.records.service import (
    ConsultationNoteConflictError,
    DoctorNotFoundError,
    PatientNotFoundError,
    create_consultation_note,
    get_consultation_note_by_record_id,
    get_patient_history,
    search_icd10_codes,
)

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/records", tags=["records"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/records", tags=["records-pages"])


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
        created_at=note.created_at,
    )


def _serialize_summary(note: ConsultationNote) -> ConsultationNoteSummary:
    return ConsultationNoteSummary(
        record_id=note.record_id or "",
        visit_date=note.visit_date,
        doctor_name=note.doctor.full_name,
        notes=note.notes,
        diagnoses=[DiagnosisOut.model_validate(d) for d in note.diagnoses],
    )


@api_router.post("", response_model=ConsultationNoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: ConsultationNoteCreate, db: Session = Depends(get_db)
) -> ConsultationNoteOut:
    """Document a consultation. At least one diagnosis is required (enforced by the schema)."""
    try:
        note = create_consultation_note(db, payload)
    except (PatientNotFoundError, DoctorNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConsultationNoteConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(note)


@api_router.get("/icd10", response_model=list[Icd10Entry])
def autocomplete_icd10(
    q: str = Query(default="", description="Search term matched against code or description"),
) -> list[Icd10Entry]:
    return [Icd10Entry(**entry) for entry in search_icd10_codes(q)]


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
    request: Request, patient_id: str = Query(..., description="Patient to document a visit for")
) -> HTMLResponse:
    return templates.TemplateResponse(request, "records/new.html", {"patient_id": patient_id})


@pages_router.get("/{record_id}", response_class=HTMLResponse)
def note_detail_page(request: Request, record_id: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "records/detail.html", {"record_id": record_id})
