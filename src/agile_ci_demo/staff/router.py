from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.templates import templates
from agile_ci_demo.staff.schemas import DoctorOut, DoctorRegister, DoctorUpdate, StaffCreate, StaffOut, StaffStatusUpdate
from agile_ci_demo.staff.service import (
    DoctorEmailAlreadyExistsError,
    DoctorNotFoundError,
    DoctorUpdateEmailExistsError,
    DoctorUpdateLicenseExistsError,
    DuplicateDoctorLicenseError,
    DuplicateStaffEmailError,
    StaffNotFoundError,
    create_doctor_with_account,
    create_staff,
    get_doctor_by_doctor_id,
    list_doctors,
    list_staff,
    set_staff_active_status,
    update_doctor,
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


@api_router.get("/doctors", response_model=list[DoctorOut])
def get_doctor_list(db: Session = Depends(get_db)) -> list[DoctorOut]:
    return list_doctors(db)


@api_router.get("/doctors/{doctor_id}",response_model=DoctorOut)
def get_doctor_details(doctor_id: str,db: Session = Depends(get_db)
) -> DoctorOut:
    """Return one doctor using the public doctor ID."""
    try:
        return get_doctor_by_doctor_id(db, doctor_id)
    except DoctorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


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


@pages_router.get("/admin/listDoctor",response_class=HTMLResponse,)
def admin_doctor_list_page(request: Request
) -> HTMLResponse:
    """Render the doctor list page."""
    return templates.TemplateResponse( request,"staff/admin/listDoctor.html",{},)


@pages_router.get("/admin/viewDoctor/{doctor_id}",response_class=HTMLResponse,)
def admin_view_doctor_page(request: Request,doctor_id: str,
) -> HTMLResponse:
    """Render the selected doctor detail page."""

    return templates.TemplateResponse(
        request,
        "staff/admin/viewDoctor.html",
        {
            "doctor_id": doctor_id,
        },
    )

@api_router.patch(
    "/doctors/{doctor_id}",
    response_model=DoctorOut,
)
def update_doctor_details(
    doctor_id: str,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
) -> DoctorOut:
    try:
        return update_doctor(
            db,
            doctor_id,
            payload,
        )
    except DoctorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DoctorUpdateEmailExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DoctorUpdateLicenseExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc