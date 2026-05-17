"""Admin user-management routes — only accessible to users with role='admin'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin
from ..config import TEMPLATE_DIR, VERSION, RELEASE_DATE
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.globals.update(app_version=VERSION, app_release_date=RELEASE_DATE)

VALID_ROLES = ("admin", "readwrite", "readonly")


@router.get("/users", response_class=HTMLResponse)
def users_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.username).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "current_user": current_user,
        "users": users,
        "error": None,
        "success": None,
    })


@router.post("/users", response_class=HTMLResponse)
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("readwrite"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.username).all()
    error = None
    success = None

    if role not in VALID_ROLES:
        error = f"Invalid role '{role}'."
    elif db.query(User).filter(User.username == username).first():
        error = f"Username '{username}' is already taken."
    elif len(password) < 4:
        error = "Password must be at least 4 characters."
    else:
        new_user = User(
            username=username,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        users = db.query(User).order_by(User.username).all()
        success = f"User '{username}' created."

    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "current_user": current_user,
        "users": users,
        "error": error,
        "success": success,
    })


@router.post("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.id != current_user.id:  # prevent self-lockout
        user.is_active = False
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/activate")
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_active = True
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user and len(new_password) >= 4:
        user.hashed_password = hash_password(new_password)
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/set-role")
def set_role(
    user_id: int,
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if role in VALID_ROLES:
        user = db.query(User).filter(User.id == user_id).first()
        if user and not (user.id == current_user.id and role != "admin"):
            # Prevent admin from demoting themselves
            user.role = role
            db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.id != current_user.id:  # prevent self-delete
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)
