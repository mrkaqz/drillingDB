# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Drilling Motor Output DB** — a local-network FastAPI + SQLite web app that replaces an Excel/VBA workflow for tracking directional drilling motor output across BHA runs. Drillers upload slide sheets and BHA config files; the app parses them, computes motor output, and provides cross-well analytics.

- **Version:** 1.3 (released 2026-05-18)
- **Server:** `http://0.0.0.0:7000` (LAN accessible)
- **Database:** `drilling.db` (SQLite, in `app/`)
- **Uploaded files archived in:** `app/uploads/`

---

## Commands

### Start the app
```bat
cd "C:\Users\RWongmalasit\Drilling Database\app"
run.bat
```
`run.bat` creates the venv if missing, installs requirements, runs `alembic upgrade head`, then starts uvicorn with `--reload`.

On first start with an empty DB, a default admin account is seeded automatically:
- **username:** `admin` · **password:** `admin1234`
- Change the password immediately via `/admin/users → Reset Password`.

### Manual start (dev, after venv exists)
```bat
cd "C:\Users\RWongmalasit\Drilling Database\app"
set PYTHONPATH=src
set SESSION_SECRET_KEY=some-long-random-string
.venv\Scripts\uvicorn drilling_app.main:app --host 0.0.0.0 --port 7000 --reload --app-dir src
```

### Install dependencies
```bat
.venv\Scripts\pip install -r requirements.txt
```

### Database migrations
```bat
.venv\Scripts\alembic upgrade head
# If tables already exist from Base.metadata.create_all and migration fails:
.venv\Scripts\alembic stamp 0001
```

### Run tests
```bat
cd "C:\Users\RWongmalasit\Drilling Database\app"
.venv\Scripts\pytest tests/ -v
```
- `test_app.py` — CI-safe smoke tests; no external files needed, always run
- `test_parsers.py` — full parser + compute tests; skip automatically when xlsx fixture files are absent

### Run a quick parse test
```bat
.venv\Scripts\python -c "
import sys; sys.path.insert(0, 'src')
from drilling_app.parsers.slide_sheet import parse
r = parse(r'uploads\<filename>.xlsx')
print(r.header, len(r.surveys), len(r.intervals))
"
```

---

## Architecture

```
app/
├── run.bat                        Launcher
├── requirements.txt
├── drilling.db                    SQLite database
├── uploads/                       Archived source xlsx files
├── exports/                       Generated xlsx export files
├── migrations/
│   ├── versions/0001_initial_schema.py
│   └── versions/0002_add_users.py
├── tests/
│   ├── conftest.py
│   ├── test_app.py                CI-safe smoke tests (no fixture files needed)
│   └── test_parsers.py            Parser + compute tests (skipped in CI)
└── src/drilling_app/
    ├── main.py                    FastAPI app entry point; seeds default admin on first start
    ├── config.py                  Paths, version, SESSION_SECRET_KEY, DEFAULT_STAND_LENGTH_FT
    ├── auth.py                    Password hashing, session deps, role guards
    ├── db.py                      SQLAlchemy engine / Session / Base
    ├── models.py                  ORM models (User, Well, BhaRun, BhaConfig, Survey, SlideInterval, MotorOutput)
    ├── schemas.py                 Pydantic request/response models
    ├── create_first_user.py       CLI seed script (alternative to auto-seed)
    ├── parsers/
    │   ├── label_map.py           Synonym table: raw Excel labels → canonical field keys
    │   ├── slide_sheet.py         Slide sheet parser → ParsedSlideSheet
    │   └── bha_config.py          BHAReport Final.xlsx parser → ParsedBhaConfig
    ├── compute/
    │   ├── units.py               ft↔m, deg/100ft↔deg/30m↔deg/10m, PPG↔SG conversions
    │   └── motor_output.py        Interval arithmetic: DLS / slide_footage → motor_output_deg_per_ft
    ├── export/
    │   └── motor_output_xlsx.py   Legacy Motor Output.xlsx wide-format export
    ├── api/
    │   ├── bha_runs.py            /api/bha-runs/* (import, preview, export, delete)
    │   ├── batch_import.py        /api/batch/* (folder scan, batch import, upload)
    │   └── analytics.py           /api/analytics/* (compare overlay data)
    └── web/
        ├── pages.py               HTML page routes (Jinja2 templates)
        ├── auth_routes.py         /login · /logout
        └── admin.py               /admin/users — user management (admin only)
```

