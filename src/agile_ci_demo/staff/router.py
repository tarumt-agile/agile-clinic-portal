from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.templates import templates
from agile_ci_demo.staff.schemas import (
    DoctorOut,
    DoctorRegister,
    DoctorUpdate,
    StaffCreate,
    StaffOut,
    StaffStatusUpdate,
)
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


api_router = APIRouter(
    prefix="/api/staff",
    tags=["staff"],
)

pages_router = APIRouter(
    prefix="/staff",
    tags=["staff-pages"],
)


# =========================================================
# GENERAL STAFF API
# =========================================================

@api_router.post(
    "",
    response_model=StaffOut,
    status_code=status.HTTP_201_CREATED,
)
def register_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
) -> StaffOut:
    """Create a general staff account."""

    try:
        staff = create_staff(db, payload)

    except DuplicateStaffEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return StaffOut.model_validate(staff)


@api_router.get(
    "",
    response_model=list[StaffOut],
)
def get_staff_list(
    db: Session = Depends(get_db),
) -> list[StaffOut]:
    """Return all staff accounts."""

    return [
        StaffOut.model_validate(staff)
        for staff in list_staff(db)
    ]


@api_router.patch(
    "/{staff_id}/status",
    response_model=StaffOut,
)
def update_staff_status(
    staff_id: str,
    payload: StaffStatusUpdate,
    db: Session = Depends(get_db),
) -> StaffOut:
    """Activate or deactivate a staff account."""

    try:
        staff = set_staff_active_status(
            db,
            staff_id,
            payload.is_active,
        )

    except StaffNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StaffOut.model_validate(staff)


# =========================================================
# DOCTOR API
# =========================================================

@api_router.post(
    "/doctor",
    response_model=DoctorOut,
    status_code=status.HTTP_201_CREATED,
)
def create_doctor(
    payload: DoctorRegister,
    db: Session = Depends(get_db),
) -> DoctorOut:
    """Create a doctor staff account and doctor profile."""

    try:
        return create_doctor_with_account(
            db,
            payload,
        )

    except DoctorEmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except DuplicateDoctorLicenseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@api_router.get(
    "/doctor",
    response_model=list[DoctorOut],
)
def get_doctor_list(
    db: Session = Depends(get_db),
) -> list[DoctorOut]:
    """Return all doctor profiles."""

    return list_doctors(db)


@api_router.get(
    "/doctor/{doctor_id}",
    response_model=DoctorOut,
)
def get_doctor_details(
    doctor_id: str,
    db: Session = Depends(get_db),
) -> DoctorOut:
    """Return one doctor using the public doctor ID."""

    try:
        return get_doctor_by_doctor_id(
            db,
            doctor_id,
        )

    except DoctorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@api_router.patch(
    "/doctor/{doctor_id}",
    response_model=DoctorOut,
)
def update_doctor_details(
    doctor_id: str,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
) -> DoctorOut:
    """Update a doctor account and doctor profile."""

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


# =========================================================
# GENERAL STAFF PAGES
# =========================================================

@pages_router.get(
    "",
    response_class=HTMLResponse,
)
def staff_list_page(
    request: Request,
) -> HTMLResponse:
    """Render the general staff list page."""

    return templates.TemplateResponse(
        request,
        "staff/staff_list.html",
        {},
    )


@pages_router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_staff_page(
    request: Request,
) -> HTMLResponse:
    """Render the general staff creation page."""

    return templates.TemplateResponse(
        request,
        "staff/staff_create.html",
        {},
    )


# =========================================================
# DOCTOR PAGES
# =========================================================

@pages_router.get(
    "/doctor",
    response_class=HTMLResponse,
)
def doctor_list_page(
    request: Request,
) -> HTMLResponse:
    """Render the doctor list page."""

    return templates.TemplateResponse(
        request,
        "staff/doctor/doctor_list.html",
        {},
    )


@pages_router.get(
    "/doctor/create",
    response_class=HTMLResponse,
)
def create_doctor_page(
    request: Request,
) -> HTMLResponse:
    """Render the doctor creation page."""

    return templates.TemplateResponse(
        request,
        "staff/doctor/doctor_create.html",
        {},
    )


@pages_router.get(
    "/doctor/{doctor_id}",
    response_class=HTMLResponse,
)
def view_doctor_page(
    request: Request,
    doctor_id: str,
) -> HTMLResponse:
    """Render one doctor detail page."""

    return templates.TemplateResponse(
        request,
        "staff/doctor/doctor_view.html",
        {
            "doctor_id": doctor_id,
        },
    )