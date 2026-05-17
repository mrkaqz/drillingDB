# Drilling Motor Output DB

A local-network web app that replaces an Excel/VBA workflow for tracking directional drilling motor output across BHA runs.

Drillers upload directional drilling slide sheets and BHA config files → the app parses them, computes motor output, and stores everything in SQLite → per-well and cross-well analytics with interactive Plotly charts.

**Version 0.5 · Released 2026-05-15**

---

## Features

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

---

## Quick Start

### Requirements

- Python 3.11+
- Windows (paths in `run.bat` use backslashes; the Python code is cross-platform)

### Run

```bat
cd "C:\path\to\drillingDB\app"
run.bat
```

`run.bat` will:
1. Create a virtualenv (`.venv`) if it doesn't exist
2. Install all dependencies from `requirements.txt`
3. Run `alembic upgrade head` to apply migrations
4. Start Uvicorn on `http://0.0.0.0:7000` with `--reload`

Open `http://localhost:7000` in a browser. Other machines on the same LAN can reach it at `http://<server-ip>:7000`.

### Manual start (after venv exists)

```bat
set PYTHONPATH=src
.venv\Scripts\uvicorn drilling_app.main:app --host 0.0.0.0 --port 7000 --reload --app-dir src
```

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
│   └── versions/0001_initial_schema.py
├── tests/
│   ├── conftest.py
│   └── test_parsers.py
└── src/drilling_app/
    ├── main.py                     FastAPI app entry point
    ├── config.py                   Paths, version, stand length default
    ├── db.py                       SQLAlchemy engine / session
    ├── models.py                   ORM models
    ├── schemas.py                  Pydantic schemas
    ├── parsers/
    │   ├── label_map.py            Synonym table (raw label → canonical key)
    │   ├── slide_sheet.py          Slide sheet parser → ParsedSlideSheet
    │   └── bha_config.py          BHAReport Final.xlsx parser → ParsedBhaConfig
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
        └── pages.py                HTML page routes (Jinja2 templates)
```

---

## Pages

| URL | Description |
|-----|-------------|
| `/` | Dashboard — BHA runs table with search, filter, and sort |
| `/import` | Single slide sheet import with auto-fill from file |
| `/batch-import` | Batch import from a server-side folder path |
| `/wells` | Wells list |
| `/wells/{id}` | Well detail + BHA runs; delete well or individual runs |
| `/bha-runs/{id}` | Run detail: motor output chart + table with ft/m unit toggle |
| `/compare` | Multi-run overlay chart |
| `/benchmarks` | Motor output stats grouped by bent angle / hole size / motor model |
| `/bha-configs` | BHA config library (browse, auto-imported from Final.xlsx) |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/bha-runs/preview-slide` | Parse slide header → JSON for form auto-fill |
| POST | `/api/bha-runs/preview-bha` | Parse BHA Final header → JSON for form auto-fill |
| POST | `/api/bha-runs/import` | Full single import (slide + optional BHA config) |
| PATCH | `/api/bha-runs/{id}` | Update motor bent deg / make / model / notes |
| DELETE | `/api/bha-runs/{id}` | Delete a BHA run and all child records |
| DELETE | `/api/bha-runs/wells/{id}` | Delete a well and all its runs |
| GET | `/api/bha-runs/{id}/export.xlsx` | Export one run to legacy Motor Output.xlsx |
| GET | `/api/bha-runs/export.xlsx?run_ids=1,2` | Export multiple runs |
| GET | `/api/batch/preview` | Scan folder, return pairing plan |
| POST | `/api/batch/import` | Import all pairs, move source files to `imported/` subfolder |

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

Tests reference xlsx fixture files from the parent folder. They skip gracefully if those files are absent.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | *(none — uses `app/`)* | Override data root (for Docker volume mounts). DB goes in `$DATA_DIR/db/`, uploads in `$DATA_DIR/uploads/` |

---

## Roadmap

- [ ] Phase 3: one-time backfill script for the legacy `Motor Output.xlsx` historical wide-format file
- [ ] Multi-well export UI trigger (`/export.xlsx?well_ids=...` endpoint exists, no button yet)
- [ ] NSSM Windows service setup for always-on LAN deployment
