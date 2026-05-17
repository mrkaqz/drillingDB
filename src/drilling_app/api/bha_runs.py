"""API routes for BHA runs: import, list, get, export."""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import openpyxl
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_login_api, require_readwrite_api
from ..config import UPLOAD_DIR, DEFAULT_STAND_LENGTH_FT
from ..db import get_db
from ..models import BhaRun, BhaConfig, MotorOutput, Survey, SlideInterval, User, Well
from ..parsers.slide_sheet import parse as parse_slide, _scan_header_block, _safe_float
from ..parsers.bha_config import parse as parse_bha
from ..compute.motor_output import compute_motor_outputs
from ..export.motor_output_xlsx import build_export

router = APIRouter(prefix="/api/bha-runs", tags=["bha-runs"])


@router.post("/preview-slide")
async def preview_slide(slide_file: UploadFile = File(...), _: User = Depends(require_login_api)):
    """Parse slide sheet header only — returns well name, field, BHA name for form auto-fill."""
    content = await slide_file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.worksheets[0]
        raw = _scan_header_block(ws, 4, 15)
        def _s(k): return str(raw[k]).strip() if raw.get(k) else None

        # Derive best well name. In GYR-format sheets "Well" = platform/slot
        # (e.g. "D6", "Slot #07") and "Borehole" holds the real designation.
        # Priority:
        #   1. Borehole — if it contains a space it's a compound name ("Nong Yao A-43H(EJ)")
        #   2. First "_"-segment of BHA Run name — often "Jasmine A-39(AAA)"
        #   3. Borehole as-is (short code like "A39(AAA)")
        #   4. Raw "Well" value as last resort
        borehole = _s("borehole") or ""
        bha_first = (_s("bha_name") or "").split("_")[0].strip()
        if " " in borehole:
            well_name = borehole
        elif " " in bha_first:
            well_name = bha_first
        elif borehole:
            well_name = borehole
        else:
            well_name = _s("well_name")

        return {
            "well_name":    well_name,
            "field":        _s("field"),
            "rig":          _s("rig"),
            "client":       _s("client"),
            "bha_name":     _s("bha_name"),
            "hole_size_in": _safe_float(raw.get("hole_size_in")),
        }
    except Exception:
        return {}


@router.post("/preview-bha")
async def preview_bha(bha_file: UploadFile = File(...), _: User = Depends(require_login_api)):
    """Parse BHA config header — returns well name, motor bent angle, motor model for form auto-fill."""
    content = await bha_file.read()
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            parsed = parse_bha(tmp_path)
        finally:
            os.unlink(tmp_path)
        return {
            "well_name":      parsed.well_name or parsed.borehole_name or None,
            "field":          parsed.field_name or None,
            "motor_bent_deg": parsed.motor_bent_deg,
            "motor_make":     parsed.motor.make if parsed.motor else None,
            "motor_model":    parsed.motor.model if parsed.motor else None,
        }
    except Exception:
        return {}


@router.delete("/wells/{well_id}")
def delete_well(well_id: int, db: Session = Depends(get_db), _: User = Depends(require_readwrite_api)):
    """Delete a well and all its BHA runs, surveys, intervals, and motor outputs."""
    well = db.query(Well).filter(Well.id == well_id).first()
    if not well:
        raise HTTPException(404, "Well not found")
    db.delete(well)
    db.commit()
    return {"deleted": well_id}


@router.delete("/{run_id}")
def delete_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(require_readwrite_api)):
    """Delete a single BHA run and all its child records."""
    run = db.query(BhaRun).filter(BhaRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "BHA run not found")
    well_id = run.well_id
    db.delete(run)
    db.commit()
    return {"deleted": run_id, "well_id": well_id}


class BhaRunPatch(BaseModel):
    motor_bent_deg: Optional[float] = None
    motor_make: Optional[str] = None
    motor_model: Optional[str] = None
    notes: Optional[str] = None


