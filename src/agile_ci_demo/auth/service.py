from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agile_ci_demo.core.security import verify_password
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.service import get_patient_by_ic
from agile_ci_demo.staff.models import Staff


class InvalidCredentialsError(Exception):
    """Raised when the email/password combination does not match a staff account."""


class AccountInactiveError(Exception):
    """Raised when login is attempted on a deactivated staff account."""


def authenticate_staff(db: Session, email: str, password: str) -> Staff:
    """Verify credentials and block login for deactivated accounts.

    Password is checked before the active-status check so that a wrong password
    always reports as invalid credentials rather than leaking account status.
    """
    staff = db.execute(select(Staff).where(Staff.email == email)).scalar_one_or_none()
    if staff is None or not verify_password(password, staff.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    if not staff.is_active:
        raise AccountInactiveError("This account has been deactivated")

    return staff


def authenticate_patient(db: Session, ic_or_passport: str, phone_number: str) -> Patient:
    """Verify a patient's IC/passport number and phone number match a registered patient."""
    patient = get_patient_by_ic(db, ic_or_passport)
    if patient is None or patient.phone_number != phone_number:
        raise InvalidCredentialsError("Invalid IC/passport number or phone number")
    return patient
