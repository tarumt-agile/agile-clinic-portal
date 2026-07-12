from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.appointments.schemas import AppointmentCreate
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.patients.service import get_patient_by_patient_id
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.staff.service import get_staff_by_staff_id

# Clinic working hours and slot size. A teaching-app constant rather than a DB-backed
# setting - every appointment must start on one of these boundaries.
CLINIC_OPEN = dt.time(9, 0)
CLINIC_CLOSE = dt.time(17, 0)
SLOT_MINUTES = 30


class PatientNotFoundError(Exception):
    """Raised when a patient_id does not match any stored patient."""


class DoctorNotFoundError(Exception):
    """Raised when a staff_id does not match an active doctor account."""


class InvalidSlotError(Exception):
    """Raised when the requested date/time falls outside working hours, off the
    slot grid, or in the past."""


class SlotUnavailableError(Exception):
    """Raised when the doctor already has a scheduled appointment overlapping this slot."""


class PastDateError(Exception):
    """Raised when a doctor's schedule is requested for a date before today."""


def add_minutes(value: dt.time, minutes: int) -> dt.time:
    combined = dt.datetime.combine(dt.date.today(), value) + dt.timedelta(minutes=minutes)
    return combined.time()


def _validate_slot(appointment_date: dt.date, start_time: dt.time, end_time: dt.time) -> None:
    now = dt.datetime.now()
    if appointment_date < now.date():
        raise InvalidSlotError("Appointment date cannot be in the past")

    if appointment_date == now.date() and start_time < now.time():
        raise InvalidSlotError("Appointment time cannot be in the past")

    if start_time < CLINIC_OPEN or end_time > CLINIC_CLOSE:
        raise InvalidSlotError(
            f"Appointments must be between {CLINIC_OPEN.strftime('%H:%M')} "
            f"and {CLINIC_CLOSE.strftime('%H:%M')}"
        )

    minutes_since_open = (
        dt.datetime.combine(appointment_date, start_time)
        - dt.datetime.combine(appointment_date, CLINIC_OPEN)
    ).total_seconds() / 60
    if minutes_since_open % SLOT_MINUTES != 0:
        raise InvalidSlotError(f"Appointment start time must align to {SLOT_MINUTES}-minute slots")


def create_appointment(db: Session, data: AppointmentCreate) -> Appointment:
    """Book a new appointment, validating slot availability and preventing double-booking."""
    patient = get_patient_by_patient_id(db, data.patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{data.patient_id}'")

    doctor = get_staff_by_staff_id(db, data.doctor_id)
    if doctor is None or doctor.role != Role.DOCTOR.value:
        raise DoctorNotFoundError(f"No doctor found with staff_id '{data.doctor_id}'")

    end_time = add_minutes(data.start_time, SLOT_MINUTES)
    _validate_slot(data.appointment_date, data.start_time, end_time)

    conflict = db.execute(
        select(Appointment).where(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == data.appointment_date,
            Appointment.status == "scheduled",
            Appointment.start_time < end_time,
            Appointment.end_time > data.start_time,
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise SlotUnavailableError(
            f"{doctor.full_name} already has an appointment at "
            f"{data.start_time.strftime('%H:%M')} on {data.appointment_date}"
        )

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=data.appointment_date,
        start_time=data.start_time,
        end_time=end_time,
        reason=data.reason,
        status="scheduled",
    )
    db.add(appointment)

    try:
        db.flush()  # assigns appointment.id (autoincrement) without committing
        appointment.reference_number = f"A{appointment.id:05d}"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SlotUnavailableError("Appointment could not be created due to a conflict") from exc

    db.refresh(appointment)
    return appointment


def get_appointment_by_reference(db: Session, reference_number: str) -> Appointment | None:
    return db.execute(
        select(Appointment).where(Appointment.reference_number == reference_number)
    ).scalar_one_or_none()


def get_current_doctor(db: Session) -> Staff | None:
    """Stand-in for real authentication: returns the first doctor on record as "the
    logged-in doctor". There is no session/token yet - swap this for a real
    Depends(get_current_user) once login sessions are wired up."""
    return (
        db.execute(select(Staff).where(Staff.role == Role.DOCTOR.value).order_by(Staff.id))
        .scalars()
        .first()
    )


def get_doctor_schedule(db: Session, doctor_id: int, schedule_date: dt.date) -> list[Appointment]:
    """Return a doctor's appointments for a given date, ordered by start time ascending."""
    if schedule_date < dt.date.today():
        raise PastDateError("Cannot view a schedule for a date before today")

    return list(
        db.execute(
            select(Appointment)
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == schedule_date,
            )
            .order_by(Appointment.start_time)
        )
        .scalars()
        .all()
    )


def get_available_slots(
    db: Session, doctor_id: int, schedule_date: dt.date
) -> list[tuple[dt.time, dt.time, bool]]:
    """Compute the full working-hours slot grid for a doctor on a date, marking each
    slot as available or not. A slot is unavailable if it is already scheduled
    (cancelled appointments free the slot back up) or already in the past today."""
    if schedule_date < dt.date.today():
        raise PastDateError("Cannot view available slots for a date before today")

    booked_starts = set(
        db.execute(
            select(Appointment.start_time).where(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == schedule_date,
                Appointment.status == "scheduled",
            )
        )
        .scalars()
        .all()
    )

    now = dt.datetime.now()
    is_today = schedule_date == now.date()

    slots = []
    current = CLINIC_OPEN
    while current < CLINIC_CLOSE:
        end = add_minutes(current, SLOT_MINUTES)
        is_past = is_today and current < now.time()
        available = current not in booked_starts and not is_past
        slots.append((current, end, available))
        current = end
    return slots
