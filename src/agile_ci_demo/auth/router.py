from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.deps import login_patient, login_staff, logout
from agile_ci_demo.auth.schemas import (
    LoginRequest,
    LoginResponse,
    PatientLoginRequest,
    PatientLoginResponse,
)
from agile_ci_demo.auth.service import (
    AccountInactiveError,
    InvalidCredentialsError,
    authenticate_patient,
    authenticate_staff,
)
from agile_ci_demo.core.database import get_db
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
    return LoginResponse.model_validate(staff)


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


@pages_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html", {})
