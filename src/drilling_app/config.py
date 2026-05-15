from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # app/
DB_PATH = BASE_DIR / "drilling.db"
UPLOAD_DIR = BASE_DIR / "uploads"
EXPORT_DIR = BASE_DIR / "exports"
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

DEFAULT_STAND_LENGTH_FT: float = 100.0
