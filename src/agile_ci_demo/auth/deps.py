from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.staff.service import get_staff_by_staff_id


class NotAuthenticatedError(Exception):
    """Raised when a page needs a session that isn't there, or the wrong role is signed in."""


def login_staff(request: Request, staff: Staff) -> None:
    request.session["user_type"] = "staff"
    request.session["staff_id"] = staff.staff_id
    request.session["role"] = staff.role


def logout(request: Request) -> None:
    request.session.clear()


def require_role(*roles: Role):
    """Dependency factory: only lets the given staff roles through, otherwise redirects to login."""
    allowed = {role.value for role in roles}

    def dependency(request: Request, db: Session = Depends(get_db)) -> Staff:
        staff_id = request.session.get("staff_id")
        staff = get_staff_by_staff_id(db, staff_id) if staff_id else None
        if staff is None or staff.role not in allowed:
            raise NotAuthenticatedError()
        return staff

    return dependency
