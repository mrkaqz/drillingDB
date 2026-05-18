from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # app/

# DATA_DIR can be overridden via env var (used in Docker to point at a mounted volume)
_data_env = os.getenv("DATA_DIR")
DATA_DIR = Path(_data_env) if _data_env else BASE_DIR

# When DATA_DIR is set (Docker), DB lives in db/ so it can have its own volume mount.
# Without DATA_DIR (local dev), DB stays at app/drilling.db as before.
DB_DIR = DATA_DIR / "db" if _data_env else DATA_DIR
DB_PATH = DB_DIR / "drilling.db"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

DB_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_STAND_LENGTH_FT: float = 100.0

VERSION = "1.2"
RELEASE_DATE = "2026-05-18"

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-in-production")
if SESSION_SECRET_KEY == "change-me-in-production":
    import warnings
    warnings.warn(
        "SESSION_SECRET_KEY is not set — using the insecure default. "
        "Set the SESSION_SECRET_KEY environment variable before exposing this app on a network.",
        stacklevel=1,
    )
