from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # app/

# DATA_DIR can be overridden via env var (used in Docker to point at a mounted volume)
_data_env = os.getenv("DATA_DIR")
DATA_DIR = Path(_data_env) if _data_env else BASE_DIR

DB_PATH = DATA_DIR / "drilling.db"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_STAND_LENGTH_FT: float = 100.0

VERSION = "0.5"
RELEASE_DATE = "2026-05-15"
