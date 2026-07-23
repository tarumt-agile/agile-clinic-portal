from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.templates import templates
from agile_ci_demo.staff.schemas import (
    DoctorOut,
    StaffCreate,
    StaffOut,
    StaffStatusUpdate,
    StaffUpdate,
)
from agile_ci_demo.staff.service import (
    DoctorNotFoundError,
    DuplicateStaffEmailError,
    StaffNotFoundError,
    StaffUpdateEmailExistsError,
    StaffUpdateLicenseExistsError,
    create_staff,
    get_doctor_by_doctor_id,
    get_staff_by_staff_id,
    list_doctors,
    list_staff,
    set_staff_active_status,
    update_staff,
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


# This route creates a new staff account.
@api_router.post(
    "",
    response_model=StaffOut,
    status_code=status.HTTP_201_CREATED,
)
def register_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
) -> StaffOut:
    try:
        staff = create_staff(
            db,
            payload,
        )

    except DuplicateStaffEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY),
            detail=str(exc),
        ) from exc

    return StaffOut.model_validate(staff)


# This route returns the list of all staff accounts.
@api_router.get(
    "",
    response_model=list[StaffOut],
)
def get_staff_list(
    db: Session = Depends(get_db),
) -> list[StaffOut]:
    staff_accounts = list_staff(db)

    return [StaffOut.model_validate(staff) for staff in staff_accounts]


# =========================================================
# DOCTOR READ API
# =========================================================


# This route returns the list of all doctors.
@api_router.get(
    "/doctor",
    response_model=list[DoctorOut],
)
def get_doctor_list(
    db: Session = Depends(get_db),
) -> list[DoctorOut]:
    return list_doctors(db)


# This route returns the details of one doctor.
@api_router.get(
    "/doctor/{doctor_id}",
    response_model=DoctorOut,
)
def get_doctor_details(
    doctor_id: str,
    db: Session = Depends(get_db),
) -> DoctorOut:
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


# =========================================================
# STAFF DETAILS AND UPDATE API
# =========================================================


# This route activates or deactivates one staff account.
@api_router.patch(
    "/{staff_id}/status",
    response_model=StaffOut,
)
def update_staff_status(
    staff_id: str,
    payload: StaffStatusUpdate,
    db: Session = Depends(get_db),
) -> StaffOut:
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


# This route returns the details of one staff account.
@api_router.get(
    "/{staff_id}",
    response_model=StaffOut,
)
def get_staff_details(
    staff_id: str,
    db: Session = Depends(get_db),
) -> StaffOut:
    staff = get_staff_by_staff_id(
        db,
        staff_id,
    )

    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("No staff account found with " f"staff_id '{staff_id}'."),
        )

    return StaffOut.model_validate(staff)


# This route updates the details of one staff account.
@api_router.patch(
    "/{staff_id}",
    response_model=StaffOut,
)
def update_staff_details(
    staff_id: str,
    payload: StaffUpdate,
    db: Session = Depends(get_db),
) -> StaffOut:
    try:
        staff = update_staff(
            db,
            staff_id,
            payload,
        )

    except StaffNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except (
        StaffUpdateEmailExistsError,
        StaffUpdateLicenseExistsError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY),
            detail=str(exc),
        ) from exc

    return StaffOut.model_validate(staff)


# =========================================================
# STAFF PAGES
# =========================================================


# This route displays the staff list page.
@pages_router.get(
    "",
    response_class=HTMLResponse,
)
def staff_list_page(
    request: Request,
    _staff=Depends(require_role(Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "staff/staff_list.html",
        {},
    )


# This route displays the staff creation page.
@pages_router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_staff_page(
    request: Request,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "staff/staff_create.html",
        {},
    )


# This route displays the details page for one staff account.
@pages_router.get(
    "/{staff_id}",
    response_class=HTMLResponse,
)
def staff_detail_page(
    request: Request,
    staff_id: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "staff/staff_view.html",
        {
            "staff_id": staff_id,
        },
    )
