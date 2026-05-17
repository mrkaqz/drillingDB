"""Authentication utilities and FastAPI dependency functions."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Custom exceptions (caught by exception handlers in main.py) ──────────────

class LoginRequired(Exception):
    """Raised by web-page dependencies when no valid session exists."""


class PermissionDenied(Exception):
    """Raised by web-page dependencies when the user lacks the required role."""


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Internal session lookup ───────────────────────────────────────────────────

def _get_session_user(request: Request, db: Session) -> Optional[User]:
    """Return the logged-in User or None (does not raise)."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return (
        db.query(User)
        .filter(User.id == user_id, User.is_active == True)  # noqa: E712
        .first()
    )


# ── Web (HTML) dependencies — raise custom exceptions → handled in main.py ───

def require_login(request: Request, db: Session = Depends(get_db)) -> User:
    """Any authenticated active user. Redirects to /login on failure."""
    user = _get_session_user(request, db)
    if user is None:
        raise LoginRequired()
    return user


def require_readwrite(request: Request, db: Session = Depends(get_db)) -> User:
    """Role 'admin' or 'readwrite'. Redirects to /login or shows 403."""
    user = _get_session_user(request, db)
    if user is None:
        raise LoginRequired()
    if user.role not in ("admin", "readwrite"):
        raise PermissionDenied()
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Role 'admin' only. Redirects to /login or shows 403."""
    user = _get_session_user(request, db)
    if user is None:
        raise LoginRequired()
    if user.role != "admin":
        raise PermissionDenied()
    return user


# ── API dependencies — return HTTP status codes directly ─────────────────────

def require_login_api(request: Request, db: Session = Depends(get_db)) -> User:
    """For JSON API routes — returns 401 when unauthenticated."""
    user = _get_session_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_readwrite_api(request: Request, db: Session = Depends(get_db)) -> User:
    """For JSON API routes — 401 if not logged in, 403 if wrong role."""
    user = _get_session_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.role not in ("admin", "readwrite"):
        raise HTTPException(status_code=403, detail="Read/write or admin role required")
    return user
