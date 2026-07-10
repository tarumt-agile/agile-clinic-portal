from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.appointments.schemas import AppointmentCreate, AppointmentOut
from agile_ci_demo.appointments.service import (
    DoctorNotFoundError,
    InvalidSlotError,
    PatientNotFoundError,
    SlotUnavailableError,
    create_appointment,
    get_appointment_by_reference,
)
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.templates import templates

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


@api_router.get("/{reference_number}", response_model=AppointmentOut)
def get_appointment(reference_number: str, db: Session = Depends(get_db)) -> AppointmentOut:
    appointment = get_appointment_by_reference(db, reference_number)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return _serialize(appointment)


@pages_router.get("/create", response_class=HTMLResponse)
def create_appointment_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "appointments/create.html", {})
