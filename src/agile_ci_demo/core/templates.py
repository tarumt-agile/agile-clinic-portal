# core/templates.py
from fastapi import Request
from fastapi.templating import Jinja2Templates

from agile_ci_demo.core.database import get_db
from agile_ci_demo.patients.service import get_patient_by_patient_id
from agile_ci_demo.staff.service import get_staff_by_staff_id


def _inject_current_user_full_name(request: Request) -> dict[str, str | None]:
    """Look up the signed-in user's full name fresh on every render, rather than
    caching it in the session at login time - a session-cached name would go
    stale the moment a staff member edits their own name via /staff/profile.

    Goes through request.app.dependency_overrides for get_db (the same
    override point FastAPI's own dependency injection uses) rather than
    importing SessionLocal directly, so this respects the in-memory test
    database the test suite substitutes via app.dependency_overrides[get_db].
    """
    staff_id = request.session.get("staff_id")
    patient_id = request.session.get("patient_id")

    if not staff_id and not patient_id:
        return {"full_name": None}

    db_dependency = request.app.dependency_overrides.get(get_db, get_db)
    db_generator = db_dependency()
    db = next(db_generator)
    try:
        if staff_id:
            staff = get_staff_by_staff_id(db, staff_id)
            return {"full_name": staff.full_name if staff else None}

        patient = get_patient_by_patient_id(db, patient_id)
        return {"full_name": patient.full_name if patient else None}
    finally:
        next(db_generator, None)


templates = Jinja2Templates(
    directory="templates",
    context_processors=[_inject_current_user_full_name],
)
