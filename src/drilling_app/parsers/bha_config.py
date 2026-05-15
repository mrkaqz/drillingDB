"""Parser for SLB BHAReport Final.xlsx files.

Single-sheet ('BHAReport') format with stable layout:
- Rows 3-5: run header
- Rows 7-54: components table (2 rows per component)
- Rows 55-59: totals
- Rows 61-65: mud properties
- Rows 67-76: sensor offsets, stabilizer summary, nozzle summary
- Rows 77-79: bend summary (authoritative motor bent angle)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import openpyxl
from dateutil import parser as dateutil_parser

from ..compute.units import depth_to_ft, mw_to_ppg, detect_depth_unit, detect_mw_unit, M_TO_FT


@dataclass
class BhaComponent:
    sequence: int
    description: str
    manufacturer: str
    serial_number: str
    od_in: Optional[float]
    max_od_in: Optional[float]
    id_in: Optional[float]
    length: Optional[float]  # in feet (canonical)
    cum_length: Optional[float]  # in feet


@dataclass
class StabilizerSpec:
    mid_pt_to_bit_ft: float
    blade_od_in: Optional[float]
    blade_length_ft: Optional[float]


@dataclass
class NozzleSpec:
    component: str
    count_x_id: Optional[str]
    tfa_in2: Optional[float]


@dataclass
class MotorSpec:
    make: str
    model: str
    serial: str
    od_in: Optional[float]
    length_ft: Optional[float]
    description: str


@dataclass
class ParsedBhaConfig:
    field_name: str
    structure_name: str
    well_name: str
    borehole_name: str
    bha_name: str
    hole_size_in: Optional[float]
    depth_in_ft: Optional[float]
    depth_out_ft: Optional[float]
    source_unit_system: str  # "field" | "metric"
    components: list[BhaComponent]
    motor: Optional[MotorSpec]
    motor_bent_deg: Optional[float]
    bend_to_bit_ft: Optional[float]
    stabilizers: list[StabilizerSpec]
    sensor_offsets_ft: dict[str, float]
    nozzles: list[NozzleSpec]
    mud_weight_ppg: Optional[float]
    mud_type: Optional[str]
    designed_by: Optional[str]
    bha_date: Optional[date]
    source_filename: str


def _cv(ws, row: int, col: int):
    v = ws.cell(row=row, column=col).value
    if v is None:
        return None
    if hasattr(v, "text"):
        return None
    return v


def _sf(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ss(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _find_value_after_label(ws, target_label: str, search_rows: range, label_cols: list[int], value_offset: int = 2) -> Any:
    """Search for a label cell and return the value from a fixed column offset."""
    tl = target_label.strip().lower()
    for r in search_rows:
        for lc in label_cols:
            v = _cv(ws, r, lc)
            if v is not None and str(v).strip().lower() == tl:
                return _cv(ws, r, lc + value_offset)
    return None


def _find_label_row(ws, target_label: str, search_rows: range, col: int) -> Optional[int]:
    tl = target_label.strip().lower()
    for r in search_rows:
        v = _cv(ws, r, col)
        if v is not None and str(v).strip().lower() == tl:
            return r
    return None


def parse(filepath: str) -> ParsedBhaConfig:
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb["BHAReport"]

    # --- Rows 3-5: run header ---
    # Col 3=label, Col 5=value | Col 7=label, Col 9=value | Col 12=label, Col 14=value

    def hdr(label: str) -> Any:
        return _find_value_after_label(ws, label, range(3, 6), [3, 7, 12], value_offset=2)

    field_name = _ss(hdr("field name") or hdr("field"))
    structure_name = _ss(hdr("structure name"))
    well_name = _ss(hdr("well name") or hdr("well"))
    borehole_name = _ss(hdr("borehole name") or hdr("borehole"))
    bha_name = _ss(hdr("bha name") or hdr("bha run"))

    hole_size_raw = _cv(ws, 3, 14)  # Hole Size → col 14
    hole_size_in = _sf(hole_size_raw)

    # Detect units from depth label
    depth_in_label = ""
    for r in range(3, 6):
        for lc in [3, 7, 12]:
            v = _cv(ws, r, lc)
            if v and "depth in" in str(v).lower():
                depth_in_label = str(v)
                break

    depth_unit = detect_depth_unit(depth_in_label)
    source_unit_system = "metric" if depth_unit == "m" else "field"

    depth_in_raw = _sf(hdr("depth in (ft)") or hdr("depth in (m)") or hdr("depth in"))
    depth_out_raw = _sf(hdr("depth out (ft)") or hdr("depth out (m)") or hdr("depth out"))
    depth_in_ft = depth_to_ft(depth_in_raw, depth_unit) if depth_in_raw is not None else None
    depth_out_ft = depth_to_ft(depth_out_raw, depth_unit) if depth_out_raw is not None else None

    # --- Components table (rows 7 onwards) ---
    # Header row = 7-8 (two-row header). Components start at row 9.
    # Component number is in col 3. Each component spans 2 rows.
    # Find total-length row to know where table ends.
    total_len_row = None
    for r in range(50, 70):
        v = _cv(ws, r, 12)
        if v and "total length" in str(v).lower():
            total_len_row = r
            break
    table_end = (total_len_row - 1) if total_len_row else 54

    components: list[BhaComponent] = []
    r = 9
    while r <= table_end:
        num_raw = _cv(ws, r, 3)
        if num_raw is None or not str(num_raw).strip().isdigit():
            r += 1
            continue
        seq = int(str(num_raw).strip())
        desc = _ss(_cv(ws, r, 4))
        manuf = _ss(_cv(ws, r, 5))
        serial = _ss(_cv(ws, r, 6))
        od = _sf(_cv(ws, r, 7))          # OD top row
        max_od = _sf(_cv(ws, r, 8))
        id_val = _sf(_cv(ws, r + 1, 7)) if r + 1 <= table_end else None  # ID bottom row
        length_raw = _sf(_cv(ws, r, 13))
        cum_len_raw = _sf(_cv(ws, r, 14))
        length_ft = depth_to_ft(length_raw, depth_unit) if length_raw is not None else None
        cum_len_ft = depth_to_ft(cum_len_raw, depth_unit) if cum_len_raw is not None else None
        components.append(BhaComponent(
            sequence=seq,
            description=desc,
            manufacturer=manuf,
            serial_number=serial,
            od_in=od,
            max_od_in=max_od,
            id_in=id_val,
            length=length_ft,
            cum_length=cum_len_ft,
        ))
        r += 2

    # --- Motor identification ---
    motor: Optional[MotorSpec] = None
    motor_keywords = ("motor", "powerpak", "powerdrive", "mud motor", "directional motor")
    for comp in components:
        if any(kw in comp.description.lower() for kw in motor_keywords):
            make_model = comp.manufacturer
            # Try to extract model code (pattern: letters+digits like A825M7840XP, A962M5640)
            model_match = re.search(r'[A-Z][A-Z0-9]{4,}', make_model)
            motor_model = model_match.group(0) if model_match else make_model
            motor = MotorSpec(
                make=make_model,
                model=motor_model,
                serial=comp.serial_number,
                od_in=comp.max_od_in,
                length_ft=comp.length,
                description=comp.description,
            )
            break

    # --- Bend Summary (rows 77-79, col 7) ---
    motor_bent_deg: Optional[float] = None
    bend_to_bit_ft: Optional[float] = None
    for r in range(75, 85):
        v = _cv(ws, r, 7)
        if v and "bend angle" in str(v).lower():
            # Value is in the next row, same column
            motor_bent_deg = _sf(_cv(ws, r + 1, 7))
            bend_raw = _sf(_cv(ws, r + 1, 9))
            bend_to_bit_ft = depth_to_ft(bend_raw, depth_unit) if bend_raw is not None else None
            break

    # --- Stabilizer Summary (rows ~67-76, cols 7-10) ---
    stabilizers: list[StabilizerSpec] = []
    for r in range(65, 80):
        v = _cv(ws, r, 7)
        if v is None:
            continue
        mid_pt = _sf(v)
        if mid_pt is not None:
            blade_od = _sf(_cv(ws, r, 9))
            blade_len_raw = _sf(_cv(ws, r, 10))
            blade_len_ft = depth_to_ft(blade_len_raw, depth_unit) if blade_len_raw is not None else None
            stabilizers.append(StabilizerSpec(
                mid_pt_to_bit_ft=depth_to_ft(mid_pt, depth_unit),
                blade_od_in=blade_od,
                blade_length_ft=blade_len_ft,
            ))

    # --- Sensor offsets (rows ~67-70, cols 4-5) ---
    sensor_offsets_ft: dict[str, float] = {}
    sensor_labels = ("d&i", "gwd d&i", "mwd d+i", "mwd d&i", "gwd", "mwd")
    for r in range(65, 75):
        lbl = _ss(_cv(ws, r, 4)).lower()
        val = _sf(_cv(ws, r, 5))
        if any(sl in lbl for sl in sensor_labels) and val is not None:
            key = lbl.upper().replace(" ", "_").replace("&", "").replace("+", "")
            sensor_offsets_ft[key] = depth_to_ft(val, depth_unit)

    # --- Nozzle Summary (cols 12-15) ---
    nozzles: list[NozzleSpec] = []
    for r in range(65, 80):
        comp_lbl = _ss(_cv(ws, r, 12))
        count_id = _ss(_cv(ws, r, 14))
        tfa = _sf(_cv(ws, r, 15))
        if comp_lbl and (count_id or tfa):
            nozzles.append(NozzleSpec(component=comp_lbl, count_x_id=count_id or None, tfa_in2=tfa))

    # --- Mud properties ---
    mud_weight_ppg: Optional[float] = None
    mud_type: Optional[str] = None
    for r in range(60, 70):
        lbl = _ss(_cv(ws, r, 12)).lower()
        val = _cv(ws, r, 15)
        if "mud weight" in lbl:
            mw_unit = detect_mw_unit(lbl)
            fv = _sf(val)
            mud_weight_ppg = mw_to_ppg(fv, mw_unit) if fv is not None else None
        elif "mud type" in lbl:
            mud_type = _ss(val) or None

    # --- Sign-off ---
    designed_by: Optional[str] = None
    bha_date: Optional[date] = None
    for r in range(76, 85):
        lbl = _ss(_cv(ws, r, 12)).lower()
        val = _cv(ws, r, 14)
        if "designed by" in lbl:
            designed_by = _ss(val) or None
        elif "date" == lbl:
            if isinstance(val, (datetime, date)):
                bha_date = val.date() if isinstance(val, datetime) else val
            elif val:
                try:
                    bha_date = dateutil_parser.parse(str(val)).date()
                except Exception:
                    pass

    return ParsedBhaConfig(
        field_name=field_name,
        structure_name=structure_name,
        well_name=well_name,
        borehole_name=borehole_name,
        bha_name=bha_name,
        hole_size_in=hole_size_in,
        depth_in_ft=depth_in_ft,
        depth_out_ft=depth_out_ft,
        source_unit_system=source_unit_system,
        components=components,
        motor=motor,
        motor_bent_deg=motor_bent_deg,
        bend_to_bit_ft=bend_to_bit_ft,
        stabilizers=stabilizers,
        sensor_offsets_ft=sensor_offsets_ft,
        nozzles=nozzles,
        mud_weight_ppg=mud_weight_ppg,
        mud_type=mud_type,
        designed_by=designed_by,
        bha_date=bha_date,
        source_filename="",
    )
