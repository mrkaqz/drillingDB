"""FastAPI application entry point."""
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .auth import LoginRequired, PermissionDenied
from .config import STATIC_DIR, TEMPLATE_DIR, SESSION_SECRET_KEY, VERSION, RELEASE_DATE
from .db import Base, engine
from .api import bha_runs as bha_runs_api
from .api import analytics as analytics_api
from .api import batch_import as batch_import_api
from .web import pages as web_pages
from .web import auth_routes
from .web import admin as admin_web

# Create all tables on startup (Alembic handles migrations; this is a fallback for fresh installs)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Drilling Motor Output DB", version=VERSION)

# Session middleware (must be added before routers)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# Static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Exception handlers for auth custom exceptions
_templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
_templates.env.globals.update(app_version=VERSION, app_release_date=RELEASE_DATE)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired):
    return RedirectResponse(url="/login", status_code=302)


@app.exception_handler(PermissionDenied)
async def permission_denied_handler(request: Request, exc: PermissionDenied):
    return _templates.TemplateResponse(
        "403.html",
        {"request": request, "current_user": None},
        status_code=403,
    )


# Routers
app.include_router(auth_routes.router)
app.include_router(admin_web.router)
app.include_router(bha_runs_api.router)
app.include_router(analytics_api.router)
app.include_router(batch_import_api.router)
app.include_router(web_pages.router)
