from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import get_db
from agile_ci_demo.patients.schemas import PaginatedPatients, PatientCreate, PatientOut
from agile_ci_demo.patients.service import (
    DuplicatePatientError,
    create_patient,
    get_patient_by_patient_id,
    search_patients,
)

templates = Jinja2Templates(directory=str(settings.templates_dir))

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/patients", tags=["patients"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/patients", tags=["patients-pages"])


@api_router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def register_patient(payload: PatientCreate, db: Session = Depends(get_db)) -> PatientOut:
    """Register a new patient. Required fields are validated by PatientCreate."""
    try:
        patient = create_patient(db, payload)
    except DuplicatePatientError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return PatientOut.model_validate(patient)


@api_router.get("", response_model=PaginatedPatients)
def list_patients(
    q: str | None = Query(default=None, description="Search by name or patient ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedPatients:
    items, total = search_patients(db, q, page, page_size)
    total_pages = max(1, ceil(total / page_size))
    return PaginatedPatients(
        items=[PatientOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@api_router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: str, db: Session = Depends(get_db)) -> PatientOut:
    patient = get_patient_by_patient_id(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return PatientOut.model_validate(patient)


@pages_router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "patients/register.html", {})


@pages_router.get("", response_class=HTMLResponse)
def list_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "patients/list.html", {})
