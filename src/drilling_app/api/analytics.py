"""Analytics API: aggregations for benchmarks and comparisons."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth import require_login_api
from ..db import get_db
from ..models import BhaRun, MotorOutput, User, Well

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/compare")
def compare_runs(run_ids: str, db: Session = Depends(get_db), _: User = Depends(require_login_api)):
    """Return motor output series for multiple runs for chart overlay."""
    ids = [int(x) for x in run_ids.split(",") if x.strip()]
    result = []
    for rid in ids:
        run = db.query(BhaRun).filter(BhaRun.id == rid).first()
        if not run:
            continue
        rows = run.motor_outputs
        result.append({
            "run_id": rid,
            "label": f"{run.well.name} {run.bha_name or ''} {run.motor_bent_deg or ''}°",
            "motor_bent_deg": run.motor_bent_deg,
            "hole_size_in": run.hole_size_in,
            "motor_model": run.motor_model,
            "data": [
                {
                    "svy_md_ft": r.svy_md_ft,
                    "motor_output": r.motor_output_deg_per_ft,
                    "dls": r.dls_deg_per_100ft,
                    "slide_ft": r.slide_footage_ft,
                }
                for r in rows if r.motor_output_deg_per_ft is not None
            ],
        })
    return result


@router.get("/benchmarks")
def benchmarks(db: Session = Depends(get_db), _: User = Depends(require_login_api)):
    """Return per-BHA-config aggregated motor output stats."""
    rows = (
        db.query(
            BhaRun.motor_bent_deg,
            BhaRun.hole_size_in,
            BhaRun.motor_model,
            func.avg(MotorOutput.motor_output_deg_per_ft).label("avg_mo"),
            func.min(MotorOutput.motor_output_deg_per_ft).label("min_mo"),
            func.max(MotorOutput.motor_output_deg_per_ft).label("max_mo"),
            func.count(MotorOutput.id).label("n_intervals"),
        )
        .join(MotorOutput, MotorOutput.bha_run_id == BhaRun.id)
        .filter(MotorOutput.motor_output_deg_per_ft.isnot(None))
        .filter(MotorOutput.motor_output_deg_per_ft > 0)
        .group_by(BhaRun.motor_bent_deg, BhaRun.hole_size_in, BhaRun.motor_model)
        .all()
    )
    return [
        {
            "motor_bent_deg": r.motor_bent_deg,
            "hole_size_in": r.hole_size_in,
            "motor_model": r.motor_model,
            "avg_motor_output": round(r.avg_mo, 5) if r.avg_mo else None,
            "min_motor_output": round(r.min_mo, 5) if r.min_mo else None,
            "max_motor_output": round(r.max_mo, 5) if r.max_mo else None,
            "n_intervals": r.n_intervals,
        }
        for r in rows
    ]
