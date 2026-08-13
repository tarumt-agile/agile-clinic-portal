import datetime as dt
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.audit import get_auth_audit_log, log_auth_event
from agile_ci_demo.auth.deps import login_patient, login_staff, logout, require_role, require_staff
from agile_ci_demo.auth.schemas import (
    AuthAuditLogEntry,
    AuthAuditLogPage,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    PatientLoginRequest,
    PatientLoginResponse,
    ResetPasswordRequest,
)
from agile_ci_demo.auth.service import (
    AccountInactiveError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    WrongCurrentPasswordError,
    authenticate_patient,
    authenticate_staff,
    change_password,
    redirect_url_for_role,
    request_password_reset,
    reset_password,
    send_account_lockout_alert,
)
from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rate_limit import is_locked_out, record_failure, record_success
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.security import generate_session_token
from agile_ci_demo.core.templates import templates
from agile_ci_demo.staff.models import Staff

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/auth", tags=["auth"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/auth", tags=["auth-pages"])


@api_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    email = str(payload.email)
    ip = request.client.host if request.client else None

    if is_locked_out(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. This account is locked for 15 minutes.",
        )

    try:
        staff = authenticate_staff(db, email, payload.password)
    except InvalidCredentialsError as exc:
        just_locked = record_failure(email)
        log_auth_event(db, event="login_failed", email=email, ip=ip)
        if just_locked:
            log_auth_event(db, event="account_locked", email=email, ip=ip)
            send_account_lockout_alert(db, email)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. This account is locked for 15 minutes.",
            ) from exc
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AccountInactiveError as exc:
        log_auth_event(db, event="login_blocked_inactive", email=email, ip=ip)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    record_success(email)
    login_staff(request, staff)
    role = Role(staff.role)
    log_auth_event(db, event="login_success", user_id=staff.staff_id, email=email, ip=ip)
    return LoginResponse(
        staff_id=cast(str, staff.staff_id),
        full_name=staff.full_name,
        role=role,
        must_change_password=staff.must_change_password,
        redirect_url=redirect_url_for_role(role),
        session_token=generate_session_token(
            staff_id=cast(str, staff.staff_id),
            role=staff.role,
            secret_key=settings.secret_key,
        ),
    )


@api_router.post("/patient-login", response_model=PatientLoginResponse)
def patient_login(
    payload: PatientLoginRequest, request: Request, db: Session = Depends(get_db)
) -> PatientLoginResponse:
    ip = request.client.host if request.client else None
    try:
        patient = authenticate_patient(db, payload.ic_or_passport, payload.phone_number)
    except InvalidCredentialsError as exc:
        log_auth_event(db, event="patient_login_failed", ip=ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    login_patient(request, patient)
    log_auth_event(db, event="patient_login_success", user_id=patient.patient_id, ip=ip)
    return PatientLoginResponse.model_validate(patient)


@api_router.post("/logout")
def logout_endpoint(request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else None
    user_id = request.session.get("staff_id") or request.session.get("patient_id")
    logout(request)
    log_auth_event(db, event="logout", user_id=user_id, ip=ip)
    return {"status": "ok"}


@api_router.delete("/session")
def delete_session(request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else None
    user_id = request.session.get("staff_id") or request.session.get("patient_id")
    logout(request)
    log_auth_event(db, event="logout", user_id=user_id, ip=ip)
    return {"status": "ok"}


@pages_router.get("/login", response_class=HTMLResponse, response_model=None)
def login_page(request: Request) -> HTMLResponse | RedirectResponse:
    """Renders the login form - unless a still-valid session already exists,
    in which case it sends the visitor straight to their dashboard instead.

    Session cookies are signed and outlive the server process (14-day expiry,
    same secret key across restarts), so restarting the dev server does not
    log anyone out. Without this check, a still-authenticated visitor landing
    here would see the login form wrapped in the full authenticated app shell
    (sidebar included) - base.html's `authed` gating is keyed off the same
    session, so it has no way to know this particular page should always
    render as logged-out.
    """
    role = request.session.get("role")
    if role:
        return RedirectResponse(redirect_url_for_role(Role(role)), status_code=303)
    if request.session.get("user_type") == "patient":
        return RedirectResponse("/patients/dashboard", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", {})


@api_router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    request_password_reset(db, str(payload.email), base_url=str(request.base_url))
    log_auth_event(
        db,
        event="password_reset_requested",
        email=str(payload.email),
        ip=request.client.host if request.client else None,
    )
    return ForgotPasswordResponse(message="If that email is registered, we've sent a reset link.")


@pages_router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/forgot_password.html", {})


@api_router.post("/reset-password")
def reset_password_endpoint(
    payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    try:
        reset_password(db, payload.token, payload.new_password)
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    log_auth_event(
        db, event="password_reset_completed", ip=request.client.host if request.client else None
    )
    return {"status": "ok"}


@pages_router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/reset_password.html", {})


@api_router.post("/change-password")
def change_password_endpoint(
    payload: ChangePasswordRequest,
    request: Request,
    staff: Staff = Depends(require_staff),
    db: Session = Depends(get_db),
) -> dict:
    try:
        change_password(db, staff, payload.current_password, payload.new_password)
    except WrongCurrentPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    log_auth_event(
        db,
        event="password_changed",
        user_id=staff.staff_id,
        ip=request.client.host if request.client else None,
    )
    return {"status": "ok"}


@pages_router.get("/audit-log", response_class=HTMLResponse)
def audit_log_page(
    request: Request,
    _admin: Staff = Depends(require_role(Role.ADMIN)),
) -> HTMLResponse:
    today = dt.date.today()
    return templates.TemplateResponse(
        request,
        "auth/audit_log.html",
        {
            "default_from_date": (today - dt.timedelta(days=7)).isoformat(),
            "default_to_date": today.isoformat(),
        },
    )


@api_router.get("/audit-log", response_model=AuthAuditLogPage)
def get_audit_log(
    from_date: dt.date | None = Query(default=None, alias="from"),
    to_date: dt.date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _admin: Staff = Depends(require_role(Role.ADMIN)),
) -> AuthAuditLogPage:
    entries = get_auth_audit_log(db, from_date=from_date, to_date=to_date)
    return AuthAuditLogPage(
        items=[AuthAuditLogEntry.model_validate(e) for e in entries], total=len(entries)
    )
