from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.security import InvalidSessionTokenError, decode_session_token
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.service import get_patient_by_patient_id
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.staff.service import get_staff_by_staff_id


class NotAuthenticatedError(Exception):
    """Raised when a page needs a session that isn't there, or the wrong role is signed in."""


staff_bearer = HTTPBearer(
    auto_error=False,
    description="Staff JWT returned by POST /api/auth/login.",
)


def login_staff(request: Request, staff: Staff) -> None:
    request.session.clear()
    request.session["user_type"] = "staff"
    request.session["staff_id"] = staff.staff_id
    request.session["role"] = staff.role


def login_patient(request: Request, patient: Patient) -> None:
    request.session.clear()
    request.session["user_type"] = "patient"
    request.session["patient_id"] = patient.patient_id


def logout(request: Request) -> None:
    request.session.clear()


def require_role(
    *roles: Role,
    forbidden_for_wrong_role: bool = False,
) -> Callable[..., Staff]:
    """Require an active staff cookie session or Bearer JWT with an allowed role."""
    allowed = {role.value for role in roles}
    forbidden_detail = (
        f"{roles[0].value.title()} role required."
        if len(roles) == 1
        else "Required staff role missing."
    )

    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        credentials: HTTPAuthorizationCredentials | None = Depends(staff_bearer),
    ) -> Staff:
        staff_id: str | None = None
        token_role: str | None = None
        if credentials is not None:
            try:
                payload = decode_session_token(credentials.credentials, settings.secret_key)
            except InvalidSessionTokenError as exc:
                raise NotAuthenticatedError() from exc
            staff_id = payload["sub"]
            token_role = payload["role"]
        else:
            staff_id = request.session.get("staff_id")

        staff = get_staff_by_staff_id(db, staff_id) if staff_id else None
        if staff is None or not staff.is_active:
            raise NotAuthenticatedError()
        if token_role is not None and token_role != staff.role:
            raise NotAuthenticatedError()
        if staff.role not in allowed:
            if forbidden_for_wrong_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=forbidden_detail,
                )
            raise NotAuthenticatedError()
        return staff

    return dependency


def require_staff(request: Request, db: Session = Depends(get_db)) -> Staff:
    """Any authenticated staff member, regardless of role - used by self-service
    endpoints (like the staff profile page) that every staff role can reach,
    unlike require_role(*roles) which requires an explicit allowed-role list."""
    staff_id = request.session.get("staff_id")
    staff = get_staff_by_staff_id(db, staff_id) if staff_id else None
    if staff is None or not staff.is_active:
        raise NotAuthenticatedError()
    return staff


def require_patient(request: Request, db: Session = Depends(get_db)) -> Patient:
    patient_id = request.session.get("patient_id")
    patient = get_patient_by_patient_id(db, patient_id) if patient_id else None
    if patient is None:
        raise NotAuthenticatedError()
    return patient


def require_booking_actor(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(staff_bearer),
) -> Staff | Patient:
    """Require either front-desk staff (receptionist, nurse, or admin) or a
    patient - the two audiences allowed to create or cancel appointments.
    Doctors are read-only for appointments, so a doctor session is rejected
    here the same way an unauthenticated request would be.
    """
    if credentials is not None or request.session.get("staff_id"):
        return require_role(Role.RECEPTIONIST, Role.NURSE, Role.ADMIN)(request, db, credentials)
    return require_patient(request, db)
