from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.templates import templates
from agile_ci_demo.staff.schemas import DoctorCreate, DoctorOut, DoctorRegister, StaffCreate, StaffOut, StaffStatusUpdate
from agile_ci_demo.staff.service import (
    DoctorEmailAlreadyExistsError,
    DoctorProfileAlreadyExistsError,
    DuplicateDoctorLicenseError,
    DuplicateStaffEmailError,
    StaffAccountIsNotDoctorError,
    StaffNotFoundError,
    create_doctor_profile,
    create_doctor_with_account,
    create_staff,
    list_available_doctor_staff_accounts,
    list_doctors,
    list_staff,
    set_staff_active_status,
)

api_router = APIRouter(prefix="/api/staff", tags=["staff"])
pages_router = APIRouter(prefix="/staff", tags=["staff-pages"])


@api_router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def register_staff(payload: StaffCreate, db: Session = Depends(get_db)) -> StaffOut:
    """Create a staff account."""
    try:
        staff = create_staff(db, payload)
    except DuplicateStaffEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return StaffOut.model_validate(staff)


@api_router.get("", response_model=list[StaffOut])
def get_staff_list(db: Session = Depends(get_db)) -> list[StaffOut]:
    return [StaffOut.model_validate(s) for s in list_staff(db)]


@api_router.get("/doctor-accounts/available", response_model=list[StaffOut])
def get_available_doctor_staff_accounts(db: Session = Depends(get_db)) -> list[StaffOut]:
    return [StaffOut.model_validate(s) for s in list_available_doctor_staff_accounts(db)]


@api_router.post("/doctors", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
def register_doctor_profile(payload: DoctorCreate, db: Session = Depends(get_db)) -> DoctorOut:
    """Create a doctor profile linked to an existing doctor staff account."""
    try:
        return create_doctor_profile(db, payload)
    except StaffNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StaffAccountIsNotDoctorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DoctorProfileAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DuplicateDoctorLicenseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@api_router.get("/doctors", response_model=list[DoctorOut])
def get_doctor_list(db: Session = Depends(get_db)) -> list[DoctorOut]:
    return list_doctors(db)


@api_router.patch("/{staff_id}/status", response_model=StaffOut)
def update_staff_status(
    staff_id: str, payload: StaffStatusUpdate, db: Session = Depends(get_db)
) -> StaffOut:
    """Activate or deactivate a staff account."""
    try:
        staff = set_staff_active_status(db, staff_id, payload.is_active)
    except StaffNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return StaffOut.model_validate(staff)

@api_router.post("/admin/doctors", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
def admin_create_doctor(payload: DoctorRegister, db: Session = Depends(get_db)) -> DoctorOut:
    """Admin creates a doctor account and doctor profile together."""
    try:
        return create_doctor_with_account(db, payload)
    except DoctorEmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DuplicateDoctorLicenseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    
@pages_router.get("/create", response_class=HTMLResponse)
def create_staff_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "staff/create.html", {})


@pages_router.get("", response_class=HTMLResponse)
def staff_list_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "staff/list.html", {})

@pages_router.get("/admin/createDoctor", response_class=HTMLResponse)
def admin_create_doctor_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "staff/admin/createDoctor.html", {})

