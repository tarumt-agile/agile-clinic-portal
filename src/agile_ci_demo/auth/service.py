from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from agile_ci_demo.auth.models import PasswordResetToken
from agile_ci_demo.core.email import send_email
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.security import hash_password, verify_password
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.service import get_patient_by_ic
from agile_ci_demo.staff.models import Staff

logger = logging.getLogger(__name__)

_REDIRECT_BY_ROLE: dict[Role, str] = {
    Role.ADMIN: "/staff",
    Role.DOCTOR: "/appointments/schedule",
    Role.NURSE: "/patients",
    Role.RECEPTIONIST: "/patients",
}


def redirect_url_for_role(role: Role) -> str:
    """Return the landing page a staff member is sent to right after login."""
    return _REDIRECT_BY_ROLE[role]


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
    """Verify a patient's IC/passport number and phone number match a registered patient.

    Phone numbers are compared digit-only: registration leaves the phone field
    freeform (whatever dash/space grouping the staff member typed), while the
    login page auto-formats it into a fixed grouping as you type - an exact
    string match would fail whenever those two don't happen to produce the
    same punctuation, even with the correct number.
    """
    patient = get_patient_by_ic(db, ic_or_passport)
    if patient is None or re.sub(r"\D", "", patient.phone_number) != re.sub(
        r"\D", "", phone_number
    ):
        raise InvalidCredentialsError("Invalid IC/passport number or phone number")
    return patient


_RESET_TOKEN_TTL = dt.timedelta(minutes=30)


class InvalidResetTokenError(Exception):
    """Raised when a password reset token is unknown, expired, or already used."""


class WrongCurrentPasswordError(Exception):
    """Raised when the supplied current password doesn't match the account's."""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str, base_url: str) -> None:
    """Email a password reset link if the email matches a staff account.

    Always succeeds silently for an unknown email, so this endpoint can't be used
    to discover which emails have accounts - same reasoning as authenticate_staff
    checking the password before the active-status check.

    base_url must be an absolute URL (e.g. request.base_url from the caller) - a
    relative link isn't clickable in a real mail client, and gets mangled when a
    plain-text email gets word-wrapped and copy-pasted.
    """
    staff = db.execute(select(Staff).where(Staff.email == email)).scalar_one_or_none()
    if staff is None:
        return

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        staff_id=staff.id,
        token_hash=_hash_token(raw_token),
        expires_at=dt.datetime.utcnow() + _RESET_TOKEN_TTL,
    )
    db.add(reset_token)
    db.commit()

    reset_link = f"{base_url.rstrip('/')}/auth/reset-password?token={raw_token}"
    try:
        send_email(
            to=staff.email,
            subject="Reset your Agile Clinic Portal password",
            body=(
                f"Hi {staff.full_name},\n\n"
                "We received a request to reset your password. This link expires in "
                "30 minutes:\n"
                f"{reset_link}\n\n"
                "If you didn't request this, you can ignore this email."
            ),
        )
    except Exception:
        # A delivery failure must never surface differently than success, or the
        # generic response above stops being generic (see docstring). Still log
        # it server-side so a real failure (e.g. the SMTP account being
        # throttled) is diagnosable instead of vanishing without a trace.
        logger.exception("Password reset email failed to send to %s", staff.email)


def reset_password(db: Session, token: str, new_password: str) -> None:
    """Set a new password for the staff account owning a valid, unused, unexpired token."""
    token_hash = _hash_token(token)
    reset_token = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).scalar_one_or_none()

    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at < dt.datetime.utcnow()
    ):
        raise InvalidResetTokenError("This reset link is invalid or has expired")

    staff = db.get(Staff, reset_token.staff_id)
    assert staff is not None  # the FK guarantees the staff row exists

    staff.password_hash = hash_password(new_password)
    staff.must_change_password = False
    reset_token.used_at = dt.datetime.utcnow()
    db.commit()


def change_password(db: Session, staff: Staff, current_password: str, new_password: str) -> None:
    """Change a logged-in staff member's own password, verifying their current
    one first - unlike reset_password (reached via an emailed token), which
    doesn't check the old password at all."""
    if not verify_password(current_password, staff.password_hash):
        raise WrongCurrentPasswordError("Current password is incorrect")

    staff.password_hash = hash_password(new_password)
    staff.must_change_password = False
    db.commit()
