from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.deps import login_patient, login_staff, logout
from agile_ci_demo.auth.schemas import (
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
    authenticate_patient,
    authenticate_staff,
    redirect_url_for_role,
    request_password_reset,
    reset_password,
)
from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.security import generate_session_token
from agile_ci_demo.core.templates import templates

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/auth", tags=["auth"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/auth", tags=["auth-pages"])


@api_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        staff = authenticate_staff(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AccountInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    login_staff(request, staff)
    role = Role(staff.role)
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
    try:
        patient = authenticate_patient(db, payload.ic_or_passport, payload.phone_number)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    login_patient(request, patient)
    return PatientLoginResponse.model_validate(patient)


@api_router.post("/logout")
def logout_endpoint(request: Request) -> dict:
    logout(request)
    return {"status": "ok"}


@api_router.delete("/session")
def delete_session(request: Request) -> dict:
    logout(request)
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
    return ForgotPasswordResponse(message="If that email is registered, we've sent a reset link.")


@pages_router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/forgot_password.html", {})


@api_router.post("/reset-password")
def reset_password_endpoint(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    try:
        reset_password(db, payload.token, payload.new_password)
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "ok"}


@pages_router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/reset_password.html", {})
