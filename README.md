# Drilling Motor Output DB

A local-network web app that replaces an Excel/VBA workflow for tracking directional drilling motor output across BHA runs.

Drillers upload directional drilling slide sheets and BHA config files → the app parses them, computes motor output, and stores everything in SQLite → per-well and cross-well analytics with interactive Plotly charts.

**Version 1.3 · Released 2026-05-18**

---

## Features

- **Login & role-based access** — username/password login with three roles: `admin`, `readwrite`, `readonly`
- **Admin user management** — admin UI to create, deactivate, reset passwords, and assign roles
- **Single & batch import** — drag-drop one slide sheet at a time, or point the app at a folder to import all pairs in one click
- **Auto-fill from file** — well name, field, rig, hole size, motor bent angle, and motor model are extracted from the xlsx without manual entry
- **Format-tolerant parser** — handles multiple slide sheet layouts (field-unit and metric variants); columns are located by header text, not fixed indices
- **Unit-aware** — source files in field units (ft, PPG, deg/100ft) or metric (m, SG, deg/10m) are normalised to canonical storage; display unit toggled client-side
- **Motor output computation** — interval arithmetic replicates the Excel/VBA `Process` macro: DLS ÷ sliding footage per survey interval → deg/ft and full-stand deg
- **Cross-well compare** — overlay motor output vs MD for multiple runs on one chart
- **Benchmarks** — average/median/P90 motor output grouped by bent angle, hole size, and motor model
- **BHA config library** — reusable BHA templates parsed from `*_Final.xlsx` BHA report files
- **Export** — download any run or selection as a legacy-format `Motor Output.xlsx` (8-columns-per-well layout)

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Web framework | FastAPI |
| Server | Uvicorn (run via `run.bat`) |
| Templating | Jinja2 |
| Frontend | Tailwind CSS · Alpine.js · Plotly.js (all CDN, no build step) |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Database | SQLite (`drilling.db`) |
| Excel parsing / export | openpyxl |
| Validation | Pydantic v2 |
| Auth | passlib[bcrypt] · itsdangerous (session cookies) |

---

## Quick Start

### Requirements

- Python 3.11+
- Windows (paths in `run.bat` use backslashes; the Python code is cross-platform)

### First-time setup

```bat
cd "C:\path\to\drillingDB\app"
run.bat
```

`run.bat` will:
1. Create a virtualenv (`.venv`) if it doesn't exist
2. Install all dependencies from `requirements.txt`
3. Run `alembic upgrade head` to apply migrations (creates the `users` table)
4. Start Uvicorn on `http://0.0.0.0:7000` with `--reload`

On first start, if no users exist in the database, a default admin account is created automatically:

| Username | Password |
|----------|----------|
| `admin` | `admin1234` |

> **Change the default password immediately** after first login via **Users → Reset Password**.

Open `http://localhost:7000` in a browser and log in. Other machines on the same LAN can reach it at `http://<server-ip>:7000`.

Go to **Users** (top-right nav, admin only) to add further accounts and assign roles.

### Manual start (after venv exists)

```bat
set PYTHONPATH=src
set SESSION_SECRET_KEY=some-long-random-string
.venv\Scripts\uvicorn drilling_app.main:app --host 0.0.0.0 --port 7000 --reload --app-dir src
```

---

## Authentication & Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access + manage users at `/admin/users` |
| `readwrite` | View all data + import / delete wells & runs |
| `readonly` | View only — import and delete actions are hidden and blocked |

- Session cookies are signed with `SESSION_SECRET_KEY` (set via environment variable; a warning is logged if the default is used)
- Only admins can create accounts — there is no self-service signup
- Admin cannot deactivate, delete, or demote their own account

---

## Project Layout

```
app/
├── run.bat                         Launcher script
├── requirements.txt
├── alembic.ini
├── drilling.db                     SQLite database (gitignored)
├── uploads/                        Archived source xlsx files
├── exports/                        Generated Motor Output.xlsx exports
├── migrations/
│   ├── versions/0001_initial_schema.py
│   └── versions/0002_add_users.py
├── tests/
│   ├── conftest.py
│   ├── test_app.py                 CI-safe smoke tests (no fixture files needed)
│   └── test_parsers.py             Parser tests (skipped in CI — require local xlsx files)
└── src/drilling_app/
    ├── main.py                     FastAPI app entry point
    ├── config.py                   Paths, version, session secret key
    ├── auth.py                     Password hashing, session deps, role guards
    ├── db.py                       SQLAlchemy engine / session
    ├── models.py                   ORM models (incl. User)
    ├── schemas.py                  Pydantic schemas
    ├── create_first_user.py        CLI seed script for first admin account
    ├── parsers/
    │   ├── label_map.py            Synonym table (raw label → canonical key)
    │   ├── slide_sheet.py          Slide sheet parser → ParsedSlideSheet
    │   └── bha_config.py           BHAReport Final.xlsx parser → ParsedBhaConfig
    ├── compute/
    │   ├── units.py                Unit conversions (ft↔m, deg/100ft↔deg/10m, PPG↔SG)
    │   └── motor_output.py         Motor output interval arithmetic
    ├── export/
    │   └── motor_output_xlsx.py    Legacy wide-format xlsx export
    ├── api/
    │   ├── bha_runs.py             /api/bha-runs/* (import, preview, export, delete)
    │   ├── batch_import.py         /api/batch/* (folder scan, batch import)
    │   └── analytics.py            /api/analytics/* (compare overlay data)
    └── web/
        ├── pages.py                HTML page routes (Jinja2 templates)
        ├── auth_routes.py          /login · /logout
        └── admin.py                /admin/users — user management (admin only)
```

