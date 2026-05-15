"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import STATIC_DIR
from .db import Base, engine
from .api import bha_runs as bha_runs_api
from .api import analytics as analytics_api
from .api import batch_import as batch_import_api
from .web import pages as web_pages

# Create all tables on startup (Alembic handles migrations; this is a fallback for fresh installs)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Drilling Motor Output DB", version="1.0.0")

# Static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Routers
app.include_router(bha_runs_api.router)
app.include_router(analytics_api.router)
app.include_router(batch_import_api.router)
app.include_router(web_pages.router)
