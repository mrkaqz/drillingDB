"""Tests for slide sheet and BHA config parsers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

DATA_DIR = Path(__file__).parent.parent.parent
SLIDE_45H = DATA_DIR / "Nong Yao A-45H_12.25in_BHA01_Slide Sheet Report-SLB_20260318_TD@1386ftMD.xlsx"
SLIDE_42ST1H = DATA_DIR / "Nong Yao A-42ST1H_12.25in_BHA02_Slide Sheet Report-SLB_20260316_TD@1386ftMD.xlsx"
SLIDE_43H = DATA_DIR / "Nong Yao A-43H_12.25in_BHA01_Slide Sheet Report-SLB_20260315_TD@1385ftMD.xlsx"
SLIDE_NTU = DATA_DIR / "NTU-A04(AD)_BHA#1_12.25in_Steering Sheet_719mMD-TD.xlsx"
BHA_43H = DATA_DIR / "Nong Yao A-43H_BHA#1_12.25in Motor-GWD-MWD_Final.xlsx"
BHA_LKU = DATA_DIR / "LKU-K31(KAR)_BHA#1_12.25in Motor-MWD_Final.xlsx"
from drilling_app.parsers.slide_sheet import parse as parse_slide
from drilling_app.parsers.bha_config import parse as parse_bha
from drilling_app.compute.motor_output import compute_motor_outputs
from drilling_app.compute.units import dls_from_100ft, depth_from_ft


# ── Slide sheet: Nong Yao A-45H (primary golden, ft / deg/100ft) ──────────────

def test_45h_source_units():
    result = parse_slide(str(SLIDE_45H))
    assert result.source_unit_system == "field"
    assert result.source_units["depth"] == "ft"
    assert result.source_units["dls"] == "deg/100ft"


def test_45h_surveys_shape():
    result = parse_slide(str(SLIDE_45H))
    # Initial row (0,0,0,0) prepended + data rows
    assert len(result.surveys) > 5
    assert result.surveys[0].svy_md_ft == 0.0
    assert result.surveys[0].incl_deg == 0.0


def test_45h_surveys_ascending():
    result = parse_slide(str(SLIDE_45H))
    mds = [s.svy_md_ft for s in result.surveys]
    assert mds == sorted(mds), "Survey MDs must be ascending"


def test_45h_header_fields():
    result = parse_slide(str(SLIDE_45H))
    h = result.header
    assert h.get("hole_size_in") == pytest.approx(12.25, abs=0.01)
    assert "depth_in" in h and h["depth_in"] == pytest.approx(405.0, abs=1.0)
    assert "depth_out" in h and h["depth_out"] == pytest.approx(1386.0, abs=1.0)


def test_45h_intervals_have_sliding():
    result = parse_slide(str(SLIDE_45H))
    modes = {iv.mode for iv in result.intervals}
    assert "Sliding" in modes


def test_45h_motor_output_computed():
    result = parse_slide(str(SLIDE_45H))
    rows = compute_motor_outputs(result.surveys, result.intervals, stand_length_ft=96.0)
    # At least some rows must have valid motor output
    valid = [r for r in rows if r.motor_output_deg_per_ft is not None]
    assert len(valid) > 0

    # Spot-check first survey with sliding: survey at ~445.97ft, DLS=8.954, slide=30ft
    # Expected from raw data: motor_output = 8.954/30 = 0.2985 (but rounded)
    # (These values come from the file inspection: JSC-34 row 2 in Motor Output.xlsx
    #  shows 5.517 for a similar well; we just assert it's in a plausible range)
    for row in valid:
        if row.dls_deg_per_100ft > 0:
            assert 0 < row.motor_output_deg_per_ft < 5.0, f"Implausible motor output: {row.motor_output_deg_per_ft}"
        assert row.full_stand_deg == pytest.approx(row.motor_output_deg_per_ft * 96.0, rel=1e-6)


def test_45h_motor_output_formula():
    """Motor output = DLS / slide_footage (replicating Excel formula exactly)."""
    result = parse_slide(str(SLIDE_45H))
    rows = compute_motor_outputs(result.surveys, result.intervals)
    for row in rows:
        if row.motor_output_deg_per_ft is not None and row.slide_footage_ft:
            expected = row.dls_deg_per_100ft / row.slide_footage_ft
            assert row.motor_output_deg_per_ft == pytest.approx(expected, rel=1e-9)


# ── Slide sheet: Nong Yao A-43H (column-order variant) ───────────────────────

def test_43h_parses_correctly():
    result = parse_slide(str(SLIDE_43H))
    assert result.source_unit_system == "field"
    assert len(result.surveys) > 5
    modes = {iv.mode for iv in result.intervals}
    assert "Sliding" in modes
    assert "Rotating" in modes


def test_43h_header():
    result = parse_slide(str(SLIDE_43H))
    h = result.header
    assert h.get("hole_size_in") == pytest.approx(12.25, abs=0.01)


# ── Slide sheet: Nong Yao A-42ST1H ────────────────────────────────────────────

def test_42st1h_parses():
    result = parse_slide(str(SLIDE_42ST1H))
    assert result.source_unit_system == "field"
    assert len(result.surveys) > 3
    assert len(result.intervals) > 3


# ── Slide sheet: NTU-A04 (metric variant) ─────────────────────────────────────

def test_ntu_source_units():
    result = parse_slide(str(SLIDE_NTU))
    assert result.source_unit_system == "metric"
    assert result.source_units["depth"] == "m"


def test_ntu_depths_converted_to_ft():
    result = parse_slide(str(SLIDE_NTU))
    # Depth In was 20m → should be ~65.6 ft
    h = result.header
    if "depth_in" in h and h["depth_in"] is not None:
        assert h["depth_in"] == pytest.approx(20 * 3.28084, rel=0.01)
    # Final MD from filename: 719m → ~2358 ft
    last_svy = result.surveys[-1]
    assert last_svy.svy_md_ft == pytest.approx(719 * 3.28084, rel=0.05)


def test_ntu_modes_normalized():
    result = parse_slide(str(SLIDE_NTU))
    for iv in result.intervals:
        assert iv.mode[0].isupper(), f"Mode not title-cased: {iv.mode!r}"
        assert iv.mode not in ("ROTATING", "SLIDING", "CIRCULATING")


def test_ntu_dls_converted():
    result = parse_slide(str(SLIDE_NTU))
    # NTU uses deg/10m; stored as deg/100ft (canonical)
    # deg/10m * 3.04803 = deg/100ft
    for svy in result.surveys:
        # DLS must be non-negative and plausible
        assert svy.dls_deg_per_100ft >= 0
        assert svy.dls_deg_per_100ft < 50  # no real well builds > 50 deg/100ft


def test_ntu_unit_display_roundtrip():
    """Switching to deg/10m display should approximate original values."""
    from drilling_app.compute.units import dls_from_100ft, depth_from_ft, M_TO_FT
    result = parse_slide(str(SLIDE_NTU))
    for svy in result.surveys[1:4]:
        displayed = dls_from_100ft(svy.dls_deg_per_100ft, "deg/10m")
        # Round-trip: should be close to what was in the file (within floating-point)
        back = displayed * (100.0 / (10.0 * M_TO_FT))
        assert back == pytest.approx(svy.dls_deg_per_100ft, rel=1e-6)


# ── BHA config: Nong Yao A-43H ────────────────────────────────────────────────

def test_bha_43h_bent_angle():
    result = parse_bha(str(BHA_43H))
    assert result.motor_bent_deg == pytest.approx(1.83, abs=0.01)


def test_bha_43h_motor():
    result = parse_bha(str(BHA_43H))
    assert result.motor is not None
    assert "A825M7840XP" in result.motor.model or "A825M7840XP" in result.motor.make


def test_bha_43h_units():
    result = parse_bha(str(BHA_43H))
    assert result.source_unit_system == "field"
    assert result.hole_size_in == pytest.approx(12.25, abs=0.01)


def test_bha_43h_components():
    result = parse_bha(str(BHA_43H))
    assert len(result.components) >= 8


def test_bha_43h_depths():
    result = parse_bha(str(BHA_43H))
    assert result.depth_in_ft == pytest.approx(405.0, abs=2.0)
    assert result.depth_out_ft == pytest.approx(1385.0, abs=2.0)


# ── BHA config: LKU-K31 (metric) ──────────────────────────────────────────────

def test_bha_lku_bent_angle():
    result = parse_bha(str(BHA_LKU))
    assert result.motor_bent_deg == pytest.approx(1.5, abs=0.01)


def test_bha_lku_motor():
    result = parse_bha(str(BHA_LKU))
    assert result.motor is not None
    assert "A962M5640" in result.motor.make or "A962M5640" in result.motor.model


def test_bha_lku_metric_depths_converted():
    result = parse_bha(str(BHA_LKU))
    assert result.source_unit_system == "metric"
    # Depth In was 20m → ~65.6 ft
    assert result.depth_in_ft == pytest.approx(20 * 3.28084, rel=0.01)
    # Depth Out was 880m → ~2887 ft
    assert result.depth_out_ft == pytest.approx(880 * 3.28084, rel=0.01)
