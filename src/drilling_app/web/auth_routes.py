"""Login / logout routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import verify_password
from ..config import TEMPLATE_DIR, VERSION, RELEASE_DATE
from ..db import get_db
from ..models import User

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.globals.update(app_version=VERSION, app_release_date=RELEASE_DATE)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    # Already logged in → go to dashboard
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
