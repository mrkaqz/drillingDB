# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Drilling Motor Output DB** — a local-network FastAPI + SQLite web app that replaces an Excel/VBA workflow for tracking directional drilling motor output across BHA runs. Drillers upload slide sheets and BHA config files; the app parses them, computes motor output, and provides cross-well analytics.

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

### Manual start (dev, after venv exists)
```bat
cd "C:\Users\RWongmalasit\Drilling Database\app"
set PYTHONPATH=src
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
Test fixtures reference xlsx files in `C:\Users\RWongmalasit\Drilling Database\` (the parent folder, not inside `app/`). Tests skip gracefully if those files are absent.

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
├── migrations/                    Alembic versions
│   └── versions/0001_initial_schema.py
├── tests/
│   ├── conftest.py                Test data paths (DATA_DIR points to parent of app/)
│   └── test_parsers.py            Parser + compute unit tests
└── src/drilling_app/
    ├── main.py                    FastAPI app, mounts all routers
    ├── schemas.py                 Pydantic request/response models (WellCreate, BhaRunCreate, etc.)
    ├── config.py                  Paths + DEFAULT_STAND_LENGTH_FT = 100.0
    ├── db.py                      SQLAlchemy engine / Session / Base
    ├── models.py                  ORM models (Well, BhaRun, BhaConfig, Survey, SlideInterval, MotorOutput)
    ├── parsers/
    │   ├── label_map.py           Synonym table: raw Excel labels → canonical field keys
    │   ├── slide_sheet.py         DOX / GYR / SLB Steering Sheet parser → ParsedSlideSheet
    │   └── bha_config.py          BHAReport Final.xlsx parser → ParsedBhaConfig
    ├── compute/
    │   ├── units.py               ft↔m, deg/100ft↔deg/30m↔deg/10m, PPG↔SG conversions
    │   └── motor_output.py        Interval arithmetic: DLS / slide_footage → motor_output_deg_per_ft
    ├── export/
    │   └── motor_output_xlsx.py   Legacy Motor Output.xlsx wide-format export
    ├── api/
    │   ├── bha_runs.py            /api/bha-runs/* (import, preview, export, delete)
    │   ├── batch_import.py        /api/batch/* (folder scan, batch import)
    │   └── analytics.py           /api/analytics/* (compare overlay data)
    └── web/
        └── pages.py               All HTML page routes (Jinja2 templates)
```

### Frontend stack
- **Tailwind CSS** (CDN), **Alpine.js** (CDN) for reactivity, **Plotly.js** (CDN) for charts
- No build step — all JS inline in templates or from CDN
- Forms use `x-data` Alpine components; file previews use `fetch()` to preview endpoints before form submit

---

## Key Data Flow

1. **Single import** (`/import`): user uploads slide sheet + optional BHA Final → `POST /api/bha-runs/import` → parse → compute → store → redirect to run detail
2. **Batch import** (`/batch-import`): user enters folder path → `GET /api/batch/preview` shows pairing plan → `POST /api/batch/import` imports all pairs → moves files to `{folder}/imported`
3. **File pairing (batch):** files grouped by the first `_`-delimited segment of the filename (e.g. `Jasmine D-38(DF)` from `Jasmine D-38(DF)_11.75in_BHA01_...xlsx`). BHA files are identified by `_Final` in the stem (case-insensitive).

---

## Parser — Critical Gotchas

### `_scan_header_block` lookahead = 2
The header scanner looks **up to 2 cells ahead** (not just 1) for the value after a label cell. GYR-format slide sheets have a blank column between label and value — lookahead 1 misses them.

### Well name derivation (in both `preview_slide` and `_import_one`)
Priority order:
1. `borehole` field — if it contains a space (compound name like `"Nong Yao A-43H(EJ)"`)
2. First `_`-segment of `bha_name` — if it contains a space (e.g. `"Jasmine A-39(AAA)"`)
3. `borehole` as-is (short code)
4. Raw `well_name` field (often a slot/platform ID like `"D6"` or `"Slot #07"` — not useful)

### Slide sheet format variants
| Format | Depth | DLS | Op Mode column | Label style |
|--------|-------|-----|----------------|-------------|
| DOX/SLB modern | ft | deg/100ft | varies (col 10–12) | full English |
| GYR (Jasmine/Borr Mist) | ft | deg/100ft | col 10 | same, but label-value gap = 2 cols |
| NTU SLB Steering Sheet | m | deg/10m | col 3 | abbreviated (`"S/N"`, `"Lead DD"`) |

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

## Pages & Routes

| URL | Description |
|-----|-------------|
| `/` | Dashboard — BHA runs table with search/filter/sort |
| `/import` | Single slide sheet import with auto-fill from file |
| `/batch-import` | Batch import from a server-side folder |
| `/wells` | Wells list |
| `/wells/{id}` | Well detail + BHA runs; has Delete Well + Delete Run buttons |
| `/bha-runs/{id}` | Run detail: motor output chart + table with unit toggle |
| `/compare` | Multi-run overlay chart |
| `/benchmarks` | Motor output stats grouped by bent angle / hole size / motor model |
| `/bha-configs` | BHA config library |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/bha-runs/preview-slide` | Parse slide header only → JSON for form auto-fill |
| POST | `/api/bha-runs/preview-bha` | Parse BHA Final header only → JSON for form auto-fill |
| POST | `/api/bha-runs/import` | Full single import |
| DELETE | `/api/bha-runs/wells/{id}` | Delete well + all child records |
| DELETE | `/api/bha-runs/{id}` | Delete single BHA run |
| GET | `/api/bha-runs/{id}/export.xlsx` | Export one run to legacy Motor Output.xlsx |
| GET | `/api/batch/preview` | Scan folder, return pairing plan |
| POST | `/api/batch/import` | Import all pairs in folder, move files to done folder |

---

## Pending / Next Steps

- **Phase 3 (legacy backfill):** one-time script to import the existing `Motor Output.xlsx` historical wide-format file into the DB
- **Export:** `GET /export.xlsx?well_ids=...` multi-well export exists but no UI trigger yet
- **Client rep fields** (`client_rep_primary/secondary`) are imported — consider whether to exclude like DD names
- **NSSM Windows service install** — not yet configured; currently run manually via `run.bat`
