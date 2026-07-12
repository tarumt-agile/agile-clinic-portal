import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.appointments.schemas import (
    AppointmentCreate,
    AppointmentOut,
    DoctorSchedule,
    DoctorSlots,
    SlotInfo,
)
from agile_ci_demo.appointments.service import (
    DoctorNotFoundError,
    InvalidSlotError,
    PastDateError,
    PatientNotFoundError,
    SlotUnavailableError,
    create_appointment,
    get_appointment_by_reference,
    get_available_slots,
    get_current_doctor,
    get_doctor_schedule,
)
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.templates import templates
from agile_ci_demo.staff.service import get_staff_by_staff_id

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/appointments", tags=["appointments"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/appointments", tags=["appointments-pages"])


def _serialize(appointment: Appointment) -> AppointmentOut:
    return AppointmentOut(
        reference_number=appointment.reference_number or "",
        patient_id=appointment.patient.patient_id or "",
        patient_name=appointment.patient.full_name,
        doctor_id=appointment.doctor.staff_id or "",
        doctor_name=appointment.doctor.full_name,
        appointment_date=appointment.appointment_date,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        reason=appointment.reason,
        status=appointment.status,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
    )


@api_router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)) -> AppointmentOut:
    """Book a new appointment. Validates slot availability and rejects double-booking."""
    try:
        appointment = create_appointment(db, payload)
    except (PatientNotFoundError, DoctorNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidSlotError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(appointment)


@api_router.get("/schedule", response_model=DoctorSchedule)
def get_my_schedule(
    schedule_date: dt.date = Query(default_factory=dt.date.today, alias="date"),
    db: Session = Depends(get_db),
) -> DoctorSchedule:
    """The current doctor's appointments for a given date (defaults to today).

    "Current doctor" is a placeholder - see get_current_doctor() - until real
    login sessions exist.
    """
    doctor = get_current_doctor(db)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No doctor account found")

    try:
        appointments = get_doctor_schedule(db, doctor.id, schedule_date)
    except PastDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return DoctorSchedule(
        doctor_id=doctor.staff_id or "",
        doctor_name=doctor.full_name,
        schedule_date=schedule_date,
        appointments=[_serialize(a) for a in appointments],
    )


@api_router.get("/slots", response_model=DoctorSlots)
def get_slots(
    doctor_id: str = Query(..., description="Doctor's public staff_id, e.g. S00001"),
    schedule_date: dt.date = Query(..., alias="date"),
    db: Session = Depends(get_db),
) -> DoctorSlots:
    """The full working-hours slot grid for a doctor on a date, each marked free or
    booked, for the booking form's slot picker."""
    doctor = get_staff_by_staff_id(db, doctor_id)
    if doctor is None or doctor.role != Role.DOCTOR.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No doctor found with staff_id '{doctor_id}'",
        )

    try:
        slots = get_available_slots(db, doctor.id, schedule_date)
    except PastDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return DoctorSlots(
        doctor_id=doctor.staff_id or "",
        doctor_name=doctor.full_name,
        schedule_date=schedule_date,
        slots=[SlotInfo(start_time=s, end_time=e, available=a) for s, e, a in slots],
    )


@api_router.get("/{reference_number}", response_model=AppointmentOut)
def get_appointment(reference_number: str, db: Session = Depends(get_db)) -> AppointmentOut:
    appointment = get_appointment_by_reference(db, reference_number)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return _serialize(appointment)


@pages_router.get("/create", response_class=HTMLResponse)
def create_appointment_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "appointments/create.html", {})


@pages_router.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "appointments/schedule.html", {})