@router.patch("/{run_id}")
def update_run(run_id: int, patch: BhaRunPatch, db: Session = Depends(get_db), _: User = Depends(require_readwrite_api)):
    """Partially update editable fields on a BHA run."""
    run = db.query(BhaRun).filter(BhaRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(run, field, value)
    db.commit()
    return {"ok": True}


def _get_or_create_well(db: Session, name: str, **kwargs) -> Well:
    well = db.query(Well).filter(Well.name == name).first()
    if not well:
        well = Well(name=name, **kwargs)
        db.add(well)
        db.flush()
    return well


@router.post("/import")
async def import_bha_run(  # noqa: PLR0913
    slide_file: UploadFile = File(...),
    bha_file: Optional[UploadFile] = File(None),
    well_name: str = Form(...),
    field: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    rig: Optional[str] = Form(None),
    client: Optional[str] = Form(None),
    motor_bent_deg: Optional[float] = Form(None),
    motor_make: Optional[str] = Form(None),
    motor_model: Optional[str] = Form(None),
    stand_length_ft: float = Form(DEFAULT_STAND_LENGTH_FT),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_readwrite_api),
):
    # Save uploaded slide file
    slide_path = UPLOAD_DIR / slide_file.filename
    with slide_path.open("wb") as f:
        shutil.copyfileobj(slide_file.file, f)

    # Parse slide sheet
    try:
        parsed = parse_slide(str(slide_path))
    except Exception as e:
        raise HTTPException(400, f"Slide sheet parse error: {e}")
    parsed.source_filename = slide_file.filename

    # Parse BHA config if provided
    bha_config_id: Optional[int] = None
    if bha_file and bha_file.filename:
        bha_path = UPLOAD_DIR / bha_file.filename
        with bha_path.open("wb") as f:
            shutil.copyfileobj(bha_file.file, f)
        try:
            parsed_bha = parse_bha(str(bha_path))
        except Exception as e:
            raise HTTPException(400, f"BHA config parse error: {e}")
        # Auto-fill from BHA if not provided by user
        if motor_bent_deg is None and parsed_bha.motor_bent_deg is not None:
            motor_bent_deg = parsed_bha.motor_bent_deg
        if motor_make is None and parsed_bha.motor and parsed_bha.motor.make:
            motor_make = parsed_bha.motor.make
        if motor_model is None and parsed_bha.motor and parsed_bha.motor.model:
            motor_model = parsed_bha.motor.model
        # Upsert BHA config
        cfg_name = parsed_bha.bha_name or Path(bha_file.filename).stem
        cfg = db.query(BhaConfig).filter(BhaConfig.name == cfg_name).first()
        if not cfg:
            cfg = BhaConfig(name=cfg_name)
            db.add(cfg)
        cfg.source_filename = bha_file.filename
        cfg.source_unit_system = parsed_bha.source_unit_system
        cfg.hole_size_in = parsed_bha.hole_size_in
        cfg.motor_bent_deg = parsed_bha.motor_bent_deg
        cfg.bend_to_bit_ft = parsed_bha.bend_to_bit_ft
        if parsed_bha.motor:
            cfg.motor_make = parsed_bha.motor.make
            cfg.motor_model = parsed_bha.motor.model
            cfg.motor_serial = parsed_bha.motor.serial
            cfg.motor_od_in = parsed_bha.motor.od_in
            cfg.motor_length_ft = parsed_bha.motor.length_ft

        cfg.bha_date = parsed_bha.bha_date
        cfg.components_json = json.dumps([c.__dict__ for c in parsed_bha.components])
        cfg.stabilizers_json = json.dumps([s.__dict__ for s in parsed_bha.stabilizers])
        cfg.sensor_offsets_json = json.dumps(parsed_bha.sensor_offsets_ft)
        cfg.nozzles_json = json.dumps([n.__dict__ for n in parsed_bha.nozzles])
        db.flush()
        bha_config_id = cfg.id

    # Get or create well
    h = parsed.header
    well = _get_or_create_well(
        db, well_name,
        field=field or h.get("field"),
        borehole=h.get("borehole") or h.get("well_name"),
        location=location or h.get("location"),
        rig=rig or h.get("rig"),
        client=client or h.get("client"),
    )

    # Create BHA run
    run = BhaRun(
        well_id=well.id,
        bha_config_id=bha_config_id,
        bha_name=h.get("bha_name"),
        bit_run_number=h.get("bit_run_number"),
        source_unit_system=parsed.source_unit_system,
        hole_size_in=h.get("hole_size_in"),
        casing_shoe_ft=h.get("casing_shoe"),
        mud_type=h.get("mud_type"),
        end_mw_ppg=h.get("end_mw_ppg"),
        motor_bent_deg=motor_bent_deg,
        motor_make=motor_make,
        motor_model=motor_model,
        depth_in_ft=h.get("depth_in"),
        depth_out_ft=h.get("depth_out"),
        incl_in_deg=h.get("incl_in_deg"),
        incl_out_deg=h.get("incl_out_deg"),
        azimuth_in_deg=h.get("azimuth_in_deg"),
        azimuth_out_deg=h.get("azimuth_out_deg"),
        date_in=h.get("date_in"),
        date_td=h.get("date_td"),
        date_out=h.get("date_out"),
        drilling_hours=h.get("drilling_hours"),
        pumping_hours=h.get("pumping_hours"),
        brt_hours=h.get("brt_hours"),
        dd_primary=None,
        dd_secondary=None,
        client_rep_primary=h.get("client_rep_primary"),
        client_rep_secondary=h.get("client_rep_secondary"),
        bit_serial=h.get("bit_serial"),
        bit_type=h.get("bit_type"),
        bit_manuf=h.get("bit_manuf"),
        bit_iadc=h.get("bit_iadc"),
        bit_jets=h.get("bit_jets"),
        bit_tfa_in2=h.get("bit_tfa_in2"),
        stand_length_ft=stand_length_ft,
        source_filename=parsed.source_filename,
        notes=notes,
    )
    db.add(run)
    db.flush()

    # Store surveys
    for s in parsed.surveys:
        db.add(Survey(
            bha_run_id=run.id,
            sequence=s.sequence,
            svy_md_ft=s.svy_md_ft,
            incl_deg=s.incl_deg,
            azmth_deg=s.azmth_deg,
            dls_deg_per_100ft=s.dls_deg_per_100ft,
        ))

    # Store intervals
    for iv in parsed.intervals:
        db.add(SlideInterval(
            bha_run_id=run.id,
            sequence=iv.sequence,
            md_from_ft=iv.md_from_ft,
            md_to_ft=iv.md_to_ft,
            mode=iv.mode,
            course_ft=iv.course_ft,
            calc_rop=iv.calc_rop,
            tf_mode=iv.tf_mode,
            tf_angle=iv.tf_angle,
            start_time=iv.start_time,
            end_time=iv.end_time,
        ))

    # Compute and store motor output
    mo_rows = compute_motor_outputs(parsed.surveys, parsed.intervals, stand_length_ft)
    for mo in mo_rows:
        db.add(MotorOutput(
            bha_run_id=run.id,
            sequence=mo.sequence,
            svy_md_ft=mo.svy_md_ft,
            incl_deg=mo.incl_deg,
            azmth_deg=mo.azmth_deg,
            dls_deg_per_100ft=mo.dls_deg_per_100ft,
            slide_footage_ft=mo.slide_footage_ft,
            motor_output_deg_per_ft=mo.motor_output_deg_per_ft,
            full_stand_deg=mo.full_stand_deg,
        ))

    db.commit()
    return {"id": run.id, "well_id": well.id}


@router.get("/{run_id}/export.xlsx")
def export_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(require_login_api)):
    run = db.query(BhaRun).filter(BhaRun.id == run_id).first()
    if not run:
        raise HTTPException(404)
    data = build_export([run])
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="motor_output_{run_id}.xlsx"'},
    )


@router.get("/export.xlsx")
def export_multiple(run_ids: str, db: Session = Depends(get_db), _: User = Depends(require_login_api)):
    ids = [int(x) for x in run_ids.split(",") if x.strip()]
    runs = db.query(BhaRun).filter(BhaRun.id.in_(ids)).all()
    data = build_export(runs)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="motor_output.xlsx"'},
    )
