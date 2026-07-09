from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.core.email import send_email
from agile_ci_demo.core.security import generate_temp_password, hash_password
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.staff.schemas import StaffCreate


class DuplicateStaffEmailError(Exception):
    """Raised when a staff account with the same email already exists."""


class StaffNotFoundError(Exception):
    """Raised when a staff_id does not match any stored staff account."""


def create_staff(db: Session, data: StaffCreate) -> Staff:
    """Create a staff account with a generated temporary password and email it to them."""
    existing = db.execute(select(Staff).where(Staff.email == data.email)).scalar_one_or_none()
    if existing is not None:
        raise DuplicateStaffEmailError(f"A staff account with email '{data.email}' already exists")

    temp_password = generate_temp_password()
    staff = Staff(
        full_name=data.full_name,
        email=data.email,
        role=data.role.value,
        password_hash=hash_password(temp_password),
        must_change_password=True,
        is_active=True,
    )
    db.add(staff)

    try:
        db.flush()  # assigns staff.id (autoincrement) without committing
        staff.staff_id = f"S{staff.id:05d}"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateStaffEmailError(
            "Staff account could not be created due to a conflict"
        ) from exc

    db.refresh(staff)

    send_email(
        to=staff.email,
        subject="Welcome to Agile Clinic Portal",
        body=(
            f"Hi {staff.full_name},\n\n"
            f"An account has been created for you as {staff.role}.\n"
            f"Your temporary password is: {temp_password}\n\n"
            "Please log in and change your password as soon as possible."
        ),
    )

    return staff


def list_staff(db: Session) -> list[Staff]:
    return list(db.execute(select(Staff).order_by(Staff.id)).scalars().all())


def get_staff_by_staff_id(db: Session, staff_id: str) -> Staff | None:
    return db.execute(select(Staff).where(Staff.staff_id == staff_id)).scalar_one_or_none()


def set_staff_active_status(db: Session, staff_id: str, is_active: bool) -> Staff:
    """Activate or deactivate a staff account. A deactivated account is blocked from logging in."""
    staff = get_staff_by_staff_id(db, staff_id)
    if staff is None:
        raise StaffNotFoundError(f"No staff account found with staff_id '{staff_id}'")

    staff.is_active = is_active
    db.commit()
    db.refresh(staff)
    return staff
