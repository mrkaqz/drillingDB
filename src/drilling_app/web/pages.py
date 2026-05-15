"""Web page routes — return full HTML pages."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from ..config import TEMPLATE_DIR
from ..db import get_db
from ..models import Well, BhaRun, BhaConfig, MotorOutput

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    n_wells = db.query(Well).count()
    n_runs = db.query(BhaRun).count()
    all_runs = (
        db.query(BhaRun)
        .options(joinedload(BhaRun.well))
        .order_by(desc(BhaRun.imported_at))
        .all()
    )
    runs_json = [
        {
            "id": r.id,
            "well_id": r.well_id,
            "well_name": r.well.name if r.well else "",
            "bha_name": r.bha_name or "",
            "depth_in_ft": r.depth_in_ft,
            "depth_out_ft": r.depth_out_ft,
            "motor_bent_deg": r.motor_bent_deg,
            "hole_size_in": r.hole_size_in,
            "imported_at": r.imported_at.strftime("%Y-%m-%d") if r.imported_at else "",
        }
        for r in all_runs
    ]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "n_wells": n_wells,
        "n_runs": n_runs,
        "runs_json": runs_json,
    })


@router.get("/import", response_class=HTMLResponse)
def import_page(request: Request, db: Session = Depends(get_db)):
    bha_configs = db.query(BhaConfig).order_by(BhaConfig.name).all()
    return templates.TemplateResponse("import.html", {
        "request": request,
        "bha_configs": bha_configs,
    })


@router.get("/wells", response_class=HTMLResponse)
def wells_list(request: Request, db: Session = Depends(get_db)):
    wells = db.query(Well).order_by(Well.name).all()
    wells_json = [
        {
            "id": w.id,
            "name": w.name,
            "field": w.field or "",
            "borehole": w.borehole or "",
            "rig": w.rig or "",
            "client": w.client or "",
            "run_count": len(w.bha_runs),
        }
        for w in wells
    ]
    return templates.TemplateResponse("wells.html", {
        "request": request,
        "wells_json": wells_json,
    })


@router.get("/wells/{well_id}", response_class=HTMLResponse)
def well_detail(request: Request, well_id: int, db: Session = Depends(get_db)):
    well = db.query(Well).filter(Well.id == well_id).first()
    if not well:
        raise HTTPException(404)
    runs = (
        db.query(BhaRun)
        .filter(BhaRun.well_id == well_id)
        .order_by(desc(BhaRun.imported_at))
        .all()
    )
    return templates.TemplateResponse("well_detail.html", {
        "request": request,
        "well": well,
        "runs": runs,
    })


@router.get("/bha-runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(BhaRun)
        .options(joinedload(BhaRun.well), joinedload(BhaRun.motor_outputs), joinedload(BhaRun.slide_intervals))
        .filter(BhaRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(404)

    def _mo_dict(m):
        return {
            "svy_md_ft": m.svy_md_ft,
            "incl_deg": m.incl_deg,
            "azmth_deg": m.azmth_deg,
            "dls_deg_per_100ft": m.dls_deg_per_100ft,
            "slide_footage_ft": m.slide_footage_ft,
            "motor_output_deg_per_ft": m.motor_output_deg_per_ft,
            "full_stand_deg": m.full_stand_deg,
        }

    def _iv_dict(iv):
        return {
            "md_from_ft": iv.md_from_ft,
            "md_to_ft": iv.md_to_ft,
            "mode": iv.mode,
        }

    return templates.TemplateResponse("bha_run_detail.html", {
        "request": request,
        "run": run,
        "motor_outputs": run.motor_outputs,
        "intervals": run.slide_intervals,
        "motor_outputs_json": [_mo_dict(m) for m in run.motor_outputs],
        "intervals_json": [_iv_dict(iv) for iv in run.slide_intervals],
    })


@router.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request, db: Session = Depends(get_db)):
    runs = (
        db.query(BhaRun)
        .options(joinedload(BhaRun.well))
        .order_by(desc(BhaRun.imported_at))
        .all()
    )
    return templates.TemplateResponse("compare.html", {
        "request": request,
        "runs": runs,
    })


@router.get("/benchmarks", response_class=HTMLResponse)
def benchmarks_page(request: Request, db: Session = Depends(get_db)):
    from collections import defaultdict
    import statistics

    # Fetch all motor output rows with their run's config info
    mos = (
        db.query(MotorOutput, BhaRun)
        .join(BhaRun, MotorOutput.bha_run_id == BhaRun.id)
        .filter(MotorOutput.motor_output_deg_per_ft.isnot(None))
        .filter(MotorOutput.motor_output_deg_per_ft > 0)
        .all()
    )

    # Group by (bent_deg, hole_size, motor_model)
    groups: dict = defaultdict(list)
    run_ids_per_group: dict = defaultdict(set)
    for mo, run in mos:
        key = (run.motor_bent_deg, run.hole_size_in, run.motor_model)
        groups[key].append((mo.motor_output_deg_per_ft, mo.full_stand_deg, run.stand_length_ft))
        run_ids_per_group[key].add(run.id)

    rows = []
    for (bent, size, model), vals in sorted(groups.items(), key=lambda x: (x[0][0] or 0, x[0][1] or 0)):
        mo_vals = sorted(v[0] for v in vals)
        fs_vals = [v[1] for v in vals if v[1] is not None]
        n = len(mo_vals)
        median_mo = statistics.median(mo_vals) if mo_vals else None
        p90_mo = mo_vals[int(n * 0.9)] if n >= 2 else (mo_vals[-1] if mo_vals else None)
        rows.append({
            "motor_bent_deg": bent,
            "hole_size_in": size,
            "motor_model": model,
            "run_count": len(run_ids_per_group[(bent, size, model)]),
            "avg_motor_output": sum(mo_vals) / n if n else None,
            "median_motor_output": median_mo,
            "p90_motor_output": p90_mo,
            "avg_full_stand": sum(fs_vals) / len(fs_vals) if fs_vals else None,
        })

    n_runs = sum(r["run_count"] for r in rows)
    bent_angles = sorted({r["motor_bent_deg"] for r in rows if r["motor_bent_deg"] is not None})
    hole_sizes = sorted({r["hole_size_in"] for r in rows if r["hole_size_in"] is not None})

    return templates.TemplateResponse("benchmarks.html", {
        "request": request,
        "rows": rows,
        "n_configs": len(rows),
        "n_runs": n_runs,
        "bent_angles": bent_angles,
        "hole_sizes": hole_sizes,
    })


@router.get("/batch-import", response_class=HTMLResponse)
def batch_import_page(request: Request):
    default_folder = r"C:\Users\RWongmalasit\Drilling Database\batch import"
    return templates.TemplateResponse("batch_import.html", {
        "request": request,
        "default_folder": default_folder,
    })


@router.get("/bha-configs", response_class=HTMLResponse)
def bha_configs_page(request: Request, db: Session = Depends(get_db)):
    import json as _json
    configs = db.query(BhaConfig).order_by(BhaConfig.name).all()

    def _parse_json(s):
        if not s:
            return None
        try:
            return _json.loads(s)
        except Exception:
            return None

    cfg_data = []
    for cfg in configs:
        cfg_data.append({
            "obj": cfg,
            "sensor_offsets": _parse_json(cfg.sensor_offsets_json),
            "stabilizers": _parse_json(cfg.stabilizers_json),
            "nozzles": _parse_json(cfg.nozzles_json),
        })

    return templates.TemplateResponse("bha_configs.html", {
        "request": request,
        "cfg_data": cfg_data,
    })