### Frontend stack
- **Tailwind CSS** (CDN), **Alpine.js** (CDN) for reactivity, **Plotly.js** (CDN) for charts
- No build step — all JS inline in templates or from CDN
- Forms use `x-data` Alpine components; file previews use `fetch()` to preview endpoints before form submit

---

## Authentication & Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access + manage users at `/admin/users` |
| `readwrite` | View all data + import / delete wells & runs |
| `readonly` | View only — import and delete actions hidden and API-blocked |

- Session cookies signed with `SESSION_SECRET_KEY` env var (warning logged if default is used)
- HTML routes use `require_login` / `require_readwrite` / `require_admin` deps that raise `LoginRequired` / `PermissionDenied` custom exceptions → caught by `@app.exception_handler` → redirect or 403 page
- API routes use `require_login_api` / `require_readwrite_api` deps that raise `HTTPException(401/403)` directly
- Admin cannot deactivate, delete, or demote their own account (self-lockout prevention)
- Default admin seeded in `main.py` `_seed_default_admin()` when `users` table is empty

---

## Key Data Flow

1. **Single import** (`/import`): user uploads slide sheet + optional BHA Final → `POST /api/bha-runs/import` → **duplicate check by `source_filename`** → parse → compute → store → redirect to run detail
2. **Batch import** (`/batch-import`): user enters folder path or uploads files → preview pairing plan → import all pairs → **duplicate filenames skipped** → originals moved to `{folder}/imported`
3. **File pairing (batch):** files grouped by the first `_`-delimited segment of the filename (e.g. `Nong Yao A-45H` from `Nong Yao A-45H_12.25in_BHA01_...xlsx`). BHA files identified by `_Final` in stem (case-insensitive).

---

## Duplicate Import Protection

Both import paths check `BhaRun.source_filename` before creating any records:

- **Single import:** returns HTTP 409 with run # and well name if filename already exists. Error shown in red banner on `/import`.
- **Batch import:** `_import_one` returns `status="skipped"` with "Already imported as run #X — skipped." The row shows yellow in the results table.

No partial writes occur — the check runs before any DB insert or file save.

---

## Parser — Critical Gotchas

### `_scan_header_block` lookahead = 2
The header scanner looks **up to 2 cells ahead** (not just 1) for the value after a label cell. Some slide sheet formats have a blank column between label and value — lookahead 1 misses them.

### Well name derivation (in both `preview_slide` and `_import_one`)
Priority order:
1. `borehole` field — if it contains a space (compound name like `"Nong Yao A-43H(EJ)"`)
2. First `_`-segment of `bha_name` — if it contains a space (e.g. `"Jasmine A-39(AAA)"`)
3. First `_`-segment of filename — if it contains a space (e.g. `"Jasmine D-40H(DB-AN)"`)
   Preferred over a short-code `borehole` like `"D-40H(DBAN)"` that has no space.
4. `borehole` as-is (short code — no space)
5. Raw `well_name` field (often a slot/platform ID like `"D6"` — not useful as well name)

### Slide sheet format variants
| Format | Depth | DLS | Op Mode column | Label style |
|--------|-------|-----|----------------|-------------|
| Standard field-unit (modern) | ft | deg/100ft | varies (col 10–12) | Full English |
| Field-unit with wide label gap | ft | deg/100ft | col 10 | Same, label-value gap = 2 cols |
| Metric / older steering sheet | m | deg/10m | col 3 | Abbreviated (`S/N`, `Lead DD`) |

All formats handled by column-name lookup (not fixed indices) via `label_map.py`.

### Canonical storage units
All values stored in feet (depth), deg/100ft (DLS), PPG (mud weight), inches (hole/casing size). Display unit toggled client-side in Alpine.js — never re-stored.

