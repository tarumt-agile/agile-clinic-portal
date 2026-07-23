from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.service import get_patient_by_patient_id
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.staff.service import get_staff_by_staff_id


class NotAuthenticatedError(Exception):
    """Raised when a page needs a session that isn't there, or the wrong role is signed in."""


def login_staff(request: Request, staff: Staff) -> None:
    request.session["user_type"] = "staff"
    request.session["staff_id"] = staff.staff_id
    request.session["role"] = staff.role


def login_patient(request: Request, patient: Patient) -> None:
    request.session["user_type"] = "patient"
    request.session["patient_id"] = patient.patient_id


def logout(request: Request) -> None:
    request.session.clear()


def require_role(*roles: Role) -> Callable[..., Staff]:
    """Dependency factory: only lets the given staff roles through, otherwise redirects to login."""
    allowed = {role.value for role in roles}

    def dependency(request: Request, db: Session = Depends(get_db)) -> Staff:
        staff_id = request.session.get("staff_id")
        staff = get_staff_by_staff_id(db, staff_id) if staff_id else None
        if staff is None or staff.role not in allowed or not staff.is_active:
            raise NotAuthenticatedError()
        return staff

    return dependency


def require_patient(request: Request, db: Session = Depends(get_db)) -> Patient:
    patient_id = request.session.get("patient_id")
    patient = get_patient_by_patient_id(db, patient_id) if patient_id else None
    if patient is None:
        raise NotAuthenticatedError()
    return patient
