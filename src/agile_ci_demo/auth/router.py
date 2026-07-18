from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.schemas import LoginRequest, LoginResponse
from agile_ci_demo.auth.service import (
    AccountInactiveError,
    InvalidCredentialsError,
    authenticate_staff,
)
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.templates import templates

# JSON API used by the frontend's JavaScript.
api_router = APIRouter(prefix="/api/auth", tags=["auth"])

# Server-rendered HTML pages.
pages_router = APIRouter(prefix="/auth", tags=["auth-pages"])


@api_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        staff = authenticate_staff(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AccountInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return LoginResponse.model_validate(staff)


@pages_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html", {})