---

## Deliberately Excluded Fields

These fields are parsed but **intentionally not written to the DB**:

| Field | Reason |
|-------|--------|
| `dd_primary`, `dd_secondary` | Personnel privacy — DD names not stored |
| `designed_by` (BhaConfig) | Not displayed or stored |

The DB columns still exist (no migration needed) but are always set to `None` on import.

---

## Database Schema

```
users            id, username, hashed_password, role, is_active, created_at
wells            id, name, field, borehole, rig, client, notes
bha_configs      id, name, hole_size_in, motor_make, motor_model, motor_bent_deg,
                 bend_to_bit_ft, stabilizers_json, sensor_offsets_json, nozzles_json
bha_runs         id, well_id, bha_config_id, bha_name, hole_size_in, motor_bent_deg,
                 motor_make, motor_model, depth_in/out_ft, date_in/td/out,
                 stand_length_ft, source_filename, ...
surveys          id, bha_run_id, sequence, svy_md_ft, incl_deg, azmth_deg, dls_deg_per_100ft
slide_intervals  id, bha_run_id, sequence, md_from_ft, md_to_ft, mode, ...
motor_outputs    id, bha_run_id, sequence, svy_md_ft, dls_deg_per_100ft,
                 slide_footage_ft, motor_output_deg_per_ft, full_stand_deg
```

---

## Pages & Routes

| URL | Auth | Description |
|-----|------|-------------|
| `/login` | — | Login page |
| `/` | any | Dashboard — BHA runs table with search/filter/sort |
| `/import` | readwrite+ | Single slide sheet import with auto-fill |
| `/batch-import` | readwrite+ | Batch import from folder or file upload |
| `/wells` | any | Wells list |
| `/wells/{id}` | any | Well detail + BHA runs; delete buttons (readwrite+) |
| `/bha-runs/{id}` | any | Run detail: motor output chart + table with unit toggle |
| `/compare` | any | Multi-run overlay chart |
| `/benchmarks` | any | Motor output stats grouped by bent angle / hole size / motor model |
| `/bha-configs` | any | BHA config library |
| `/admin/users` | admin | Create / manage user accounts and roles |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/bha-runs/preview-slide` | any | Parse slide header → JSON for form auto-fill |
| POST | `/api/bha-runs/preview-bha` | any | Parse BHA Final header → JSON for form auto-fill |
| POST | `/api/bha-runs/import` | readwrite+ | Full single import; 409 if filename already imported |
| PATCH | `/api/bha-runs/{id}` | readwrite+ | Update motor bent deg / make / model / notes |
| DELETE | `/api/bha-runs/{id}` | readwrite+ | Delete single BHA run |
| DELETE | `/api/bha-runs/wells/{id}` | readwrite+ | Delete well + all child records |
| GET | `/api/bha-runs/{id}/export.xlsx` | any | Export one run to legacy Motor Output.xlsx |
| GET | `/api/bha-runs/export.xlsx?run_ids=1,2` | any | Export multiple runs |
| GET | `/api/batch/preview` | any | Scan folder, return pairing plan |
| POST | `/api/batch/import` | readwrite+ | Import all pairs in folder; duplicate filenames skipped |
| POST | `/api/batch/upload` | readwrite+ | Upload files directly and import all pairs |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_SECRET_KEY` | `change-me-in-production` | Signs session cookies. **Set before exposing on a network.** Changing it invalidates all active sessions. |
| `DATA_DIR` | *(none — uses `app/`)* | Override data root (Docker volume mounts). DB in `$DATA_DIR/db/`, uploads in `$DATA_DIR/uploads/`. |

---

## Pending / Next Steps

- **Phase 3 (legacy backfill):** one-time script to import the existing `Motor Output.xlsx` historical wide-format file into the DB
- **Self-service password change** for non-admin users
- **Multi-well export UI trigger** (`/export.xlsx?well_ids=...` endpoint exists, no button yet)
- **NSSM Windows service install** — not yet configured; currently run manually via `run.bat`
