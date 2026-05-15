"""Batch import API — scan a local folder, pair slide sheets with BHA configs, import all."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR, DEFAULT_STAND_LENGTH_FT
from ..db import get_db
from ..models import BhaRun, BhaConfig, MotorOutput, Survey, SlideInterval, Well
from ..parsers.slide_sheet import parse as parse_slide
from ..parsers.bha_config import parse as parse_bha
from ..compute.motor_output import compute_motor_outputs

router = APIRouter(prefix="/api/batch", tags=["batch"])


def _is_bha_file(path: Path) -> bool:
    return "_final" in path.stem.lower()


def _well_key(path: Path) -> str:
    """Extract the well identifier prefix — everything before the first '_'."""
    return path.stem.split("_")[0].strip()


def _scan_folder(folder: Path) -> list[dict]:
    """Return a list of {key, slide, bha} dicts grouped by well prefix."""
    if not folder.exists() or not folder.is_dir():
        return []
    xlsx_files = [
        f for f in folder.iterdir()
        if f.suffix.lower() in (".xlsx", ".xls") and f.is_file()
    ]
    groups: dict[str, dict] = {}
    for f in xlsx_files:
        key = _well_key(f)
        if key not in groups:
            groups[key] = {"key": key, "slide": None, "bha": None}
        if _is_bha_file(f):
            groups[key]["bha"] = f
        else:
            groups[key]["slide"] = f
    return sorted(groups.values(), key=lambda g: g["key"])


@router.get("/preview")
def preview_batch(folder: str):
    """Scan folder and return pairing plan without importing anything."""
    groups = _scan_folder(Path(folder))
    result = []
    for g in groups:
        result.append({
            "key":        g["key"],
            "slide_file": g["slide"].name if g["slide"] else None,
            "bha_file":   g["bha"].name if g["bha"] else None,
            "can_import": g["slide"] is not None,
        })
    return {"folder": folder, "groups": result}


def _get_or_create_well(db: Session, name: str, **kwargs) -> Well:
    well = db.query(Well).filter(Well.name == name).first()
    if not well:
        well = Well(name=name, **kwargs)
        db.add(well)
        db.flush()
    return well


def _import_one(
    slide_path: Path,
    bha_path: Optional[Path],
    stand_length_ft: float,
    db: Session,
) -> dict:
    """Import a single slide+BHA pair. Returns a status dict."""
    # Parse slide sheet
    try:
        parsed = parse_slide(str(slide_path))
    except Exception as e:
        return {"status": "error", "message": f"Slide sheet parse error: {e}"}
    parsed.source_filename = slide_path.name

    # Validate: must be a motor slide sheet (has both rotation and sliding intervals)
    has_sliding = any("slide" in iv.mode.lower() for iv in parsed.intervals)
    if not has_sliding:
        return {
            "status": "skipped",
            "message": "Not a motor slide sheet — no sliding intervals found. Skipped.",
        }

    # Parse BHA config if provided
    motor_bent_deg: Optional[float] = None
    motor_make: Optional[str] = None
    motor_model: Optional[str] = None
    bha_config_id: Optional[int] = None

    if bha_path and bha_path.exists():
        try:
            parsed_bha = parse_bha(str(bha_path))
        except Exception as e:
            return {"status": "error", "message": f"BHA config parse error: {e}"}

        motor_bent_deg = parsed_bha.motor_bent_deg
        motor_make = parsed_bha.motor.make if parsed_bha.motor else None
        motor_model = parsed_bha.motor.model if parsed_bha.motor else None

        cfg_name = parsed_bha.bha_name or bha_path.stem
        cfg = db.query(BhaConfig).filter(BhaConfig.name == cfg_name).first()
        if not cfg:
            cfg = BhaConfig(name=cfg_name)
            db.add(cfg)
        cfg.source_filename = bha_path.name
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

    # Derive well name from parsed header
    h = parsed.header

    def _h(k): return h.get(k)

    borehole = str(_h("borehole") or "").strip()
    bha_name_val = str(_h("bha_name") or "").strip()
    bha_first = bha_name_val.split("_")[0].strip() if bha_name_val else ""
    well_name_raw = str(_h("well_name") or "").strip()

    if " " in borehole:
        well_name = borehole
    elif " " in bha_first:
        well_name = bha_first
    elif borehole:
        well_name = borehole
    elif well_name_raw:
        well_name = well_name_raw
    else:
        well_name = slide_path.stem.split("_")[0].strip()

    well = _get_or_create_well(
        db, well_name,
        field=_h("field"),
        borehole=borehole or None,
        rig=_h("rig"),
        client=_h("client"),
    )

    # Create BHA run
    run = BhaRun(
        well_id=well.id,
        bha_config_id=bha_config_id,
        bha_name=_h("bha_name"),
        bit_run_number=_h("bit_run_number"),
        source_unit_system=parsed.source_unit_system,
        hole_size_in=_h("hole_size_in"),
        casing_shoe_ft=_h("casing_shoe"),
        mud_type=_h("mud_type"),
        end_mw_ppg=_h("end_mw_ppg"),
        motor_bent_deg=motor_bent_deg,
        motor_make=motor_make,
        motor_model=motor_model,
        depth_in_ft=_h("depth_in"),
        depth_out_ft=_h("depth_out"),
        incl_in_deg=_h("incl_in_deg"),
        incl_out_deg=_h("incl_out_deg"),
        azimuth_in_deg=_h("azimuth_in_deg"),
        azimuth_out_deg=_h("azimuth_out_deg"),
        date_in=_h("date_in"),
        date_td=_h("date_td"),
        date_out=_h("date_out"),
        drilling_hours=_h("drilling_hours"),
        pumping_hours=_h("pumping_hours"),
        brt_hours=_h("brt_hours"),
        dd_primary=_h("dd_primary"),
        dd_secondary=_h("dd_secondary"),
        client_rep_primary=_h("client_rep_primary"),
        client_rep_secondary=_h("client_rep_secondary"),
        bit_serial=_h("bit_serial"),
        bit_type=_h("bit_type"),
        bit_manuf=_h("bit_manuf"),
        bit_iadc=_h("bit_iadc"),
        bit_jets=_h("bit_jets"),
        bit_tfa_in2=_h("bit_tfa_in2"),
        stand_length_ft=stand_length_ft,
        source_filename=slide_path.name,
        notes=None,
    )
    db.add(run)
    db.flush()

    for s in parsed.surveys:
        db.add(Survey(
            bha_run_id=run.id,
            sequence=s.sequence,
            svy_md_ft=s.svy_md_ft,
            incl_deg=s.incl_deg,
            azmth_deg=s.azmth_deg,
            dls_deg_per_100ft=s.dls_deg_per_100ft,
        ))

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
    return {
        "status": "ok",
        "well_name": well_name,
        "run_id": run.id,
        "well_id": well.id,
        "message": f"Imported as run #{run.id}",
    }


@router.post("/import")
def run_batch_import(
    folder: str = Form(...),
    done_folder: str = Form(None),
    stand_length_ft: float = Form(DEFAULT_STAND_LENGTH_FT),
    db: Session = Depends(get_db),
):
    """Import all slide+BHA pairs in the folder. Moves completed files to done_folder."""
    folder_path = Path(folder)
    if not folder_path.exists() or not folder_path.is_dir():
        return {"error": f"Folder not found: {folder}"}

    # Default done folder: subfolder called "imported" inside the source folder
    done_path = Path(done_folder) if done_folder and done_folder.strip() else folder_path / "imported"
    done_path.mkdir(parents=True, exist_ok=True)

    groups = _scan_folder(folder_path)
    results = []

    for g in groups:
        slide: Optional[Path] = g["slide"]
        bha: Optional[Path] = g["bha"]

        if slide is None:
            # BHA-only group — skip (nothing to import without a slide sheet)
            results.append({
                "key": g["key"],
                "slide_file": None,
                "bha_file": bha.name if bha else None,
                "status": "skipped",
                "message": "No slide sheet found — skipped.",
            })
            continue

        # Copy files to UPLOAD_DIR before parsing (keeps uploads archive consistent)
        slide_dest = UPLOAD_DIR / slide.name
        shutil.copy2(slide, slide_dest)
        bha_dest = (UPLOAD_DIR / bha.name) if bha else None
        if bha and bha_dest:
            shutil.copy2(bha, bha_dest)

        result = _import_one(slide_dest, bha_dest if bha else None, stand_length_ft, db)
        result["key"] = g["key"]
        result["slide_file"] = slide.name
        result["bha_file"] = bha.name if bha else None
        results.append(result)

        # Move originals to done folder on success
        if result["status"] == "ok":
            shutil.move(str(slide), done_path / slide.name)
            if bha:
                shutil.move(str(bha), done_path / bha.name)

    return {"results": results, "done_folder": str(done_path)}


@router.post("/upload")
async def batch_upload_import(
    files: List[UploadFile] = File(...),
    stand_length_ft: float = Form(DEFAULT_STAND_LENGTH_FT),
    db: Session = Depends(get_db),
):
    """Accept uploaded xlsx files, pair them, and import all slide+BHA pairs."""
    # Save uploaded files to a temp subdir so _scan_folder can pair them
    batch_dir = UPLOAD_DIR / f"batch_{uuid4().hex[:8]}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    try:
        for f in files:
            dest = batch_dir / (f.filename or f.filename)
            dest.write_bytes(await f.read())

        groups = _scan_folder(batch_dir)
        results = []
        ok_count = skipped_count = error_count = 0

        for g in groups:
            slide: Optional[Path] = g["slide"]
            bha: Optional[Path] = g["bha"]

            if slide is None:
                results.append({
                    "key": g["key"],
                    "slide_file": None,
                    "bha_file": bha.name if bha else None,
                    "status": "skipped",
                    "message": "No slide sheet found — skipped.",
                })
                skipped_count += 1
                continue

            # Archive copies to UPLOAD_DIR root (consistent with folder-path flow)
            slide_dest = UPLOAD_DIR / slide.name
            shutil.copy2(slide, slide_dest)
            bha_dest: Optional[Path] = None
            if bha:
                bha_dest = UPLOAD_DIR / bha.name
                shutil.copy2(bha, bha_dest)

            result = _import_one(slide_dest, bha_dest, stand_length_ft, db)
            result["key"] = g["key"]
            result["slide_file"] = slide.name
            result["bha_file"] = bha.name if bha else None
            results.append(result)

            if result["status"] == "ok":
                ok_count += 1
            else:
                error_count += 1

    finally:
        shutil.rmtree(batch_dir, ignore_errors=True)

    return {
        "results": results,
        "total": len(results),
        "ok": ok_count,
        "errors": error_count,
        "skipped": skipped_count,
    }
