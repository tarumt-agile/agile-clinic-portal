from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

# auth/router.py
from agile_ci_demo.core.templates import templates

router = APIRouter(prefix="/auth", tags=["auth"])
# templates = Jinja2Templates(directory="templates")


@router.get("/login")
def login_page(request: Request):
    # return templates.TemplateResponse("auth/login.html", {"request": request})
    templates.TemplateResponse(request, "auth/login.html", {"request": request})   # NEW