---

## Pages

| URL | Auth required | Description |
|-----|---------------|-------------|
| `/login` | — | Login page |
| `/` | any | Dashboard — BHA runs table with search, filter, and sort |
| `/import` | readwrite+ | Single slide sheet import with auto-fill from file |
| `/batch-import` | readwrite+ | Batch import from a server-side folder path |
| `/wells` | any | Wells list |
| `/wells/{id}` | any | Well detail + BHA runs; delete well or individual runs |
| `/bha-runs/{id}` | any | Run detail: motor output chart + table with ft/m unit toggle |
| `/compare` | any | Multi-run overlay chart |
| `/benchmarks` | any | Motor output stats grouped by bent angle / hole size / motor model |
| `/bha-configs` | any | BHA config library (browse, auto-imported from Final.xlsx) |
| `/admin/users` | admin | Create / manage user accounts and roles |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/bha-runs/preview-slide` | any | Parse slide header → JSON for form auto-fill |
| POST | `/api/bha-runs/preview-bha` | any | Parse BHA Final header → JSON for form auto-fill |
| POST | `/api/bha-runs/import` | readwrite+ | Full single import (slide + optional BHA config) |
| PATCH | `/api/bha-runs/{id}` | readwrite+ | Update motor bent deg / make / model / notes |
| DELETE | `/api/bha-runs/{id}` | readwrite+ | Delete a BHA run and all child records |
| DELETE | `/api/bha-runs/wells/{id}` | readwrite+ | Delete a well and all its runs |
| GET | `/api/bha-runs/{id}/export.xlsx` | any | Export one run to legacy Motor Output.xlsx |
| GET | `/api/bha-runs/export.xlsx?run_ids=1,2` | any | Export multiple runs |
| GET | `/api/batch/preview` | any | Scan folder, return pairing plan |
| POST | `/api/batch/import` | readwrite+ | Import all pairs, move source files to `imported/` subfolder |

---

## Slide Sheet Format Support

The parser uses header-text column lookup (not fixed column indices) and handles multiple slide sheet layouts from different software exporters:

| Variant | Depth | DLS | Op Mode column | Label style |
|---------|-------|-----|----------------|-------------|
| Standard field-unit (modern) | ft | deg/100ft | varies (col 10–12) | Full English |
| Field-unit with wide label gap | ft | deg/100ft | col 10 | Same, label–value gap = 2 cols |
| Metric / older steering sheet | m | deg/10m | col 3 | Abbreviated (`S/N`, `Lead DD`) |

All values are converted to canonical storage units on import: **feet** (depth), **deg/100ft** (DLS), **PPG** (mud weight), **inches** (hole/casing size).

---

## Database Schema

```
users            id, username, hashed_password, role, is_active, created_at
wells            id, name, field, borehole, rig, client, notes
bha_configs      id, name, hole_size_in, motor_make, motor_model, motor_bent_deg,
                 bend_to_bit_ft, stabilizers_json, sensor_offsets_json, nozzles_json
bha_runs         id, well_id, bha_config_id, bha_name, hole_size_in, motor_bent_deg,
                 motor_make, motor_model, depth_in/out_ft, date_in/td/out, stand_length_ft, ...
surveys          id, bha_run_id, sequence, svy_md_ft, incl_deg, azmth_deg, dls_deg_per_100ft
slide_intervals  id, bha_run_id, sequence, md_from_ft, md_to_ft, mode, ...
motor_outputs    id, bha_run_id, sequence, svy_md_ft, dls_deg_per_100ft,
                 slide_footage_ft, motor_output_deg_per_ft, full_stand_deg
```

---

## Running Tests

```bat
cd "C:\path\to\drillingDB\app"
.venv\Scripts\pytest tests/ -v
```

- **`test_app.py`** — CI-safe smoke tests; run everywhere, no external files needed
- **`test_parsers.py`** — full parser + compute tests; skipped automatically when the xlsx fixture files are not present (e.g. CI)

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_SECRET_KEY` | `change-me-in-production` | Signs session cookies. **Set this before exposing the app on a network.** Changing it invalidates all active sessions. |
| `DATA_DIR` | *(none — uses `app/`)* | Override data root (for Docker volume mounts). DB goes in `$DATA_DIR/db/`, uploads in `$DATA_DIR/uploads/` |

---

## Roadmap

- [ ] Phase 3: one-time backfill script for the legacy `Motor Output.xlsx` historical wide-format file
- [ ] Multi-well export UI trigger (`/export.xlsx?well_ids=...` endpoint exists, no button yet)
- [ ] NSSM Windows service setup for always-on LAN deployment
- [ ] Self-service password change for non-admin users
