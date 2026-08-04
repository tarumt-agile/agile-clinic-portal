from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.templates import templates
from agile_ci_demo.dashboard.schemas import AdminDashboardStats
from agile_ci_demo.dashboard.service import get_admin_dashboard_stats
from agile_ci_demo.staff.models import Staff

api_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

pages_router = APIRouter(prefix="/dashboard", tags=["dashboard-pages"])


# This route returns the clinic-wide stats shown on the admin dashboard.
@api_router.get(
    "/admin-stats",
    response_model=AdminDashboardStats,
)
def get_admin_dashboard_stats_endpoint(
    db: Session = Depends(get_db),
    _admin: Staff = Depends(require_role(Role.ADMIN)),
) -> AdminDashboardStats:
    return AdminDashboardStats(**get_admin_dashboard_stats(db))


# This route displays the admin dashboard page.
@pages_router.get(
    "",
    response_class=HTMLResponse,
)
def admin_dashboard_page(
    request: Request,
    _admin: Staff = Depends(require_role(Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard/admin_dashboard.html",
        {},
    )
