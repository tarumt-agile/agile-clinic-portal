from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.templates import templates
from agile_ci_demo.reports.schemas import (
    AppointmentActivityReport,
    MonthlyPatientRegistrationReport,
)
from agile_ci_demo.reports.service import (
    InvalidReportDateRangeError,
    ReportDateRange,
    build_appointment_activity_report,
    build_monthly_patient_registration_report,
    generate_appointment_activity_pdf,
    generate_monthly_patient_registration_pdf,
    patient_registration_years,
    resolve_report_date_range,
)

report_admin = require_role(
    Role.ADMIN,
    forbidden_for_wrong_role=True,
)
admin_only_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {
        "description": "Forbidden: an authenticated staff member does not have the admin role."
    }
}

api_router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(report_admin)],
    responses=admin_only_responses,
)

pages_router = APIRouter(
    prefix="/reports",
    tags=["report-pages"],
    dependencies=[Depends(report_admin)],
    include_in_schema=False,
)


def _resolve_date_range_or_422(
    from_date: dt.date | None,
    to_date: dt.date | None,
) -> ReportDateRange:
    try:
        return resolve_report_date_range(
            from_date,
            to_date,
        )
    except InvalidReportDateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@api_router.get(
    "/appointments/daily",
    response_model=AppointmentActivityReport,
)
def get_daily_appointment_report(
    from_date: dt.date | None = Query(default=None, alias="from"),
    to_date: dt.date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> AppointmentActivityReport:
    date_range = _resolve_date_range_or_422(
        from_date,
        to_date,
    )
    return build_appointment_activity_report(
        db,
        date_range,
    )


@api_router.get("/appointments/daily/export.pdf")
def export_daily_appointment_report(
    from_date: dt.date | None = Query(default=None, alias="from"),
    to_date: dt.date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> Response:
    date_range = _resolve_date_range_or_422(
        from_date,
        to_date,
    )
    report = build_appointment_activity_report(
        db,
        date_range,
    )
    pdf_bytes = generate_appointment_activity_pdf(
        report,
        clinic_name=settings.clinic_name,
        clinic_address=settings.clinic_address,
        clinic_phone=settings.clinic_phone,
    )
    filename = (
        "appointment-activity-"
        f"{date_range.from_date.isoformat()}-to-"
        f"{date_range.to_date.isoformat()}.pdf"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": (f'attachment; filename="{filename}"')},
    )


@api_router.get(
    "/patients/registrations/monthly",
    response_model=MonthlyPatientRegistrationReport,
    summary="View monthly new patient registrations",
    description=(
        "Returns all twelve calendar months and their new-patient counts for the "
        "selected year. Requires an authenticated staff JWT with the admin role."
    ),
)
def get_monthly_patient_registration_report(
    year: int | None = Query(default=None, ge=1900, le=9998),
    db: Session = Depends(get_db),
) -> MonthlyPatientRegistrationReport:
    selected_year = year or dt.date.today().year
    return build_monthly_patient_registration_report(db, selected_year)


@api_router.get(
    "/patients/registrations/monthly/export.pdf",
    summary="Export monthly new patient registrations",
    description="Exports the selected year's monthly registration counts as a PDF.",
)
def export_monthly_patient_registration_report(
    year: int | None = Query(default=None, ge=1900, le=9998),
    db: Session = Depends(get_db),
) -> Response:
    selected_year = year or dt.date.today().year
    report = build_monthly_patient_registration_report(db, selected_year)
    pdf_bytes = generate_monthly_patient_registration_pdf(
        report,
        clinic_name=settings.clinic_name,
        clinic_address=settings.clinic_address,
        clinic_phone=settings.clinic_phone,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="patient-registrations-{selected_year}.pdf"'
            )
        },
    )


@pages_router.get("", response_class=HTMLResponse)
def reports_dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    date_range = resolve_report_date_range(
        None,
        None,
    )
    return templates.TemplateResponse(
        request,
        "reports/reports_dashboard.html",
        {
            "default_from_date": date_range.from_date.isoformat(),
            "default_to_date": date_range.to_date.isoformat(),
            "today_date": dt.date.today().isoformat(),
            "registration_years": patient_registration_years(db),
            "default_registration_year": dt.date.today().year,
        },
    )
