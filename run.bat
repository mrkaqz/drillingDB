@echo off
cd /d "%~dp0"

:: Install dependencies if venv doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    echo Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt
)

:: Apply database migrations
echo Applying database migrations...
.venv\Scripts\alembic upgrade head

:: Start the server
echo Starting Drilling Motor Output DB on http://0.0.0.0:8000
.venv\Scripts\uvicorn drilling_app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir src
