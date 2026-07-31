from __future__ import annotations

import datetime as dt

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
from agile_ci_demo.reports.schemas import AppointmentActivityReport
from agile_ci_demo.reports.service import (
    InvalidReportDateRangeError,
    ReportDateRange,
    build_appointment_activity_report,
    generate_appointment_activity_pdf,
    resolve_report_date_range,
)
from agile_ci_demo.staff.models import Staff

api_router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
)

pages_router = APIRouter(
    prefix="/reports",
    tags=["report-pages"],
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
    _admin: Staff = Depends(require_role(Role.ADMIN)),
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
    _admin: Staff = Depends(require_role(Role.ADMIN)),
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


@pages_router.get("", response_class=HTMLResponse)
def reports_dashboard_page(
    request: Request,
    _admin: Staff = Depends(require_role(Role.ADMIN)),
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
        },
    )
