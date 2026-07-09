from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.templates import templates
from agile_ci_demo.staff.schemas import StaffCreate, StaffOut, StaffStatusUpdate
from agile_ci_demo.staff.service import (
    DuplicateStaffEmailError,
    StaffNotFoundError,
    create_staff,
    list_staff,
    set_staff_active_status,
)

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/staff", tags=["staff"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/staff", tags=["staff-pages"])


@api_router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def register_staff(payload: StaffCreate, db: Session = Depends(get_db)) -> StaffOut:
    """Create a staff account. Sends a welcome email containing a generated temp password."""
    try:
        staff = create_staff(db, payload)
    except DuplicateStaffEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return StaffOut.model_validate(staff)


@api_router.get("", response_model=list[StaffOut])
def get_staff_list(db: Session = Depends(get_db)) -> list[StaffOut]:
    return [StaffOut.model_validate(s) for s in list_staff(db)]


@api_router.patch("/{staff_id}/status", response_model=StaffOut)
def update_staff_status(
    staff_id: str, payload: StaffStatusUpdate, db: Session = Depends(get_db)
) -> StaffOut:
    """Activate or deactivate a staff account from the user management page."""
    try:
        staff = set_staff_active_status(db, staff_id, payload.is_active)
    except StaffNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return StaffOut.model_validate(staff)


@pages_router.get("/create", response_class=HTMLResponse)
def create_staff_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "staff/create.html", {})


@pages_router.get("", response_class=HTMLResponse)
def staff_list_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "staff/list.html", {})
